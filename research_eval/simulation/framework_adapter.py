from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .conditions import MAX_SYSTEM_TURNS, SimulationState, SystemStep
from .models import Condition


@dataclass(frozen=True)
class ThinkingFunctions:
    evaluate_description: Callable[..., tuple[float, str]]
    generate_stage1_hint: Callable[..., str]
    generate_stage2_hint: Callable[..., str]
    teacher_agent_chat: Callable[..., str]
    student_agent_chat: Callable[..., str]
    student_agent_write_code: Callable[..., dict]
    evaluate_feynman_code_fix: Callable[..., tuple[bool, str]]


def default_thinking_functions() -> ThinkingFunctions:
    from utils.thinking_ai import (
        evaluate_description,
        evaluate_feynman_code_fix,
        generate_stage1_hint,
        generate_stage2_hint,
        student_agent_chat,
        student_agent_write_code,
        teacher_agent_chat,
    )

    return ThinkingFunctions(
        evaluate_description=evaluate_description,
        generate_stage1_hint=generate_stage1_hint,
        generate_stage2_hint=generate_stage2_hint,
        teacher_agent_chat=teacher_agent_chat,
        student_agent_chat=student_agent_chat,
        student_agent_write_code=student_agent_write_code,
        evaluate_feynman_code_fix=evaluate_feynman_code_fix,
    )


