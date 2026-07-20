"""Create publication-ready aggregate figures for the guided-learning paper."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch


COLORS = {
    "blue": "#2563EB",
    "green": "#059669",
    "orange": "#D97706",
    "purple": "#7C3AED",
    "gray": "#64748B",
    "dark": "#1F2937",
    "light": "#F8FAFC",
}

EVENT_LABELS = {
    "description_submit": "描述提交",
    "hint_request": "提示请求",
    "companion_chat": "陪伴对话",
    "stage_pass": "阶段通过",
    "verify_fail": "验证失败",
    "dialogue": "教学对话",
    "generated_error_code": "生成错误代码",
    "fix_code": "修正代码",
    "other": "其他",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _configure_style() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["savefig.facecolor"] = "white"


def _save(fig: plt.Figure, path: Path) -> Path:
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _plot_activity_chain_evidence(output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(x, y, width, height, face, edge):
        patch = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            linewidth=1.8,
            edgecolor=edge,
            facecolor=face,
            transform=ax.transAxes,
        )
        ax.add_patch(patch)

    ax.text(
        0.5,
        0.93,
        "三阶段程序设计引导的活动链与证据边界",
        ha="center",
        va="center",
        fontsize=19,
        fontweight="bold",
        color=COLORS["dark"],
    )
    ax.text(
        0.5,
        0.865,
        "AI组织提问、校验和角色模拟；学生负责表达、转换、讲解与纠错",
        ha="center",
        va="center",
        fontsize=11,
        color=COLORS["gray"],
    )

    stages = [
        (
            0.06,
            "1  思路外化",
            "用自然语言说明\n算法步骤、输入输出与边界",
            "描述提交 · 提示请求",
            "#EFF6FF",
            COLORS["blue"],
        ),
        (
            0.365,
            "2  代码重构",
            "把自然语言表征\n转换为程序结构表征",
            "验证失败 · 阶段通过",
            "#ECFDF5",
            COLORS["green"],
        ),
        (
            0.67,
            "3  讲解纠错",
            "回应虚拟学生追问\n检查并修正错误代码",
            "教学对话 · 代码修正",
            "#FFF7ED",
            COLORS["orange"],
        ),
    ]
    for x, title, activity, evidence, face, edge in stages:
        box(x, 0.39, 0.265, 0.34, face, edge)
        ax.text(
            x + 0.1325,
            0.67,
            title,
            ha="center",
            va="center",
            fontsize=14,
            fontweight="bold",
            color=edge,
        )
        ax.text(
            x + 0.1325,
            0.56,
            activity,
            ha="center",
            va="center",
            fontsize=11.5,
            linespacing=1.5,
        )
        ax.text(
            x + 0.1325,
            0.445,
            f"平台证据：{evidence}",
            ha="center",
            va="center",
            fontsize=9.5,
            color=COLORS["gray"],
        )

    for start, end in ((0.325, 0.365), (0.63, 0.67)):
        ax.annotate(
            "",
            xy=(end - 0.006, 0.56),
            xytext=(start + 0.006, 0.56),
            xycoords=ax.transAxes,
            arrowprops={
                "arrowstyle": "-|>",
                "lw": 2,
                "color": COLORS["gray"],
                "mutation_scale": 16,
            },
        )

    box(0.08, 0.13, 0.84, 0.14, COLORS["light"], "#CBD5E1")
    ax.text(
        0.5,
        0.225,
        "本研究已观察：采用、阶段推进、操作转换与首次提交表现",
        ha="center",
        va="center",
        fontsize=11.5,
        fontweight="bold",
        color=COLORS["dark"],
    )
    ax.text(
        0.5,
        0.17,
        "本研究未直接测量：解释质量、认知变化与学习增益",
        ha="center",
        va="center",
        fontsize=10.5,
        color=COLORS["gray"],
    )
    return _save(fig, output_dir / "activity_chain_evidence.png")


def _plot_adoption_profile(results_dir: Path, output_dir: Path) -> Path:
    summary = json.loads(
        (results_dir / "analysis_summary.json").read_text(encoding="utf-8")
    )
    usage = summary["usage"]
    total = int(usage["users"])
    labels = ["进入引导", "重复使用", "跨作业使用", "至少完成一次"]
    values = [
        total,
        int(usage["repeat_users"]),
        int(usage["cross_assignment_users"]),
        int(usage["users_with_completed_session"]),
    ]
    colors = [
        COLORS["blue"],
        COLORS["green"],
        COLORS["purple"],
        COLORS["orange"],
    ]
    fig, ax = plt.subplots(figsize=(9, 5.6))
    bars = ax.bar(labels, values, color=colors, width=0.62)
    for bar, value in zip(bars, values):
        percent = 100 * value / total if total else 0
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + max(values) * 0.025,
            f"{value}（{percent:.1f}%）",
            ha="center",
            va="bottom",
            fontsize=10,
        )
    ax.set_title(f"引导用户的采用与持续使用（n={total}）")
    ax.set_ylabel("学生人数")
    ax.set_ylim(0, max(values) * 1.2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.18)
    ax.text(
        0.5,
        -0.18,
        "百分比以进入过引导式学习的学生为分母",
        transform=ax.transAxes,
        ha="center",
        fontsize=9.5,
        color=COLORS["gray"],
    )
    fig.subplots_adjust(bottom=0.23)
    return _save(fig, output_dir / "adoption_profile.png")


def _plot_stable_session_paths(results_dir: Path, output_dir: Path) -> Path:
    rows = _read_csv(results_dir / "stable_session_paths.csv")
    labels = [row["label"] for row in rows]
    values = [int(row["sessions"]) for row in rows]
    percents = [float(row["percent"]) for row in rows]
    fig, ax = plt.subplots(figsize=(9, 5.6))
    bars = ax.barh(
        labels[::-1],
        values[::-1],
        color=["#94A3B8", "#64748B", "#F59E0B", "#2563EB"][::-1],
    )
    for bar, value, percent in zip(bars, values[::-1], percents[::-1]):
        ax.text(
            value + max(values) * 0.018,
            bar.get_y() + bar.get_height() / 2,
            f"{value}（{percent:.2f}%）",
            va="center",
            fontsize=10,
        )
    ax.set_title("稳定版本会话的阶段路径（n=398）")
    ax.set_xlabel("会话数")
    ax.set_xlim(0, max(values) * 1.28)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", alpha=0.18)
    return _save(fig, output_dir / "stable_session_paths.png")


def _plot_event_transitions(results_dir: Path, output_dir: Path) -> Path:
    rows = [
        row
        for row in _read_csv(results_dir / "event_transitions.csv")
        if int(row["show_in_main_figure"]) == 1
    ]
    categories = [
        category
        for category in EVENT_LABELS
        if any(
            row["source"] == category or row["target"] == category
            for row in rows
        )
    ]
    if not categories:
        categories = ["other"]
    index = {category: position for position, category in enumerate(categories)}
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.3), constrained_layout=True)
    image = None
    for ax, group, title in zip(
        axes,
        ("completed", "incomplete"),
        ("完成会话", "未完成会话"),
    ):
        matrix = np.full((len(categories), len(categories)), np.nan)
        counts = np.zeros((len(categories), len(categories)), dtype=int)
        for row in rows:
            if row["completion_group"] != group:
                continue
            source = index[row["source"]]
            target = index[row["target"]]
            matrix[source, target] = float(row["conditional_percent"])
            counts[source, target] = int(row["count"])
        image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=100)
        ax.set_title(title)
        ax.set_xticks(range(len(categories)), [EVENT_LABELS[item] for item in categories])
        ax.set_yticks(range(len(categories)), [EVENT_LABELS[item] for item in categories])
        ax.tick_params(axis="x", rotation=45, labelsize=8.5)
        ax.tick_params(axis="y", labelsize=8.5)
        ax.set_xlabel("后一事件")
        ax.set_ylabel("前一事件")
        for source in range(len(categories)):
            for target in range(len(categories)):
                if np.isnan(matrix[source, target]):
                    continue
                color = "white" if matrix[source, target] >= 50 else COLORS["dark"]
                ax.text(
                    target,
                    source,
                    f"{counts[source, target]}\n{matrix[source, target]:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=7.5,
                    color=color,
                )
    assert image is not None
    colorbar = fig.colorbar(image, ax=axes, shrink=0.82, pad=0.02)
    colorbar.set_label("条件比例（%）")
    fig.suptitle("完成与未完成会话的主要相邻事件转换", fontsize=15)
    fig.text(
        0.5,
        0.01,
        "单元格依次标示转换次数和条件比例；连续同类事件已折叠",
        ha="center",
        fontsize=9.5,
        color=COLORS["gray"],
    )
    return _save(fig, output_dir / "event_transitions.png")


def _plot_version_timeline(results_dir: Path, output_dir: Path) -> Path:
    rows = _read_csv(results_dir / "version_summary.csv")
    versions = [row["version"] for row in rows]
    sessions = [int(row["sessions"]) for row in rows]
    completion = [float(row["completion_percent"]) for row in rows]
    fig, ax1 = plt.subplots(figsize=(9, 5.6))
    bars = ax1.bar(versions, sessions, color=COLORS["purple"], alpha=0.82)
    ax1.set_ylabel("会话数")
    ax1.set_xlabel("系统版本")
    ax1.spines[["top", "right"]].set_visible(False)
    for bar, value in zip(bars, sessions):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            value + max(sessions) * 0.015,
            str(value),
            ha="center",
        )
    ax2 = ax1.twinx()
    ax2.plot(
        versions,
        completion,
        color=COLORS["orange"],
        marker="o",
        linewidth=2,
    )
    ax2.set_ylabel("完成率（%）")
    ax2.set_ylim(0, max(70, max(completion) + 10))
    ax2.spines["top"].set_visible(False)
    ax1.set_title("现场迭代期间的会话量与完成率（仅作描述）")
    ax1.text(
        0.5,
        -0.18,
        "各版本的学生、作业和教学时间不等价，不用于估计改版效果",
        transform=ax1.transAxes,
        ha="center",
        fontsize=9.5,
        color=COLORS["gray"],
    )
    fig.subplots_adjust(bottom=0.23)
    return _save(fig, output_dir / "appendix_version_timeline.png")


def create_figures(results_dir: Path, output_dir: Path) -> list[Path]:
    _configure_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    return [
        _plot_activity_chain_evidence(output_dir),
        _plot_adoption_profile(results_dir, output_dir),
        _plot_stable_session_paths(results_dir, output_dir),
        _plot_event_transitions(results_dir, output_dir),
        _plot_version_timeline(results_dir, output_dir),
    ]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=root / "research" / "guided_learning_paper" / "results",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "research" / "guided_learning_paper" / "figures",
    )
    args = parser.parse_args()
    for path in create_figures(args.results_dir, args.output_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
