from dataclasses import dataclass, field
from datetime import datetime

import pytest
from flask import Flask

from utils.agents.contracts import AgentDecision, AgentResult, AgentRole, GoalStatus, ToolCall, ToolResult, UIAction
from utils.agents.feynman import FeynmanCallbacks, build_feynman_runtime
from utils.agents.memory import EventRecord, FeynmanState, MemorySnapshot, MemoryStore
from utils.agents.model import ModelError
from utils.agents.loop import AgentLoop, AgentLoopConfig, AgentLoopSpec


@dataclass
class FakeMemory:
    snapshot: MemorySnapshot = field(
        default_factory=lambda: MemorySnapshot(state=FeynmanState(session_id=12))
    )
    events: list = field(default_factory=list)
    saved_results: dict = field(default_factory=dict)

    def find_request_result(self, session_id, request_id):
        return self.saved_results.get(request_id)

    def load(self, session_id):
        return self.snapshot

    def view_for(self, snapshot, role):
        return MemoryStore.view_for(self, snapshot, role)

    def append_event(self, session_id, event_type, role, content="", metadata=None):
        self.events.append((event_type, role, content, dict(metadata or {})))


class FakeDecisionModel:
    def __init__(self, decisions, *, last_error=None):
        self.decisions = list(decisions)
        self.last_error = last_error
        self.calls = []

    def decide(self, **kwargs):
        self.calls.append(kwargs)
        decision = self.decisions.pop(0)
        if isinstance(decision, Exception):
            raise decision
        return decision


class FakeRegistry:
    def __init__(self, results=None):
        self.results = dict(results or {})
        self.calls = []

    def specs_for(self, role):
        return [{"name": name} for name in self.results]

    def is_side_effect(self, name):
        return False

    def execute(self, role, call, context):
        self.calls.append((role, call.name))
        value = self.results.get(call.name, ToolResult(ok=False, error_code="UNKNOWN_TOOL"))
        if isinstance(value, list):
            return value.pop(0)
        return value


class FakeEventStore:
    def __init__(self):
        self.events = []
        self.batches = []

    def list_events(self, session_id, stage=3):
        return [event for event in self.events if event.session_id == session_id and event.stage == stage]

    def append(self, event):
        event.event_id = str(len(self.events) + 1)
        self.events.append(event)
        return event

    def append_many(self, events):
        self.batches.append([event.event_type for event in events])
        return [self.append(event) for event in events]


@dataclass
class FakeAssignment:
    title: str = "循环练习"
    description: str = "解释循环边界并修复错误代码"


@dataclass
class FakePreset:
    reference_code: str = "标准答案：return 0;"
    key_steps: list = field(default_factory=lambda: ["输入范围", "循环边界"])
    algorithm_summary: str = "标准答案派生摘要：循环从 i=0 开始。"

    def get_key_steps(self):
        return list(self.key_steps)

    def get_algorithm_summary(self):
        return self.algorithm_summary


@dataclass
class FakeSession:
    id: int = 12
    stage1_description: str = "我会先读入数据。"
    stage2_completed: bool = True
    stage3_completed: bool = False
    status: str = "in_progress"
    completed_at: datetime | None = None
    stage3_teacher_rounds: int = 0
    stage3_student_rounds: int = 0


def make_feynman_runtime(*, fake_model=None, buggy_code_generator=None, fix_evaluator=None):
    event_store = FakeEventStore()
    callbacks = FeynmanCallbacks(
        event_store=event_store,
        buggy_code_generator=buggy_code_generator,
        fix_evaluator=fix_evaluator,
        persist_session=lambda session: None,
    )
    runtime = build_feynman_runtime(
        FakeSession(),
        FakeAssignment(),
        FakePreset(),
        model=fake_model or FakeDecisionModel([]),
        callbacks=callbacks,
    )
    runtime.event_store = event_store
    return runtime


def mark_runtime_ready_for_fix(runtime):
    runtime.memory.append_event(
        runtime.session.id,
        "state_snapshot",
        "system",
        metadata={"state": {
            "phase": "code_review",
            "code_review_status": "pending",
            "learning_evidence": [{
                "concept": "循环边界",
                "evidence": "能够解释边界条件为什么能避免越界。",
            }],
        }},
    )


class ContextCheckingModel(FakeDecisionModel):
    def __init__(self, decisions, *, expected_phase=None):
        super().__init__(decisions)
        self.expected_phase = expected_phase

    def decide(self, **kwargs):
        if self.expected_phase is not None and self.calls:
            assert f'"phase": "{self.expected_phase}"' in kwargs["context"]
        return super().decide(**kwargs)


