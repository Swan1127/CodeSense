import pandas as pd

from scripts.analyze_guided_learning_simulation import build_comparisons


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
