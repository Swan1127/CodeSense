from utils.agents.contracts import (
    AgentResult,
    FeynmanState,
    ForumEnvelope,
    Stage3MessageKind,
    Stage3Target,
)


def test_stage3_target_exposes_stable_public_values():
    assert {item.value for item in Stage3Target} >= {
        "teacher_agent",
        "student_agent",
        "user",
        "system",
    }


def test_stage3_message_kind_exposes_stable_public_values():
    assert {item.value for item in Stage3MessageKind} >= {
        "user_message",
        "agent_message",
        "student_probe",
        "agent_trigger",
    }


def test_forum_envelope_metadata_serializes_public_routing_fields():
    envelope = ForumEnvelope(
        request_id="req-1",
        source=Stage3Target.USER,
        target=Stage3Target.TEACHER_AGENT,
        content="请解释边界条件。",
        message_kind=Stage3MessageKind.USER_MESSAGE,
        reply_to_event_id="evt-1",
        parent_request_id="parent-1",
        visibility="public",
    )

    assert envelope.to_metadata() == {
        "request_id": "req-1",
        "source_role": "user",
        "target_role": "teacher_agent",
        "message_kind": "user_message",
        "reply_to_event_id": "evt-1",
        "parent_request_id": "parent-1",
        "visibility": "public",
    }


def test_feynman_state_defaults_cover_stage3_forum_fields():
    state = FeynmanState(session_id=12)

    assert state.concept_coverage == []
    assert state.coverage_score == 0.0
    assert state.unresolved_concepts == []
    assert state.ready_for_code is False
    assert state.pending_probe is None


def test_agent_result_to_public_dict_filters_internal_signals():
    result = AgentResult(
        success=True,
        agent=Stage3Target.STUDENT_AGENT,
        response="继续。",
        state={"phase": "student_dialogue"},
        public_content={"message": "visible"},
        internal_signals={"next_actor": "teacher_agent"},
    )

    public = result.to_public_dict()

    assert public["message"] == "visible"
    assert "internal_signals" not in public
