from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any


class Condition(str, Enum):
    C0 = "C0"
    C1 = "C1"
    C2 = "C2"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"


@dataclass(frozen=True)
class Persona:
    persona_id: str
    label: str
    hidden_state: str
    observable_behavior: str
    transition_rules: tuple[str, ...]
    forbidden_knowledge: tuple[str, ...]


@dataclass(frozen=True)
class TaskCase:
    task_id: str
    split: str
    topic: str
    difficulty: str
    title: str
    description: str
    key_steps: tuple[str, ...]
    reference_code: str
    quiz_steps: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Turn:
    turn_index: int
    actor: str
    content: str
    stage: int
    technical_status: str = "ok"


@dataclass(frozen=True)
class LearnerStep:
    response: str
    state_before: str
    state_after: str
    applied_transition: str


@dataclass
class Trajectory:
    trajectory_id: str
    task_id: str
    persona_id: str
    condition: str
    repeat: int
    prompt_hashes: dict[str, str]
    freeze_hash: str = ""
    started_at_utc: str = ""
    finished_at_utc: str = ""
    elapsed_seconds: float = 0.0
    turns: list[Turn] = field(default_factory=list)
    completed: bool = False
    invalid_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def content_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_personas(path: Path) -> list[Persona]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("persona manifest must be a JSON list")

    personas: list[Persona] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("each persona must be a JSON object")
        personas.append(
            Persona(
                persona_id=str(row["persona_id"]),
                label=str(row["label"]),
                hidden_state=str(row["hidden_state"]),
                observable_behavior=str(row["observable_behavior"]),
                transition_rules=tuple(str(item) for item in row["transition_rules"]),
                forbidden_knowledge=tuple(str(item) for item in row["forbidden_knowledge"]),
            )
        )

    if len({row.persona_id for row in personas}) != len(personas):
        raise ValueError("persona IDs must be unique")
    return personas
