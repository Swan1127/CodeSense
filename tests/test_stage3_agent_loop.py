from dataclasses import dataclass, field
from datetime import datetime

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

    def execute(self, role, call, context):
        self.calls.append((role, call.name))
        value = self.results.get(call.name, ToolResult(ok=False, error_code="UNKNOWN_TOOL"))
        if isinstance(value, list):
            return value.pop(0)
        return value


class FakeEventStore:
    def __init__(self):
        self.events = []

    def list_events(self, session_id, stage=3):
        return [event for event in self.events if event.session_id == session_id and event.stage == stage]

    def append(self, event):
        event.event_id = str(len(self.events) + 1)
        self.events.append(event)
        return event


@dataclass
class FakeAssignment:
    title: str = "循环练习"
    description: str = "解释循环边界并修复错误代码"


@dataclass
class FakePreset:
    reference_code: str = "标准答案：return 0;"
    key_steps: list = field(default_factory=lambda: ["输入范围", "循环边界"])
    algorithm_summary: str = "先确定循环的不变量。"

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


def test_student_runtime_exposes_student_goal_but_not_reference_code():
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
    exposed = str(code_result.to_public_dict())
    assert "隐藏 Bug" not in context
    assert "正确修复" not in context
    assert "隐藏 Bug" not in exposed
    assert "正确修复" not in exposed
    artifact_event = next(event for event in runtime.event_store.events if event.event_type == "buggy_attempt")
    assert artifact_event.metadata["artifact"]["bugs"][0]["fix"] == "正确修复：i < n"


def test_failed_fix_does_not_complete_session():
    runtime = make_feynman_runtime(
        buggy_code_generator=lambda context: {
            "buggy_code": "while (i <= n) { ++i; }", "bugs": [], "message": "检查一下。",
        },
        fix_evaluator=lambda context, fixed_code: {"correct": False, "feedback": "边界仍有问题"},
    )
    runtime.generate_buggy_attempt(request_id="r-code-2")

    result = runtime.evaluate_fix("still wrong", request_id="r-fix-0")

    assert result.public_content["correct"] is False
    assert runtime.session.stage3_completed is False
    assert runtime.session.status == "in_progress"
    assert not any(event.event_type == "stage_pass" for event in runtime.event_store.events)


def test_successful_fix_marks_session_completed_only_after_evaluation():
    runtime = make_feynman_runtime(
        buggy_code_generator=lambda context: {
            "buggy_code": "while (i <= n) { ++i; }", "bugs": [], "message": "检查一下。",
        },
        fix_evaluator=lambda context, fixed_code: {
            "correct": True,
            "feedback": "修复正确",
        },
    )
    runtime.generate_buggy_attempt(request_id="r-code-3")

    result = runtime.evaluate_fix("fixed code", request_id="r-fix-1")

    assert result.public_content["correct"] is True
    assert runtime.session.status == "completed"
    assert runtime.session.stage3_completed is True
    assert runtime.session.completed_at is not None
    assert any(event.event_type == "stage_pass" for event in runtime.event_store.events)
