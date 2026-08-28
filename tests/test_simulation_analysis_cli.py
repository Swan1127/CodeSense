import pandas as pd

from scripts.analyze_guided_learning_simulation import (
    build_comparisons,
    build_judge_calibration,
    build_teacher_condition_summary,
)


def test_build_comparisons_keeps_task_persona_as_analysis_unit():
    rows = []
    for task_id, c0, c2 in [("T1", 0, 1), ("T2", 1, 1)]:
        rows.extend([
            {"task_id": task_id, "persona_id": "P1", "condition": "C0", "repeat": 1, "completed": c0},
            {"task_id": task_id, "persona_id": "P1", "condition": "C2", "repeat": 1, "completed": c2},
        ])

    result = build_comparisons(
        pd.DataFrame(rows),
        metrics=["completed"],
        comparisons=[("C2", "C0")],
        seed=17,
        n_resamples=200,
    )

    assert len(result) == 1
    assert result.loc[0, "cluster_count"] == 2
    assert result.loc[0, "trajectory_count"] == 4
    assert result.loc[0, "p_value_holm"] >= result.loc[0, "p_value"]


def test_teacher_summary_uses_blinding_key_and_calibration_is_flagged():
    teacher = pd.DataFrame([
        {"review_id": "R1", "rater_id": "t1", "guidance_quality": 1},
        {"review_id": "R1", "rater_id": "t2", "guidance_quality": 1},
        {"review_id": "R2", "rater_id": "t1", "guidance_quality": 5},
        {"review_id": "R2", "rater_id": "t2", "guidance_quality": 5},
    ])
    key = pd.DataFrame([
        {"review_id": "R1", "trajectory_id": "T1", "condition": "C0"},
        {"review_id": "R2", "trajectory_id": "T2", "condition": "C2"},
    ])
    automatic = pd.DataFrame([
        {"review_id": "R1", "guidance_quality": 5},
        {"review_id": "R2", "guidance_quality": 1},
    ])

    summary = build_teacher_condition_summary(teacher, key, fields=["guidance_quality"])
    calibration = build_judge_calibration(automatic, teacher, fields=["guidance_quality"])

    assert set(summary["condition"]) == {"C0", "C2"}
    assert calibration.loc[0, "supplementary_only"] == 1
