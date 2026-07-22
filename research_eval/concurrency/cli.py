from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform as platform_module
import re
import socket
import sys
import time
import uuid
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import urlsplit, urlunsplit

from .models import LevelSummary, RequestRecord
from .output import JsonlSink
from .platform import PlatformTarget, load_users
from .runner import DEFAULT_LEVELS, run_staircase
from .upstream import DEFAULT_MODEL, ZHIPU_CHAT_COMPLETIONS_URL, ZhipuTarget


PAPER_ARTIFACTS = (
    "raw_requests.jsonl",
    "level_summary.csv",
    "run_config.json",
    "latency_by_concurrency.png",
    "throughput_by_concurrency.png",
    "error_rate_by_concurrency.png",
)
_SENSITIVE_WORDS = {"key", "password", "passwd", "pwd", "cookie", "authorization", "secret", "token"}
_BEARER = re.compile(r"\bbearer\s+\S+", re.IGNORECASE)


@dataclass(frozen=True)
class ExperimentConfig:
    mode: str
    request_kind: str = "short"
    levels: tuple[int, ...] = DEFAULT_LEVELS
    requests_per_level: int = 20
    warmups: int = 3
    repetitions: int = 3
    cooldown_seconds: float = 30.0
    output_dir: Path = Path("research_exports/concurrency")
    base_url: str | None = None
    credentials_file: Path | None = None
    assignment_id: int | None = None
    allow_validated_ramp: bool = False
    max_concurrency: int | None = None
    model: str = DEFAULT_MODEL
    overwrite: bool = False


@dataclass(frozen=True)
class SummaryRow:
    repetition: int
    run_id: str
    target: str
    request_kind: str
    level: int
    total: int
    successful: int
    success_rate: float
    error_rate: float
    rate_limit_rate: float
    throughput_per_second: float
    mean_seconds: float
    p50_seconds: float
    p95_seconds: float
    p99_seconds: float
    retry_rate: float
    gateway_errors: int
    stop_reasons: str

    @classmethod
    def from_summary(
        cls,
        repetition: int,
        run_id: str,
        target: str,
        request_kind: str,
        summary: LevelSummary,
    ) -> "SummaryRow":
        values = asdict(summary)
        values["stop_reasons"] = "|".join(summary.stop_reasons)
        return cls(repetition, _hash_run_id(run_id), target, request_kind, **values)


def _parse_levels(value: str) -> tuple[int, ...]:
    try:
        levels = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise ValueError("levels must be comma-separated integers") from exc
    if (
        not levels
        or levels[0] != 1
        or any(level < 1 or level > 32 for level in levels)
        or any(left >= right for left, right in zip(levels, levels[1:]))
    ):
        raise ValueError("levels must start at 1, increase strictly, and stay between 1 and 32")
    return levels


