from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def prepare_paired_cells(
    metrics: pd.DataFrame,
    metric: str,
    treatment: str,
    reference: str,
) -> pd.DataFrame:
    """Average repeats within each task-persona-condition cell, then pair cells."""
    required = {"task_id", "persona_id", "condition", metric}
    missing = required.difference(metrics.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")

    selected = metrics.loc[
        metrics["condition"].isin([treatment, reference]),
        ["task_id", "persona_id", "condition", metric],
    ].copy()
    selected[metric] = pd.to_numeric(selected[metric], errors="coerce")
    grouped = (
        selected.dropna(subset=[metric])
        .groupby(["task_id", "persona_id", "condition"], as_index=False)[metric]
        .mean()
    )
    paired = grouped.pivot(
        index=["task_id", "persona_id"], columns="condition", values=metric
    ).reset_index()
    if treatment not in paired or reference not in paired:
        return pd.DataFrame(
            columns=[
                "task_id",
                "persona_id",
                "treatment_value",
                "reference_value",
                "difference",
            ]
        )
    paired = paired.dropna(subset=[treatment, reference]).copy()
    paired = paired.rename(
        columns={treatment: "treatment_value", reference: "reference_value"}
    )
    paired["difference"] = (
        paired["treatment_value"] - paired["reference_value"]
    )
    return paired[
        [
            "task_id",
            "persona_id",
            "treatment_value",
            "reference_value",
            "difference",
        ]
    ].reset_index(drop=True)


def paired_cluster_bootstrap(
    metrics: pd.DataFrame,
    metric: str,
    treatment: str,
    reference: str,
    *,
    seed: int = 20260721,
    n_resamples: int = 10_000,
    confidence: float = 0.95,
) -> dict[str, float | int | str]:
    """Estimate a paired mean difference over task-persona cells.

    Repeated model trajectories are first averaged within a cell. Bootstrap
    resampling is then performed over paired cells, so repeats are not treated
    as independent learners or independent experimental units.
    """
    if n_resamples <= 0:
        raise ValueError("n_resamples must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")

    paired = prepare_paired_cells(metrics, metric, treatment, reference)
    if paired.empty:
        raise ValueError("no complete paired task-persona cells")
    differences = paired["difference"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    indices = rng.integers(
        0, len(differences), size=(n_resamples, len(differences))
    )
    bootstrap_means = differences[indices].mean(axis=1)
    alpha = 1.0 - confidence
    relevant_rows = metrics["condition"].isin([treatment, reference])
    difference_sd = float(np.std(differences, ddof=1)) if len(differences) > 1 else float("nan")
    standardized_effect = (
        float(differences.mean() / difference_sd)
        if np.isfinite(difference_sd)
        and difference_sd > np.finfo(float).eps * max(1.0, abs(float(differences.mean())))
        else None
    )
    treatment_mean = float(paired["treatment_value"].mean())
    reference_mean = float(paired["reference_value"].mean())
    source_values = set(pd.to_numeric(metrics.loc[relevant_rows, metric], errors="coerce").dropna().unique())
    is_binary = source_values.issubset({0, 1})
    risk_ratio = (
        float(treatment_mean / reference_mean)
        if is_binary and reference_mean > 0
        else None
    )
    p_value = _paired_sign_flip_p_value(differences, seed=seed, n_resamples=n_resamples)
    return {
        "metric": metric,
        "treatment": treatment,
        "reference": reference,
        "cluster_count": int(len(paired)),
        "trajectory_count": int(relevant_rows.sum()),
        "difference": float(differences.mean()),
        "standardized_paired_effect": standardized_effect,
        "risk_ratio": risk_ratio,
        "p_value": p_value,
        "ci_low": float(np.quantile(bootstrap_means, alpha / 2)),
        "ci_high": float(np.quantile(bootstrap_means, 1 - alpha / 2)),
        "confidence": float(confidence),
        "n_resamples": int(n_resamples),
        "seed": int(seed),
    }


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Return Holm step-down family-wise error adjusted p-values."""
    values = np.asarray(p_values, dtype=float)
    if values.ndim != 1 or np.any(~np.isfinite(values)):
        raise ValueError("p_values must be a finite one-dimensional sequence")
    if np.any((values < 0) | (values > 1)):
        raise ValueError("p_values must lie between 0 and 1")
    count = len(values)
    if count == 0:
        return []
    order = np.argsort(values, kind="stable")
    ordered = values[order]
    adjusted_ordered = np.maximum.accumulate(
        [(count - rank) * value for rank, value in enumerate(ordered)]
    )
    adjusted_ordered = np.minimum(adjusted_ordered, 1.0)
    adjusted = np.empty(count, dtype=float)
    adjusted[order] = adjusted_ordered
    return adjusted.tolist()


def weighted_cohen_kappa(
    first: Sequence[int | float], second: Sequence[int | float]
) -> float:
    """Compute quadratic-weighted Cohen's kappa for ordinal ratings."""
    first_values = np.asarray(first)
    second_values = np.asarray(second)
    if first_values.ndim != 1 or second_values.ndim != 1:
        raise ValueError("ratings must be one-dimensional")
    if len(first_values) != len(second_values) or len(first_values) == 0:
        raise ValueError("rating sequences must have equal positive length")
    if np.any(pd.isna(first_values)) or np.any(pd.isna(second_values)):
        raise ValueError("ratings must not contain missing values")

    categories = np.unique(np.concatenate([first_values, second_values]))
    if len(categories) == 1:
        return 1.0 if np.array_equal(first_values, second_values) else 0.0
    category_index = {value: index for index, value in enumerate(categories)}
    observed = np.zeros((len(categories), len(categories)), dtype=float)
    for left, right in zip(first_values, second_values):
        observed[category_index[left], category_index[right]] += 1
    observed /= observed.sum()
    left_marginal = observed.sum(axis=1)
    right_marginal = observed.sum(axis=0)
    expected = np.outer(left_marginal, right_marginal)
    grid = np.arange(len(categories), dtype=float)
    weights = ((grid[:, None] - grid[None, :]) / (len(categories) - 1)) ** 2
    observed_disagreement = float(np.sum(weights * observed))
    expected_disagreement = float(np.sum(weights * expected))
    if expected_disagreement == 0:
        return 1.0 if observed_disagreement == 0 else 0.0
    return float(1.0 - observed_disagreement / expected_disagreement)


def _paired_sign_flip_p_value(
    differences: np.ndarray,
    *,
    seed: int,
    n_resamples: int,
) -> float:
    """Two-sided paired randomization test over task-persona cells."""
    observed = abs(float(np.mean(differences)))
    if observed == 0:
        return 1.0
    rng = np.random.default_rng(seed + 1)
    signs = rng.choice((-1.0, 1.0), size=(n_resamples, len(differences)))
    permuted = np.abs((signs * differences).mean(axis=1))
    return float((np.count_nonzero(permuted >= observed) + 1) / (n_resamples + 1))


def cohen_kappa(
    first: Sequence[int | bool], second: Sequence[int | bool]
) -> float:
    """Compute unweighted Cohen's kappa for nominal or binary decisions."""
    left = np.asarray(first)
    right = np.asarray(second)
    if left.ndim != 1 or right.ndim != 1:
        raise ValueError("ratings must be one-dimensional")
    if len(left) != len(right) or len(left) == 0:
        raise ValueError("rating sequences must have equal positive length")
    if np.any(pd.isna(left)) or np.any(pd.isna(right)):
        raise ValueError("ratings must not contain missing values")
    categories = np.unique(np.concatenate([left, right]))
    observed = float(np.mean(left == right))
    expected = sum(
        float(np.mean(left == category)) * float(np.mean(right == category))
        for category in categories
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return float((observed - expected) / (1.0 - expected))


def average_ranks(values: Sequence[int | float]) -> np.ndarray:
    """Return one-based average ranks, including ties."""
    return pd.Series(values, dtype=float).rank(method="average").to_numpy(dtype=float)


def spearman_correlation(
    first: Sequence[int | float], second: Sequence[int | float]
) -> float:
    """Compute Spearman correlation using average ranks for ties."""
    if len(first) != len(second) or len(first) < 2:
        raise ValueError("sequences must have equal length of at least two")
    left = average_ranks(first)
    right = average_ranks(second)
    if np.std(left) == 0 or np.std(right) == 0:
        return float("nan")
    return float(np.corrcoef(left, right)[0, 1])


def calibration_summary(
    automatic: Sequence[int | float], teacher_mean: Sequence[int | float]
) -> dict[str, float | int]:
    """Summarize automatic-judge calibration against mean teacher ratings."""
    if len(automatic) != len(teacher_mean) or len(automatic) == 0:
        raise ValueError("calibration sequences must have equal positive length")
    automatic_values = np.asarray(automatic, dtype=float)
    teacher_values = np.asarray(teacher_mean, dtype=float)
    if np.any(~np.isfinite(automatic_values)) or np.any(~np.isfinite(teacher_values)):
        raise ValueError("calibration values must be finite")
    return {
        "n": int(len(automatic_values)),
        "spearman": spearman_correlation(automatic_values, teacher_values),
        "mae": float(np.mean(np.abs(automatic_values - teacher_values))),
    }
