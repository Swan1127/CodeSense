"""Event-backed memory for the Stage 3 dual-agent runtime.

The core store only depends on the small ``EventStore`` protocol.  This
keeps state reduction usable from tests and workers without requiring a
Flask application context.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any, Dict, List, Mapping, Optional, Protocol

from .contracts import (
    AgentResult,
    AgentRole,
    AgentState,
    FeynmanState,
    ForumEnvelope,
    GoalStatus,
    Stage3MessageKind,
    Stage3Target,
    ToolResult,
    UIAction,
)


_MAX_MESSAGES = 10
_COMPLETED_RESULT_EVENTS = frozenset({
    "agent_message", "tool_result", "agent_result", "state_snapshot",
})
_REPLAYABLE_STATE_FIELDS = frozenset({
    "phase", "learning_evidence", "code_review_status", "status",
})
_STUDENT_SAFE_ARTIFACT_FIELDS = frozenset({"public_hint"})
_ADVANCEMENT_RESULT_FIELDS = frozenset({
    "success",
    "agent",
    "ui_action",
    "ready_for_code",
    "state",
    "error_code",
})


@dataclass
class EventRecord:
    session_id: int
    stage: int
    event_type: str
    role: str
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_id: Optional[str] = None

    @classmethod
    def from_log(cls, log: Any) -> "EventRecord":
        try:
            metadata = log.get_metadata()
        except (AttributeError, TypeError, ValueError):
            metadata = _parse_metadata(getattr(log, "metadata_json", None))
        if not isinstance(metadata, dict):
            metadata = {}
        return cls(
            session_id=int(log.session_id),
            stage=int(log.stage),
            event_type=str(log.event_type or ""),
            role=str(log.role or ""),
            content=str(log.content or ""),
            metadata=metadata,
            event_id=str(log.id) if getattr(log, "id", None) is not None else None,
        )


class EventStore(Protocol):
    def list_events(self, session_id: int, stage: int = 3) -> List[EventRecord]:
        raise NotImplementedError

    def append(self, event: EventRecord) -> EventRecord:
        raise NotImplementedError


class SqlAlchemyEventStore:
    """Persist stage events in short SQLAlchemy transactions."""

    def __init__(self, model_cls: Any = None, db_session: Any = None) -> None:
        if model_cls is None or db_session is None:
            from models import ThinkingStageLog, db

            model_cls = model_cls or ThinkingStageLog
            db_session = db_session or db.session
        self.model_cls = model_cls
        self.db_session = db_session

    def list_events(self, session_id: int, stage: int = 3) -> List[EventRecord]:
        logs = self.model_cls.query.filter_by(
            session_id=session_id,
            stage=stage,
        ).order_by(self.model_cls.created_at.asc(), self.model_cls.id.asc()).all()
        return [EventRecord.from_log(log) for log in logs]

    def append(self, event: EventRecord) -> EventRecord:
        return self.append_many([event])[0]

    def append_many(self, events: List[EventRecord]) -> List[EventRecord]:
        logs = [self.model_cls(
            session_id=event.session_id,
            stage=event.stage,
            event_type=event.event_type,
            role=event.role,
            content=event.content,
            metadata_json=json.dumps(event.metadata, ensure_ascii=False),
        ) for event in events]
        try:
            self.db_session.add_all(logs)
            self.db_session.commit()
        except Exception:
            self.db_session.rollback()
            raise
        return [EventRecord.from_log(log) for log in logs]


@dataclass
class MemorySnapshot:
    state: FeynmanState
    agent_states: Dict[AgentRole, AgentState] = field(default_factory=dict)
    agent_messages: Dict[AgentRole, List[Dict[str, str]]] = field(
        default_factory=lambda: {role: [] for role in AgentRole}
    )
    student_messages: List[Dict[str, str]] = field(default_factory=list)
    visible_messages: Dict[AgentRole, List[Dict[str, str]]] = field(
        default_factory=lambda: {role: [] for role in AgentRole}
    )
    code_artifact_index: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    student_learning_evidence: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MemoryView:
    role: AgentRole
    state: FeynmanState
    agent_state: AgentState
    messages: List[Dict[str, str]]
    code_artifacts: List[Dict[str, Any]]

    def to_prompt_dict(self) -> Dict[str, Any]:
        state = asdict(self.state)
        if self.role is AgentRole.STUDENT_AGENT:
            state.pop("buggy_code_event_id", None)
        return {
            "state": state,
            "agent_state": asdict(self.agent_state),
            "messages": self.messages,
            "code_artifacts": self.code_artifacts,
        }


class MemoryStore:
    def __init__(self, event_store: EventStore) -> None:
        self.event_store = event_store

    def load(self, session_id: int) -> MemorySnapshot:
        snapshot = MemorySnapshot(state=FeynmanState(session_id=session_id))
        for record in self.event_store.list_events(session_id, stage=3):
            if record.event_type == "state_snapshot":
                raw_state = record.metadata.get("state")
                if isinstance(raw_state, Mapping):
                    snapshot.state = _feynman_state(raw_state, session_id)
                    snapshot.agent_states = _agent_states(record.metadata.get("agent_states"))
                    snapshot.student_learning_evidence = _project_student_snapshot_learning_evidence(
                        snapshot.student_learning_evidence,
                        record,
                        snapshot.state.learning_evidence,
                    )
            elif record.event_type == "tool_result":
                _apply_replayable_state_patch(snapshot.state, record.metadata.get("state_patch"))
                snapshot.student_learning_evidence = _project_student_learning_evidence(
                    snapshot.student_learning_evidence,
                    record,
                    snapshot.state.learning_evidence,
                )
            elif record.event_type in {"agent_user_message", "chat"}:
                message = _message(record)
                snapshot.student_messages.append(message)
                for agent_role in AgentRole:
                    if _message_visible_to_role(record, agent_role):
                        snapshot.visible_messages[agent_role].append(message)
            elif record.event_type == "agent_message":
                role = _agent_role(record.role)
                if role is not None:
                    message = _message(record)
                    snapshot.agent_messages[role].append(message)
                    for agent_role in AgentRole:
                        if _message_visible_to_role(record, agent_role):
                            snapshot.visible_messages[agent_role].append(message)

            artifact = record.metadata.get("artifact")
            if isinstance(artifact, Mapping):
                key = str(record.metadata.get("artifact_id") or record.event_id or len(snapshot.code_artifact_index))
                snapshot.code_artifact_index[key] = {
                    "event_id": record.event_id,
                    "role": record.role,
                    "artifact": dict(artifact),
                }

        snapshot.student_messages = snapshot.student_messages[-_MAX_MESSAGES:]
        for role in AgentRole:
            snapshot.agent_messages[role] = snapshot.agent_messages[role][-_MAX_MESSAGES:]
            snapshot.visible_messages[role] = snapshot.visible_messages[role][-_MAX_MESSAGES:]
        return snapshot

    def forum_events(self, session_id: int) -> List[Dict[str, Any]]:
        projected: List[Dict[str, Any]] = []
        for record in self.event_store.list_events(session_id, stage=3):
            event = _forum_event(record)
            if event is not None:
                projected.append(event)
        return projected

    def view_for(self, snapshot: MemorySnapshot, role: AgentRole) -> MemoryView:
        agent_state = snapshot.agent_states.get(role, AgentState())
        messages = list(snapshot.visible_messages[role])
        artifacts = list(snapshot.code_artifact_index.values())
        state = snapshot.state
        if role is AgentRole.STUDENT_AGENT:
            artifacts = [_student_safe_artifact(item) for item in artifacts]
            state = replace(snapshot.state, learning_evidence=list(snapshot.student_learning_evidence))
        return MemoryView(
            role=role,
            state=state,
            agent_state=agent_state,
            messages=messages[-_MAX_MESSAGES:],
            code_artifacts=artifacts,
        )

    def append_event(
        self,
        session_id: int,
        event_type: str,
        role: str,
        content: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EventRecord:
        event = EventRecord(
            session_id=session_id,
            stage=3,
            event_type=event_type,
            role=role,
            content=content,
            metadata=dict(metadata or {}),
        )
        return self.event_store.append(event)

    def append_events(self, events: List[EventRecord]) -> List[EventRecord]:
        if not events:
            return []
        append_many = getattr(self.event_store, "append_many", None)
        if callable(append_many):
            return append_many(events)
        return [self.event_store.append(event) for event in events]

    def has_request_event(self, session_id: int, request_id: str, event_type: str) -> bool:
        return any(
            record.event_type == event_type and record.metadata.get("request_id") == request_id
            for record in self.event_store.list_events(session_id, stage=3)
        )

    def find_tool_result(
        self, session_id: int, request_id: str, call_id: str,
    ) -> Optional[ToolResult]:
        for record in reversed(self.event_store.list_events(session_id, stage=3)):
            if (
                record.event_type == "tool_result"
                and _matches_tool_call(record, request_id, call_id)
                and isinstance(record.metadata.get("ok"), bool)
            ):
                return _tool_result_from_event(record)
        return None

    def has_tool_call_claim(self, session_id: int, request_id: str, call_id: str) -> bool:
        return any(
            record.event_type == "tool_call"
            and record.metadata.get("claim") is True
            and _matches_tool_call(record, request_id, call_id)
            for record in self.event_store.list_events(session_id, stage=3)
        )

    def find_request_result(self, session_id: int, request_id: str) -> Optional[AgentResult]:
        for record in reversed(self.event_store.list_events(session_id, stage=3)):
            if record.metadata.get("request_id") != request_id or not _is_terminal_result_event(record):
                continue
            result = _result_from_event(record)
            if result is not None:
                return result
        return None


def _is_terminal_result_event(record: EventRecord) -> bool:
    if record.event_type not in _COMPLETED_RESULT_EVENTS:
        return False
    if record.event_type == "agent_message":
        return record.metadata.get("terminal") is not False
    if record.event_type == "tool_result":
        if _tool_result_failed(record):
            return True
        return (
            record.metadata.get("terminal") is True
            and not isinstance(record.metadata.get("tool_call"), Mapping)
        )
    if record.event_type == "state_snapshot":
        return (
            record.metadata.get("terminal") is not False
            and isinstance(record.metadata.get("agent_result"), Mapping)
        )
    return True


def _matches_tool_call(record: EventRecord, request_id: str, call_id: str) -> bool:
    raw_call = record.metadata.get("tool_call")
    return (
        record.metadata.get("request_id") == request_id
        and isinstance(raw_call, Mapping)
        and str(raw_call.get("id") or "") == call_id
    )


def _tool_result_from_event(record: EventRecord) -> ToolResult:
    metadata = record.metadata
    public_content = metadata.get("public_content")
    model_content = metadata.get("model_content")
    state_patch = metadata.get("state_patch")
    return ToolResult(
        ok=metadata.get("ok") is True,
        model_content=dict(model_content) if isinstance(model_content, Mapping) else {},
        public_content=dict(public_content) if isinstance(public_content, Mapping) else {},
        state_patch=dict(state_patch) if isinstance(state_patch, Mapping) else {},
        error_code=str(metadata["error_code"]) if metadata.get("error_code") else None,
        retryable=False,
    )


def _apply_replayable_state_patch(state: FeynmanState, patch: Any) -> None:
    if not isinstance(patch, Mapping):
        return
    for field_name, value in patch.items():
        if field_name in _REPLAYABLE_STATE_FIELDS:
            setattr(state, field_name, value)


def _parse_metadata(raw_metadata: Any) -> Dict[str, Any]:
    if isinstance(raw_metadata, Mapping):
        return dict(raw_metadata)
    if not isinstance(raw_metadata, str):
        return {}
    try:
        parsed = json.loads(raw_metadata)
    except (TypeError, ValueError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _feynman_state(raw_state: Any, session_id: int) -> FeynmanState:
    if not isinstance(raw_state, Mapping):
        return FeynmanState(session_id=session_id)
    allowed = {item.name for item in fields(FeynmanState)}
    values = {key: value for key, value in raw_state.items() if key in allowed}
    values["session_id"] = session_id
    try:
        return FeynmanState(**values)
    except (TypeError, ValueError):
        return FeynmanState(session_id=session_id)


def _agent_states(raw_states: Any) -> Dict[AgentRole, AgentState]:
    if not isinstance(raw_states, Mapping):
        return {}
    states: Dict[AgentRole, AgentState] = {}
    allowed = {item.name for item in fields(AgentState)}
    for raw_role, raw_state in raw_states.items():
        role = _agent_role(raw_role)
        if role is None or not isinstance(raw_state, Mapping):
            continue
        values = {key: value for key, value in raw_state.items() if key in allowed}
        if "goal_status" in values:
            try:
                values["goal_status"] = GoalStatus(values["goal_status"])
            except ValueError:
                values.pop("goal_status")
        try:
            states[role] = AgentState(**values)
        except TypeError:
            continue
    return states


def _agent_role(value: Any) -> Optional[AgentRole]:
    try:
        return AgentRole(value)
    except ValueError:
        return None


def _message(record: EventRecord) -> Dict[str, str]:
    return {"role": record.role, "content": record.content, "event_type": record.event_type}


def _message_visible_to_role(record: EventRecord, viewer_role: AgentRole) -> bool:
    target_role = _target_role(record)
    if record.event_type in {"agent_user_message", "chat"}:
        if target_role is None:
            return True
        return target_role == viewer_role.value
    if record.event_type == "agent_message":
        source_role = _source_role(record)
        if source_role == viewer_role.value:
            return True
        if target_role is None:
            return _agent_role(record.role) == viewer_role
        return target_role == viewer_role.value
    return False


def _project_student_learning_evidence(
    current: List[Dict[str, Any]],
    record: EventRecord,
    candidate: Any,
) -> List[Dict[str, Any]]:
    if "learning_evidence" not in record.metadata.get("state_patch", {}):
        return current
    if not _has_student_learning_evidence_provenance(record):
        return current
    return _normalized_learning_evidence(candidate)


def _project_student_snapshot_learning_evidence(
    current: List[Dict[str, Any]],
    record: EventRecord,
    candidate: Any,
) -> List[Dict[str, Any]]:
    if not _has_student_learning_evidence_provenance(record):
        return current
    return _normalized_learning_evidence(candidate)


def _forum_event(record: EventRecord) -> Optional[Dict[str, Any]]:
    message_kind = _message_kind(record)
    target_role = _target_role(record)
    if message_kind is None or target_role is None:
        return None
    visibility = _visibility(record)
    if visibility != "public":
        return None
    if record.event_type not in {"agent_user_message", "agent_message", "chat"}:
        return None
    return {
        "event_id": record.event_id,
        "event_type": record.event_type,
        "role": record.role,
        "source_role": _source_role(record),
        "target_role": target_role,
        "message_kind": message_kind,
        "visibility": visibility,
        "content": record.content,
        "request_id": _string_metadata(record, "request_id"),
        "reply_to_event_id": _string_metadata(record, "reply_to_event_id"),
        "parent_request_id": _string_metadata(record, "parent_request_id"),
    }


def _message_kind(record: EventRecord) -> Optional[str]:
    raw_value = record.metadata.get("message_kind")
    if raw_value is not None:
        try:
            return Stage3MessageKind(raw_value).value
        except ValueError:
            return None
    if record.event_type in {"agent_user_message", "chat"} and record.role == "student":
        return Stage3MessageKind.USER_MESSAGE.value
    if record.event_type == "agent_message":
        return Stage3MessageKind.AGENT_MESSAGE.value
    return None


def _target_role(record: EventRecord) -> Optional[str]:
    raw_value = record.metadata.get("target_role")
    if raw_value is not None:
        try:
            return Stage3Target(raw_value).value
        except ValueError:
            return None
    panel = record.metadata.get("panel")
    if panel in {AgentRole.TEACHER_AGENT.value, AgentRole.STUDENT_AGENT.value}:
        return str(panel)
    if record.event_type == "agent_message":
        return Stage3Target.USER.value
    return None


def _source_role(record: EventRecord) -> str:
    raw_value = record.metadata.get("source_role")
    if raw_value is not None:
        try:
            return Stage3Target(raw_value).value
        except ValueError:
            pass
    if record.role == "student":
        return Stage3Target.USER.value
    if record.role == "system":
        return Stage3Target.SYSTEM.value
    target = _target_role(record)
    if target in {Stage3Target.USER.value, Stage3Target.SYSTEM.value}:
        role = _agent_role(record.role)
        if role is not None:
            return role.value
    return record.role


def _visibility(record: EventRecord) -> str:
    raw_value = record.metadata.get("visibility")
    if isinstance(raw_value, str) and raw_value:
        return raw_value
    if _message_kind(record) is not None and _target_role(record) is not None:
        return ForumEnvelope.visibility
    return "private"


def _string_metadata(record: EventRecord, key: str) -> Optional[str]:
    value = record.metadata.get(key)
    return str(value) if value else None


def _normalized_learning_evidence(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            normalized.append(dict(item))
    return normalized


def _has_student_learning_evidence_provenance(record: EventRecord) -> bool:
    if _agent_role(record.role) is AgentRole.STUDENT_AGENT:
        return True
    raw_source = record.metadata.get("source_role")
    if raw_source == AgentRole.STUDENT_AGENT.value:
        return True
    raw_target = record.metadata.get("target_role")
    return raw_target == AgentRole.STUDENT_AGENT.value


def _student_safe_artifact(item: Dict[str, Any]) -> Dict[str, Any]:
    artifact = item.get("artifact")
    if not isinstance(artifact, Mapping):
        return {}
    return {
        key: artifact[key]
        for key in _STUDENT_SAFE_ARTIFACT_FIELDS
        if key in artifact
    }


def _result_from_event(record: EventRecord) -> Optional[AgentResult]:
    payload = record.metadata.get("agent_result") or record.metadata.get("result")
    if record.event_type == "tool_result" and _tool_result_failed(record):
        payload_map = payload if isinstance(payload, Mapping) else {}
        role = _agent_role(payload_map.get("agent") or record.metadata.get("agent") or record.role)
        if role is None:
            return None
        public_content = payload_map.get("public_content", record.metadata.get("public_content", {}))
        return _failed_result(
            role=role,
            response=str(payload_map.get("response", record.content)),
            public_content=public_content,
            error_code=payload_map.get("error_code") or record.metadata.get("error_code"),
        )
    if isinstance(payload, Mapping):
        return _agent_result_from_payload(payload, record)

    role = _agent_role(record.metadata.get("agent") or record.role)
    if role is None:
        return None
    public_content = record.metadata.get("public_content", {})
    if not isinstance(public_content, Mapping):
        public_content = {}
    return AgentResult(
        success=True,
        agent=role,
        response=record.content or str(public_content.get("response", public_content.get("message", ""))),
        ui_action=_ui_action(record.metadata.get("ui_action")),
        ready_for_code=(
            bool(record.metadata.get("ready_for_code", False))
            or _ui_action(record.metadata.get("ui_action")) is UIAction.SHOW_CODE_REVIEW
        ),
        state=dict(record.metadata.get("state", {})) if isinstance(record.metadata.get("state"), Mapping) else {},
        public_content=dict(public_content),
        error_code=record.metadata.get("error_code"),
    )


def _agent_result_from_payload(payload: Mapping[str, Any], record: EventRecord) -> Optional[AgentResult]:
    role = _agent_role(payload.get("agent") or record.role)
    if role is None:
        return None
    public_content = payload.get("public_content", {})
    if not isinstance(public_content, Mapping):
        public_content = {}
    success = bool(payload.get("success", True))
    if not success:
        return _failed_result(
            role=role,
            response=str(payload.get("response", record.content)),
            public_content=public_content,
            error_code=payload.get("error_code") or record.metadata.get("error_code"),
        )
    return AgentResult(
        success=True,
        agent=role,
        response=str(payload.get("response", record.content)),
        ui_action=_ui_action(payload.get("ui_action")),
        ready_for_code=bool(payload.get("ready_for_code", False)),
        state=dict(payload.get("state", {})) if isinstance(payload.get("state"), Mapping) else {},
        public_content=dict(public_content),
        error_code=payload.get("error_code"),
    )


def _tool_result_failed(record: EventRecord) -> bool:
    metadata = record.metadata
    return (
        metadata.get("ok") is False
        or metadata.get("success") is False
        or bool(metadata.get("error_code"))
    )


def _failed_result(
    role: AgentRole,
    response: str,
    public_content: Any,
    error_code: Any,
) -> AgentResult:
    safe_public_content = (
        {
            str(key): value
            for key, value in public_content.items()
            if str(key) not in _ADVANCEMENT_RESULT_FIELDS
        }
        if isinstance(public_content, Mapping)
        else {}
    )
    return AgentResult(
        success=False,
        agent=role,
        response=response,
        ui_action=UIAction.CONTINUE_CHAT,
        ready_for_code=False,
        state={},
        public_content=safe_public_content,
        error_code=str(error_code) if error_code else None,
    )


def _ui_action(value: Any) -> UIAction:
    try:
        return UIAction(value or UIAction.CONTINUE_CHAT)
    except ValueError:
        return UIAction.CONTINUE_CHAT
