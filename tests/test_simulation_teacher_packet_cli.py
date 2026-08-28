import csv
import json

from research_eval.simulation.blinding import SAMPLE_QUOTAS
from scripts.build_simulation_teacher_packet import main


PERSONAS = [
    "P1_NO_PLAN",
    "P2_CONCEPT_MISCONCEPTION",
    "P3_BOUNDARY_OMISSION",
    "P4_COMPLEXITY_GAP",
    "P5_ANSWER_SEEKING",
    "P6_LOCAL_REASONING_ERROR",
]


def test_source_only_packet_has_96_blinded_rows_and_separate_key(tmp_path):
    input_dir = tmp_path / "formal"
    output_dir = tmp_path / "review"
    input_dir.mkdir()
    trajectories = []
    turns = []
    serial = 0
    for condition, quota in SAMPLE_QUOTAS.items():
        for index in range(quota):
            serial += 1
            trajectory_id = f"trajectory-{serial:03d}"
            trajectories.append({
                "trajectory_id": trajectory_id,
                "task_id": f"F{index % 12 + 1:02d}",
                "persona_id": PERSONAS[index % len(PERSONAS)],
                "condition": condition,
                "invalid_reason": "",
            })
            turns.extend([
                {"trajectory_id": trajectory_id, "turn_index": 0, "actor": "learner", "content": "我的理解"},
                {"trajectory_id": trajectory_id, "turn_index": 1, "actor": "system", "content": "请解释边界"},
            ])
    for name, rows in (("trajectories.jsonl", trajectories), ("turns.jsonl", turns)):
        (input_dir / name).write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")

    assert main(["--input", str(input_dir), "--output-dir", str(output_dir), "--source-only"]) == 0

    packet = json.loads((output_dir / "teacher_packet_source.json").read_text(encoding="utf-8"))
    with (output_dir / "blinding_key.csv").open(encoding="utf-8-sig", newline="") as handle:
        key = list(csv.DictReader(handle))
    assert len(packet) == len(key) == 96
    assert all("condition" not in row and "trajectory_id" not in row for row in packet)
    assert all("condition" in row and "trajectory_id" in row for row in key)
