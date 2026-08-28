from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .models import Condition, Persona, TaskCase


DEFAULT_FORMAL_REPEATS = (1,)
EXTENDED_REPEATS = (1, 2, 3)


@dataclass(frozen=True, order=True)
class TrajectorySpec:
    task_id: str
    persona_id: str
    condition: str
    repeat: int
    freeze_hash: str

    @property
    def key(self) -> tuple[str, str, str, int, str]:
        return (
            self.task_id,
            self.persona_id,
            self.condition,
            self.repeat,
            self.freeze_hash,
        )


def build_core_matrix(
    tasks: Sequence[TaskCase],
    personas: Sequence[Persona],
    freeze_hash: str,
    repeats: Sequence[int] = DEFAULT_FORMAL_REPEATS,
) -> list[TrajectorySpec]:
    repeat_ids = _validated_repeats(repeats)
    formal_tasks = sorted(
        (task for task in tasks if task.split == "formal"),
        key=lambda row: row.task_id,
    )
    ordered_personas = sorted(personas, key=lambda row: row.persona_id)
    return [
        TrajectorySpec(
            task.task_id,
            persona.persona_id,
            condition.value,
            repeat,
            freeze_hash,
        )
        for task in formal_tasks
        for persona in ordered_personas
        for condition in (Condition.C0, Condition.C1, Condition.C2)
        for repeat in repeat_ids
    ]


def build_ablation_matrix(
    tasks: Sequence[TaskCase],
    personas: Sequence[Persona],
    freeze_hash: str,
    task_ids: Sequence[str],
    persona_ids: Sequence[str],
    repeats: Sequence[int] = DEFAULT_FORMAL_REPEATS,
) -> list[TrajectorySpec]:
    repeat_ids = _validated_repeats(repeats)
    if len(task_ids) != 6 or len(set(task_ids)) != 6:
        raise ValueError("ablation matrix requires six explicitly selected task IDs")
    if len(persona_ids) != 4 or len(set(persona_ids)) != 4:
        raise ValueError("ablation matrix requires four explicitly selected persona IDs")

    task_map = {row.task_id: row for row in tasks}
    persona_map = {row.persona_id: row for row in personas}
    missing_tasks = set(task_ids) - set(task_map)
    missing_personas = set(persona_ids) - set(persona_map)
    if missing_tasks or missing_personas:
        raise ValueError("ablation selection references unknown task or persona IDs")

    ordered_tasks = [task_map[item] for item in sorted(task_ids)]
    ordered_personas = [persona_map[item] for item in sorted(persona_ids)]
    return [
        TrajectorySpec(
            task.task_id,
            persona.persona_id,
            condition.value,
            repeat,
            freeze_hash,
        )
        for task in ordered_tasks
        for persona in ordered_personas
        for condition in (Condition.A1, Condition.A2, Condition.A3)
        for repeat in repeat_ids
    ]


def _validated_repeats(repeats: Sequence[int]) -> tuple[int, ...]:
    values = tuple(int(value) for value in repeats)
    if not values or len(set(values)) != len(values) or any(value <= 0 for value in values):
        raise ValueError("repeats must contain unique positive integers")
    return values


def filter_completed(
    specs: Iterable[TrajectorySpec],
    completed_keys: set[tuple[str, str, str, int, str]],
) -> list[TrajectorySpec]:
    return [spec for spec in specs if spec.key not in completed_keys]
