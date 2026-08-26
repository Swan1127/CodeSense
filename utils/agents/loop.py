"""Bounded, server-authoritative execution loop for Stage 3 agents."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from .contracts import AgentDecision, AgentResult, AgentRole, AgentState, GoalStatus, ToolCall, ToolResult, UIAction
from .memory import MemorySnapshot, MemoryStore
from .model import DecisionModel, ModelError
from .tools import ToolContext, ToolRegistry


_SESSION_LOCKS: Dict[int, threading.RLock] = {}
_SESSION_LOCKS_GUARD = threading.Lock()
_READ_ONLY_TOOLS = frozenset({"inspect_learning_state", "recall_memory"})
_PUBLIC_STATE_FIELDS = frozenset({
    "goal", "phase", "teacher_rounds", "student_rounds", "learning_evidence",
    "misconceptions", "code_review_status", "status",
})


class AgentLoopError(Exception):
    """An expected bounded-loop failure represented by a public error code."""


@dataclass(frozen=True)
class AgentLoopConfig:
    max_model_steps: int = 4

    def __post_init__(self) -> None:
        if self.max_model_steps != 4:
            raise ValueError("max_model_steps must be exactly 4")


@dataclass(frozen=True)
class AgentLoopSpec:
    system_prompt: str
    assignment_title: str = ""
    key_concepts: List[str] = field(default_factory=list)
    reference_code: str = ""


class AgentLoop:
    def __init__(
        self,
        *,
        session_id: int,
        role: AgentRole,
        model: DecisionModel,
        tools: ToolRegistry,
        memory: MemoryStore,
        spec: AgentLoopSpec,
        config: Optional[AgentLoopConfig] = None,
    ) -> None:
        self.session_id = session_id
        self.role = role
        self.model = model
        self.tools = tools
        self.memory = memory
        self.spec = spec
        self.config = config or AgentLoopConfig()

    def handle_turn(
        self,
        user_message: str,
        *,
        request_id: str,
        input_kind: str = "chat",
    ) -> AgentResult:
        """Handle one idempotent user request without exposing private artifacts."""
        lock = _session_lock(self.session_id)
        with lock:
            existing = self.memory.find_request_result(self.session_id, request_id)
            if existing is not None:
                return existing

            self.memory.append_event(
                self.session_id, "agent_user_message", "student", content=user_message,
                metadata={"request_id": request_id, "input_kind": input_kind},
            )
            snapshot = self.memory.load(self.session_id)
            context = self._tool_context(snapshot, request_id)
            tool_results: List[Dict[str, Any]] = []

            for _ in range(self.config.max_model_steps):
                decision = self._decide(input_kind, tool_results, request_id)
                if isinstance(decision, AgentResult):
                    return decision
                self.memory.append_event(
                    self.session_id, "agent_decision", self.role.value, content=decision.message,
                    metadata={"request_id": request_id, "decision": decision.to_payload()},
                )
                if not decision.tool_calls:
                    return self._finish_public_response(decision, snapshot, request_id)

                for call in decision.tool_calls:
                    result = self._execute_tool(call, context, request_id)
                    if not result.ok:
                        return self._failure(result.error_code or "TOOL_EXECUTION_FAILED", request_id)
                    tool_results.append(_tool_result_for_model(call, result))
                    self._apply_state_patch(snapshot, result.state_patch)
                    if result.public_content.get("ui_action") == UIAction.SHOW_CODE_REVIEW.value:
                        return self._finish_code_review(result, snapshot, request_id)

            return self._failure("MAX_AGENT_STEPS", request_id)

    def _decide(
        self, input_kind: str, tool_results: List[Dict[str, Any]], request_id: str,
    ) -> AgentDecision | AgentResult:
        try:
            decision = self.model.decide(
                system_prompt=self.spec.system_prompt,
                context=self._build_context(input_kind=input_kind),
                tool_specs=self.tools.specs_for(self.role),
                tool_results=tool_results,
            )
        except ModelError as error:
            return self._failure(error.code, request_id=request_id)
        except Exception:
            return self._failure("MODEL_ERROR", request_id=request_id)
        error = getattr(self.model, "last_error", None)
        if isinstance(error, ModelError):
            return self._failure(error.code, request_id=request_id)
        if not isinstance(decision, AgentDecision):
            return self._failure("INVALID_DECISION", request_id=request_id)
        return decision

    def _build_context(self, *, input_kind: str) -> str:
        snapshot = self.memory.load(self.session_id)
        prompt = self.memory.view_for(snapshot, self.role).to_prompt_dict()
        prompt["input_kind"] = input_kind
        return json.dumps(prompt, ensure_ascii=False)

    def _tool_context(self, snapshot: MemorySnapshot, request_id: str) -> ToolContext:
        return ToolContext(
            session_id=self.session_id,
            request_id=request_id,
            role=self.role,
            memory=snapshot,
            assignment_title=self.spec.assignment_title,
            key_concepts=list(self.spec.key_concepts),
            reference_code=self.spec.reference_code,
        )

    def _execute_tool(self, call: ToolCall, context: ToolContext, request_id: str) -> ToolResult:
        result = self.tools.execute(self.role, call, context)
        self._persist_tool_result(call, result, request_id)
        if result.ok or not result.retryable or call.name not in _READ_ONLY_TOOLS:
            return result
        retry = self.tools.execute(self.role, call, context)
        self._persist_tool_result(call, retry, request_id)
        return retry

    def _persist_tool_result(self, call: ToolCall, result: ToolResult, request_id: str) -> None:
        metadata = {
            "request_id": request_id,
            "tool_call": call.to_payload(),
            "ok": result.ok,
            "error_code": result.error_code,
            "public_content": dict(result.public_content),
            "state_patch": dict(result.state_patch),
        }
        if not result.ok:
            metadata["agent_result"] = _result_payload(
                AgentResult(success=False, agent=self.role, error_code=result.error_code)
            )
        self.memory.append_event(
            self.session_id, "tool_call", self.role.value,
            metadata={"request_id": request_id, "tool_call": call.to_payload()},
        )
        self.memory.append_event(self.session_id, "tool_result", self.role.value, metadata=metadata)
        for event in result.memory_events:
            if not isinstance(event, Mapping) or not isinstance(event.get("event_type"), str):
                continue
            event_metadata = event.get("metadata")
            self.memory.append_event(
                self.session_id,
                event["event_type"],
                self.role.value,
                content=str(event.get("content", "")),
                metadata={
                    "request_id": request_id,
                    **(dict(event_metadata) if isinstance(event_metadata, Mapping) else {}),
                },
            )

    def _apply_state_patch(self, snapshot: MemorySnapshot, patch: Mapping[str, Any]) -> None:
        if not isinstance(patch, Mapping):
            return
        for name, value in patch.items():
            if hasattr(snapshot.state, name):
                setattr(snapshot.state, name, value)

    def _finish_public_response(
        self, decision: AgentDecision, snapshot: MemorySnapshot, request_id: str,
    ) -> AgentResult:
        state = snapshot.agent_states.setdefault(self.role, AgentState())
        state.turn_index += 1
        state.last_decision = decision.message
        state.goal_status = GoalStatus.COMPLETE if snapshot.state.status == "complete" else GoalStatus.IN_PROGRESS
        result = AgentResult(
            success=True, agent=self.role, response=decision.message,
            ui_action=UIAction.CONTINUE_CHAT,
            ready_for_code=False,
            state=self._public_state(snapshot),
        )
        self._persist_completion(result, snapshot, request_id)
        return result

    def _finish_code_review(
        self, tool_result: ToolResult, snapshot: MemorySnapshot, request_id: str,
    ) -> AgentResult:
        public_content = dict(tool_result.public_content)
        response = str(public_content.pop("message", ""))
        result = AgentResult(
            success=True, agent=self.role, response=response,
            ui_action=UIAction.SHOW_CODE_REVIEW, ready_for_code=True,
            state=self._public_state(snapshot), public_content=public_content,
        )
        self._persist_completion(result, snapshot, request_id)
        return result

    def _persist_completion(self, result: AgentResult, snapshot: MemorySnapshot, request_id: str) -> None:
        payload = _result_payload(result)
        self.memory.append_event(
            self.session_id, "agent_message", self.role.value, content=result.response,
            metadata={"request_id": request_id, "agent_result": payload, "ready_for_code": result.ready_for_code},
        )
        self.memory.append_event(
            self.session_id, "state_snapshot", self.role.value,
            metadata={
                "request_id": request_id,
                "state": asdict(snapshot.state),
                "agent_states": {role.value: asdict(state) for role, state in snapshot.agent_states.items()},
                "agent_result": payload,
            },
        )

    def _failure(self, error_code: str, request_id: Optional[str]) -> AgentResult:
        result = AgentResult(success=False, agent=self.role, error_code=error_code)
        if request_id is not None:
            self.memory.append_event(
                self.session_id, "agent_result", self.role.value,
                metadata={"request_id": request_id, "agent_result": _result_payload(result)},
            )
        return result

    @staticmethod
    def _public_state(snapshot: MemorySnapshot) -> Dict[str, Any]:
        state = asdict(snapshot.state)
        return {name: value for name, value in state.items() if name in _PUBLIC_STATE_FIELDS}


def _session_lock(session_id: int) -> threading.RLock:
    with _SESSION_LOCKS_GUARD:
        return _SESSION_LOCKS.setdefault(session_id, threading.RLock())


def _result_payload(result: AgentResult) -> Dict[str, Any]:
    return {
        "success": result.success,
        "agent": result.agent.value,
        "response": result.response,
        "ui_action": result.ui_action.value,
        "ready_for_code": result.ready_for_code,
        "state": dict(result.state),
        "public_content": dict(result.public_content),
        "error_code": result.error_code,
    }


def _tool_result_for_model(call: ToolCall, result: ToolResult) -> Dict[str, Any]:
    return {
        "tool_call_id": call.call_id,
        "name": call.name,
        "ok": result.ok,
        "content": dict(result.model_content),
    }
