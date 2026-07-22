from collections import Counter
import json

import pytest

from research_eval.simulation.blinding import (
    SAMPLE_QUOTAS,
    stratified_blind_sample,
    validate_teacher_ratings,
)
from research_eval.simulation.judging import RATING_DIMENSIONS, parse_judge_json


def valid_judge_payload():
    return json.dumps(
        {
            "ratings": {name: 4 for name in RATING_DIMENSIONS},
            "flags": {
                "possible_complete_code_leakage": False,
                "possible_full_step_leakage": True,
            },
            "evidence": {name: f"evidence for {name}" for name in RATING_DIMENSIONS},
        }
    )


def test_judge_json_requires_six_bounded_ratings_flags_and_evidence():
    parsed = parse_judge_json(valid_judge_payload())
    assert set(parsed["ratings"]) == set(RATING_DIMENSIONS)
    assert all(value == 4 for value in parsed["ratings"].values())

    bad = json.loads(valid_judge_payload())
    bad["ratings"][RATING_DIMENSIONS[0]] = 6
    with pytest.raises(ValueError, match="1..5"):
        parse_judge_json(json.dumps(bad))


def synthetic_candidates():
    rows = []
    for condition, quota in SAMPLE_QUOTAS.items():
        for index in range(quota + 12):
            rows.append(
                {
                    "trajectory_id": f"{condition}-T{index:03d}",
                    "condition": condition,
                    "task_id": f"T{index % 12:02d}",
                    "persona_id": f"P{index % 6}",
                    "difficulty": ("easy", "medium", "hard")[index % 3],
                    "task_text": "task",
                    "persona_visible": "visible learner behavior",
                    "transcript": "dialogue",
                }
            )
    return rows


def test_blind_sample_has_exact_96_rows_and_no_condition_field():
    packet, key = stratified_blind_sample(synthetic_candidates(), seed=20260721)

    assert len(packet) == 96
    assert len(key) == 96
    assert all("condition" not in row and "trajectory_id" not in row for row in packet)
    assert Counter(row["condition"] for row in key) == SAMPLE_QUOTAS
    assert {row["review_id"] for row in packet} == {row["review_id"] for row in key}


def test_blind_sampling_is_deterministic_for_recorded_seed():
    first = stratified_blind_sample(synthetic_candidates(), seed=7)
    second = stratified_blind_sample(synthetic_candidates(), seed=7)
    assert first == second


def test_teacher_rating_import_requires_two_complete_raters():
    packet_ids = {"R0001", "R0002"}
    rows = []
    for rater in ("teacher_1", "teacher_2"):
        for review_id in sorted(packet_ids):
            row = {"review_id": review_id, "rater_id": rater}
            row.update({name: 3 for name in RATING_DIMENSIONS})
            row.update(
                {
                    "possible_complete_code_leakage": 0,
                    "possible_full_step_leakage": 1,
                }
            )
            rows.append(row)

    validated = validate_teacher_ratings(rows, packet_ids)
    assert len(validated) == 4

    with pytest.raises(ValueError, match="two ratings"):
        validate_teacher_ratings(rows[:-1], packet_ids)
