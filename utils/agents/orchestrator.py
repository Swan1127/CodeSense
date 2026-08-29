from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from .contracts import AgentResult, AgentRole, Stage3MessageKind, Stage3Target

_PRIVATE_PUBLIC_KEYS = frozenset({
    "internal_signals",
    "trigger",
    "topic_signal",
    "tool_arguments",
    "tool_call",
    "tool_calls",
    "decision",
    "state_decision",
    "artifact",
    "artifacts",
})


@dataclass
class ForumTurnResult:
    primary: AgentResult
    interventions: List[AgentResult] = field(default_factory=list)

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "primary": _sanitize_public_payload(self.primary.to_public_dict()),
            "interventions": [
                _sanitize_public_payload(item.to_public_dict())
                for item in self.interventions
            ],
        }


class Stage3Orchestrator:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def handle_user_message(
        self,
        message: str,
        *,
        target_role: AgentRole | Stage3Target | str,
        request_id: str,
        reply_to_event_id: Optional[str] = None,
    ) -> ForumTurnResult:
        role = _normalize_target_role(target_role)
        parent_request_id = self._parent_request_id(reply_to_event_id)
        primary = self.runtime.handle_chat(
            role,
            message,
            request_id=request_id,
            event_metadata={
                "source_role": Stage3Target.USER.value,
                "target_role": role.value,
                "message_kind": Stage3MessageKind.USER_MESSAGE.value,
                "visibility": "public",
                "reply_to_event_id": reply_to_event_id,
                "parent_request_id": parent_request_id,
            },
        )
        interventions: List[AgentResult] = []
        if role is AgentRole.TEACHER_AGENT:
            trigger_request_id = f"{request_id}:student_probe"
            signal = _sanitize_student_probe(primary.internal_signals.get("student_probe"))
            if signal is not None:
                intervention = self.runtime.handle_trigger(
                    signal,
                    request_id=trigger_request_id,
                    event_metadata={
                        "reply_to_event_id": self._agent_event_id(request_id, AgentRole.TEACHER_AGENT),
                        "parent_request_id": request_id,
                    },
                )
                if intervention.success:
                    interventions.append(intervention)
            else:
                existing = self.runtime.memory.find_request_result(self.runtime.session.id, trigger_request_id)
                if existing is not None and existing.success:
                    interventions.append(existing)
        return ForumTurnResult(primary=primary, interventions=interventions[:1])

    def _parent_request_id(self, reply_to_event_id: Optional[str]) -> Optional[str]:
        if reply_to_event_id is None:
            return None
        for event in self.runtime.memory.forum_events(self.runtime.session.id):
            if str(event.get("event_id") or "") == str(reply_to_event_id):
                request_id = event.get("parent_request_id") or event.get("request_id")
                return str(request_id) if request_id else None
        raise ValueError("reply_to_event_id not found in current session")

    def _agent_event_id(self, request_id: str, role: AgentRole) -> Optional[str]:
        for event in reversed(self.runtime.memory.forum_events(self.runtime.session.id)):
            if event.get("request_id") != request_id:
                continue
            if event.get("source_role") == role.value and event.get("target_role") == Stage3Target.USER.value:
                event_id = event.get("event_id")
                return str(event_id) if event_id else None
        return None


def _normalize_target_role(value: AgentRole | Stage3Target | str) -> AgentRole:
    if isinstance(value, AgentRole):
        return value
    text = value.value if isinstance(value, Stage3Target) else str(value)
    try:
        return AgentRole(text)
    except ValueError as exc:
        raise ValueError(f"invalid target_role: {value!r}") from exc


def _sanitize_student_probe(value: Any) -> Optional[Dict[str, str]]:
    if not isinstance(value, Mapping):
        return None
    keys = ("concept", "dimension", "goal")
    cleaned = {
        key: str(value.get(key, "")).strip()
        for key in keys
    }
    if not all(cleaned.values()):
        return None
    return cleaned


def _sanitize_public_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_public_payload(item)
            for key, item in value.items()
            if str(key) not in _PRIVATE_PUBLIC_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_public_payload(item) for item in value]
    return value