def make_loop(*, model, tools=None, memory=None):
    return AgentLoop(
        session_id=12,
        role=AgentRole.TEACHER_AGENT,
        model=model,
        tools=tools or FakeRegistry({"inspect_learning_state": ToolResult(ok=True)}),
        memory=memory or FakeMemory(),
        spec=AgentLoopSpec(system_prompt="teach safely"),
        config=AgentLoopConfig(),
    )


def test_agent_loop_sanitizes_code_before_public_response_and_persistence():
    memory = FakeMemory()
    result = AgentLoop(
        session_id=12,
        role=AgentRole.TEACHER_AGENT,
        model=FakeDecisionModel([AgentDecision(
            message="先看这一段：\n```cpp\nint main() { return 0; }\n```",
        )]),
        tools=FakeRegistry(),
        memory=memory,
        spec=AgentLoopSpec(system_prompt="teach safely", max_output_chars=1200),
    ).handle_turn("继续", request_id="sanitize-code")

    persisted = next(event for event in memory.events if event[0] == "agent_message")
    assert "int main" not in result.response
    assert "代码已被过滤" in result.response
    assert persisted[2] == result.response


def test_agent_loop_bounds_sanitized_response_before_persistence():
    memory = FakeMemory()
    result = AgentLoop(
        session_id=12,
        role=AgentRole.STUDENT_AGENT,
        model=FakeDecisionModel([AgentDecision(message="解释" * 100)]),
        tools=FakeRegistry(),
        memory=memory,
        spec=AgentLoopSpec(system_prompt="teach safely", max_output_chars=24),
    ).handle_turn("继续", request_id="bounded-output")

    persisted = next(event for event in memory.events if event[0] == "agent_message")
    assert len(result.response) == 24
    assert persisted[2] == result.response


def test_agent_loop_rejects_oversized_tool_batch_before_executing_any_call():
    tools = FakeRegistry({"inspect_learning_state": ToolResult(ok=True)})
    result = make_loop(
        model=FakeDecisionModel([AgentDecision(tool_calls=[
            ToolCall(f"batch-{index}", "inspect_learning_state", {})
            for index in range(5)
        ])]),
        tools=tools,
    ).handle_turn("继续", request_id="tool-batch-limit")

    assert (result.success, result.error_code) == (False, "TOOL_CALL_LIMIT")
    assert tools.calls == []


def test_agent_loop_rejects_request_tool_limit_before_executing_next_batch():
    tools = FakeRegistry({"inspect_learning_state": ToolResult(ok=True)})
    result = make_loop(
        model=FakeDecisionModel([
            AgentDecision(tool_calls=[
                ToolCall(f"first-{index}", "inspect_learning_state", {})
                for index in range(3)
            ]),
            AgentDecision(tool_calls=[
                ToolCall(f"second-{index}", "inspect_learning_state", {})
                for index in range(2)
            ]),
        ]),
        tools=tools,
    ).handle_turn("继续", request_id="tool-request-limit")

    assert (result.success, result.error_code) == (False, "TOOL_CALL_LIMIT")
    assert tools.calls == [
        (AgentRole.TEACHER_AGENT, "inspect_learning_state"),
    ] * 3


def test_agent_loop_executes_tool_then_uses_result():
    model = FakeDecisionModel([
        AgentDecision(tool_calls=[ToolCall("c1", "inspect_learning_state", {})]),
        AgentDecision(message="根据状态，我们先讨论循环边界。"),
    ])
    tools = FakeRegistry({"inspect_learning_state": ToolResult(
        ok=True,
        model_content={"focus": "循环边界"},
    )})
    loop = make_loop(model=model, tools=tools)

    result = loop.handle_turn("我不知道怎么判断结束", request_id="r1")

    assert result.response == "根据状态，我们先讨论循环边界。"
    assert tools.calls == [(AgentRole.TEACHER_AGENT, "inspect_learning_state")]
    assert model.calls[1]["tool_results"] == [{
        "tool_call_id": "c1", "name": "inspect_learning_state", "ok": True,
        "content": {"focus": "循环边界"},
    }]


def test_agent_loop_stops_after_four_model_decisions():
    model = FakeDecisionModel([
        AgentDecision(tool_calls=[ToolCall(str(i), "inspect_learning_state", {})])
        for i in range(5)
    ])

    result = make_loop(model=model).handle_turn("继续", request_id="r2")

    assert result.success is False
    assert result.error_code == "MAX_AGENT_STEPS"
    assert len(model.calls) == 4


