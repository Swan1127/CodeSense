import pandas as pd
import pytest

from research_eval.simulation.analysis import (
    calibration_summary,
    cohen_kappa,
    holm_adjust,
    paired_cluster_bootstrap,
    prepare_paired_cells,
    spearman_correlation,
    weighted_cohen_kappa,
)


def toy_metrics():
    rows = []
    values = {
        ("T1", "P1", "C0"): [0, 0, 1],
        ("T1", "P1", "C2"): [1, 1, 1],
        ("T2", "P1", "C0"): [0, 0, 0],
        ("T2", "P1", "C2"): [0, 1, 1],
    }
    for (task_id, persona_id, condition), repeats in values.items():
        for repeat, value in enumerate(repeats, 1):
            rows.append(
                {
                    "task_id": task_id,
                    "persona_id": persona_id,
                    "condition": condition,
                    "repeat": repeat,
                    "completed": value,
                }
            )
    return pd.DataFrame(rows)


def test_repeats_are_averaged_before_paired_comparison():
    paired = prepare_paired_cells(toy_metrics(), "completed", "C2", "C0")

    assert len(paired) == 2
    assert set(paired["task_id"]) == {"T1", "T2"}
    assert paired.loc[
        paired["task_id"] == "T1", "difference"
    ].iloc[0] == pytest.approx(2 / 3)


def test_clustered_bootstrap_reports_hand_calculated_estimate():
    result = paired_cluster_bootstrap(
        toy_metrics(),
        metric="completed",
        treatment="C2",
        reference="C0",
        seed=7,
        n_resamples=1000,
    )

    assert result["cluster_count"] == 2
    assert result["trajectory_count"] == 12
    assert abs(result["difference"] - 2 / 3) < 1e-12
    assert result["ci_low"] <= result["difference"] <= result["ci_high"]


def test_holm_adjusted_values_are_monotone_in_p_value_order():
    adjusted = holm_adjust([0.03, 0.01, 0.02])
    ordered = [adjusted[index] for index in [1, 2, 0]]

    assert ordered == sorted(ordered)
    assert all(0 <= value <= 1 for value in adjusted)


def test_weighted_kappa_is_one_for_identical_ratings():
    ratings = [1, 2, 3, 4, 5]
    assert weighted_cohen_kappa(ratings, ratings) == 1.0


def test_binary_kappa_and_calibration_are_reported():
    assert cohen_kappa([0, 1, 1, 0], [0, 1, 1, 0]) == 1.0
    assert spearman_correlation([1, 2, 2, 4], [1, 2, 2, 4]) == pytest.approx(1.0)

    summary = calibration_summary([1, 2, 4], [1, 3, 5])

    assert summary["n"] == 3
    assert summary["mae"] == pytest.approx(2 / 3)
    assert -1 <= summary["spearman"] <= 1


def test_bootstrap_reports_effect_and_p_value_without_inflating_repeats():
    result = paired_cluster_bootstrap(
        toy_metrics(), "completed", "C2", "C0", seed=11, n_resamples=500
    )

    assert result["cluster_count"] == 2
    assert result["standardized_paired_effect"] is None
    assert 0 <= result["p_value"] <= 1
    assert result["risk_ratio"] > 1
