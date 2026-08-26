"""Assembly for the Stage 3 Teacher/Student Feynman runtime.

The runtime is deliberately a thin composition layer: :mod:`loop` remains the
only model/tool execution path and :mod:`memory` remains the source of truth
for request de-duplication and private code artifacts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional

from .contracts import AgentDecision, AgentResult, AgentRole, ToolCall, UIAction
from .loop import AgentLoop, AgentLoopSpec
from .memory import EventRecord, EventStore, MemorySnapshot, MemoryStore, SqlAlchemyEventStore
from .model import DecisionModel, StructuredDecisionModel
from .tools import (
    BuggyCodeGenerator,
    ToolRegistry,
    build_feynman_tool_registry,
)


@dataclass(frozen=True)
class AgentSpec:
    role: AgentRole
    goal: str
    system_prompt: str
    fallback_message: str
    max_output_chars: int = 1200


TEACHER_SPEC = AgentSpec(
    role=AgentRole.TEACHER_AGENT,
    goal="引导学习者清楚解释思路，并在通过服务端检查后完成学习目标。",
    system_prompt=(
        "你是教师 Agent。根据学习者的解释追问和纠偏，不直接泄露标准答案或隐藏修复。"
        "只有在工具返回的服务端条件满足时才调用 complete_goal。"
    ),
    fallback_message="请再用自己的话解释一下这一步。",
)
STUDENT_SPEC = AgentSpec(
    role=AgentRole.STUDENT_AGENT,
    goal="以同伴身份追问学习者的解释，并在需要时提交一份待检查的代码。",
    system_prompt=(
        "你是学生 Agent。只基于题目、概念和学习者的解释追问。"
        "不要声称知道标准答案、隐藏缺陷或正确修复；需要代码时使用允许的工具。"
    ),
    fallback_message="你能换一种说法解释这一段吗？",
)


@dataclass
class FeynmanCallbacks:
    """Inject persistence and domain callbacks without coupling unit tests to Flask."""

    event_store: Optional[EventStore] = None
    buggy_code_generator: Optional[BuggyCodeGenerator] = None
    fix_evaluator: Optional[FixEvaluator] = None
    persist_session: Optional[Callable[[Any], None]] = None
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc).replace(tzinfo=None)

    def memory_store(self) -> MemoryStore:
        if self.event_store is None:
            self.event_store = SqlAlchemyEventStore()
        return MemoryStore(self.event_store)

    def tool_registry(self) -> ToolRegistry:
        return build_feynman_tool_registry(
            buggy_code_generator=self.buggy_code_generator,
            fix_evaluator=self.fix_evaluator,
        )

    def save_session(self, session: Any) -> None:
        if self.persist_session is not None:
            self.persist_session(session)
            return
        from models import db

        db.session.add(session)
        db.session.commit()


class _RoleContextLoop(AgentLoop):
    """AgentLoop with a role-specific, explicitly allowlisted prompt context."""

    def __init__(self, *, context_builder: Callable[[MemorySnapshot, str], Dict[str, Any]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._context_builder = context_builder

    def _build_context(self, snapshot: MemorySnapshot, *, input_kind: str) -> str:
        return json.dumps(self._context_builder(snapshot, input_kind), ensure_ascii=False)


class _ForcedToolModel:
    """Use the normal AgentLoop path for non-chat runtime actions without an LLM."""

    def __init__(self, call: ToolCall) -> None:
        self.call = call
        self._returned_call = False
        self.last_error = None

    def decide(self, **_: Any) -> AgentDecision:
        if not self._returned_call:
            self._returned_call = True
            return AgentDecision(tool_calls=[self.call])
        return AgentDecision(message="")


class DualFeynmanRuntime:
    def __init__(
        self,
        *,
        session: Any,
        assignment: Any,
        preset: Any,
        model: DecisionModel,
        callbacks: FeynmanCallbacks,
    ) -> None:
        self.session = session
        self.assignment = assignment
        self.preset = preset
        self.model = model
        self.callbacks = callbacks
        self.memory = callbacks.memory_store()
        self.tools = callbacks.tool_registry()
        self.specs = {TEACHER_SPEC.role: TEACHER_SPEC, STUDENT_SPEC.role: STUDENT_SPEC}

    def handle_chat(self, role: AgentRole, message: str, *, request_id: str) -> AgentResult:
        if role not in self.specs:
            raise ValueError("unsupported agent role")
        duplicate = self.memory.find_request_result(self.session.id, request_id) is not None
        result = self._loop_for(role, self.model).handle_turn(message, request_id=request_id)
        if not duplicate:
            self._sync_completed_goal(role, result)
        return result

    def generate_buggy_attempt(self, *, request_id: str) -> AgentResult:
        result = self._run_forced_tool("generate_buggy_attempt", {}, request_id)
        if not result.success:
            return result
        artifact = self._artifact_for(request_id)
        if artifact is None:
            return AgentResult(success=False, agent=AgentRole.STUDENT_AGENT, error_code="BUGGY_ATTEMPT_FAILED")
        buggy_code = artifact.get("buggy_code")
        if not isinstance(buggy_code, str):
            return AgentResult(success=False, agent=AgentRole.STUDENT_AGENT, error_code="BUGGY_ATTEMPT_FAILED")
        content = self._tool_public_content(request_id, "generate_buggy_attempt")
        return AgentResult(
            success=True,
            agent=AgentRole.STUDENT_AGENT,
            response=str(content.get("message", "我写了一版代码，请帮我检查。")),
            ui_action=UIAction.SHOW_CODE_REVIEW,
            ready_for_code=True,
            state=result.state,
            public_content={"buggy_code": buggy_code},
        )

    def evaluate_fix(self, fixed_code: str, *, request_id: str) -> AgentResult:
        duplicate = self.memory.find_request_result(self.session.id, request_id) is not None
        result = self._run_forced_tool("evaluate_fix", {"fixed_code": fixed_code}, request_id)
        if not result.success:
            return result
        content = self._tool_public_content(request_id, "evaluate_fix")
        if not isinstance(content.get("correct"), bool):
            return AgentResult(success=False, agent=AgentRole.STUDENT_AGENT, error_code="FIX_EVALUATION_FAILED")
        evaluation = AgentResult(
            success=True,
            agent=AgentRole.STUDENT_AGENT,
            response=str(content.get("feedback", "")),
            state=result.state,
            public_content={"correct": content["correct"], "feedback": str(content.get("feedback", ""))},
        )
        if not duplicate and content["correct"]:
            self._complete_session(str(content.get("feedback", "")), request_id, source="validated_evaluation")
        return evaluation

    def _loop_for(self, role: AgentRole, model: DecisionModel) -> AgentLoop:
        spec = self.specs[role]
        return _RoleContextLoop(
            session_id=self.session.id,
            role=role,
            model=model,
            tools=self.tools,
            memory=self.memory,
            spec=AgentLoopSpec(
                system_prompt=_system_prompt(spec),
                assignment_title=str(getattr(self.assignment, "title", "") or ""),
                key_concepts=self._key_concepts(),
                reference_code=str(getattr(self.preset, "reference_code", "") or ""),
            ),
            context_builder=lambda snapshot, input_kind: self._context_for(role, snapshot, input_kind),
        )

    def _run_forced_tool(self, name: str, arguments: Dict[str, Any], request_id: str) -> AgentResult:
        return self._loop_for(
            AgentRole.STUDENT_AGENT,
            _ForcedToolModel(ToolCall(f"{request_id}:{name}", name, arguments)),
        ).handle_turn("", request_id=request_id, input_kind=name)

    def _context_for(self, role: AgentRole, snapshot: MemorySnapshot, input_kind: str) -> Dict[str, Any]:
        view = self.memory.view_for(snapshot, role)
        state = snapshot.state
        common = {
            "goal": state.goal,
            "phase": state.phase,
            "code_review_status": state.code_review_status,
            "input_kind": input_kind,
        }
        if role is AgentRole.TEACHER_AGENT:
            return {
                **common,
                "assignment": {
                    "title": str(getattr(self.assignment, "title", "") or ""),
                    "description": str(getattr(self.assignment, "description", "") or ""),
                },
                "stage1_description": str(getattr(self.session, "stage1_description", "") or ""),
                "stage2_completed": bool(getattr(self.session, "stage2_completed", False)),
                "learning_evidence": list(state.learning_evidence),
                "role_memory": {"agent_state": asdict(view.agent_state), "messages": list(view.messages)},
            }
        return {
            **common,
            "assignment": {
                "title": str(getattr(self.assignment, "title", "") or ""),
                "description": str(getattr(self.assignment, "description", "") or ""),
            },
            "key_concepts": self._key_concepts(),
            "algorithm_summary": self._algorithm_summary(),
            "user_explanations": list(snapshot.student_messages),
            "role_memory": {"agent_state": asdict(view.agent_state), "messages": list(view.messages)},
        }

    def _key_concepts(self) -> list[str]:
        getter = getattr(self.preset, "get_key_steps", None)
        raw = getter() if callable(getter) else getattr(self.preset, "key_steps", [])
        return [item.strip() for item in raw if isinstance(item, str) and item.strip()] if isinstance(raw, list) else []

    def _algorithm_summary(self) -> str:
        getter = getattr(self.preset, "get_algorithm_summary", None)
        value = getter() if callable(getter) else getattr(self.preset, "algorithm_summary", "")
        return str(value or "")

    def _artifact_for(self, request_id: str) -> Optional[Mapping[str, Any]]:
        for event in reversed(self._events()):
            if event.event_type != "buggy_attempt" or event.metadata.get("request_id") != request_id:
                continue
            artifact = event.metadata.get("artifact")
            if isinstance(artifact, Mapping):
                return artifact
        return None

    def _tool_public_content(self, request_id: str, tool_name: str) -> Dict[str, Any]:
        for event in reversed(self._events()):
            call = event.metadata.get("tool_call")
            if (
                event.event_type == "tool_result"
                and event.metadata.get("request_id") == request_id
                and isinstance(call, Mapping)
                and call.get("name") == tool_name
                and event.metadata.get("ok") is True
            ):
                content = event.metadata.get("public_content")
                return dict(content) if isinstance(content, Mapping) else {}
        return {}

    def _events(self) -> list[EventRecord]:
        return self.memory.event_store.list_events(self.session.id, stage=3)

    def _sync_completed_goal(self, role: AgentRole, result: AgentResult) -> None:
        if role is AgentRole.TEACHER_AGENT and result.success and result.state.get("status") == "complete":
            self._complete_session("学习目标已通过服务端检查。", request_id=None, source="complete_goal")

    def _complete_session(self, feedback: str, request_id: Optional[str], *, source: str) -> None:
        if getattr(self.session, "stage3_completed", False) or getattr(self.session, "status", "") == "completed":
            return
        self.session.stage3_completed = True
        self.session.status = "completed"
        self.session.completed_at = self.callbacks.now()
        self.memory.append_event(
            self.session.id,
            "stage_pass",
            "system",
            content=feedback,
            metadata={"request_id": request_id, "source": source},
        )
        self.callbacks.save_session(self.session)


def _system_prompt(spec: AgentSpec) -> str:
    return f"{spec.system_prompt}\n目标：{spec.goal}\n回复不超过 {spec.max_output_chars} 个字符。"


def build_feynman_runtime(session, assignment, preset, *, model=None, callbacks=None):
    return DualFeynmanRuntime(
        session=session,
        assignment=assignment,
        preset=preset,
        model=model or StructuredDecisionModel(),
        callbacks=callbacks or FeynmanCallbacks(),
    )


__all__ = [
    "AgentSpec",
    "DualFeynmanRuntime",
    "FeynmanCallbacks",
    "build_feynman_runtime",
]