def test_agent_loop_returns_direct_response_and_persists_public_snapshot():
    memory = FakeMemory()
    result = make_loop(model=FakeDecisionModel([AgentDecision(message="先看循环条件。")]), memory=memory).handle_turn(
        "怎么开始？", request_id="direct"
    )

    public = result.to_public_dict()
    assert public["response"] == "先看循环条件。"
    assert "buggy_code_event_id" not in public["state"]
    assert [event[0] for event in memory.events] == [
        "agent_user_message", "agent_decision", "agent_message", "state_snapshot"
    ]
    assert memory.events[-1][3]["agent_result"]["response"] == "先看循环条件。"


def test_agent_loop_reuses_request_result_before_model_call():
    existing = AgentResult(success=True, agent=AgentRole.TEACHER_AGENT, response="已处理。")
    memory = FakeMemory(saved_results={"same": existing})
    model = FakeDecisionModel([AgentDecision(message="不应调用")])

    assert make_loop(model=model, memory=memory).handle_turn("重复", request_id="same") is existing
    assert model.calls == []
    assert memory.events == []


def test_agent_loop_continues_after_persisted_intermediate_tool_result():
    event_store = FakeEventStore()
    event_store.append(EventRecord(
        session_id=12,
        stage=3,
        event_type="tool_result",
        role="teacher_agent",
        metadata={"request_id": "resume", "ok": True, "terminal": False},
    ))
    model = FakeDecisionModel([AgentDecision(message="继续完成本轮。")])

    result = make_loop(model=model, memory=MemoryStore(event_store)).handle_turn("重试", request_id="resume")

    assert result.response == "继续完成本轮。"
    assert len(model.calls) == 1


def test_agent_loop_persists_unknown_tool_failure_without_state_advancement():
    memory = FakeMemory()
    result = make_loop(
        model=FakeDecisionModel([AgentDecision(tool_calls=[ToolCall("missing", "nope", {})])]),
        memory=memory,
    ).handle_turn("继续", request_id="unknown")

    assert (result.success, result.error_code, result.state) == (False, "UNKNOWN_TOOL", {})
    tool_event = next(event for event in memory.events if event[0] == "tool_result")
    assert tool_event[3]["ok"] is False
    assert tool_event[3]["agent_result"]["error_code"] == "UNKNOWN_TOOL"


def test_agent_loop_retries_read_only_tool_error_once_then_continues():
    memory = FakeMemory()
    tools = FakeRegistry({"inspect_learning_state": [
        ToolResult(ok=False, error_code="TEMPORARY", retryable=True),
        ToolResult(ok=True, model_content={"focus": "边界"}),
    ]})
    result = make_loop(
        model=FakeDecisionModel([
            AgentDecision(tool_calls=[ToolCall("c1", "inspect_learning_state", {})]),
            AgentDecision(message="现在检查边界。"),
        ]),
        tools=tools,
        memory=memory,
    ).handle_turn("继续", request_id="retry")

    assert result.success is True
    assert tools.calls == [(AgentRole.TEACHER_AGENT, "inspect_learning_state")] * 2
    assert [event[0] for event in memory.events].count("tool_result") == 2


def test_agent_loop_returns_model_fallback_error_without_advancing_state():
    memory = FakeMemory()
    result = make_loop(
        model=FakeDecisionModel([AgentDecision(message="请重试。")], last_error=ModelError("INVALID_DECISION")),
        memory=memory,
    ).handle_turn("继续", request_id="invalid")

    assert (result.success, result.error_code, result.state) == (False, "INVALID_DECISION", {})
    assert "agent_message" not in [event[0] for event in memory.events]


def test_agent_loop_records_sanitized_agent_decision_error_event():
    memory = FakeMemory()
    result = make_loop(
        model=FakeDecisionModel([ModelError("INVALID_DECISION")]),
        memory=memory,
    ).handle_turn("继续", request_id="decision-error")

    assert (result.success, result.error_code) == (False, "INVALID_DECISION")
    error_event = next(event for event in memory.events if event[0] == "agent_decision_error")
    assert error_event[2] == ""
    assert error_event[3] == {
        "request_id": "decision-error",
        "role": "teacher_agent",
        "step": 0,
        "error_code": "INVALID_DECISION",
    }


