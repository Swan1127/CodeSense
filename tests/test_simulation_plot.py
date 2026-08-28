import pandas as pd

from scripts.plot_guided_learning_simulation import create_figures


def test_create_figures_writes_separate_non_composite_outputs(tmp_path):
    results = tmp_path / "results"
    figures = tmp_path / "figures"
    results.mkdir()
    pd.DataFrame([
        {"condition": "C0", "n_trajectories": 2, "completed": 0.5, "recovered": 0.0, "technical_failure": 0.0},
        {"condition": "C2", "n_trajectories": 2, "completed": 1.0, "recovered": 0.5, "technical_failure": 0.0},
    ]).to_csv(results / "condition_summary.csv", index=False)
    comparison = pd.DataFrame([
        {"metric": "completed", "treatment": "C2", "reference": "C0", "difference": 0.5, "ci_low": 0.0, "ci_high": 1.0, "cluster_count": 2},
    ])
    comparison.to_csv(results / "core_comparisons.csv", index=False)
    comparison.assign(treatment="A1", reference="C2", difference=-0.5).to_csv(results / "ablation_comparisons.csv", index=False)
    pd.DataFrame([
        {"condition": "C0", "n_review_items": 24, "guidance_quality": 2.5, "cognitive_activation": 2.0},
        {"condition": "C2", "n_review_items": 24, "guidance_quality": 4.0, "cognitive_activation": 4.2},
    ]).to_csv(results / "teacher_condition_summary.csv", index=False)
    pd.DataFrame([
        {"condition": "C0", "slice_dimension": "difficulty", "slice_value": "easy", "n_trajectories": 2, "technical_failure": 0.0, "completed": 0.5},
        {"condition": "C2", "slice_dimension": "difficulty", "slice_value": "easy", "n_trajectories": 2, "technical_failure": 0.0, "completed": 1.0},
    ]).to_csv(results / "failure_slices.csv", index=False)

    paths = create_figures(results, figures)

    assert len(paths) >= 4
    assert any(path.name == "teacher_ratings_by_condition.png" for path in paths)
    assert all(path.exists() and path.stat().st_size > 0 for path in paths)