def parse_args(argv: Sequence[str] | None = None) -> ExperimentConfig:
    parser = argparse.ArgumentParser(description="Run the guarded CodeSense concurrency evaluation.")
    parser.add_argument("--mode", choices=("upstream", "platform"), required=True)
    parser.add_argument("--request-kind", choices=("short", "long", "mixed"), default="short")
    parser.add_argument("--levels", default=",".join(map(str, DEFAULT_LEVELS)))
    parser.add_argument("--max-concurrency", type=int)
    parser.add_argument("--requests-per-level", type=int, default=20)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--cooldown-seconds", type=float, default=30.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--assignment-id", type=int)
    parser.add_argument("--allow-validated-ramp", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--overwrite", action="store_true")
    namespace = parser.parse_args(argv)

    levels = _parse_levels(namespace.levels)
    if namespace.max_concurrency is not None:
        if namespace.max_concurrency < 1 or namespace.max_concurrency > 32:
            raise ValueError("max-concurrency must be between 1 and 32")
        levels = tuple(level for level in levels if level <= namespace.max_concurrency)
        if not levels:
            raise ValueError("levels must include a value at or below max-concurrency")
    if namespace.requests_per_level < 1:
        raise ValueError("requests-per-level must be positive")
    if namespace.warmups < 0 or namespace.repetitions < 1 or namespace.cooldown_seconds < 0:
        raise ValueError("warmups, repetitions, and cooldown must be non-negative")
    if namespace.mode == "platform":
        if not namespace.base_url or not namespace.credentials_file or not namespace.assignment_id:
            raise ValueError("platform mode requires base-url, credentials-file, and assignment-id")
        if max(levels) > 8 and not namespace.allow_validated_ramp:
            raise ValueError("platform levels above 8 require --allow-validated-ramp")
    output_dir = namespace.output_dir.resolve()
    if not namespace.overwrite and any((output_dir / name).exists() for name in PAPER_ARTIFACTS):
        raise FileExistsError("output directory already contains concurrency artifacts")
    return ExperimentConfig(
        mode=namespace.mode,
        request_kind=namespace.request_kind,
        levels=levels,
        requests_per_level=namespace.requests_per_level,
        warmups=namespace.warmups,
        repetitions=namespace.repetitions,
        cooldown_seconds=namespace.cooldown_seconds,
        output_dir=output_dir,
        base_url=namespace.base_url,
        credentials_file=namespace.credentials_file,
        assignment_id=namespace.assignment_id,
        allow_validated_ramp=namespace.allow_validated_ramp,
        max_concurrency=namespace.max_concurrency,
        model=namespace.model,
        overwrite=namespace.overwrite,
    )


def mixed_request_kinds(count: int) -> tuple[str, ...]:
    if count < 1:
        raise ValueError("request count must be positive")
    short_total = (3 * count + 2) // 5
    kinds: list[str] = []
    short_used = 0
    for index in range(count):
        expected = ((index + 1) * short_total) // count
        if expected > short_used:
            kinds.append("short")
            short_used += 1
        else:
            kinds.append("long")
    return tuple(kinds)


def _sensitive_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
    if normalized.endswith("_count"):
        return False
    words = set(normalized.split("_"))
    return bool(words & _SENSITIVE_WORDS) or "api_key" in normalized or "access_token" in normalized


def _sanitize_string(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        host = parsed.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    if _BEARER.search(value):
        return "[REDACTED]"
    return value


def sanitize_snapshot(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): sanitize_snapshot(item)
            for key, item in value.items()
            if not _sensitive_key(key)
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_snapshot(item) for item in value]
    if isinstance(value, Path):
        return value.name
    if isinstance(value, str):
        return _sanitize_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


class _TargetBundle:
    def __init__(self, targets: dict[str, Any], mixed_platform: PlatformTarget | None = None):
        self._targets = targets
        self._mixed_platform = mixed_platform

    def call(self, kind: str, level: int, index: int) -> RequestRecord:
        if self._mixed_platform is not None:
            return self._mixed_platform.call_kind(level, index, kind)
        return self._targets[kind].call(level, index)


def _build_target_bundle(config: ExperimentConfig, experiment_id: str) -> _TargetBundle:
    kinds = ("short", "long") if config.request_kind == "mixed" else (config.request_kind,)
    if config.mode == "upstream":
        api_key = os.environ.get("ZHIPU_API_KEY", "")
        if not api_key:
            raise ValueError("ZHIPU_API_KEY is required for upstream mode")
        return _TargetBundle(
            {kind: ZhipuTarget(api_key, experiment_id, kind, model=config.model) for kind in kinds}
        )
    required_users = max(config.levels)
    users = load_users(config.credentials_file or Path("missing"), required_users)
    platform_target = PlatformTarget(
        config.base_url or "",
        config.assignment_id or 0,
        kinds[0],
        users[:required_users],
        experiment_id,
    )
    return (
        _TargetBundle({}, mixed_platform=platform_target)
        if config.request_kind == "mixed"
        else _TargetBundle({kinds[0]: platform_target})
    )


def _hash_run_id(run_id: str) -> str:
    return "sha256:" + hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:16]