def test_agent_loop_persists_internal_memory_events_but_never_returns_them():
    memory = FakeMemory()
    result = make_loop(
        model=FakeDecisionModel([
            AgentDecision(tool_calls=[ToolCall("c1", "inspect_learning_state", {})]),
            AgentDecision(message="已记录。"),
        ]),
        tools=FakeRegistry({"inspect_learning_state": ToolResult(
            ok=True,
            model_content={"safe": True},
            public_content={"hint": "公开提示"},
            memory_events=[{"event_type": "private_note", "content": "internal", "metadata": {"secret": "x"}}],
        )}),
        memory=memory,
    ).handle_turn("继续", request_id="events")

    assert result.public_content == {}
    assert any(event[0] == "private_note" and event[3]["secret"] == "x" for event in memory.events)


def test_agent_loop_persists_state_patch_in_tool_result_and_final_snapshot():
    memory = FakeMemory()
    make_loop(
        model=FakeDecisionModel([
            AgentDecision(tool_calls=[ToolCall("c1", "inspect_learning_state", {})]),
            AgentDecision(message="已更新。"),
        ]),
        tools=FakeRegistry({"inspect_learning_state": ToolResult(
            ok=True, state_patch={"phase": "code_review"},
        )}),
        memory=memory,
    ).handle_turn("继续", request_id="patch")

    tool_event = next(event for event in memory.events if event[0] == "tool_result")
    snapshot_event = next(event for event in memory.events if event[0] == "state_snapshot")
    assert tool_event[3]["state_patch"] == {"phase": "code_review"}
    assert snapshot_event[3]["state"]["phase"] == "code_review"


def test_agent_loop_does_not_complete_goal_from_model_claim_alone():
    memory = FakeMemory()
    result = make_loop(
        model=FakeDecisionModel([AgentDecision(message="完成。", goal_status=GoalStatus.COMPLETE)]),
        memory=memory,
    ).handle_turn("继续", request_id="model-goal")

    assert result.state["status"] == "in_progress"


def test_agent_loop_does_not_show_code_review_from_model_claim_alone():
    result = make_loop(
        model=FakeDecisionModel([AgentDecision(message="查看代码。", ui_action=UIAction.SHOW_CODE_REVIEW)]),
    ).handle_turn("继续", request_id="model-ui")

    assert result.ready_for_code is False
    assert result.ui_action.value == "continue_chat"


def test_agent_loop_rejects_sensitive_state_patch_without_persisting_it():
    memory = FakeMemory()
    result = make_loop(
        model=FakeDecisionModel([AgentDecision(tool_calls=[ToolCall("c1", "inspect_learning_state", {})])]),
        tools=FakeRegistry({"inspect_learning_state": ToolResult(
            ok=True, state_patch={"session_id": 999, "buggy_code_event_id": "secret"},
        )}),
        memory=memory,
    ).handle_turn("继续", request_id="invalid-patch")

    assert (result.success, result.error_code, result.state) == (False, "INVALID_STATE_PATCH", {})
    tool_event = next(event for event in memory.events if event[0] == "tool_result")
    assert tool_event[3]["state_patch"] == {}
    assert tool_event[3]["error_code"] == "INVALID_STATE_PATCH"
    assert not any(event[0] == "state_snapshot" for event in memory.events)


def test_agent_loop_rejects_status_patch_outside_complete_goal():
    result = make_loop(
        model=FakeDecisionModel([AgentDecision(tool_calls=[ToolCall("c1", "inspect_learning_state", {})])]),
        tools=FakeRegistry({"inspect_learning_state": ToolResult(ok=True, state_patch={"status": "complete"})}),
    ).handle_turn("继续", request_id="invalid-status")

    assert (result.success, result.error_code, result.state) == (False, "INVALID_STATE_PATCH", {})


def test_agent_loop_rejects_unhashable_scalar_state_patch_values_without_persisting_state():
    for field, expected_state in {
        "phase": "student_dialogue",
        "code_review_status": "pending",
    }.items():
        memory = FakeMemory()
        result = make_loop(
            model=FakeDecisionModel([AgentDecision(tool_calls=[ToolCall("c1", "inspect_learning_state", {})])]),
            tools=FakeRegistry({"inspect_learning_state": ToolResult(ok=True, state_patch={field: []})}),
            memory=memory,
        ).handle_turn("继续", request_id=f"invalid-{field}")

        assert (result.success, result.error_code, result.state) == (False, "INVALID_STATE_PATCH", {})
        assert getattr(memory.snapshot.state, field) == expected_state
        assert not any(event[0] == "state_snapshot" for event in memory.events)


def test_agent_loop_uses_request_local_patched_state_for_next_model_decision():
    memory = MemoryStore(FakeEventStore())
    model = ContextCheckingModel([
        AgentDecision(tool_calls=[ToolCall("c1", "inspect_learning_state", {})]),
        AgentDecision(message="现在进入代码检查。"),
    ], expected_phase="code_review")

    result = make_loop(
        model=model,
        tools=FakeRegistry({"inspect_learning_state": ToolResult(ok=True, state_patch={"phase": "code_review"})}),
        memory=memory,
    ).handle_turn("继续", request_id="continuity")

    assert result.success is True


