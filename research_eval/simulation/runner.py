from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
from typing import Any

from .conditions import MAX_SYSTEM_TURNS, SimulationState
from .matrix import TrajectorySpec
from .models import LearnerStep, Persona, TaskCase, Trajectory, Turn


class JsonlSink:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())


def run_trajectory(
    spec: TrajectorySpec,
    task: TaskCase,
    persona: Persona,
    learner_client: Any,
    adapter: Any,
    learner_prompt: str,
    prompt_hashes: dict[str, str],
    turn_sink: JsonlSink,
    trajectory_sink: JsonlSink,
) -> Trajectory:
    if spec.task_id != task.task_id or spec.persona_id != persona.persona_id:
        raise ValueError("trajectory spec does not match task/persona")

    trajectory = Trajectory(
        trajectory_id=_trajectory_id(spec),
        task_id=task.task_id,
        persona_id=persona.persona_id,
        condition=spec.condition,
        repeat=spec.repeat,
        prompt_hashes=dict(prompt_hashes),
        freeze_hash=spec.freeze_hash,
    )
    state = SimulationState(task=task, persona=persona, condition=_condition(spec.condition))

    try:
        while state.system_turns < MAX_SYSTEM_TURNS:
            learner_step = _generate_learner_step(
                learner_client,
                learner_prompt,
                task,
                persona,
                state,
            )
            if learner_step is None:
                trajectory.invalid_reason = "learner_format_invalid"
                break
            if isinstance(learner_step, str):
                trajectory.invalid_reason = learner_step
                break

            learner_turn = Turn(
                turn_index=len(trajectory.turns),
                actor="learner",
                content=learner_step.response,
                stage=state.stage,
            )
            trajectory.turns.append(learner_turn)
            state.history.append({"role": "user", "content": learner_step.response})
            turn_sink.append(
                {
                    "trajectory_id": trajectory.trajectory_id,
                    **asdict(learner_turn),
                    "state_before": learner_step.state_before,
                    "state_after": learner_step.state_after,
                    "applied_transition": learner_step.applied_transition,
                }
            )

            try:
                system_step = adapter.respond(state, learner_step.response)
            except Exception as exc:
                trajectory.invalid_reason = f"system_technical_failure:{type(exc).__name__}"
                break

            system_turn = Turn(
                turn_index=len(trajectory.turns),
                actor="system",
                content=system_step.content,
                stage=system_step.stage,
                technical_status=system_step.technical_status,
            )
            trajectory.turns.append(system_turn)
            state.history.append({"role": "assistant", "content": system_step.content})
            turn_sink.append(
                {
                    "trajectory_id": trajectory.trajectory_id,
                    **asdict(system_turn),
                    "event_type": system_step.event_type,
                }
            )

            if system_step.technical_status != "ok":
                trajectory.invalid_reason = (
                    f"system_technical_failure:{system_step.technical_status}"
                )
                break
            if system_step.completed:
                trajectory.completed = True
                break

        if not trajectory.completed and not trajectory.invalid_reason:
            trajectory.invalid_reason = "turn_limit"
    finally:
        trajectory_sink.append(trajectory.to_dict())
    return trajectory


def load_finalized_keys(
    path: Path,
) -> set[tuple[str, str, str, int, str]]:
    if not path.exists():
        return set()
    keys: set[tuple[str, str, str, int, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        keys.add(
            (
                str(row["task_id"]),
                str(row["persona_id"]),
                str(row["condition"]),
                int(row["repeat"]),
                str(row.get("freeze_hash", "")),
            )
        )
    return keys


def _generate_learner_step(
    client: Any,
    learner_prompt: str,
    task: TaskCase,
    persona: Persona,
    state: SimulationState,
) -> LearnerStep | str | None:
    context = {
        "task": {
            "title": task.title,
            "description": task.description,
            "key_steps_visible": [],
        },
        "persona": {
            "hidden_state": persona.hidden_state,
            "observable_behavior": persona.observable_behavior,
            "transition_rules": list(persona.transition_rules),
            "forbidden_knowledge": list(persona.forbidden_knowledge),
        },
        "current_stage": state.stage,
        "dialogue": [dict(item) for item in state.history],
    }
    messages = [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
    response = client.complete(
        "learner",
        learner_prompt,
        messages,
        temperature=0.6,
        max_tokens=400,
    )
    if not response.success:
        return f"learner_api_failure:{response.error_code or response.status_code}"

    parsed = _parse_learner_step(response.content, persona)
    if parsed is not None:
        return parsed

    retry_messages = [
        *messages,
        {"role": "assistant", "content": response.content},
        {
            "role": "user",
            "content": (
                "仅修复输出格式。只返回包含 response、state_before、state_after、"
                "applied_transition 的 JSON 对象，不改变原回答含义。"
            ),
        },
    ]
    retry = client.complete(
        "learner",
        learner_prompt,
        retry_messages,
        temperature=0.6,
        max_tokens=400,
    )
    if not retry.success:
        return f"learner_api_failure:{retry.error_code or retry.status_code}"
    return _parse_learner_step(retry.content, persona)


def _parse_learner_step(content: str, persona: Persona) -> LearnerStep | None:
    try:
        row = json.loads(content)
    except (TypeError, ValueError):
        return None
    if not isinstance(row, dict):
        return None
    required = ("response", "state_before", "state_after", "applied_transition")
    if any(not isinstance(row.get(field), str) or not row[field].strip() for field in required):
        return None
    transition = row["applied_transition"].strip()
    if transition != "NONE" and transition not in persona.transition_rules:
        return None
    return LearnerStep(
        response=row["response"].strip(),
        state_before=row["state_before"].strip(),
        state_after=row["state_after"].strip(),
        applied_transition=transition,
    )


def _trajectory_id(spec: TrajectorySpec) -> str:
    return (
        f"{spec.task_id}-{spec.persona_id}-{spec.condition}-"
        f"R{spec.repeat}-{spec.freeze_hash[:12]}"
    )


def _condition(value: str):
    from .models import Condition

    return Condition(value)
