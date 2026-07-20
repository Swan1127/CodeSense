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
    fig, ax = plt.subplots(figsize=(13.4, 8.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(x, y, width, height, face, edge, *, linestyle="solid"):
        patch = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            linewidth=1.8,
            edgecolor=edge,
            facecolor=face,
            linestyle=linestyle,
            transform=ax.transAxes,
        )
        ax.add_patch(patch)

    def arrow(start, end, *, color=COLORS["gray"], linestyle="solid"):
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            xycoords=ax.transAxes,
            arrowprops={
                "arrowstyle": "-|>",
                "lw": 1.9,
                "color": color,
                "linestyle": linestyle,
                "mutation_scale": 15,
            },
        )

    ax.text(
        0.5,
        0.945,
        "状态驱动的三阶段程序设计引导方法",
        ha="center",
        va="center",
        fontsize=20,
        fontweight="bold",
        color=COLORS["dark"],
    )
    ax.text(
        0.5,
        0.895,
        "系统仅在本次会话内读取可观察状态，并调整提示、追问和反馈；学习活动始终由学生完成",
        ha="center",
        va="center",
        fontsize=10.8,
        color=COLORS["gray"],
    )

    top_boxes = [
        (
            0.04,
            "可观察的学生状态",
            "自然语言回答 · 提示次数 · 当前进度/得分\n错误/未答步骤 · 代码块错误与修正结果\n对话/教学记录",
            "#EFF6FF",
            COLORS["blue"],
        ),
        (
            0.365,
            "会话内智能体决策",
            "诊断当前状态，选择下一步\n不建立跨作业学习者画像",
            "#F5F3FF",
            COLORS["purple"],
        ),
        (
            0.69,
            "适配的学习支架",
            "提示强度 · 追问对象 · 反馈内容\n阶段推进条件",
            "#FFF7ED",
            COLORS["orange"],
        ),
    ]
    for x, title, detail, face, edge in top_boxes:
        box(x, 0.67, 0.27, 0.16, face, edge)
        ax.text(
            x + 0.135,
            0.79,
            title,
            ha="center",
            va="center",
            fontsize=12.2,
            fontweight="bold",
            color=edge,
        )
        ax.text(
            x + 0.135,
            0.725,
            detail,
            ha="center",
            va="center",
            fontsize=8.7,
            linespacing=1.35,
            color=COLORS["dark"],
        )

    arrow((0.315, 0.76), (0.355, 0.76), color=COLORS["purple"])
    arrow((0.64, 0.76), (0.68, 0.76), color=COLORS["orange"])

    ax.text(
        0.5,
        0.625,
        "基于当前状态的支架贯穿三个阶段",
        ha="center",
        va="center",
        fontsize=10.8,
        fontweight="bold",
        color=COLORS["dark"],
    )

    stages = [
        (
            0.04,
            "1  思路外化",
            "用自然语言说明算法步骤、\n输入输出与边界条件",
            "学生表达 → 针对性提示",
            "#EFF6FF",
            COLORS["blue"],
        ),
        (
            0.365,
            "2  程序构建",
            "把思路转换为程序结构，\n诊断并修正代码错误",
            "状态诊断 → 反馈与验证",
            "#ECFDF5",
            COLORS["green"],
        ),
        (
            0.69,
            "3  讲解纠错",
            "教师角色—真实学生—虚拟学生\n围绕讲解与错误代码协同追问",
            "角色化追问 → 解释与修正",
            "#FFF7ED",
            COLORS["orange"],
        ),
    ]
    for x, title, activity, scaffold, face, edge in stages:
        box(x, 0.35, 0.27, 0.20, face, edge)
        ax.text(
            x + 0.135,
            0.50,
            title,
            ha="center",
            va="center",
            fontsize=13.6,
            fontweight="bold",
            color=edge,
        )
        ax.text(
            x + 0.135,
            0.435,
            activity,
            ha="center",
            va="center",
            fontsize=10.2,
            linespacing=1.45,
        )
        ax.text(
            x + 0.135,
            0.375,
            scaffold,
            ha="center",
            va="center",
            fontsize=9.0,
            color=COLORS["gray"],
        )

    rail_y = 0.585
    ax.plot(
        (0.825, 0.825),
        (0.67, rail_y),
        color=COLORS["orange"],
        linewidth=1.9,
        transform=ax.transAxes,
    )
    ax.plot(
        (0.175, 0.825),
        (rail_y, rail_y),
        color=COLORS["orange"],
        linewidth=1.9,
        solid_capstyle="round",
        transform=ax.transAxes,
    )
    for stage_center in (0.175, 0.50, 0.825):
        arrow((stage_center, rail_y), (stage_center, 0.55), color=COLORS["orange"])
    arrow((0.31, 0.45), (0.355, 0.45), color=COLORS["gray"])
    arrow((0.635, 0.45), (0.68, 0.45), color=COLORS["gray"])

    ax.text(
        0.5,
        0.285,
        "过程日志的证据边界",
        ha="center",
        va="center",
        fontsize=11.8,
        fontweight="bold",
        color=COLORS["dark"],
    )
    arrow((0.175, 0.35), (0.175, 0.25), linestyle="dashed")
    arrow((0.50, 0.35), (0.50, 0.25), linestyle="dashed")
    arrow((0.825, 0.35), (0.825, 0.25), linestyle="dashed")

    box(0.04, 0.09, 0.43, 0.13, "#F0F9FF", COLORS["blue"])
    ax.text(
        0.255,
        0.175,
        "日志可观察：采用、阶段推进、回退、退出\n及其相邻操作转换",
        ha="center",
        va="center",
        fontsize=10.0,
        fontweight="bold",
        color=COLORS["blue"],
    )
    box(0.53, 0.09, 0.43, 0.13, COLORS["light"], COLORS["gray"], linestyle="dashed")
    ax.text(
        0.745,
        0.175,
        "日志不能直接观察：认知质量与学习增益\n需经内容编码或后续对照研究验证",
        ha="center",
        va="center",
        fontsize=10.0,
        fontweight="bold",
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