def _snapshot(config: ExperimentConfig, experiment_id: str) -> dict[str, Any]:
    target_url = ZHIPU_CHAT_COMPLETIONS_URL if config.mode == "upstream" else config.base_url
    run_ids = {
        str(rep): _hash_run_id(f"{experiment_id}-rep-{rep:02d}")
        for rep in range(1, config.repetitions + 1)
    }
    return sanitize_snapshot(
        {
            "schema_version": 1,
            "experiment_id": _hash_run_id(experiment_id),
            "formal_run_ids": run_ids,
            "target": config.mode,
            "request_kind": config.request_kind,
            "levels": config.levels,
            "requests_per_level": config.requests_per_level,
            "warmups": config.warmups,
            "repetitions": config.repetitions,
            "cooldown_seconds": config.cooldown_seconds,
            "model": config.model,
            "target_url": target_url,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "python_version": sys.version.split()[0],
            "hostname": socket.gethostname(),
            "platform": platform_module.platform(),
            "cpu_count": os.cpu_count(),
            "gunicorn": {
                "workers": os.environ.get("WEB_CONCURRENCY"),
                "timeout": os.environ.get("GUNICORN_TIMEOUT", "120"),
                "cmd_args": os.environ.get("GUNICORN_CMD_ARGS"),
            },
            "credentials_file_provided": config.credentials_file is not None,
            "assignment_id": config.assignment_id,
            "platform_ramp_approved": config.allow_validated_ramp,
        }
    )


def _prepare_output(config: ExperimentConfig) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    if config.overwrite:
        for name in PAPER_ARTIFACTS:
            path = config.output_dir / name
            if path.is_file():
                path.unlink()
        resources = config.output_dir / "resources"
        if resources.is_dir():
            for path in resources.glob("repetition_??_level_??.csv"):
                if path.is_file():
                    path.unlink()
    elif any((config.output_dir / name).exists() for name in PAPER_ARTIFACTS):
        raise FileExistsError("output directory already contains concurrency artifacts")


