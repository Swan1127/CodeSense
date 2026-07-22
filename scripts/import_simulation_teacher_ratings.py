from __future__ import annotations

import argparse
import csv
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

from research_eval.simulation.blinding import validate_teacher_ratings
from research_eval.simulation.judging import FLAG_FIELDS, RATING_DIMENSIONS

EXTRACTOR = PROJECT_ROOT / "scripts/extract_simulation_teacher_ratings.mjs"


def merge_extracted_ratings(
    extracted: Sequence[Mapping[str, Any]], packet_ids: set[str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for workbook in extracted:
        rater_id = str(workbook.get("rater_id", "")).strip()
        if not rater_id:
            raise ValueError("每份评分表都必须在说明页B4填写rater_id")
        source_rows = workbook.get("rows")
        if not isinstance(source_rows, list):
            raise ValueError("extracted workbook rows must be a list")
        for source in source_rows:
            if not isinstance(source, dict):
                raise ValueError("each extracted rating row must be an object")
            row = dict(source)
            row["rater_id"] = rater_id
            rows.append(row)
    return validate_teacher_ratings(rows, packet_ids)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import and validate two completed teacher review workbooks")
    parser.add_argument("--packet", type=Path, action="append", required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node", type=Path)
    parser.add_argument("--node-modules", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if len(args.packet) != 2:
        raise SystemExit("pass exactly two independently completed --packet workbooks")
    node = args.node or _environment_path("CODEX_BUNDLED_NODE")
    node_modules = args.node_modules or _environment_path("CODEX_BUNDLED_NODE_MODULES")
    if node is None or node_modules is None or not node.is_file() or not node_modules.is_dir():
        raise SystemExit("pass valid --node and --node-modules bundled dependency paths")
    with args.key.open(encoding="utf-8-sig", newline="") as handle:
        key_rows = list(csv.DictReader(handle))
    packet_ids = {str(row["review_id"]) for row in key_rows}
    if len(packet_ids) != 96 or len(key_rows) != 96:
        raise ValueError("blinding key must contain 96 unique review IDs")
    runtime = args.output.parent / ".rating_import_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    link = runtime / "node_modules"
    if not link.exists():
        os.symlink(node_modules, link, target_is_directory=True)
    runtime_extractor = runtime / "extractor.mjs"
    shutil.copy2(EXTRACTOR, runtime_extractor)
    extracted: list[dict[str, Any]] = []
    for index, workbook in enumerate(args.packet, 1):
        output_json = runtime / f"teacher_{index}.json"
        subprocess.run([str(node), str(runtime_extractor), str(workbook), str(output_json)], cwd=runtime, check=True)
        extracted.append(json.loads(output_json.read_text(encoding="utf-8")))
    validated = merge_extracted_ratings(extracted, packet_ids)
    fields = ["review_id", "rater_id", *RATING_DIMENSIONS, *FLAG_FIELDS, "comment"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(validated)
    print(f"validated_ratings={len(validated)} raters=2 output={args.output}")
    return 0


def _environment_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value) if value else None


if __name__ == "__main__":
    raise SystemExit(main())
