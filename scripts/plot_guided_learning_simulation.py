from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

COLORS = {"C0": "#8C8C8C", "C1": "#E69F00", "C2": "#1677FF", "A1": "#D55E00", "A2": "#CC79A7", "A3": "#009E73"}


def _configure_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def _save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def plot_mechanism_metrics(results_dir: Path, output_dir: Path) -> Path | None:
    path = results_dir / "condition_summary.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    metrics = [name for name in (
        "completed", "recovered", "possible_complete_code_leakage",
        "possible_full_step_leakage", "technical_failure",
    ) if name in frame.columns]
    if not metrics:
        return None
    columns = 2
    rows = int(np.ceil(len(metrics) / columns))
    fig, axes = plt.subplots(rows, columns, figsize=(10, 3.7 * rows), squeeze=False)
    for ax, metric in zip(axes.flat, metrics):
        values = frame[["condition", metric, "n_trajectories"]].dropna()
        bars = ax.bar(values["condition"], values[metric], color=[COLORS.get(str(x), "#4C78A8") for x in values["condition"]])
        ax.set_title(metric.replace("_", " "))
        ax.set_ylim(0, max(1.0, float(values[metric].max()) * 1.15))
        ax.set_ylabel("Mean rate")
        for bar, (_, row) in zip(bars, values.iterrows()):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{row[metric]:.2f}\n(n={int(row["n_trajectories"])})", ha="center", va="bottom", fontsize=8)
    for ax in axes.flat[len(metrics):]:
        ax.axis("off")
    fig.suptitle("Mechanism indicators by condition (reported separately)")
    fig.tight_layout()
    return _save(fig, output_dir / "mechanism_metrics_by_condition.png")


def plot_comparison_forest(path: Path, output: Path, title: str) -> Path | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    required = {"metric", "treatment", "reference", "difference", "ci_low", "ci_high", "cluster_count"}
    if frame.empty or not required.issubset(frame.columns):
        return None
    frame = frame.reset_index(drop=True)
    y = np.arange(len(frame))
    estimate = frame["difference"].astype(float).to_numpy()
    lower = np.minimum(frame["ci_low"].astype(float).to_numpy(), estimate)
    upper = np.maximum(frame["ci_high"].astype(float).to_numpy(), estimate)
    labels = [f"{row.metric}: {row.treatment} vs {row.reference} (cells={int(row.cluster_count)})" for row in frame.itertuples()]
    fig, ax = plt.subplots(figsize=(10, max(4, 0.42 * len(frame) + 1.5)))
    ax.errorbar(estimate, y, xerr=np.vstack((estimate - lower, upper - estimate)), fmt="o", color="#1677FF", ecolor="#7AA7E8", capsize=3)
    ax.axvline(0, color="#444444", linewidth=1, linestyle="--")
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Paired mean difference with percentile 95% CI")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    return _save(fig, output)


def plot_failure_slices(results_dir: Path, output_dir: Path) -> Path | None:
    path = results_dir / "failure_slices.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if frame.empty or "technical_failure" not in frame.columns:
        return None
    focus = frame[frame["slice_dimension"] == "difficulty"].copy()
    if focus.empty:
        focus = frame.copy()
    pivot = focus.pivot(index="slice_value", columns="condition", values="technical_failure").fillna(0)
    fig, ax = plt.subplots(figsize=(8, max(3.5, 0.55 * len(pivot) + 1.5)))
    image = ax.imshow(pivot.to_numpy(), cmap="Reds", vmin=0, vmax=max(0.1, float(pivot.to_numpy().max())))
    ax.set_xticks(range(len(pivot.columns)), pivot.columns)
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.set_xlabel("Condition")
    ax.set_ylabel(str(focus["slice_dimension"].iloc[0]))
    ax.set_title("Technical-failure rate by slice")
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            ax.text(j, i, f"{pivot.iloc[i, j]:.2f}", ha="center", va="center")
    fig.colorbar(image, ax=ax, label="Failure rate")
    fig.tight_layout()
    return _save(fig, output_dir / "technical_failure_slices.png")


def create_figures(results_dir: Path, output_dir: Path) -> list[Path]:
    _configure_style()
    candidates = [
        plot_mechanism_metrics(results_dir, output_dir),
        plot_comparison_forest(results_dir / "core_comparisons.csv", output_dir / "core_comparisons.png", "Core condition comparisons"),
        plot_comparison_forest(results_dir / "ablation_comparisons.csv", output_dir / "ablation_comparisons.png", "Ablation comparisons against C2"),
        plot_failure_slices(results_dir, output_dir),
    ]
    return [path for path in candidates if path is not None]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot guided-learning simulation analyses")
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    for path in create_figures(args.results_dir, args.output_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
