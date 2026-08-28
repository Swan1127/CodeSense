from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .models import TaskCase


ALLOWED_SPLITS = {"development", "formal"}
ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
REQUIRED_TOPICS = {"linear", "tree", "graph", "search_sort"}


def validate_task_manifest(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 14:
        raise ValueError("task manifest must contain exactly 14 tasks")

    task_ids = [str(row.get("task_id", "")).strip() for row in rows]
    if any(not value for value in task_ids) or len(set(task_ids)) != len(task_ids):
        raise ValueError("task IDs must be non-empty and unique")

    source_ids = [row.get("source_assignment_id") for row in rows]
    if any(value in (None, "") for value in source_ids) or len(set(source_ids)) != len(source_ids):
        raise ValueError("source assignment IDs must be non-empty and unique")

    for row in rows:
        split = str(row.get("split", ""))
        difficulty = str(row.get("difficulty", ""))
        topic = str(row.get("topic", ""))
        if split not in ALLOWED_SPLITS:
            raise ValueError("task split must be development or formal")
        if difficulty not in ALLOWED_DIFFICULTIES:
            raise ValueError("task difficulty must be easy, medium, or hard")
        if topic not in REQUIRED_TOPICS:
            raise ValueError("task topic is not in the frozen topic set")
        for field in ("title", "description", "reference_code"):
            if not str(row.get(field, "")).strip():
                raise ValueError(f"task field {field} must not be empty")
        key_steps = row.get("key_steps")
        if not isinstance(key_steps, list) or not key_steps or any(
            not str(item).strip() for item in key_steps
        ):
            raise ValueError("task key_steps must be a non-empty list")
        quiz_steps = row.get("quiz_steps", [])
        if not isinstance(quiz_steps, list):
            raise ValueError("task quiz_steps must be a list")

    development = [row for row in rows if row["split"] == "development"]
    formal = [row for row in rows if row["split"] == "formal"]
    if len(development) != 2 or len(formal) != 12:
        raise ValueError("task manifest must contain 2 development and 12 formal tasks")

    difficulty_counts = {
        level: sum(row["difficulty"] == level for row in formal)
        for level in ALLOWED_DIFFICULTIES
    }
    if difficulty_counts != {"easy": 4, "medium": 4, "hard": 4}:
        raise ValueError("formal task difficulty must be balanced 4/4/4")

    formal_topics = {str(row["topic"]) for row in formal}
    if not REQUIRED_TOPICS.issubset(formal_topics):
        raise ValueError("formal task topic coverage is incomplete")


def load_task_manifest(path: Path) -> list[TaskCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("task manifest must be a JSON list")
    validate_task_manifest(payload)
    return [
        TaskCase(
            task_id=str(row["task_id"]),
            split=str(row["split"]),
            topic=str(row["topic"]),
            difficulty=str(row["difficulty"]),
            title=str(row["title"]),
            description=str(row["description"]),
            key_steps=tuple(str(item) for item in row["key_steps"]),
            reference_code=str(row["reference_code"]),
            quiz_steps=tuple(dict(item) for item in row.get("quiz_steps", [])),
        )
        for row in payload
    ]


def freeze_files(paths: Mapping[str, Path]) -> dict[str, str]:
    return {
        str(name): hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in sorted(paths.items())
    }
