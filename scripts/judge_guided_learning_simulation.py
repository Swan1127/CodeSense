from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import random
import sys
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from research_eval.simulation.blinding import build_review_candidates
from research_eval.simulation.judging import judge_trajectory
from research_eval.simulation.models import load_personas
from research_eval.simulation.runner import JsonlSink
from research_eval.simulation.tasks import load_task_manifest
from research_eval.simulation.zhipu_roles import RoleClient

CONFIG = PROJECT_ROOT / "research/guided_learning_paper/experiments/simulation/config"
PROMPTS = PROJECT_ROOT / "research/guided_learning_paper/experiments/simulation/prompts"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row is not an object: {path}")
            rows.append(value)
    return rows


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run blinded automatic review of simulation trajectories")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seed", type=int, default=20260721)
    parser.add_argument("--limit", type=int)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv(args.env_file if args.env_file else PROJECT_ROOT / ".env", override=False)
    api_key = os.environ.get("ZHIPU_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ZHIPU_API_KEY is missing")
    if args.output.exists() and args.output.stat().st_size and not args.resume:
        raise SystemExit("output exists; pass --resume")
    trajectories = read_jsonl(args.input / "trajectories.jsonl")
    turns = read_jsonl(args.input / "turns.jsonl")
    tasks = {row.task_id: asdict(row) for row in load_task_manifest(CONFIG / "tasks.json")}
    personas = {row.persona_id: asdict(row) for row in load_personas(CONFIG / "personas.json")}
    candidates = build_review_candidates(trajectories, turns, tasks, personas)
    completed_ids = set()
    if args.output.exists():
        completed_ids = {str(row["trajectory_id"]) for row in read_jsonl(args.output)}
    candidates = [row for row in candidates if row["trajectory_id"] not in completed_ids]
    random.Random(args.seed).shuffle(candidates)
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit must be positive")
        candidates = candidates[: args.limit]
    prompt = (PROMPTS / "judge.txt").read_text(encoding="utf-8")
    client = RoleClient(api_key)
    sink = JsonlSink(args.output)
    for index, row in enumerate(candidates, 1):
        judged = judge_trajectory(
            client,
            prompt,
            task_text=row["task_text"],
            persona_visible=row["persona_visible"],
            transcript=row["transcript"],
        )
        sink.append({
            "trajectory_id": row["trajectory_id"],
            "task_id": row["task_id"],
            "persona_id": row["persona_id"],
            "condition": row["condition"],
            **judged,
        })
        print(f"[{index}/{len(candidates)}] {row['trajectory_id']} failure={judged.get('technical_failure') or '-'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
