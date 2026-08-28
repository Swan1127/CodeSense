import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

import research_eval.concurrency.cli as cli_module
from research_eval.concurrency.cli import (
    ExperimentConfig,
    SummaryRow,
    execute_experiment,
    mixed_request_kinds,
    parse_args,
    sanitize_snapshot,
    write_paper_outputs,
)
from research_eval.concurrency.models import LevelSummary, RequestRecord


def _record(level, index, kind="short"):
    return RequestRecord(
        run_id="internal",
        level=level,
        request_index=index,
        target="fake",
        request_kind=kind,
        started_at="2026-07-22T00:00:00+00:00",
        elapsed_seconds=0.1,
        success=True,
        status_code=200,
        error_code="",
        retries=0,
        input_chars=10,
        output_chars=20,
    )


def _summary(level):
    return LevelSummary(
        level=level,
        total=20,
        successful=20,
        success_rate=1.0,
        error_rate=0.0,
        rate_limit_rate=0.0,
        throughput_per_second=10.0,
        mean_seconds=0.2,
        p50_seconds=0.2,
        p95_seconds=0.3,
        p99_seconds=0.4,
        retry_rate=0.0,
        gateway_errors=0,
    )


def test_defaults_and_platform_canary_gate(tmp_path):
    args = parse_args(["--mode", "upstream", "--output-dir", str(tmp_path)])
    assert args.levels == (1, 2, 4, 8, 16, 24, 32)
    assert args.warmups == 3
    assert args.repetitions == 3

    with pytest.raises(ValueError, match="allow-validated-ramp"):
        parse_args(
            [
                "--mode",
                "platform",
                "--levels",
                "1,2,4,8,16",
                "--max-concurrency",
                "16",
                "--base-url",
                "https://example.test/codesense",
                "--credentials-file",
                str(tmp_path / "users.json"),
                "--assignment-id",
                "85",
                "--output-dir",
                str(tmp_path),
            ]
        )


@pytest.mark.parametrize("bad", ["2,4", "1,4,2", "1,2,2", "1,33", "0,1"])
def test_levels_must_be_safe_staircase(tmp_path, bad):
    with pytest.raises(ValueError, match="levels"):
        parse_args(
            ["--mode", "upstream", "--levels", bad, "--output-dir", str(tmp_path)]
        )


def test_mixed_schedule_is_exact_and_deterministic():
    kinds = mixed_request_kinds(20)
    assert len(kinds) == 20
    assert kinds.count("short") == 12
    assert kinds.count("long") == 8
    assert kinds == mixed_request_kinds(20)


def test_snapshot_redaction_is_recursive_and_removes_url_secrets():
    payload = {
        "api_key": "top-secret",
        "nested": {
            "password": "pw",
            "Cookie": "session=abc",
            "authorization_header": "Bearer abc",
            "safe": "ok",
            "url": "https://user:pw@example.test/app?q=secret#frag",
        },
        "token_count": 12,
    }
    clean = sanitize_snapshot(payload)
    encoded = json.dumps(clean, ensure_ascii=False)
    assert "top-secret" not in encoded
    assert "session=abc" not in encoded
    assert "Bearer abc" not in encoded
    assert "user:pw" not in encoded
    assert "q=secret" not in encoded
    assert clean["nested"]["safe"] == "ok"
    assert clean["nested"]["url"] == "https://example.test/app"
    assert "api_key" not in clean
    assert "password" not in clean["nested"]
    assert "Cookie" not in clean["nested"]
    assert "authorization_header" not in clean["nested"]
    assert clean["token_count"] == 12


class FakeBundle:
    def __init__(self):
        self.calls = []

    def call(self, kind, level, index):
        self.calls.append((kind, level, index))
        return _record(level, index, kind)


def test_execute_schedules_three_warmups_and_three_separate_repetitions(tmp_path):
    config = ExperimentConfig(
        mode="upstream",
        request_kind="mixed",
        levels=(1, 2),
        requests_per_level=20,
        warmups=3,
        repetitions=3,
        cooldown_seconds=0,
        output_dir=tmp_path,
        model="glm-test",
    )
    bundle = FakeBundle()
    runner_calls = []

    def fake_runner(worker, levels, requests_per_level, sink, **kwargs):
        repetition_records = [worker(level, i) for level in levels for i in range(requests_per_level)]
        runner_calls.append(repetition_records)
        return [_summary(level) for level in levels]

    rows = execute_experiment(
        config,
        target_bundle=bundle,
        staircase_runner=fake_runner,
        sleep_fn=lambda _seconds: None,
    )

    assert len(bundle.calls) == 3 + 3 * 2 * 20
    assert len(runner_calls) == 3
    assert [row.repetition for row in rows] == [1, 1, 2, 2, 3, 3]
    assert len({record.run_id for batch in runner_calls for record in batch}) == 3
    for batch in runner_calls:
        for level in (1, 2):
            kinds = [record.request_kind for record in batch if record.level == level]
            assert kinds.count("short") == 12
            assert kinds.count("long") == 8


