from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_eval.simulation.analysis import (
    calibration_summary,
    cohen_kappa,
    holm_adjust,
    paired_cluster_bootstrap,
    weighted_cohen_kappa,
)
from research_eval.simulation.judging import FLAG_FIELDS, RATING_DIMENSIONS


MECHANISM_METRICS = (
    "completed",
    "recovered",
    "possible_complete_code_leakage",
    "possible_full_step_leakage",
    "duplicate_hint_pairs",
    "stage_order_violations",
    "system_response_count",
    "technical_failure",
)
CORE_COMPARISONS = (("C2", "C0"), ("C2", "C1"))
ABLATION_COMPARISONS = (("A1", "C2"), ("A2", "C2"), ("A3", "C2"))


def build_comparisons(
    metrics_frame: pd.DataFrame,
    *,
    metrics: Sequence[str],
    comparisons: Sequence[tuple[str, str]],
    seed: int,
    n_resamples: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for metric in metrics:
        if metric not in metrics_frame.columns:
            continue
        for offset, (treatment, reference) in enumerate(comparisons):
            available = set(metrics_frame["condition"].dropna().astype(str))
            if treatment not in available or reference not in available:
                continue
            try:
                result = paired_cluster_bootstrap(
                    metrics_frame,
                    metric,
                    treatment,
                    reference,
                    seed=seed + len(rows) + offset,
                    n_resamples=n_resamples,
                )
            except ValueError:
                continue
            rows.append(result)
    if not rows:
        return pd.DataFrame(columns=[
            "metric", "treatment", "reference", "cluster_count",
            "trajectory_count", "difference", "ci_low", "ci_high",
            "standardized_paired_effect", "risk_ratio", "p_value",
            "p_value_holm", "confidence", "n_resamples", "seed",
        ])
    adjusted = holm_adjust([float(row["p_value"]) for row in rows])
    for row, value in zip(rows, adjusted):
        row["p_value_holm"] = value
    return pd.DataFrame(rows)


def build_condition_summary(metrics_frame: pd.DataFrame) -> pd.DataFrame:
    present = [name for name in MECHANISM_METRICS if name in metrics_frame.columns]
    if not present:
        return pd.DataFrame(columns=["condition", "n_trajectories"])
    means = metrics_frame.groupby("condition", as_index=False)[present].mean()
    counts = metrics_frame.groupby("condition").size().rename("n_trajectories")
    return means.merge(counts, on="condition", how="left")


def build_failure_slices(metrics_frame: pd.DataFrame) -> pd.DataFrame:
    dimensions = [name for name in ("difficulty", "persona_id") if name in metrics_frame.columns]
    value_fields = [name for name in (
        "technical_failure", "completed", "possible_complete_code_leakage",
        "possible_full_step_leakage",
    ) if name in metrics_frame.columns]
    rows: list[pd.DataFrame] = []
    for dimension in dimensions:
        grouped = metrics_frame.groupby(["condition", dimension], as_index=False)[value_fields].mean()
        grouped["slice_dimension"] = dimension
        grouped["slice_value"] = grouped[dimension].astype(str)
        grouped["n_trajectories"] = metrics_frame.groupby(["condition", dimension]).size().to_numpy()
        rows.append(grouped.drop(columns=[dimension]))
    if not rows:
        return pd.DataFrame(columns=["condition", "slice_dimension", "slice_value", "n_trajectories"])
    return pd.concat(rows, ignore_index=True)


def build_rater_agreement(teacher: pd.DataFrame) -> pd.DataFrame:
    if teacher.empty:
        return pd.DataFrame(columns=["field", "field_type", "n", "kappa"])
    raters = sorted(teacher["rater_id"].astype(str).unique())
    if len(raters) != 2:
        raise ValueError("teacher ratings must contain exactly two raters")
    rows: list[dict[str, object]] = []
    for field in (*RATING_DIMENSIONS, *FLAG_FIELDS):
        pivot = teacher.pivot(index="review_id", columns="rater_id", values=field).dropna()
        left = pivot[raters[0]].tolist()
        right = pivot[raters[1]].tolist()
        ordinal = field in RATING_DIMENSIONS
        rows.append({
            "field": field,
            "field_type": "ordinal" if ordinal else "binary",
            "n": len(pivot),
            "kappa": weighted_cohen_kappa(left, right) if ordinal else cohen_kappa(left, right),
        })
    return pd.DataFrame(rows)


def read_automatic_ratings(path: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        source = json.loads(line)
        row = {"review_id": source.get("review_id", "")}
        row.update(source.get("ratings", {}))
        row.update({name: int(value) for name, value in source.get("flags", {}).items()})
        row["technical_failure"] = source.get("technical_failure", "")
        rows.append(row)
    return pd.DataFrame(rows)


def build_judge_calibration(automatic: pd.DataFrame, teacher: pd.DataFrame) -> pd.DataFrame:
    if automatic.empty or teacher.empty:
        return pd.DataFrame(columns=["field", "field_type", "n", "spearman", "mae"])
    teacher_mean = teacher.groupby("review_id", as_index=False)[list(RATING_DIMENSIONS) + list(FLAG_FIELDS)].mean()
    merged = automatic.merge(teacher_mean, on="review_id", suffixes=("_automatic", "_teacher"))
    rows: list[dict[str, object]] = []
    for field in (*RATING_DIMENSIONS, *FLAG_FIELDS):
        valid = merged[[f"{field}_automatic", f"{field}_teacher"]].dropna()
        if len(valid) < 2:
            continue
        summary = calibration_summary(valid.iloc[:, 0], valid.iloc[:, 1])
        rows.append({"field": field, "field_type": "ordinal" if field in RATING_DIMENSIONS else "binary", **summary})
    return pd.DataFrame(rows)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze guided-learning simulation results")
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--teacher-ratings", type=Path)
    parser.add_argument("--automatic-ratings", type=Path)
    parser.add_argument("--seed", type=int, default=20260721)
    parser.add_argument("--n-resamples", type=int, default=10000)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    metrics_frame = pd.read_csv(args.metrics)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    core = build_comparisons(metrics_frame, metrics=MECHANISM_METRICS, comparisons=CORE_COMPARISONS, seed=args.seed, n_resamples=args.n_resamples)
    ablation = build_comparisons(metrics_frame, metrics=MECHANISM_METRICS, comparisons=ABLATION_COMPARISONS, seed=args.seed + 1000, n_resamples=args.n_resamples)
    summary = build_condition_summary(metrics_frame)
    failures = build_failure_slices(metrics_frame)
    teacher = pd.read_csv(args.teacher_ratings) if args.teacher_ratings and args.teacher_ratings.exists() else pd.DataFrame()
    agreement = build_rater_agreement(teacher)
    automatic = read_automatic_ratings(args.automatic_ratings) if args.automatic_ratings and args.automatic_ratings.exists() else pd.DataFrame()
    calibration = build_judge_calibration(automatic, teacher)
    outputs = {
        "core_comparisons.csv": core,
        "ablation_comparisons.csv": ablation,
        "condition_summary.csv": summary,
        "rater_agreement.csv": agreement,
        "judge_calibration.csv": calibration,
        "failure_slices.csv": failures,
    }
    for name, frame in outputs.items():
        frame.to_csv(output / name, index=False, encoding="utf-8-sig")
    print(f"core_comparisons={len(core)} ablation_comparisons={len(ablation)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