def test_agent_loop_durably_persists_valid_patch_before_later_model_failure():
    memory = MemoryStore(FakeEventStore())
    result = make_loop(
        model=FakeDecisionModel([
            AgentDecision(tool_calls=[ToolCall("c1", "inspect_learning_state", {})]),
            ModelError("MODEL_FAILURE"),
        ]),
        tools=FakeRegistry({"inspect_learning_state": ToolResult(ok=True, state_patch={"phase": "code_review"})}),
        memory=memory,
    ).handle_turn("继续", request_id="durability")

    assert (result.success, result.error_code) == (False, "MODEL_FAILURE")
    assert memory.load(12).state.phase == "code_review"


def test_feynman_student_runtime_exposes_student_goal_but_not_reference_code():
    runtime = make_feynman_runtime(fake_model=FakeDecisionModel([
        AgentDecision(message="你能解释一下输入范围吗？")
    ]))

    runtime.handle_chat(
        AgentRole.STUDENT_AGENT,
        "我先读入数据",
        request_id="r-student-1",
    )

    context = runtime.model.calls[0]["context"]
    assert "teach_and_repair" in context
    assert "标准答案" not in context
    assert "标准答案派生摘要" not in context


def test_unique_successful_chat_updates_rounds_and_agent_state_once():
    model = FakeDecisionModel([AgentDecision(message="请继续解释循环边界。")])
    runtime = make_feynman_runtime(fake_model=model)

    first = runtime.handle_chat(
        AgentRole.TEACHER_AGENT,
        "循环在 i 等于 n 前停止。",
        request_id="teacher-round-1",
    )
    duplicate = runtime.handle_chat(
        AgentRole.TEACHER_AGENT,
        "这条重复内容不应覆盖状态。",
        request_id="teacher-round-1",
    )

    restored = runtime.memory.load(runtime.session.id)
    agent_state = restored.agent_states[AgentRole.TEACHER_AGENT]
    assert first.state["teacher_rounds"] == 1
    assert duplicate.state["teacher_rounds"] == 1
    assert runtime.session.stage3_teacher_rounds == 1
    assert runtime.session.stage3_student_rounds == 0
    assert agent_state.agent_id == "teacher_agent"
    assert agent_state.turn_index == 1
    assert agent_state.last_user_message == "循环在 i 等于 n 前停止。"
    assert agent_state.current_focus == "student_dialogue"
    assert model.calls and len(model.calls) == 1


def test_student_model_generation_reaches_code_review_and_survives_recovery():
    """A real Student tool decision must make the code-review transition itself."""
    hidden_fix = "return 0;"
    runtime = make_feynman_runtime(
        fake_model=FakeDecisionModel([
            AgentDecision(tool_calls=[ToolCall("generate-1", "generate_buggy_attempt", {})]),
        ]),
        buggy_code_generator=lambda context: {
            "buggy_code": "int main() { return 1; }",
            "bugs": [{
                "line": 1,
                "description": "返回值错误",
                "correct_version": hidden_fix,
            }],
            "message": "我不确定返回值对不对。",
        },
    )

    result = runtime.handle_chat(
        AgentRole.STUDENT_AGENT,
        "我已经解释了循环的停止条件。",
        request_id="student-generate-1",
    )

    assert result.success is True
    assert result.ui_action is UIAction.SHOW_CODE_REVIEW
    assert result.ready_for_code is True
    assert result.state["phase"] == "code_review"
    assert result.public_content["buggy_code"] == "int main() { return 1; }"
    assert hidden_fix not in str(result.to_public_dict())

    restored = runtime.memory.load(runtime.session.id)
    assert restored.state.phase == "code_review"
    assert len(restored.code_artifact_index) == 1
    assert hidden_fix not in str(
        runtime.memory.view_for(restored, AgentRole.STUDENT_AGENT).to_prompt_dict()
    )


