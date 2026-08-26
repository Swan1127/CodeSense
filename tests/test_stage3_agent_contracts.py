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
from utils.agents.model import ModelError, StructuredDecisionModel, parse_json_decision


class FakeClient:
    def __init__(self, responses, *, available=True):
        self.responses = iter(responses)
        self.calls = []
        self.available = available

    def is_available(self):
        return self.available

    def chat(self, messages, temperature=0.7, max_tokens=2000):
        self.calls.append(messages)
        return next(self.responses)


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


def test_structured_model_accepts_fenced_json():
    model = StructuredDecisionModel(FakeClient([
        "```json\n{\"message\":\"请解释边界\"}\n```"
    ]))

    decision = model.decide(system_prompt="system", context="context", tool_specs=[])

    assert decision.message == "请解释边界"


def test_structured_model_repairs_invalid_json_once():
    client = FakeClient(["这不是 JSON", '{"message":"修复后"}'])
    model = StructuredDecisionModel(client)

    decision = model.decide(system_prompt="system", context="context", tool_specs=[])

    assert decision.message == "修复后"
    assert len(client.calls) == 2
    assert "只输出符合 schema 的 JSON" in client.calls[1][-1]["content"]


def test_structured_model_unavailable_client_returns_safe_fallback():
    model = StructuredDecisionModel(
        FakeClient([], available=False), fallback_message="请换一种方式说明你的想法。"
    )

    decision = model.decide(system_prompt="system", context="context", tool_specs=[])

    assert decision.message == "请换一种方式说明你的想法。"
    assert model.last_error == ModelError("CLIENT_UNAVAILABLE")


@pytest.mark.parametrize("response", [None, "", '{"ui_action":"unknown"}', '{"tool_calls":[{"id":"c1","name":"inspect","arguments":[]}]}'])
def test_structured_model_invalid_responses_fall_back_with_sanitized_error(response):
    secret = "raw-model-output-must-not-leak"
    model = StructuredDecisionModel(FakeClient([response, secret]))

    decision = model.decide(system_prompt="system", context="context", tool_specs=[])

    assert decision.message == "请继续说明你的思路。"
    assert model.last_error is not None
    assert model.last_error.code == "INVALID_DECISION"
    assert secret not in str(model.last_error)


def test_parse_json_decision_rejects_mixed_text_and_oversized_response():
    with pytest.raises(ModelError, match="INVALID_JSON"):
        parse_json_decision('{"message":"ok"}\n解释')

    with pytest.raises(ModelError, match="RESPONSE_TOO_LONG"):
        parse_json_decision("{" + '"message":"' + ("x" * 12001) + '"}')


def test_structured_model_appends_tool_results_as_json_context():
    client = FakeClient(['{"message":"继续"}'])
    model = StructuredDecisionModel(client)

    model.decide(
        system_prompt="system",
        context="context",
        tool_specs=[{"name": "inspect"}],
        tool_results=[{"ok": True, "model_content": {"focus": "循环边界"}}],
    )

    prompt = client.calls[0][-1]["content"]
    assert "[TOOL_RESULT]" in prompt
    assert '"focus": "循环边界"' in prompt
