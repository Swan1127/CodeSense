from __future__ import annotations

from collections import defaultdict
import random
from typing import Any, Iterable, Mapping, Sequence

from .judging import FLAG_FIELDS, RATING_DIMENSIONS


SAMPLE_QUOTAS = {"C0": 24, "C1": 24, "C2": 24, "A1": 8, "A2": 8, "A3": 8}


def build_review_candidates(
    trajectories: Sequence[Mapping[str, Any]],
    turns: Sequence[Mapping[str, Any]],
    tasks: Mapping[str, Mapping[str, Any]],
    personas: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build internally identified candidates for later blinded sampling."""
    turns_by_trajectory: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for turn in turns:
        if str(turn.get("actor", "")) in {"learner", "system"}:
            turns_by_trajectory[str(turn["trajectory_id"])].append(turn)
    rows: list[dict[str, Any]] = []
    for trajectory in trajectories:
        invalid_reason = str(trajectory.get("invalid_reason", ""))
        if invalid_reason not in {"", "turn_limit"}:
            continue
        trajectory_id = str(trajectory["trajectory_id"])
        dialogue = sorted(
            turns_by_trajectory.get(trajectory_id, []),
            key=lambda row: int(row.get("turn_index", 0)),
        )
        if not dialogue:
            continue
        task_id = str(trajectory["task_id"])
        persona_id = str(trajectory["persona_id"])
        task = tasks[task_id]
        persona = personas[persona_id]
        transcript = "\n".join(
            f"{'学习者' if row['actor'] == 'learner' else '系统'}：{row.get('content', '')}"
            for row in dialogue
        )
        rows.append({
            "trajectory_id": trajectory_id,
            "condition": str(trajectory["condition"]),
            "task_id": task_id,
            "persona_id": persona_id,
            "difficulty": str(task["difficulty"]),
            "task_text": f"{task['title']}\n{task['description']}",
            "persona_visible": str(persona["observable_behavior"]),
            "transcript": transcript,
        })
    return rows

def stratified_blind_sample(
    candidates: Sequence[Mapping[str, Any]],
    *,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    for condition, quota in SAMPLE_QUOTAS.items():
        condition_rows = [dict(row) for row in candidates if row.get("condition") == condition]
        if len(condition_rows) < quota:
            raise ValueError(f"insufficient candidates for {condition}: {len(condition_rows)} < {quota}")
        strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in condition_rows:
            strata[(str(row.get("difficulty", "")), str(row.get("persona_id", "")))].append(row)
        for rows in strata.values():
            rng.shuffle(rows)
        condition_selected: list[dict[str, Any]] = []
        ordered_keys = sorted(strata)
        while len(condition_selected) < quota:
            progressed = False
            for key in ordered_keys:
                if strata[key] and len(condition_selected) < quota:
                    condition_selected.append(strata[key].pop())
                    progressed = True
            if not progressed:
                raise ValueError(f"unable to fill stratified quota for {condition}")
        selected.extend(condition_selected)

    rng.shuffle(selected)
    packet: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    for index, row in enumerate(selected, 1):
        review_id = f"R{index:04d}"
        packet.append(
            {
                "review_id": review_id,
                "task_id": str(row.get("task_id", "")),
                "difficulty": str(row.get("difficulty", "")),
                "persona_visible": str(row.get("persona_visible", "")),
                "task_text": str(row.get("task_text", "")),
                "transcript": str(row.get("transcript", "")),
                **{name: "" for name in RATING_DIMENSIONS},
                **{name: "" for name in FLAG_FIELDS},
                "comment": "",
            }
        )
        key_rows.append(
            {
                "review_id": review_id,
                "trajectory_id": str(row["trajectory_id"]),
                "condition": str(row["condition"]),
                "task_id": str(row.get("task_id", "")),
                "persona_id": str(row.get("persona_id", "")),
                "difficulty": str(row.get("difficulty", "")),
                "seed": seed,
            }
        )
    return packet, key_rows


def validate_teacher_ratings(
    rows: Iterable[Mapping[str, Any]],
    packet_ids: set[str],
) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    raters: set[str] = set()
    for source in rows:
        row = dict(source)
        review_id = str(row.get("review_id", ""))
        rater_id = str(row.get("rater_id", ""))
        if review_id not in packet_ids:
            raise ValueError(f"rating references unknown packet ID: {review_id}")
        if not rater_id:
            raise ValueError("rater_id is required")
        key = (review_id, rater_id)
        if key in seen:
            raise ValueError(f"duplicate teacher rating: {review_id}/{rater_id}")
        seen.add(key)
        raters.add(rater_id)
        for name in RATING_DIMENSIONS:
            value = _integer(row.get(name), name)
            if not 1 <= value <= 5:
                raise ValueError(f"{name} must be in 1..5")
            row[name] = value
        for name in FLAG_FIELDS:
            value = _integer(row.get(name), name)
            if value not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")
            row[name] = value
        validated.append(row)
    if len(raters) != 2:
        raise ValueError("teacher review requires exactly two raters")
    counts = {review_id: sum(row["review_id"] == review_id for row in validated) for review_id in packet_ids}
    if any(value != 2 for value in counts.values()):
        raise ValueError("every packet ID must have two ratings")
    return validated


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if str(value).strip() not in {str(parsed), f"{parsed}.0"}:
        raise ValueError(f"{field} must be an integer")
    return parsed