def test_student_complete_goal_uses_the_same_server_readiness_gate_as_teacher():
    """The approved registry gives either role the same validated completion path."""
    runtime = make_feynman_runtime(fake_model=FakeDecisionModel([
        AgentDecision(tool_calls=[ToolCall("complete-1", "complete_goal", {})]),
    ]))
    runtime.memory.append_event(
        runtime.session.id,
        "state_snapshot",
        "system",
        metadata={
            "state": {
                "phase": "code_review",
                "code_review_status": "passed",
                "learning_evidence": [{
                    "concept": "循环边界",
                    "evidence": "能够说明 i < n 为什么能避免越界。",
                }],
            },
        },
    )

    result = runtime.handle_chat(
        AgentRole.STUDENT_AGENT,
        "我已经把循环边界讲清楚了。",
        request_id="student-complete-1",
    )

    assert result.success is True
    assert result.state["status"] == "complete"
    assert runtime.session.stage3_completed is True
    assert runtime.session.status == "completed"


def test_replayed_persisted_buggy_tool_result_does_not_execute_generator_twice():
    """A restart must replay the durable result rather than repeat a side effect."""
    generator_calls = []
    runtime = make_feynman_runtime(
        fake_model=FakeDecisionModel([
            AgentDecision(tool_calls=[ToolCall("generate-replay", "generate_buggy_attempt", {})]),
        ]),
        buggy_code_generator=lambda context: generator_calls.append(context.request_id) or {
            "buggy_code": "int main() { return 2; }",
            "bugs": [{"line": 1, "description": "不应再次生成", "correct_version": "return 0;"}],
            "message": "不应再次调用。",
        },
    )
    persisted_call = ToolCall("generate-replay", "generate_buggy_attempt", {})
    runtime.event_store.append(EventRecord(
        session_id=runtime.session.id,
        stage=3,
        event_type="tool_call",
        role="student_agent",
        metadata={
            "request_id": "replay-generate-1",
            "tool_call": persisted_call.to_payload(),
            "claim": True,
            "side_effect": True,
        },
    ))
    runtime.event_store.append(EventRecord(
        session_id=runtime.session.id,
        stage=3,
        event_type="tool_result",
        role="student_agent",
        metadata={
            "request_id": "replay-generate-1",
            "tool_call": persisted_call.to_payload(),
            "ok": True,
            "terminal": False,
            "model_content": {
                "buggy_code": "int main() { return 1; }",
                "message": "我写了一版代码，请帮我检查。",
            },
            "public_content": {
                "buggy_code": "int main() { return 1; }",
                "message": "我写了一版代码，请帮我检查。",
                "ui_action": "show_code_review",
            },
            "state_patch": {"phase": "code_review", "code_review_status": "pending"},
        },
    ))
    runtime.event_store.append(EventRecord(
        session_id=runtime.session.id,
        stage=3,
        event_type="buggy_attempt",
        role="student_agent",
        metadata={"request_id": "replay-generate-1", "artifact": {
            "buggy_code": "int main() { return 1; }",
            "bugs": [{"line": 1, "description": "返回值错误", "correct_version": "return 0;"}],
        }},
    ))

    result = runtime.handle_chat(
        AgentRole.STUDENT_AGENT,
        "我已经解释过边界条件。",
        request_id="replay-generate-1",
    )

    assert result.success is True
    assert result.ui_action is UIAction.SHOW_CODE_REVIEW
    assert result.state["phase"] == "code_review"
    assert generator_calls == []
    assert len([event for event in runtime.event_store.events if event.event_type == "buggy_attempt"]) == 1


def test_side_effect_tool_claim_is_persisted_before_callback_runs():
    observed_claims = []
    runtime = make_feynman_runtime(
        buggy_code_generator=lambda context: observed_claims.append(
            runtime.memory.has_tool_call_claim(
                context.session_id,
                context.request_id,
                "claim-before-callback",
            )
        ) or {
            "buggy_code": "int main() { return 1; }",
            "bugs": [{"description": "返回值错误", "correct_version": "return 0;"}],
            "message": "请检查返回值。",
        },
    )

    result = runtime._loop_for(
        AgentRole.STUDENT_AGENT,
        FakeDecisionModel([
            AgentDecision(tool_calls=[ToolCall(
                "claim-before-callback", "generate_buggy_attempt", {},
            )]),
        ]),
    ).handle_turn("请生成代码。", request_id="claim-before-callback-request")

    assert result.success is True
    assert observed_claims == [True]


def test_unfinished_side_effect_claim_is_refused_without_reexecution():
    generator_calls = []
    runtime = make_feynman_runtime(
        fake_model=FakeDecisionModel([
            AgentDecision(tool_calls=[ToolCall("unfinished-call", "generate_buggy_attempt", {})]),
        ]),
        buggy_code_generator=lambda context: generator_calls.append(context.request_id) or {},
    )
    runtime.event_store.append(EventRecord(
        session_id=runtime.session.id,
        stage=3,
        event_type="tool_call",
        role="student_agent",
        metadata={
            "request_id": "unfinished-request",
            "tool_call": ToolCall("unfinished-call", "generate_buggy_attempt", {}).to_payload(),
            "claim": True,
            "side_effect": True,
        },
    ))

    result = runtime.handle_chat(
        AgentRole.STUDENT_AGENT,
        "继续。",
        request_id="unfinished-request",
    )

    assert (result.success, result.error_code) == (False, "TOOL_CALL_UNFINISHED")
    assert generator_calls == []


