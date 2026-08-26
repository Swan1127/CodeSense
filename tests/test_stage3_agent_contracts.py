import pytest

from utils.agents.contracts import (
    AgentDecision,
    AgentResult,
    AgentRole,
    GoalStatus,
    ToolCall,
    ToolResult,
    UIAction,
)


def test_agent_decision_parses_tool_call_and_defaults_message():
    decision = AgentDecision.from_payload({
        "tool_calls": [{
            "id": "call-1",
            "name": "inspect_learning_state",
            "arguments": {}
        }]
    })

    assert decision.message == ""
    assert decision.tool_calls[0].call_id == "call-1"
    assert decision.goal_status == GoalStatus.IN_PROGRESS
    assert decision.ui_action == UIAction.CONTINUE_CHAT


def test_agent_decision_rejects_malformed_tool_call():
    with pytest.raises(ValueError, match="tool call"):
        AgentDecision.from_payload({
            "tool_calls": [{"name": "inspect_learning_state"}]
        })


def test_agent_decision_rejects_non_object_payload():
    with pytest.raises(ValueError, match="decision payload"):
        AgentDecision.from_payload(None)


def test_agent_decision_rejects_invalid_enum_values():
    with pytest.raises(ValueError, match="goal_status"):
        AgentDecision.from_payload({
            "goal_status": "finished",
            "ui_action": "continue_chat",
        })


def test_agent_decision_preserves_long_message_and_serializes_enums():
    long_message = "讲解" * 3000
    decision = AgentDecision.from_payload({
        "message": long_message,
        "goal_status": "complete",
        "ui_action": "show_code_review",
        "tool_calls": [],
    })

    assert decision.message == long_message
    assert decision.goal_status == GoalStatus.COMPLETE
    assert decision.ui_action == UIAction.SHOW_CODE_REVIEW
    assert decision.to_payload() == {
        "message": long_message,
        "tool_calls": [],
        "goal_status": "complete",
        "ui_action": "show_code_review",
    }


def test_tool_call_rejects_non_object_payload_and_invalid_arguments():
    with pytest.raises(ValueError, match="tool call"):
        ToolCall.from_payload("not a mapping")

    with pytest.raises(ValueError, match="arguments"):
        ToolCall.from_payload({
            "id": "call-1",
            "name": "inspect_learning_state",
            "arguments": []
        })


def test_agent_result_to_public_dict_hides_internal_fields():
    result = AgentResult(
        success=True,
        agent=AgentRole.STUDENT_AGENT,
        response="继续解释",
        ui_action=UIAction.SHOW_CODE_REVIEW,
        ready_for_code=True,
        state={"phase": "code_review", "goal_status": "in_progress"},
        public_content={"public_message": "ok"},
        error_code="MODEL_TIMEOUT",
    )

    public = result.to_public_dict()

    assert public == {
        "success": True,
        "response": "继续解释",
        "agent": "student_agent",
        "ui_action": "show_code_review",
        "ready_for_code": True,
        "state": {"phase": "code_review", "goal_status": "in_progress"},
        "public_message": "ok",
        "error_code": "MODEL_TIMEOUT",
    }
    assert "public_content" not in public


def test_tool_result_separates_public_and_model_content():
    result = ToolResult(
        ok=False,
        model_content={"hidden": "detail"},
        public_content={"feedback": "visible"},
        error_code="TOOL_FAILED",
        retryable=True,
    )

    assert result.ok is False
    assert result.model_content == {"hidden": "detail"}
    assert result.public_content == {"feedback": "visible"}
    assert result.error_code == "TOOL_FAILED"
    assert result.retryable is True
