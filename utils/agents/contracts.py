from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional


class AgentRole(str, Enum):
    TEACHER_AGENT = "teacher_agent"
    STUDENT_AGENT = "student_agent"


class GoalStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    BLOCKED = "blocked"


class UIAction(str, Enum):
    CONTINUE_CHAT = "continue_chat"
    SHOW_CODE_REVIEW = "show_code_review"


def _coerce_enum(value: Any, enum_cls: type[Enum], field_name: str) -> Enum:
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {value!r}") from exc


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: Dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ToolCall":
        if not isinstance(payload, Mapping):
            raise ValueError("tool call must be an object")
        if not payload.get("id") or not payload.get("name") or "arguments" not in payload:
            raise ValueError("tool call requires id, name and arguments")
        arguments = payload["arguments"]
        if not isinstance(arguments, dict):
            raise ValueError("tool call arguments must be an object")
        return cls(
            call_id=str(payload["id"]),
            name=str(payload["name"]),
            arguments=dict(arguments),
        )

    def to_payload(self) -> Dict[str, Any]:
        return {
            "id": self.call_id,
            "name": self.name,
            "arguments": dict(self.arguments),
        }


@dataclass
class AgentDecision:
    message: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    goal_status: GoalStatus = GoalStatus.IN_PROGRESS
    ui_action: UIAction = UIAction.CONTINUE_CHAT

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "AgentDecision":
        if not isinstance(payload, Mapping):
            raise ValueError("decision payload must be an object")
        raw_tool_calls = payload.get("tool_calls", [])
        if not isinstance(raw_tool_calls, list):
            raise ValueError("tool_calls must be a list")
        tool_calls = [ToolCall.from_payload(item) for item in raw_tool_calls]
        return cls(
            message=str(payload.get("message", "")),
            tool_calls=tool_calls,
            goal_status=_coerce_enum(
                payload.get("goal_status", GoalStatus.IN_PROGRESS),
                GoalStatus,
                "goal_status",
            ),
            ui_action=_coerce_enum(
                payload.get("ui_action", UIAction.CONTINUE_CHAT),
                UIAction,
                "ui_action",
            ),
        )

    def to_payload(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "tool_calls": [tool_call.to_payload() for tool_call in self.tool_calls],
            "goal_status": self.goal_status.value,
            "ui_action": self.ui_action.value,
        }


@dataclass
class ToolResult:
    ok: bool
    model_content: Dict[str, Any] = field(default_factory=dict)
    public_content: Dict[str, Any] = field(default_factory=dict)
    state_patch: Dict[str, Any] = field(default_factory=dict)
    memory_events: List[Dict[str, Any]] = field(default_factory=list)
    error_code: Optional[str] = None
    retryable: bool = False


@dataclass
class FeynmanState:
    session_id: int = 0
    goal: str = "teach_and_repair"
    phase: str = "student_dialogue"
    teacher_rounds: int = 0
    student_rounds: int = 0
    learning_evidence: List[Dict[str, Any]] = field(default_factory=list)
    misconceptions: List[Dict[str, Any]] = field(default_factory=list)
    buggy_code_event_id: Optional[str] = None
    code_review_status: str = "pending"
    status: str = "in_progress"


@dataclass
class AgentState:
    agent_id: str = ""
    current_focus: str = ""
    turn_index: int = 0
    last_user_message: str = ""
    last_decision: str = ""
    goal_status: GoalStatus = GoalStatus.IN_PROGRESS


@dataclass
class AgentResult:
    success: bool
    agent: AgentRole
    response: str = ""
    ui_action: UIAction = UIAction.CONTINUE_CHAT
    ready_for_code: bool = False
    state: Dict[str, Any] = field(default_factory=dict)
    public_content: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None

    def to_public_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "response": self.response,
            "agent": self.agent.value,
            "ui_action": self.ui_action.value,
            "ready_for_code": self.ready_for_code,
            "state": self.state,
            **self.public_content,
        }
        if self.error_code:
            result["error_code"] = self.error_code
        return result