def test_agent_loop_uses_configured_redis_lock_with_ttl():
    class FakeRedisLock:
        def __init__(self):
            self.acquired = 0
            self.released = 0

        def acquire(self, blocking=True):
            self.acquired += 1
            return True

        def release(self):
            self.released += 1

    class FakeRedis:
        def __init__(self):
            self.calls = []
            self.lock_instance = FakeRedisLock()

        def lock(self, name, *, timeout, blocking_timeout):
            self.calls.append((name, timeout, blocking_timeout))
            return self.lock_instance

    app = Flask(__name__)
    redis_client = FakeRedis()
    app.config["SESSION_REDIS"] = redis_client

    with app.app_context():
        result = make_loop(
            model=FakeDecisionModel([AgentDecision(message="继续检查边界。")]),
        ).handle_turn("继续", request_id="redis-lock")

    assert result.success is True
    assert redis_client.calls == [("stage3-agent-session:12", 120, 5)]
    assert (redis_client.lock_instance.acquired, redis_client.lock_instance.released) == (1, 1)


def test_terminal_agent_message_and_snapshot_are_persisted_in_one_batch():
    event_store = FakeEventStore()
    result = make_loop(
        model=FakeDecisionModel([AgentDecision(message="检查循环边界。")]),
        memory=MemoryStore(event_store),
    ).handle_turn("继续", request_id="terminal-batch")

    assert result.success is True
    assert ["agent_message", "state_snapshot"] in event_store.batches
    terminal_snapshot = next(
        event for event in event_store.events if event.event_type == "state_snapshot"
    )
    assert terminal_snapshot.metadata["terminal"] is True


def test_correct_evaluate_fix_is_terminal_without_second_model_step():
    model = FakeDecisionModel([
        AgentDecision(tool_calls=[ToolCall(
            "evaluate-1",
            "evaluate_fix",
            {"fixed_code": "print('fixed')"},
        )]),
    ])
    result = AgentLoop(
        session_id=12,
        role=AgentRole.STUDENT_AGENT,
        model=model,
        tools=FakeRegistry({
            "evaluate_fix": ToolResult(
                ok=True,
                public_content={"correct": True, "feedback": "修复正确。"},
                state_patch={"code_review_status": "passed"},
            ),
        }),
        memory=FakeMemory(),
        spec=AgentLoopSpec(system_prompt="teach safely"),
    ).handle_turn("请检查修复", request_id="request-evaluate-terminal")

    assert result.success is True
    assert result.public_content["correct"] is True
    assert result.response == "修复正确。"
    assert len(model.calls) == 1


def test_redis_lock_releases_and_preserves_body_exception():
    class RaisingMemory(FakeMemory):
        def find_request_result(self, session_id, request_id):
            raise RuntimeError("memory exploded")

    class FakeRedisLock:
        released = 0

        def acquire(self, blocking=True):
            return True

        def release(self):
            self.released += 1

    class FakeRedis:
        def __init__(self):
            self.lock_instance = FakeRedisLock()

        def lock(self, name, *, timeout, blocking_timeout):
            return self.lock_instance

    app = Flask(__name__)
    redis_client = FakeRedis()
    app.config["SESSION_REDIS"] = redis_client

    with app.app_context(), pytest.raises(RuntimeError, match="memory exploded"):
        make_loop(
            model=FakeDecisionModel([]),
            memory=RaisingMemory(),
        ).handle_turn("继续", request_id="redis-lock-error")

    assert redis_client.lock_instance.released == 1


def test_duplicate_successful_fix_reconciles_session_without_re_evaluation():
    evaluator_calls = []
    runtime = make_feynman_runtime(
        buggy_code_generator=lambda context: {
            "buggy_code": "int main() { return 1; }",
            "bugs": [{"description": "返回值错误", "correct_version": "return 0;"}],
            "message": "检查返回值。",
        },
        fix_evaluator=lambda context, fixed_code: evaluator_calls.append(fixed_code) or {
            "correct": True,
            "feedback": "修复正确",
        },
    )
    runtime.generate_buggy_attempt(request_id="reconcile-code")
    mark_runtime_ready_for_fix(runtime)
    first = runtime.evaluate_fix("int main() { return 0; }", request_id="reconcile-fix")
    runtime.session.stage3_completed = False
    runtime.session.status = "in_progress"
    runtime.session.completed_at = None

    duplicate = runtime.evaluate_fix("ignored duplicate", request_id="reconcile-fix")

    assert first.public_content["correct"] is True
    assert duplicate.public_content["correct"] is True
    assert evaluator_calls == ["int main() { return 0; }"]
    assert runtime.session.stage3_completed is True
    assert runtime.session.status == "completed"
    assert runtime.session.completed_at is not None


