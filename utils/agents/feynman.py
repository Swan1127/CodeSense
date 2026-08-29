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

from .contracts import (
    AgentDecision,
    AgentResult,
    AgentRole,
    Stage3MessageKind,
    Stage3Target,
    ToolCall,
    UIAction,
)
from .coverage import load_coverage_config
from .loop import (
    AgentLoop,
    AgentLoopSpec,
    _distributed_session_lock,
    _normalized_trigger,
    _session_lock,
)
from .memory import EventRecord, EventStore, MemorySnapshot, MemoryStore, SqlAlchemyEventStore
from .model import DecisionModel, StructuredDecisionModel
from .tools import (
    BuggyCodeGenerator,
    FixEvaluator,
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
        prompt = dict(self._context_builder(snapshot, input_kind))
        prompt["input_kind"] = input_kind
        prompt["target_role"] = self._active_target_role
        if input_kind == "intervention" and isinstance(self._active_trigger, Mapping):
            prompt["trigger"] = dict(self._active_trigger)
        return json.dumps(prompt, ensure_ascii=False)


class _ForumRoleContextLoop(_RoleContextLoop):
    """Role loop with metadata-aware persistence and ready-for-code escalation."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._active_event_metadata: Dict[str, Any] = {}
        self._active_user_event_id: Optional[str] = None

    def handle_turn(
        self,
        user_message: str,
        *,
        request_id: str,
        input_kind: str = "chat",
        event_metadata: Optional[Mapping[str, Any]] = None,
    ) -> AgentResult:
        lock = _session_lock(self.session_id)
        with lock:
            with _distributed_session_lock(self.session_id) as acquired:
                if not acquired:
                    return AgentResult(
                        success=False,
                        agent=self.role,
                        error_code="SESSION_LOCK_UNAVAILABLE",
                    )
                self._set_active_event_metadata(event_metadata)
                return self._handle_turn_locked(
                    user_message,
                    request_id,
                    input_kind,
                    target_role=self.role.value,
                    trigger=None,
                    skip_user_message=False,
                )

    def handle_trigger(
        self,
        trigger: Mapping[str, Any],
        *,
        request_id: str,
        event_metadata: Optional[Mapping[str, Any]] = None,
    ) -> AgentResult:
        lock = _session_lock(self.session_id)
        with lock:
            with _distributed_session_lock(self.session_id) as acquired:
                if not acquired:
                    return AgentResult(
                        success=False,
                        agent=self.role,
                        error_code="SESSION_LOCK_UNAVAILABLE",
                    )
                existing = self.memory.find_request_result(self.session_id, request_id)
                if existing is not None:
                    return existing
                normalized_trigger = _normalized_trigger(trigger)
                if normalized_trigger is None:
                    return self._failure("INVALID_AGENT_TRIGGER", request_id)
                self._set_active_event_metadata(event_metadata)
                self.memory.append_event(
                    self.session_id,
                    "agent_trigger",
                    "system",
                    content=normalized_trigger["goal"],
                    metadata={
                        "request_id": request_id,
                        "source_role": AgentRole.TEACHER_AGENT.value,
                        "target_role": self.role.value,
                        "message_kind": Stage3MessageKind.AGENT_TRIGGER.value,
                        "visibility": "private",
                        "trigger": dict(normalized_trigger),
                        **self._filtered_event_metadata(),
                    },
                )
                return self._handle_turn_locked(
                    "",
                    request_id,
                    "intervention",
                    target_role=self.role.value,
                    trigger=normalized_trigger,
                    skip_user_message=True,
                )

    def handle_tool_action(
        self,
        *,
        request_id: str,
        input_kind: str,
        event_metadata: Optional[Mapping[str, Any]] = None,
    ) -> AgentResult:
        lock = _session_lock(self.session_id)
        with lock:
            with _distributed_session_lock(self.session_id) as acquired:
                if not acquired:
                    return AgentResult(
                        success=False,
                        agent=self.role,
                        error_code="SESSION_LOCK_UNAVAILABLE",
                    )
                self._set_active_event_metadata(event_metadata)
                return self._handle_turn_locked(
                    "",
                    request_id,
                    input_kind,
                    target_role=self.role.value,
                    trigger=None,
                    skip_user_message=True,
                )

    def _handle_turn_locked(
        self,
        user_message: str,
        request_id: str,
        input_kind: str,
        *,
        target_role: str,
        trigger: Optional[Dict[str, Any]],
        skip_user_message: bool,
    ) -> AgentResult:
        existing = self.memory.find_request_result(self.session_id, request_id)
        if existing is not None:
            return existing

        self._active_user_event_id = None
        if not skip_user_message:
            user_event = self.memory.append_event(
                self.session_id,
                "agent_user_message",
                "student",
                content=user_message,
                metadata={
                    "request_id": request_id,
                    "input_kind": input_kind,
                    **self._filtered_event_metadata(),
                },
            )
            self._active_user_event_id = user_event.event_id
        snapshot = self.memory.load(self.session_id)
        self._active_trigger = dict(trigger) if isinstance(trigger, Mapping) else None
        self._active_target_role = target_role
        context = self._tool_context(snapshot, request_id, input_kind)
        tool_results: List[Dict[str, Any]] = []
        total_tool_calls = 0
        internal_signals: Dict[str, Any] = {}

        for step in range(self.config.max_model_steps):
            decision = self._decide(input_kind, tool_results, request_id, snapshot, step)
            if isinstance(decision, AgentResult):
                return decision
            safe_decision_message = self._sanitize_public_response(
                decision.message,
                self.spec.max_output_chars,
            )
            decision_payload = decision.to_payload()
            decision_payload["message"] = safe_decision_message
            self.memory.append_event(
                self.session_id,
                "agent_decision",
                self.role.value,
                content=safe_decision_message,
                metadata={
                    "request_id": request_id,
                    "step": step,
                    "decision": decision_payload,
                },
            )
            if not decision.tool_calls:
                if self._must_generate_code(snapshot, input_kind):
                    self._advance_successful_chat(
                        snapshot,
                        user_message,
                        decision.message,
                        input_kind,
                    )
                    self._persist_state_checkpoint(snapshot, request_id)
                    return AgentResult(
                        success=False,
                        agent=self.role,
                        error_code="READY_FOR_CODE_REQUIRED",
                    )
                self._advance_successful_chat(
                    snapshot,
                    user_message,
                    decision.message,
                    input_kind,
                )
                return self._finish_public_response(
                    decision,
                    snapshot,
                    request_id,
                    internal_signals,
                )
            batch_size = len(decision.tool_calls)
            if (
                batch_size > self.config.max_tool_calls_per_decision
                or total_tool_calls + batch_size > self.config.max_tool_calls_per_request
            ):
                return self._failure("TOOL_CALL_LIMIT", request_id)
            total_tool_calls += batch_size

            for call in decision.tool_calls:
                executions = self._execute_tool(call, context, request_id)
                for index, execution in enumerate(executions):
                    result = execution.result
                    terminal_failure = not result.ok and index == len(executions) - 1
                    if execution.persist:
                        if not result.ok:
                            self._persist_tool_result(call, result, request_id, terminal=terminal_failure)
                        if not result.ok:
                            if terminal_failure:
                                return self._failure(result.error_code or "TOOL_EXECUTION_FAILED", request_id)
                            continue
                    patch = self._validated_state_patch(call, result.state_patch)
                    if patch is None:
                        invalid = ToolResult(
                            ok=False,
                            error_code="INVALID_STATE_PATCH",
                            memory_events=list(result.memory_events),
                        )
                        if execution.persist:
                            self._persist_tool_result(call, invalid, request_id, terminal=True)
                        return self._failure("INVALID_STATE_PATCH", request_id)
                    self._apply_state_patch(snapshot, patch)
                    if (
                        input_kind != "intervention"
                        and not internal_signals
                        and isinstance(result.signal_type, str)
                        and result.signal_type
                        and isinstance(result.internal_content, Mapping)
                    ):
                        internal_signals[result.signal_type] = dict(result.internal_content)
                    terminal_kind = self._terminal_tool_kind(call, result)
                    terminal_success = terminal_kind is not None
                    if execution.persist:
                        self._persist_tool_result(call, result, request_id, patch=patch, terminal=terminal_success)
                    if patch and not terminal_success:
                        self._persist_state_checkpoint(snapshot, request_id)
                    tool_results.append(self._tool_result_for_model(call, result))
                    if terminal_kind == "code_review":
                        self._advance_successful_chat(
                            snapshot,
                            user_message,
                            call.name,
                            input_kind,
                        )
                        return self._finish_code_review(result, snapshot, request_id, internal_signals)
                    if terminal_kind == "complete_goal":
                        self._advance_successful_chat(
                            snapshot,
                            user_message,
                            call.name,
                            input_kind,
                        )
                        return self._finish_goal(result, snapshot, request_id, internal_signals)
                    if terminal_kind == "fix_passed":
                        self._advance_successful_chat(
                            snapshot,
                            user_message,
                            call.name,
                            input_kind,
                        )
                        return self._finish_fix(result, snapshot, request_id, internal_signals)
                    if terminal_kind == "student_probe":
                        return self._finish_probe(result, snapshot, request_id)

        return self._failure("MAX_AGENT_STEPS", request_id)

    def _persist_completion(
        self,
        result: AgentResult,
        snapshot: MemorySnapshot,
        request_id: str,
        *,
        message_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        merged_message_metadata = {
            **self._default_message_metadata(request_id),
            **dict(message_metadata or {}),
        }
        super()._persist_completion(
            result,
            snapshot,
            request_id,
            message_metadata=merged_message_metadata,
        )

    @staticmethod
    def _sanitize_public_response(value: Any, maximum: int) -> str:
        from .loop import _sanitize_public_response

        return _sanitize_public_response(value, maximum)

    @staticmethod
    def _tool_result_for_model(call: ToolCall, result: ToolResult) -> Dict[str, Any]:
        from .loop import _tool_result_for_model

        return _tool_result_for_model(call, result)

    @staticmethod
    def _terminal_tool_kind(call: ToolCall, result: ToolResult) -> Optional[str]:
        from .loop import _terminal_tool_kind

        return _terminal_tool_kind(call, result)

    def _must_generate_code(self, snapshot: MemorySnapshot, input_kind: str) -> bool:
        return (
            self.role is AgentRole.STUDENT_AGENT
            and input_kind == "chat"
            and snapshot.state.phase != "code_review"
            and bool(snapshot.state.ready_for_code)
        )

    def _set_active_event_metadata(self, event_metadata: Optional[Mapping[str, Any]]) -> None:
        self._active_event_metadata = dict(event_metadata or {})

    def _filtered_event_metadata(self) -> Dict[str, Any]:
        allowed = {
            "source_role",
            "target_role",
            "message_kind",
            "visibility",
            "reply_to_event_id",
            "parent_request_id",
        }
        return {
            key: value
            for key, value in self._active_event_metadata.items()
            if key in allowed and value is not None
        }

    def _default_message_metadata(self, request_id: str) -> Dict[str, Any]:
        reply_to_event_id = self._active_user_event_id or self._active_event_metadata.get("reply_to_event_id")
        parent_request_id = request_id if self._active_user_event_id else self._active_event_metadata.get("parent_request_id")
        return {
            "source_role": self.role.value,
            "target_role": Stage3Target.USER.value,
            "message_kind": Stage3MessageKind.AGENT_MESSAGE.value,
            "visibility": "public",
            "reply_to_event_id": reply_to_event_id,
            "parent_request_id": parent_request_id,
        }


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

    def handle_chat(
        self,
        role: AgentRole,
        message: str,
        *,
        request_id: str,
        event_metadata: Optional[Mapping[str, Any]] = None,
    ) -> AgentResult:
        if role not in self.specs:
            raise ValueError("unsupported agent role")
        result = self._loop_for(role, self.model).handle_turn(
            message,
            request_id=request_id,
            event_metadata=event_metadata,
        )
        if role is AgentRole.STUDENT_AGENT and result.error_code == "READY_FOR_CODE_REQUIRED":
            auto_request_id = f"{request_id}:generate_buggy_attempt"
            result = self.generate_buggy_attempt(
                request_id=auto_request_id,
                event_metadata={
                    "source_role": AgentRole.STUDENT_AGENT.value,
                    "target_role": Stage3Target.USER.value,
                    "message_kind": Stage3MessageKind.AGENT_MESSAGE.value,
                    "visibility": "public",
                    "parent_request_id": request_id,
                },
                enforce_ready=True,
            )
            if result.success:
                self._persist_request_alias(request_id, result)
        self._sync_compat_rounds(role, result)
        self._sync_completed_goal(role, result)
        return result

    def handle_trigger(
        self,
        trigger: Mapping[str, Any],
        *,
        request_id: str,
        event_metadata: Optional[Mapping[str, Any]] = None,
    ) -> AgentResult:
        result = self._loop_for(AgentRole.STUDENT_AGENT, self.model).handle_trigger(
            trigger,
            request_id=request_id,
            event_metadata=event_metadata,
        )
        self._sync_compat_rounds(AgentRole.STUDENT_AGENT, result)
        self._sync_completed_goal(AgentRole.STUDENT_AGENT, result)
        return result

    def generate_buggy_attempt(
        self,
        *,
        request_id: str,
        event_metadata: Optional[Mapping[str, Any]] = None,
        enforce_ready: bool = False,
    ) -> AgentResult:
        if enforce_ready and not self._ready_for_code():
            return AgentResult(
                success=False,
                agent=AgentRole.STUDENT_AGENT,
                error_code="CODE_REVIEW_NOT_READY",
            )
        result = self._run_forced_tool(
            "generate_buggy_attempt",
            {},
            request_id,
            event_metadata=event_metadata,
        )
        if not result.success:
            return result
        content = self._tool_public_content(request_id, "generate_buggy_attempt")
        buggy_code = content.get("buggy_code")
        if not isinstance(buggy_code, str):
            artifact = self._artifact_for(request_id)
            if artifact is None:
                return AgentResult(success=False, agent=AgentRole.STUDENT_AGENT, error_code="BUGGY_ATTEMPT_FAILED")
            buggy_code = artifact.get("buggy_code")
            if not isinstance(buggy_code, str):
                return AgentResult(success=False, agent=AgentRole.STUDENT_AGENT, error_code="BUGGY_ATTEMPT_FAILED")
        message = str(content.get("message", "我写了一版代码，请帮我检查。"))
        return AgentResult(
            success=True,
            agent=AgentRole.STUDENT_AGENT,
            response=message,
            ui_action=UIAction.SHOW_CODE_REVIEW,
            ready_for_code=True,
            state=result.state,
            public_content={"buggy_code": buggy_code, "message": message},
        )

    def evaluate_fix(self, fixed_code: str, *, request_id: str) -> AgentResult:
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
        if content["correct"]:
            self._complete_session(str(content.get("feedback", "")), request_id, source="validated_evaluation")
        return evaluation

    def _loop_for(self, role: AgentRole, model: DecisionModel) -> _ForumRoleContextLoop:
        spec = self.specs[role]
        return _ForumRoleContextLoop(
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
                coverage_config=self._coverage_config(),
                max_output_chars=spec.max_output_chars,
            ),
            context_builder=lambda snapshot, input_kind: self._context_for(role, snapshot, input_kind),
        )

    def _run_forced_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        request_id: str,
        *,
        event_metadata: Optional[Mapping[str, Any]] = None,
    ) -> AgentResult:
        return self._loop_for(
            AgentRole.STUDENT_AGENT,
            _ForcedToolModel(ToolCall(f"{request_id}:{name}", name, arguments)),
        ).handle_tool_action(request_id=request_id, input_kind=name, event_metadata=event_metadata)

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
            "user_explanations": [
                dict(message)
                for message in view.messages
                if message.get("role") == "student"
                and message.get("event_type") in {"agent_user_message", "chat"}
            ],
            "role_memory": {"agent_state": asdict(view.agent_state), "messages": list(view.messages)},
        }

    def _key_concepts(self) -> list[str]:
        getter = getattr(self.preset, "get_key_steps", None)
        raw = getter() if callable(getter) else getattr(self.preset, "key_steps", [])
        return [item.strip() for item in raw if isinstance(item, str) and item.strip()] if isinstance(raw, list) else []

    def _coverage_config(self):
        getter = getattr(self.preset, "get_difficulty_config", None)
        raw = getter() if callable(getter) else getattr(self.preset, "difficulty_config", {})
        try:
            return load_coverage_config(raw, self._key_concepts())
        except ValueError:
            return load_coverage_config({}, self._key_concepts())

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
        if result.success and result.state.get("status") == "complete":
            self._complete_session("学习目标已通过服务端检查。", request_id=None, source="complete_goal")

    def _sync_compat_rounds(self, role: AgentRole, result: AgentResult) -> None:
        if not result.success:
            return
        state_field = (
            "teacher_rounds"
            if role is AgentRole.TEACHER_AGENT
            else "student_rounds"
        )
        session_field = (
            "stage3_teacher_rounds"
            if role is AgentRole.TEACHER_AGENT
            else "stage3_student_rounds"
        )
        value = result.state.get(state_field)
        if type(value) is not int or value < 0:
            return
        if getattr(self.session, session_field, 0) != value:
            setattr(self.session, session_field, value)
            self.callbacks.save_session(self.session)

    def _complete_session(self, feedback: str, request_id: Optional[str], *, source: str) -> None:
        has_validated_pass = any(
            event.event_type == "stage_pass"
            and event.metadata.get("validated") is True
            for event in self._events()
        )
        if not has_validated_pass:
            self.memory.append_event(
                self.session.id,
                "stage_pass",
                "system",
                content=feedback,
                metadata={
                    "request_id": request_id,
                    "source": source,
                    "validated": True,
                },
            )
        self.session.stage3_completed = True
        self.session.status = "completed"
        if getattr(self.session, "completed_at", None) is None:
            self.session.completed_at = self.callbacks.now()
        self.callbacks.save_session(self.session)

    def _ready_for_code(self) -> bool:
        snapshot = self.memory.load(self.session.id)
        return bool(snapshot.state.ready_for_code) and snapshot.state.phase != "code_review"

    def _persist_request_alias(self, request_id: str, result: AgentResult) -> None:
        self.memory.append_event(
            self.session.id,
            "agent_result",
            result.agent.value,
            metadata={
                "request_id": request_id,
                "agent_result": {
                    "success": result.success,
                    "agent": result.agent.value,
                    "response": result.response,
                    "ui_action": result.ui_action.value,
                    "ready_for_code": result.ready_for_code,
                    "state": dict(result.state),
                    "public_content": dict(result.public_content),
                    "error_code": result.error_code,
                },
            },
        )


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
