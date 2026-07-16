"""Create publication-ready aggregate figures for the guided-learning paper."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


COLORS = {
    "blue": "#3B82F6",
    "green": "#10B981",
    "orange": "#F59E0B",
    "purple": "#8B5CF6",
    "gray": "#64748B",
}

STEP_LABELS = {
    "stage1_scored": "第一阶段产生得分",
    "reached_stage2": "到达第二阶段",
    "stage1_pass": "第一阶段通过",
    "stage2_completed": "完成第二阶段",
    "stage3_completed": "完成第三阶段",
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


def _save(fig: plt.Figure, path: Path) -> Path:
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _plot_stage_funnel(results_dir: Path, output_dir: Path) -> Path:
    rows = _read_csv(results_dir / "stable_stage_funnel.csv")
    labels = [STEP_LABELS.get(row["step"], row["step"]) for row in rows]
    values = [int(float(row["sessions"])) for row in rows]
    percents = [float(row["percent_of_started"]) for row in rows]
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bars = ax.barh(labels[::-1], values[::-1], color=COLORS["blue"])
    for bar, value, percent in zip(bars, values[::-1], percents[::-1]):
        ax.text(
            value + max(values) * 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"{value}（{percent:.1f}%）",
            va="center",
            fontsize=10,
        )
    ax.set_title("稳定版本三阶段学习漏斗")
    ax.set_xlabel("会话数")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", alpha=0.2)
    return _save(fig, output_dir / "stage_funnel.png")


def _plot_version_timeline(results_dir: Path, output_dir: Path) -> Path:
    rows = _read_csv(results_dir / "version_summary.csv")
    versions = [row["version"] for row in rows]
    sessions = [int(row["sessions"]) for row in rows]
    completion = [float(row["completion_percent"]) for row in rows]
    fig, ax1 = plt.subplots(figsize=(9, 4.8))
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
    ax2.plot(versions, completion, color=COLORS["orange"], marker="o", linewidth=2)
    ax2.set_ylabel("完成率（%）")
    ax2.set_ylim(0, max(70, max(completion) + 10))
    ax2.spines["top"].set_visible(False)
    ax1.set_title("现场迭代期间的会话量与完成率（描述性结果）")
    return _save(fig, output_dir / "version_timeline.png")


def _plot_usage_distribution(results_dir: Path, output_dir: Path) -> Path:
    rows = _read_csv(results_dir / "student_usage.csv")
    sessions = [int(row["sessions_per_user"]) for row in rows]
    users = [int(row["users"]) for row in rows]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(sessions, users, width=0.8, color=COLORS["green"])
    ax.set_title("参与学生的会话次数分布")
    ax.set_xlabel("每名学生建立的会话数")
    ax.set_ylabel("学生人数")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.2)
    return _save(fig, output_dir / "usage_distribution.png")


def _plot_sample_flow(results_dir: Path, output_dir: Path) -> Path:
    summary_path = results_dir / "analysis_summary.json"
    versions = _read_csv(results_dir / "version_summary.csv")
    usage = _read_csv(results_dir / "student_usage.csv")
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        student_accounts = int(summary["row_counts"]["students"])
        participants = int(summary["usage"]["users"])
    else:
        participants = sum(int(row["users"]) for row in usage)
        student_accounts = participants
    stable = next(
        (row for row in versions if row["version"] == "V5"),
        versions[-1],
    )
    values = [
        ("平台学生账户", student_accounts),
        ("进入引导式学习", participants),
        ("稳定版会话", int(stable["sessions"])),
        ("稳定版完成会话", int(stable["completed_sessions"])),
    ]
    fig, ax = plt.subplots(figsize=(10, 2.9))
    ax.axis("off")
    x_positions = [0.08, 0.34, 0.62, 0.88]
    for index, ((label, value), x) in enumerate(zip(values, x_positions)):
        ax.text(
            x,
            0.52,
            f"{value}\n{label}",
            ha="center",
            va="center",
            fontsize=12,
            bbox={
                "boxstyle": "round,pad=0.7",
                "facecolor": "#EFF6FF",
                "edgecolor": COLORS["blue"],
                "linewidth": 1.5,
            },
            transform=ax.transAxes,
        )
        if index < len(values) - 1:
            ax.annotate(
                "",
                xy=(x_positions[index + 1] - 0.09, 0.52),
                xytext=(x + 0.09, 0.52),
                xycoords=ax.transAxes,
                arrowprops={"arrowstyle": "->", "color": COLORS["gray"], "lw": 1.5},
            )
    ax.set_title("研究样本与稳定版本分析口径", pad=15)
    return _save(fig, output_dir / "sample_flow.png")


def _plot_conceptual_framework(output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(12, 6.75))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(x, y, width, height, face, edge):
        patch = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            linewidth=1.7,
            edgecolor=edge,
            facecolor=face,
            transform=ax.transAxes,
        )
        ax.add_patch(patch)

    ax.text(
        0.5,
        0.94,
        "三阶段引导式学习：让学生持续承担认知责任",
        ha="center",
        va="center",
        fontsize=20,
        fontweight="bold",
    )
    ax.text(
        0.5,
        0.885,
        "AI提供提问、反馈与角色模拟；学生完成表达、判断、讲解和纠错",
        ha="center",
        va="center",
        fontsize=11,
        color=COLORS["gray"],
    )

    stages = [
        (
            0.045,
            "01  思路外化",
            "学生说明\n输入 · 关键步骤\n边界条件 · 输出",
            "#EFF6FF",
            COLORS["blue"],
            "AI：分题提示与反馈",
        ),
        (
            0.285,
            "02  代码重构",
            "学生把算法思路\n映射为程序结构\n选择 · 填空 · 验证",
            "#ECFDF5",
            COLORS["green"],
            "AI/系统：即时校验与提示",
        ),
        (
            0.525,
            "03  角色反转与纠错",
            "学生向虚拟同学讲解\n检查其生成的错误代码\n定位并完成修正",
            "#FFF7ED",
            COLORS["orange"],
            "双角色：教师智能体 + 虚拟学生",
        ),
    ]
    for x, title, body, face, edge, footer in stages:
        box(x, 0.38, 0.205, 0.39, face, edge)
        ax.text(
            x + 0.1025,
            0.71,
            title,
            ha="center",
            va="center",
            fontsize=13,
            fontweight="bold",
            color=edge,
        )
        ax.text(
            x + 0.1025,
            0.565,
            body,
            ha="center",
            va="center",
            fontsize=11.5,
            linespacing=1.6,
        )
        ax.text(
            x + 0.1025,
            0.42,
            footer,
            ha="center",
            va="center",
            fontsize=9.5,
            color=COLORS["gray"],
        )

    for left, right in ((0.25, 0.285), (0.49, 0.525)):
        ax.annotate(
            "",
            xy=(right - 0.006, 0.575),
            xytext=(left + 0.006, 0.575),
            xycoords=ax.transAxes,
            arrowprops={
                "arrowstyle": "-|>",
                "lw": 2,
                "color": COLORS["gray"],
                "mutation_scale": 16,
            },
        )

    box(0.77, 0.38, 0.19, 0.39, "#F8FAFC", COLORS["purple"])
    ax.text(
        0.865,
        0.71,
        "预期学习活动",
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
        color=COLORS["purple"],
    )
    ax.text(
        0.865,
        0.575,
        "算法理解\n结构化表达\n调试与纠错\n独立编程",
        ha="center",
        va="center",
        fontsize=11.5,
        linespacing=1.55,
    )
    ax.text(
        0.865,
        0.42,
        "学习效果仍需对照研究验证",
        ha="center",
        va="center",
        fontsize=9.5,
        color=COLORS["purple"],
    )

    box(0.08, 0.15, 0.84, 0.12, "#F8FAFC", "#CBD5E1")
    ax.text(
        0.5,
        0.22,
        "学生认知责任链：表达  →  判断  →  讲解  →  纠错",
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
        color="#334155",
    )
    ax.text(
        0.5,
        0.175,
        "本研究已分析：可实施性、采用、重复使用与阶段推进　｜　尚未验证：因果学习效果",
        ha="center",
        va="center",
        fontsize=10,
        color=COLORS["gray"],
    )
    return _save(fig, output_dir / "conceptual_framework.png")


def create_figures(results_dir: Path, output_dir: Path) -> list[Path]:
    _configure_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    return [
        _plot_conceptual_framework(output_dir),
        _plot_sample_flow(results_dir, output_dir),
        _plot_stage_funnel(results_dir, output_dir),
        _plot_usage_distribution(results_dir, output_dir),
        _plot_version_timeline(results_dir, output_dir),
    ]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    results_dir = root / "research" / "guided_learning_paper" / "results"
    output_dir = root / "research" / "guided_learning_paper" / "figures"
    for path in create_figures(results_dir, output_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
