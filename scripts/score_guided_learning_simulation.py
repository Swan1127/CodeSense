from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from research_eval.simulation.metrics import score_dataset
from research_eval.simulation.tasks import load_task_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS = PROJECT_ROOT / "research/guided_learning_paper/experiments/simulation/config/tasks.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row {line_number} is not an object: {path}")
        rows.append(value)
    return rows


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score guided-learning simulation trajectories")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    trajectories = read_jsonl(args.input / "trajectories.jsonl")
    turns = read_jsonl(args.input / "turns.jsonl")
    tasks = load_task_manifest(args.tasks)
    metrics, candidates = score_dataset(trajectories, turns, tasks)
    metric_fields = [
        "trajectory_id", "task_id", "persona_id", "condition", "repeat",
        "freeze_hash", "topic", "difficulty", "completed", "recovered",
        "possible_complete_code_leakage", "possible_full_step_leakage",
        "duplicate_hint_pairs", "stage_order_violations",
        "system_response_count", "learner_response_count",
        "technical_failure", "invalid_reason",
    ]
    candidate_fields = [
        "candidate_id", "trajectory_id", "turn_index", "rule_flag", "excerpt",
        "task_id", "difficulty", "persona_id",
    ]
    write_csv(args.output_dir / "trajectory_metrics.csv", metrics, metric_fields)
    write_csv(
        args.output_dir / "leakage_review_candidates.csv",
        candidates,
        candidate_fields,
    )
    print(f"scored={len(metrics)} leakage_candidates={len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
