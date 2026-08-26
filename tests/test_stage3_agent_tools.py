import json

from utils.agents.contracts import AgentRole, FeynmanState, ToolCall
from utils.agents.memory import MemorySnapshot
from utils.agents.tools import ToolContext, build_feynman_tool_registry


def fake_tool_context(role, *, state=None):
    return ToolContext(
        session_id=12,
        request_id="request-1",
        role=role,
        memory=MemorySnapshot(state=state or FeynmanState(session_id=12)),
        key_concepts=["循环边界", "不变量"],
    )


def test_student_agent_cannot_call_evaluate_fix_as_teacher():
    registry = build_feynman_tool_registry(
        buggy_code_generator=lambda context: {},
        fix_evaluator=lambda context, fixed_code: {"correct": True},
    )

    result = registry.execute(
        role=AgentRole.TEACHER_AGENT,
        call=ToolCall("c1", "evaluate_fix", {"fixed_code": "answer"}),
        context=fake_tool_context(AgentRole.TEACHER_AGENT),
    )

    assert result.ok is False
    assert result.error_code == "TOOL_NOT_ALLOWED"


def test_buggy_attempt_keeps_hidden_bugs_out_of_model_content():
    registry = build_feynman_tool_registry(
        buggy_code_generator=lambda context: {
            "buggy_code": "code",
            "bugs": [{"description": "hidden"}],
            "message": "我写了一版。",
        },
        fix_evaluator=lambda context, fixed_code: {"correct": False},
    )

    result = registry.execute(
        role=AgentRole.STUDENT_AGENT,
        call=ToolCall("c1", "generate_buggy_attempt", {}),
        context=fake_tool_context(AgentRole.STUDENT_AGENT),
    )

    assert result.public_content["buggy_code"] == "code"
    assert "hidden" not in json.dumps(result.model_content, ensure_ascii=False)
    assert result.memory_events[0]["metadata"]["artifact"]["bugs"] == [{"description": "hidden"}]


def test_unknown_tool_returns_structured_error():
    result = build_feynman_tool_registry().execute(
        AgentRole.TEACHER_AGENT,
        ToolCall("c1", "does_not_exist", {}),
        fake_tool_context(AgentRole.TEACHER_AGENT),
    )

    assert result.ok is False
    assert result.error_code == "UNKNOWN_TOOL"


def test_schema_rejects_unknown_missing_and_oversized_arguments():
    registry = build_feynman_tool_registry()
    context = fake_tool_context(AgentRole.STUDENT_AGENT)

    for arguments in (
        {},
        {"fixed_code": "ok", "unexpected": True},
        {"fixed_code": "x" * 8001},
    ):
        result = registry.execute(
            AgentRole.STUDENT_AGENT,
            ToolCall("c1", "evaluate_fix", arguments),
            context,
        )
        assert result.ok is False
        assert result.error_code == "INVALID_TOOL_ARGUMENTS"


def test_side_effect_tool_reuses_cached_result_for_duplicate_call_id():
    calls = []
    registry = build_feynman_tool_registry(
        buggy_code_generator=lambda context: calls.append(context.request_id) or {
            "buggy_code": "code", "bugs": [], "message": "请看看。"
        },
    )
    context = fake_tool_context(AgentRole.STUDENT_AGENT)
    call = ToolCall("same-id", "generate_buggy_attempt", {})

    first = registry.execute(AgentRole.STUDENT_AGENT, call, context)
    second = registry.execute(AgentRole.STUDENT_AGENT, call, context)

    assert first.ok is True
    assert second == first
    assert calls == ["request-1"]


def test_callback_failures_are_sanitized():
    registry = build_feynman_tool_registry(
        buggy_code_generator=lambda context: (_ for _ in ()).throw(RuntimeError("secret generator error")),
        fix_evaluator=lambda context, fixed_code: (_ for _ in ()).throw(RuntimeError("secret evaluator error")),
    )

    generation = registry.execute(
        AgentRole.STUDENT_AGENT,
        ToolCall("generate", "generate_buggy_attempt", {}),
        fake_tool_context(AgentRole.STUDENT_AGENT),
    )
    evaluation = registry.execute(
        AgentRole.STUDENT_AGENT,
        ToolCall("evaluate", "evaluate_fix", {"fixed_code": "answer"}),
        fake_tool_context(AgentRole.STUDENT_AGENT),
    )

    assert (generation.ok, generation.error_code) == (False, "BUGGY_ATTEMPT_FAILED")
    assert (evaluation.ok, evaluation.error_code) == (False, "FIX_EVALUATION_FAILED")
    assert "secret" not in json.dumps(generation.model_content)
    assert "secret" not in json.dumps(evaluation.model_content)


def test_learning_evidence_and_completion_are_server_validated():
    registry = build_feynman_tool_registry()
    state = FeynmanState(session_id=12, phase="code_review", code_review_status="passed")
    context = fake_tool_context(AgentRole.TEACHER_AGENT, state=state)

    evidence = registry.execute(
        AgentRole.TEACHER_AGENT,
        ToolCall("evidence", "record_learning_evidence", {
            "concept": "循环边界", "evidence": "能够解释 i < n 的原因。",
        }),
        context,
    )
    context.memory.state.learning_evidence = evidence.state_patch["learning_evidence"]
    completion = registry.execute(
        AgentRole.TEACHER_AGENT,
        ToolCall("complete", "complete_goal", {}),
        context,
    )

    assert evidence.ok is True
    assert evidence.state_patch["learning_evidence"][-1]["concept"] == "循环边界"
    assert completion.ok is True
    assert completion.state_patch == {"status": "complete"}