def test_feynman_runtime_keeps_hidden_bugs_out_of_student_context_and_public_code_result():
    runtime = make_feynman_runtime(
        fake_model=FakeDecisionModel([AgentDecision(message="继续解释循环条件。")]),
        buggy_code_generator=lambda context: {
            "buggy_code": "while (i <= n) { ++i; }",
            "bugs": [{"description": "隐藏 Bug：越界", "fix": "正确修复：i < n"}],
            "message": "请检查循环。",
        },
    )

    runtime.generate_buggy_attempt(request_id="r-code-1")
    runtime.handle_chat(AgentRole.STUDENT_AGENT, "我觉得边界是 i < n", request_id="r-student-2")

    code_result = runtime.generate_buggy_attempt(request_id="r-code-1")
    context = runtime.model.calls[0]["context"]
    data = code_result.to_public_dict()
    exposed = str(data)
    assert "隐藏 Bug" not in context
    assert "正确修复" not in context
    assert "隐藏 Bug" not in exposed
    assert "正确修复" not in exposed
    assert data["message"] == "我写了一版代码，请帮我检查。"
    artifact_event = next(event for event in runtime.event_store.events if event.event_type == "buggy_attempt")
    assert artifact_event.metadata["artifact"]["bugs"][0]["fix"] == "正确修复：i < n"


def test_feynman_failed_fix_does_not_complete_session():
    runtime = make_feynman_runtime(
        buggy_code_generator=lambda context: {
            "buggy_code": "while (i <= n) { ++i; }",
            "bugs": [{"description": "边界错误", "correct_version": "i < n"}],
            "message": "检查一下。",
        },
        fix_evaluator=lambda context, fixed_code: {"correct": False, "feedback": "边界仍有问题"},
    )
    runtime.generate_buggy_attempt(request_id="r-code-2")
    mark_runtime_ready_for_fix(runtime)

    result = runtime.evaluate_fix("still wrong", request_id="r-fix-0")

    assert result.public_content["correct"] is False
    assert runtime.session.stage3_completed is False
    assert runtime.session.status == "in_progress"
    assert not any(event.event_type == "stage_pass" for event in runtime.event_store.events)


def test_correct_fix_cannot_complete_without_learning_evidence():
    evaluator_calls = []
    runtime = make_feynman_runtime(
        buggy_code_generator=lambda context: {
            "buggy_code": "int main() { return 1; }",
            "bugs": [{"description": "返回值错误", "correct_version": "return 0;"}],
            "message": "检查返回值。",
        },
        fix_evaluator=lambda context, fixed_code: evaluator_calls.append(fixed_code) or {
            "correct": True,
            "feedback": "修复正确",
        },
    )
    runtime.generate_buggy_attempt(request_id="no-evidence-code")

    result = runtime.evaluate_fix(
        "int main() { return 0; }",
        request_id="no-evidence-fix",
    )

    assert (result.success, result.error_code) == (False, "FIX_NOT_READY")
    assert evaluator_calls == []
    assert runtime.session.stage3_completed is False
    assert runtime.session.status == "in_progress"


def test_feynman_successful_fix_marks_session_completed_only_after_evaluation():
    runtime = make_feynman_runtime(
        buggy_code_generator=lambda context: {
            "buggy_code": "while (i <= n) { ++i; }",
            "bugs": [{"description": "边界错误", "correct_version": "i < n"}],
            "message": "检查一下。",
        },
        fix_evaluator=lambda context, fixed_code: {
            "correct": True,
            "feedback": "修复正确",
        },
    )
    runtime.generate_buggy_attempt(request_id="r-code-3")
    mark_runtime_ready_for_fix(runtime)

    result = runtime.evaluate_fix("fixed code", request_id="r-fix-1")

    assert result.public_content["correct"] is True
    assert runtime.session.status == "completed"
    assert runtime.session.stage3_completed is True
    assert runtime.session.completed_at is not None
    assert any(event.event_type == "stage_pass" for event in runtime.event_store.events)
