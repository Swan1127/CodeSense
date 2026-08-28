from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_eval.simulation.blinding import (
    SAMPLE_QUOTAS,
    build_review_candidates,
    stratified_blind_sample,
)
from research_eval.simulation.models import load_personas
from research_eval.simulation.tasks import load_task_manifest

CONFIG = PROJECT_ROOT / "research/guided_learning_paper/experiments/simulation/config"
BUILDER = PROJECT_ROOT / "scripts/build_simulation_teacher_packet.mjs"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row {line_number} is not an object: {path}")
        rows.append(value)
    return rows


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty CSV")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the 96-row blinded teacher review packet")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260721)
    parser.add_argument("--node", type=Path)
    parser.add_argument("--node-modules", type=Path)
    parser.add_argument("--source-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    trajectories = read_jsonl(args.input / "trajectories.jsonl")
    turns = read_jsonl(args.input / "turns.jsonl")
    tasks = {row.task_id: asdict(row) for row in load_task_manifest(CONFIG / "tasks.json")}
    personas = {row.persona_id: asdict(row) for row in load_personas(CONFIG / "personas.json")}
    candidates = build_review_candidates(trajectories, turns, tasks, personas)
    packet, key_rows = stratified_blind_sample(candidates, seed=args.seed)
    if any("condition" in row or "trajectory_id" in row for row in packet):
        raise RuntimeError("blinded packet contains forbidden identifiers")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source_path = args.output_dir / "teacher_packet_source.json"
    key_path = args.output_dir / "blinding_key.csv"
    source_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(key_path, key_rows)
    manifest = {
        "seed": args.seed,
        "packet_rows": len(packet),
        "condition_quotas": dict(SAMPLE_QUOTAS),
        "selected_condition_counts": dict(Counter(row["condition"] for row in key_rows)),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "blinding_key_sha256": hashlib.sha256(key_path.read_bytes()).hexdigest(),
        "contains_real_student_data": False,
    }
    (args.output_dir / "teacher_packet_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.source_only:
        print(f"packet_rows={len(packet)} source_only=1")
        return 0
    node = args.node or _environment_path("CODEX_BUNDLED_NODE")
    node_modules = args.node_modules or _environment_path("CODEX_BUNDLED_NODE_MODULES")
    if node is None or node_modules is None:
        raise SystemExit("pass --node and --node-modules from the bundled workspace dependencies")
    if not node.is_file() or not node_modules.is_dir():
        raise SystemExit("bundled node or node_modules path is invalid")
    runtime = args.output_dir / ".packet_builder_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    link = runtime / "node_modules"
    if not link.exists():
        os.symlink(node_modules, link, target_is_directory=True)
    runtime_builder = runtime / "builder.mjs"
    shutil.copy2(BUILDER, runtime_builder)
    workbook_path = args.output_dir / "teacher_packet.xlsx"
    subprocess.run([str(node), str(runtime_builder), str(source_path), str(workbook_path)], cwd=runtime, check=True)
    print(f"packet_rows={len(packet)} workbook={workbook_path}")
    return 0


def _environment_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value) if value else None


if __name__ == "__main__":
    raise SystemExit(main())
