from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import Condition, Persona, TaskCase
from .zhipu_roles import RoleClient


MAX_SYSTEM_TURNS = 8


@dataclass
class SimulationState:
    task: TaskCase
    persona: Persona
    condition: Condition
    stage: int = 1
    hint_count: int = 0
    validation_result: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)
    system_turns: int = 0
    stage1_turns: int = 0
    stage2_turns: int = 0
    stage3_phase: int = 0
    student_description: str = ""
    current_block_ids: list[str] = field(default_factory=list)
    buggy_code: str = ""
    bugs: list[dict[str, Any]] = field(default_factory=list)
    code_repair_omitted: bool = False


@dataclass(frozen=True)
class SystemStep:
    content: str
    stage: int
    completed: bool
    event_type: str
    technical_status: str = "ok"


class StructuralAdapter:
    def __init__(
        self,
        condition: Condition,
        role_client: RoleClient,
        direct_prompt: str,
        fixed_prompt: str,
    ) -> None:
        if condition not in {Condition.C0, Condition.C1}:
            raise ValueError("StructuralAdapter supports only C0 and C1")
        self.condition = condition
        self.role_client = role_client
        self.direct_prompt = direct_prompt
        self.fixed_prompt = fixed_prompt

    def respond(self, state: SimulationState, learner_response: str) -> SystemStep:
        if state.system_turns >= MAX_SYSTEM_TURNS:
            return SystemStep("", state.stage, True, "turn_limit")
        turn_index = state.system_turns
        if self.condition is Condition.C0:
            stage = 1
            prompt = self.direct_prompt
            event_type = "direct_answer"
        else:
            stage = 1 if turn_index < 2 else 2 if turn_index < 4 else 3
            prompt = self.fixed_prompt
            event_type = f"fixed_stage_{stage}"

        messages = [
            *[dict(item) for item in state.history],
            {
                "role": "user",
                "content": (
                    f"turn_index={turn_index}; task={state.task.title}; "
                    f"learner_response={learner_response}"
                ),
            },
        ]
        response = self.role_client.complete(
            "system", prompt, messages, temperature=0.2, max_tokens=800
        )
        state.stage = stage
        state.system_turns += 1
        completed = state.system_turns >= MAX_SYSTEM_TURNS or not response.success
        technical_status = "ok" if response.success else response.error_code
        return SystemStep(
            response.content,
            stage,
            completed,
            event_type,
            technical_status=technical_status,
        )