class FrameworkAdapter:
    def __init__(
        self,
        condition: Condition,
        functions: ThinkingFunctions | None = None,
    ) -> None:
        if condition not in {Condition.C2, Condition.A1, Condition.A2, Condition.A3}:
            raise ValueError("FrameworkAdapter supports C2 and A1/A2/A3")
        self.condition = condition
        self.functions = functions or default_thinking_functions()

    def respond(self, state: SimulationState, learner_response: str) -> SystemStep:
        if state.system_turns >= MAX_SYSTEM_TURNS:
            return SystemStep("", state.stage, True, "turn_limit")
        state.student_description = learner_response or state.student_description

        if state.stage == 1:
            step = self._stage1(state, learner_response)
        elif state.stage == 2:
            step = self._stage2(state)
        else:
            step = self._stage3(state, learner_response)

        state.system_turns += 1
        if state.system_turns >= MAX_SYSTEM_TURNS and not step.completed:
            return SystemStep(
                step.content,
                step.stage,
                True,
                step.event_type,
                technical_status=step.technical_status,
            )
        return step

    def _stage1(self, state: SimulationState, learner_response: str) -> SystemStep:
        score, feedback = self.functions.evaluate_description(
            learner_response,
            list(state.task.key_steps),
            state.task.title,
        )
        adaptive = self.condition is not Condition.A1
        if adaptive:
            state.validation_result = {"score": score, "feedback": feedback}
        hint_count = state.hint_count if adaptive else 0
        hint = self.functions.generate_stage1_hint(
            learner_response,
            list(state.task.key_steps),
            state.task.title,
            hint_count,
        )
        if adaptive:
            state.hint_count += 1
        state.stage1_turns += 1
        if (adaptive and score >= 70) or state.stage1_turns >= 2:
            state.stage = 2
        return SystemStep(
            f"{feedback}\n{hint}".strip(),
            1,
            False,
            "stage1_evaluate_and_hint",
        )

    def _stage2(self, state: SimulationState) -> SystemStep:
        blocks = _correct_blocks(state)
        adaptive = self.condition is not Condition.A1
        hint_count = state.hint_count if adaptive else 0
        hint = self.functions.generate_stage2_hint(
            state.student_description,
            list(state.current_block_ids),
            blocks,
            state.task.title,
            hint_count,
        )
        if adaptive:
            state.hint_count += 1
        if state.stage2_turns < len(blocks):
            state.current_block_ids.append(str(blocks[state.stage2_turns]["id"]))
        state.stage2_turns += 1
        if state.stage2_turns >= 2:
            state.stage = 3
        return SystemStep(hint, 2, False, "stage2_structure_hint")

    def _stage3(self, state: SimulationState, learner_response: str) -> SystemStep:
        if self.condition is Condition.A2:
            return self._stage3_without_student_agent(state, learner_response)
        if self.condition is Condition.A3:
            return self._stage3_without_code_repair(state)
        return self._stage3_full(state, learner_response)

    def _stage3_full(
        self, state: SimulationState, learner_response: str
    ) -> SystemStep:
        if state.stage3_phase == 0:
            content = self.functions.teacher_agent_chat(
                self._history(state),
                state.task.title,
                list(state.task.key_steps),
                state.student_description,
                assignment_description=state.task.description,
                student_state=self._student_state(state),
            )
            state.stage3_phase = 1
            return SystemStep(content, 3, False, "teacher_agent")
        if state.stage3_phase == 1:
            content = self.functions.student_agent_chat(
                self._history(state),
                state.task.title,
                list(state.task.key_steps),
                {"feynman_rounds": 4, "student_persona": "curious"},
                round_number=1,
                assignment_description=state.task.description,
                student_state=self._student_state(state),
            )
            state.stage3_phase = 2
            return SystemStep(content, 3, False, "student_agent")
        if state.stage3_phase == 2:
            result = self.functions.student_agent_write_code(
                state.task.title,
                list(state.task.key_steps),
                state.task.reference_code,
                self._history(state),
            )
            state.buggy_code = str(result.get("buggy_code", ""))
            state.bugs = list(result.get("bugs", []))
            state.stage3_phase = 3
            return SystemStep(
                str(result.get("message", "")),
                3,
                False,
                "student_agent_code",
            )

        correct, feedback = self.functions.evaluate_feynman_code_fix(
            state.buggy_code,
            learner_response,
            state.bugs,
            state.task.reference_code,
        )
        return SystemStep(
            feedback,
            3,
            True,
            "code_repair_pass" if correct else "code_repair_fail",
        )

    def _stage3_without_student_agent(
        self, state: SimulationState, learner_response: str
    ) -> SystemStep:
        if state.stage3_phase == 0:
            content = self.functions.teacher_agent_chat(
                self._history(state),
                state.task.title,
                list(state.task.key_steps),
                state.student_description,
                assignment_description=state.task.description,
                student_state=self._student_state(state),
            )
            state.stage3_phase = 1
            return SystemStep(content, 3, False, "teacher_agent")
        if state.stage3_phase == 1:
            result = self.functions.student_agent_write_code(
                state.task.title,
                list(state.task.key_steps),
                state.task.reference_code,
                self._history(state),
            )
            state.buggy_code = str(result.get("buggy_code", ""))
            state.bugs = list(result.get("bugs", []))
            state.stage3_phase = 2
            return SystemStep(
                str(result.get("message", "")),
                3,
                False,
                "student_agent_code",
            )
        correct, feedback = self.functions.evaluate_feynman_code_fix(
            state.buggy_code,
            learner_response,
            state.bugs,
            state.task.reference_code,
        )
        return SystemStep(
            feedback,
            3,
            True,
            "code_repair_pass" if correct else "code_repair_fail",
        )

    def _stage3_without_code_repair(self, state: SimulationState) -> SystemStep:
        if state.stage3_phase == 0:
            content = self.functions.teacher_agent_chat(
                self._history(state),
                state.task.title,
                list(state.task.key_steps),
                state.student_description,
                assignment_description=state.task.description,
                student_state=self._student_state(state),
            )
            state.stage3_phase = 1
            return SystemStep(content, 3, False, "teacher_agent")

        content = self.functions.student_agent_chat(
            self._history(state),
            state.task.title,
            list(state.task.key_steps),
            {"feynman_rounds": 4, "student_persona": "curious"},
            round_number=1,
            assignment_description=state.task.description,
            student_state=self._student_state(state),
        )
        state.code_repair_omitted = True
        return SystemStep(content, 3, True, "student_agent_no_code_repair")

    def _history(self, state: SimulationState) -> list[dict[str, str]]:
        if self.condition is Condition.A1:
            return []
        return [dict(item) for item in state.history]

    def _student_state(self, state: SimulationState) -> dict[str, Any]:
        if self.condition is Condition.A1:
            return {}
        return {
            "persona_id": state.persona.persona_id,
            "observable_behavior": state.persona.observable_behavior,
            "hint_count": state.hint_count,
            "validation_result": dict(state.validation_result),
        }


def _correct_blocks(state: SimulationState) -> list[dict[str, Any]]:
    if state.task.quiz_steps:
        return [
            {
                "id": str(step.get("step_id", f"step_{index:03d}")),
                "code": str(
                    step.get("correct_answer")
                    or step.get("code_line")
                    or step.get("question")
                    or ""
                ),
                "indent": int(step.get("indent") or 0),
            }
            for index, step in enumerate(state.task.quiz_steps, 1)
        ]
    return [
        {"id": f"line_{index:03d}", "code": line, "indent": 0}
        for index, line in enumerate(state.task.reference_code.splitlines(), 1)
        if line.strip()
    ]