def execute_experiment(
    config: ExperimentConfig,
    *,
    target_bundle: Any | None = None,
    staircase_runner: Callable[..., list[LevelSummary]] = run_staircase,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[SummaryRow]:
    _prepare_output(config)
    experiment_id = "concurrency-" + uuid.uuid4().hex
    snapshot = _snapshot(config, experiment_id)
    _atomic_json(config.output_dir / "run_config.json", snapshot)
    sink = JsonlSink(config.output_dir / "raw_requests.jsonl")
    rows: list[SummaryRow] = []
    active_levels = config.levels
    try:
        bundle = target_bundle or _build_target_bundle(config, experiment_id)
        schedule = (
            mixed_request_kinds(config.requests_per_level)
            if config.request_kind == "mixed"
            else (config.request_kind,) * config.requests_per_level
        )
        snapshot["warmups_completed"] = 0
        for index in range(config.warmups):
            kind = schedule[index % len(schedule)]
            warmup = bundle.call(kind, 1, index)
            if not warmup.success:
                raise RuntimeError("warm-up request failed; formal evaluation was not started")
            snapshot["warmups_completed"] = index + 1
        _atomic_json(config.output_dir / "run_config.json", snapshot)

        for repetition in range(1, config.repetitions + 1):
            run_id = f"{experiment_id}-rep-{repetition:02d}"

            def worker(level: int, index: int) -> RequestRecord:
                kind = schedule[index % len(schedule)]
                return replace(bundle.call(kind, level, index), run_id=run_id, request_kind=kind)

            summaries = staircase_runner(
                worker,
                active_levels,
                config.requests_per_level,
                sink,
                resource_path_factory=lambda level, rep=repetition: config.output_dir
                / "resources"
                / f"repetition_{rep:02d}_level_{level:02d}.csv",
            )
            rows.extend(
                SummaryRow.from_summary(repetition, run_id, config.mode, config.request_kind, summary)
                for summary in summaries
            )
            _atomic_summary_csv(config.output_dir / "level_summary.csv", rows)
            if summaries and summaries[-1].stop_reasons:
                active_levels = tuple(level for level in active_levels if level <= summaries[-1].level)
            if repetition < config.repetitions and config.cooldown_seconds:
                sleep_fn(config.cooldown_seconds)
    except BaseException as exc:
        snapshot["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        snapshot["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        _atomic_json(config.output_dir / "run_config.json", snapshot)
        if rows:
            write_paper_outputs(config.output_dir, rows, snapshot)
        raise

    snapshot["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    snapshot["status"] = "complete"
    write_paper_outputs(config.output_dir, rows, snapshot)
    return rows


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(sanitize_snapshot(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def _atomic_summary_csv(path: Path, rows: Sequence[SummaryRow]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[field.name for field in fields(SummaryRow)])
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    temporary.replace(path)


def write_paper_outputs(
    output_dir: Path, rows: Sequence[SummaryRow], snapshot: dict[str, Any]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _atomic_summary_csv(output_dir / "level_summary.csv", rows)
    _atomic_json(output_dir / "run_config.json", snapshot)
    if rows:
        plot_summary_rows(output_dir, rows, snapshot)


def plot_summary_rows(
    output_dir: Path, rows: Sequence[SummaryRow], snapshot: dict[str, Any]
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plots = (
        ("p95_seconds", "P95 latency (seconds)", "latency_by_concurrency.png"),
        ("throughput_per_second", "Successful requests / second", "throughput_by_concurrency.png"),
        ("error_rate", "Error rate", "error_rate_by_concurrency.png"),
    )
    caption = (
        f"Target: {snapshot.get('target', '')} | Request: {snapshot.get('request_kind', '')} | "
        f"Model: {snapshot.get('model', '')} | Run: {snapshot.get('started_at_utc', '')}"
    )
    for attribute, ylabel, filename in plots:
        fig, axis = plt.subplots(figsize=(7.2, 4.5))
        for repetition in sorted({row.repetition for row in rows}):
            series = sorted(
                (row for row in rows if row.repetition == repetition), key=lambda row: row.level
            )
            axis.plot(
                [row.level for row in series],
                [getattr(row, attribute) for row in series],
                marker="o",
                linewidth=1.2,
                label=f"Repetition {repetition}",
            )
        axis.set_xlabel("Target concurrency")
        axis.set_ylabel(ylabel)
        axis.set_xticks(sorted({row.level for row in rows}))
        axis.grid(True, alpha=0.25)
        axis.legend(frameon=False)
        fig.text(0.5, 0.01, caption, ha="center", fontsize=7)
        fig.tight_layout(rect=(0, 0.05, 1, 1))
        path = output_dir / filename
        temporary = path.with_name(path.name + ".tmp")
        fig.savefig(
            temporary,
            format="png",
            dpi=200,
            metadata={"Description": caption, "Software": "CodeSense research evaluation"},
        )
        plt.close(fig)
        temporary.replace(path)


def load_summary_rows(path: Path) -> list[SummaryRow]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows: list[SummaryRow] = []
        for raw in csv.DictReader(handle):
            rows.append(
                SummaryRow(
                    repetition=int(raw["repetition"]),
                    run_id=raw["run_id"],
                    target=raw["target"],
                    request_kind=raw["request_kind"],
                    level=int(raw["level"]),
                    total=int(raw["total"]),
                    successful=int(raw["successful"]),
                    success_rate=float(raw["success_rate"]),
                    error_rate=float(raw["error_rate"]),
                    rate_limit_rate=float(raw["rate_limit_rate"]),
                    throughput_per_second=float(raw["throughput_per_second"]),
                    mean_seconds=float(raw["mean_seconds"]),
                    p50_seconds=float(raw["p50_seconds"]),
                    p95_seconds=float(raw["p95_seconds"]),
                    p99_seconds=float(raw["p99_seconds"]),
                    retry_rate=float(raw["retry_rate"]),
                    gateway_errors=int(raw["gateway_errors"]),
                    stop_reasons=raw["stop_reasons"],
                )
            )
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    config = parse_args(argv)
    rows = execute_experiment(config)
    print(f"Concurrency artifacts created: {config.output_dir} ({len(rows)} level rows)")
    return 0
