"""Public, finite learning-goal state for the Stage 3 forum.

The agent loop keeps the authoritative Feynman state private.  This module
turns the safe subset of that state into a small user-facing contract: a
bounded progress value, milestones, and one concrete next action.
"""

from __future__ import annotations

from typing import Any, Mapping


_DEFAULT_MIN_COVERAGE = 0.8
_COVERED_STATUS = "covered"
_CODE_REVIEW_STATUSES = frozenset({"passed", "approved", "complete"})
_DIMENSION_LABELS = {
    "core": "核心规则",
    "edge_case": "边界情况",
    "application": "实际应用",
}


def build_stage3_user_goal(
    *,
    key_concepts: Any,
    coverage_summary: Any,
    phase: Any = "student_dialogue",
    state_status: Any = "in_progress",
    session_status: Any = "in_progress",
    code_review_status: Any = "pending",
    min_coverage: Any = _DEFAULT_MIN_COVERAGE,
) -> dict[str, Any]:
    """Build the safe, finite UserGoal contract exposed to the browser.

    ``coverage_summary`` is intentionally treated as untrusted input.  The
    helper only copies the fields needed for the progress display and never
    returns evidence, prompts, artifacts, or model internals.
    """

    concepts = _unique_strings(key_concepts)
    summary = coverage_summary if isinstance(coverage_summary, Mapping) else {}
    entries = [
        item
        for item in (_safe_coverage_item(value) for value in summary.get("concept_coverage", []))
        if item is not None
    ]
    if not concepts:
        concepts = _unique_strings(item["concept"] for item in entries)

    total_concepts = len(concepts)
    covered_concepts = sum(item["status"] == _COVERED_STATUS for item in entries)
    try:
        score = float(summary.get("coverage_score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    score = min(1.0, max(0.0, score))
    try:
        threshold = float(min_coverage)
    except (TypeError, ValueError):
        threshold = _DEFAULT_MIN_COVERAGE
    threshold = min(1.0, max(0.0, threshold))

    ready_for_code = summary.get("ready_for_code") is True
    phase_text = str(phase or "student_dialogue").strip()
    state_status_text = str(state_status or "in_progress").strip()
    session_status_text = str(session_status or "in_progress").strip()
    code_status_text = str(code_review_status or "pending").strip()
    completed = (
        session_status_text == "completed"
        or state_status_text == "complete"
        or code_status_text == "complete"
    )
    code_review_started = phase_text == "code_review" or code_status_text in _CODE_REVIEW_STATUSES

    if completed:
        progress_percent = 100
        current_milestone = "complete"
        next_action = "本阶段目标已完成，可以查看并回顾你的修复思路。"
        goal_status = "complete"
    elif code_review_started:
        progress_percent = 90
        current_milestone = "repair"
        next_action = "请修复右侧这份待检查代码，然后提交验证。"
        goal_status = "in_progress"
    elif ready_for_code:
        progress_percent = 80
        current_milestone = "buggy_code"
        next_action = "关键点已完成多角度检查，下一步生成一份错误代码来练习修复。"
        goal_status = "ready_for_code"
    else:
        progress_percent = min(79, round(score * 80))
        current_milestone = "understanding"
        pending = summary.get("pending_probe")
        if isinstance(pending, Mapping) and str(pending.get("concept") or "").strip():
            concept = str(pending.get("concept")).strip()
            dimension = _DIMENSION_LABELS.get(
                str(pending.get("dimension") or "").strip(),
                str(pending.get("dimension") or "下一角度").strip(),
            )
            next_action = f"请回答小明关于“{concept}”的{dimension}问题。"
        elif isinstance(summary.get("student_probe_intent"), Mapping):
            intent = summary["student_probe_intent"]
            concept = str(intent.get("concept") or "").strip()
            dimension = _DIMENSION_LABELS.get(
                str(intent.get("dimension") or "").strip(),
                str(intent.get("dimension") or "下一角度").strip(),
            )
            next_action = (
                f"请先回应当前问题；下一轮小明会从“{concept}”的{dimension}角度检查。"
                if concept
                else "请先回应当前问题，下一轮小明会从新的角度检查。"
            )
        elif summary.get("unresolved_concepts"):
            concept = str(summary["unresolved_concepts"][0]).strip()
            next_action = f"请继续用自己的话说明“{concept}”，小明会换一个角度检查。"
        elif concepts:
            next_action = "先用自己的话说明一个关键知识点，系统会按检查点推进。"
        else:
            next_action = "等待学习数据准备好后开始关键点检查。"
        goal_status = "in_progress"

    understanding_done = ready_for_code or code_review_started or completed
    peer_check_done = ready_for_code or code_review_started or completed
    buggy_code_done = code_review_started or completed
    repair_done = completed

    return {
        "id": "stage3-teach-and-repair",
        "title": "掌握关键思路并完成一次代码修复",
        "description": "先用自己的话解释关键点，再由小明从不同角度检查，达标后自动生成一份错误代码供你修复。",
        "status": goal_status,
        "progress_percent": progress_percent,
        "coverage_score": round(score, 3),
        "coverage_threshold": round(threshold, 3),
        "covered_concepts": covered_concepts,
        "total_concepts": total_concepts,
        "current_milestone": current_milestone,
        "next_action": next_action,
        "steps": [
            {"id": "understanding", "label": "说明关键知识点", "status": "done" if understanding_done else "active"},
            {"id": "peer_check", "label": "小明完成多角度检查", "status": "done" if peer_check_done else "todo"},
            {"id": "buggy_code", "label": "生成待修复代码", "status": "done" if buggy_code_done else "todo"},
            {"id": "repair", "label": "修复并通过验证", "status": "done" if repair_done else ("active" if buggy_code_done else "todo")},
        ],
    }


def _safe_coverage_item(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    concept = str(value.get("concept") or "").strip()
    status = str(value.get("status") or "").strip()
    if not concept or not status:
        return None
    return {"concept": concept, "status": status}


def _unique_strings(values: Any) -> list[str]:
    if isinstance(values, (str, bytes)) or values is None:
        return []
    try:
        iterator = iter(values)
    except TypeError:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in iterator:
        text = str(value).strip() if isinstance(value, str) else ""
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


__all__ = ["build_stage3_user_goal"]