def test_write_outputs_preserves_repetitions_and_creates_three_200_dpi_pngs(tmp_path):
    rows = [
        SummaryRow.from_summary(1, "run-a", "upstream", "short", _summary(1)),
        SummaryRow.from_summary(2, "run-b", "upstream", "short", _summary(1)),
    ]
    snapshot = {
        "target": "upstream",
        "request_kind": "short",
        "model": "glm-test",
        "started_at_utc": "2026-07-22T00:00:00+00:00",
    }
    write_paper_outputs(tmp_path, rows, snapshot)

    with (tmp_path / "level_summary.csv").open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert [row["repetition"] for row in csv_rows] == ["1", "2"]
    assert json.loads((tmp_path / "run_config.json").read_text(encoding="utf-8"))["model"] == "glm-test"

    from PIL import Image

    for name in (
        "latency_by_concurrency.png",
        "throughput_by_concurrency.png",
        "error_rate_by_concurrency.png",
    ):
        path = tmp_path / name
        assert path.exists() and path.stat().st_size > 1000
        with Image.open(path) as image:
            dpi = image.info.get("dpi")
            assert dpi and dpi[0] == pytest.approx(200, rel=0.02)


def test_existing_outputs_require_explicit_overwrite(tmp_path):
    (tmp_path / "run_config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        parse_args(["--mode", "upstream", "--output-dir", str(tmp_path)])
    args = parse_args(
        ["--mode", "upstream", "--output-dir", str(tmp_path), "--overwrite"]
    )
    assert args.overwrite is True

def test_failed_warmup_blocks_formal_run_and_marks_snapshot(tmp_path):
    config = ExperimentConfig(
        mode="upstream",
        levels=(1,),
        requests_per_level=2,
        warmups=1,
        repetitions=1,
        cooldown_seconds=0,
        output_dir=tmp_path,
    )

    class FailedWarmup(FakeBundle):
        def call(self, kind, level, index):
            return replace(_record(level, index, kind), success=False, status_code=500)

    runner_called = False

    def forbidden_runner(*_args, **_kwargs):
        nonlocal runner_called
        runner_called = True
        return []

    with pytest.raises(RuntimeError, match="warm-up"):
        execute_experiment(
            config,
            target_bundle=FailedWarmup(),
            staircase_runner=forbidden_runner,
            sleep_fn=lambda _seconds: None,
        )

    assert runner_called is False
    snapshot = json.loads((tmp_path / "run_config.json").read_text(encoding="utf-8"))
    assert snapshot["status"] == "failed"
    assert snapshot["warmups_completed"] == 0


def test_execute_with_real_runner_writes_incremental_raw_and_per_level_resources(tmp_path):
    config = ExperimentConfig(
        mode="upstream",
        levels=(1, 2),
        requests_per_level=5,
        warmups=0,
        repetitions=2,
        cooldown_seconds=0,
        output_dir=tmp_path,
        model="glm-test",
    )

    rows = execute_experiment(
        config,
        target_bundle=FakeBundle(),
        sleep_fn=lambda _seconds: None,
    )

    assert len(rows) == 4
    assert len((tmp_path / "raw_requests.jsonl").read_text(encoding="utf-8").splitlines()) == 20
    resource_files = sorted((tmp_path / "resources").glob("*.csv"))
    assert [path.name for path in resource_files] == [
        "repetition_01_level_01.csv",
        "repetition_01_level_02.csv",
        "repetition_02_level_01.csv",
        "repetition_02_level_02.csv",
    ]

def test_platform_canary_logs_in_only_the_users_needed_for_max_level(tmp_path, monkeypatch):
    users = [
        {"username": f"research_load_{index:02d}", "password": "x"}
        for index in range(1, 33)
    ]
    seen = {}

    def fake_load_users(path, required_count):
        seen["load"] = (path, required_count)
        return users

    class FakePlatformTarget:
        def __init__(self, base_url, assignment_id, request_kind, credentials, run_id):
            seen["target"] = (base_url, assignment_id, request_kind, credentials, run_id)

    monkeypatch.setattr(cli_module, "load_users", fake_load_users)
    monkeypatch.setattr(cli_module, "PlatformTarget", FakePlatformTarget)
    config = ExperimentConfig(
        mode="platform",
        levels=(1, 2, 4, 8),
        output_dir=tmp_path,
        base_url="https://example.test/app",
        credentials_file=tmp_path / "users.json",
        assignment_id=85,
    )

    cli_module._build_target_bundle(config, "run")

    assert seen["load"] == (config.credentials_file, 8)
    assert len(seen["target"][3]) == 8


def test_overwrite_removes_only_known_resource_outputs(tmp_path):
    resources = tmp_path / "resources"
    resources.mkdir()
    generated = resources / "repetition_01_level_08.csv"
    unrelated = resources / "notes.csv"
    generated.write_text("old", encoding="utf-8")
    unrelated.write_text("keep", encoding="utf-8")
    (tmp_path / "run_config.json").write_text("{}", encoding="utf-8")
    config = ExperimentConfig(mode="upstream", output_dir=tmp_path, overwrite=True)

    cli_module._prepare_output(config)

    assert not generated.exists()
    assert not (tmp_path / "run_config.json").exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"
