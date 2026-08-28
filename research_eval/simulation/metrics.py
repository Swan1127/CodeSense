from __future__ import annotations

from difflib import SequenceMatcher
import hashlib
import re
from typing import Any, Iterable, Mapping, Sequence

from .models import TaskCase


HINT_SIMILARITY_THRESHOLD = 0.80
_CODE_FENCE = re.compile(r"```(?:[A-Za-z0-9_+.#-]+)?\s*\n[\s\S]+?```", re.MULTILINE)
_NON_WORD = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff]+")


def normalize_text(value: str) -> str:
    return _NON_WORD.sub("", str(value)).lower()


def detect_complete_code(value: str) -> bool:
    text = str(value)
    if _CODE_FENCE.search(text):
        return True
    normalized_lines = [line.strip() for line in text.splitlines() if line.strip()]
    joined = "\n".join(normalized_lines)
    has_entry = bool(re.search(r"\b(?:int|void)\s+main\s*\(", joined))
    has_structure = "{" in joined and "}" in joined and ";" in joined
    has_program_context = "#include" in joined or len(normalized_lines) >= 3
    return has_entry and has_structure and has_program_context


def covers_all_key_steps(value: str, key_steps: Sequence[str]) -> bool:
    normalized = normalize_text(value)
    normalized_steps = [normalize_text(item) for item in key_steps if normalize_text(item)]
    return bool(normalized_steps) and all(step in normalized for step in normalized_steps)


def score_trajectory(
    trajectory: Mapping[str, Any],
    turns: Sequence[Mapping[str, Any]],
    task: TaskCase,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ordered_turns = sorted(turns, key=lambda row: int(row.get("turn_index", 0)))
    system_turns = [row for row in ordered_turns if row.get("actor") == "system"]
    learner_turns = [row for row in ordered_turns if row.get("actor") == "learner"]
    candidates: list[dict[str, Any]] = []

    code_leak_turns: list[Mapping[str, Any]] = []
    step_leak_turns: list[Mapping[str, Any]] = []
    for turn in system_turns:
        content = str(turn.get("content", ""))
        event_type = str(turn.get("event_type", ""))
        stage = int(turn.get("stage", 0) or 0)
        if event_type != "student_agent_code" and detect_complete_code(content):
            code_leak_turns.append(turn)
            candidates.append(
                _candidate(trajectory, task, turn, "possible_complete_code_leakage")
            )
        if stage < 3 and covers_all_key_steps(content, task.key_steps):
            step_leak_turns.append(turn)
            candidates.append(
                _candidate(trajectory, task, turn, "possible_full_step_leakage")
            )

    hint_turns = [
        row
        for row in system_turns
        if "hint" in str(row.get("event_type", "")).lower()
    ]
    duplicate_hint_pairs = _duplicate_pairs(
        [str(row.get("content", "")) for row in hint_turns]
    )
    stages = [int(row.get("stage", 0) or 0) for row in system_turns]
    stage_order_violations = sum(
        current < previous for previous, current in zip(stages, stages[1:])
    )
    completed = bool(trajectory.get("completed"))
    transitioned = any(
        str(row.get("applied_transition", "")).strip() not in {"", "NONE"}
        and str(row.get("state_before", "")) != str(row.get("state_after", ""))
        for row in learner_turns
    )
    invalid_reason = str(trajectory.get("invalid_reason", ""))
    technical_failure = (
        "technical_failure" in invalid_reason
        or "api_failure" in invalid_reason
        or any(str(row.get("technical_status", "ok")) != "ok" for row in ordered_turns)
    )
    metrics = {
        "trajectory_id": str(trajectory["trajectory_id"]),
        "task_id": str(trajectory["task_id"]),
        "persona_id": str(trajectory["persona_id"]),
        "condition": str(trajectory["condition"]),
        "repeat": int(trajectory["repeat"]),
        "freeze_hash": str(trajectory.get("freeze_hash", "")),
        "topic": task.topic,
        "difficulty": task.difficulty,
        "completed": int(completed),
        "recovered": int(completed and transitioned),
        "possible_complete_code_leakage": int(bool(code_leak_turns)),
        "possible_full_step_leakage": int(bool(step_leak_turns)),
        "duplicate_hint_pairs": duplicate_hint_pairs,
        "stage_order_violations": stage_order_violations,
        "system_response_count": len(system_turns),
        "learner_response_count": len(learner_turns),
        "technical_failure": int(technical_failure),
        "invalid_reason": invalid_reason,
    }
    return metrics, candidates


def score_dataset(
    trajectories: Iterable[Mapping[str, Any]],
    turns: Iterable[Mapping[str, Any]],
    tasks: Sequence[TaskCase],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    turns_by_trajectory: dict[str, list[Mapping[str, Any]]] = {}
    for turn in turns:
        turns_by_trajectory.setdefault(str(turn["trajectory_id"]), []).append(turn)
    task_map = {row.task_id: row for row in tasks}
    metric_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for trajectory in trajectories:
        task_id = str(trajectory["task_id"])
        if task_id not in task_map:
            raise ValueError(f"unknown task in trajectory: {task_id}")
        metrics, candidates = score_trajectory(
            trajectory,
            turns_by_trajectory.get(str(trajectory["trajectory_id"]), []),
            task_map[task_id],
        )
        metric_rows.append(metrics)
        candidate_rows.extend(candidates)
    return metric_rows, candidate_rows


def _duplicate_pairs(values: Sequence[str]) -> int:
    normalized = [normalize_text(value) for value in values]
    return sum(
        SequenceMatcher(None, normalized[left], normalized[right]).ratio()
        > HINT_SIMILARITY_THRESHOLD
        for left in range(len(normalized))
        for right in range(left + 1, len(normalized))
        if normalized[left] and normalized[right]
    )


def _candidate(
    trajectory: Mapping[str, Any],
    task: TaskCase,
    turn: Mapping[str, Any],
    rule_flag: str,
) -> dict[str, Any]:
    raw_id = f"{trajectory['trajectory_id']}|{turn.get('turn_index', 0)}|{rule_flag}"
    candidate_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]
    return {
        "candidate_id": candidate_id,
        "trajectory_id": str(trajectory["trajectory_id"]),
        "turn_index": int(turn.get("turn_index", 0)),
        "rule_flag": rule_flag,
        "excerpt": str(turn.get("content", ""))[:500],
        "task_id": task.task_id,
        "difficulty": task.difficulty,
        "persona_id": str(trajectory["persona_id"]),
    }
