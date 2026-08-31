import json
from dataclasses import dataclass, field
from datetime import datetime

from utils.agents.contracts import AgentDecision, AgentRole, Stage3Target, ToolCall, ToolResult, UIAction
from utils.agents.feynman import FeynmanCallbacks, build_feynman_runtime
from utils.agents.memory import EventRecord
from utils.agents.orchestrator import ForumTurnResult, Stage3Orchestrator


class FakeEventStore:
    def __init__(self):
        self.events = []

    def list_events(self, session_id, stage=3):
        return [event for event in self.events if event.session_id == session_id and event.stage == stage]

    def append(self, event):
        if event.event_id is None:
            event.event_id = str(len(self.events) + 1)
        self.events.append(event)
        return event

    def append_many(self, events):
        return [self.append(event) for event in events]


class SequencedModel:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = []
        self.last_error = None

    def decide(self, **kwargs):
        self.calls.append(kwargs)
        return self.decisions.pop(0)


@dataclass
class FakeAssignment:
    title: str = "循环练习"
    description: str = "解释循环边界并在理解后检查代码。"


@dataclass
class FakePreset:
    reference_code: str = "int main() { return 0; }"
    key_steps: list = field(default_factory=lambda: ["循环边界", "不变量"])
    difficulty_config: dict = field(default_factory=lambda: {
        "feynman_coverage": {
            "min_coverage": 0.8,
            "max_probes_per_concept": 2,
            "probe_dimensions": ["core", "edge_case", "application"],
        }
    })

    def get_key_steps(self):
        return list(self.key_steps)

    def get_difficulty_config(self):
        return dict(self.difficulty_config)


@dataclass
class FakeSession:
    id: int = 12
    stage1_description: str = "我会先读取输入。"
    stage2_completed: bool = True
    stage3_completed: bool = False
    status: str = "in_progress"
    completed_at: datetime | None = None
    stage3_teacher_rounds: int = 0
    stage3_student_rounds: int = 0


def make_runtime(*, decisions, buggy_code_generator=None):
    event_store = FakeEventStore()
    model = SequencedModel(decisions)
    runtime = build_feynman_runtime(
        FakeSession(),
        FakeAssignment(),
        FakePreset(),
        model=model,
        callbacks=FeynmanCallbacks(
            event_store=event_store,
            buggy_code_generator=buggy_code_generator,
            persist_session=lambda session: None,
        ),
    )
    return runtime, model, event_store


def _coverage_entry(
    concept,
    *,
    status="unseen",
    attempts=0,
    used_dimensions=None,
    attempt_event_ids=None,
    accepted_evidence_count=0,
    evidence_event_ids=None,
    last_evidence_event_id=None,
):
    return {
        "concept": concept,
        "status": status,
        "attempts": attempts,
        "used_dimensions": list(used_dimensions or []),
        "attempt_event_ids": list(attempt_event_ids or []),
        "accepted_evidence_count": accepted_evidence_count,
        "evidence_event_ids": list(evidence_event_ids or []),
        "last_evidence_event_id": last_evidence_event_id,
    }


def test_teacher_turn_keeps_public_answer_out_of_student_context_and_emits_one_sanitized_intervention():
    runtime, model, _ = make_runtime(
        decisions=[
            AgentDecision(tool_calls=[
                ToolCall("probe-1", "request_student_probe", {
                    "concept": "循环边界",
                    "dimension": "edge_case",
                    "goal": "检查用户能否解释边界情况",
                }),
                ToolCall("probe-2", "request_student_probe", {
                    "concept": "不变量",
                    "dimension": "core",
                    "goal": "这条信号不应进入公开结果",
                }),
            ]),
            AgentDecision(message="因为 `i <= n` 会多走一步，所以会访问到越界索引。"),
            AgentDecision(tool_calls=[ToolCall("ask-1", "ask_student_probe", {
                "question": "你能解释一下为什么最后一个合法索引是 n - 1 吗？",
            })]),
        ],
    )
    orchestrator = Stage3Orchestrator(runtime)

    result = orchestrator.handle_user_message(
        "老师，为什么这里会越界？",
        target_role=AgentRole.TEACHER_AGENT,
        request_id="teacher-1",
    )

    assert result.primary.success is True
    assert "i <= n" in result.primary.response
    assert "越界索引" in result.primary.response
    assert result.primary.internal_signals == {
        "student_probe": {
            "concept": "循环边界",
            "dimension": "edge_case",
            "goal": "检查用户能否解释边界情况",
        }
    }
    assert len(result.interventions) == 1
    assert result.interventions[0].response == "你能解释一下为什么最后一个合法索引是 n - 1 吗？"
    assert "我也懂了" not in result.interventions[0].response
    assert result.interventions[0].response.endswith("？")

    student_context = model.calls[-1]["context"]
    assert "因为 `i <= n` 会多走一步，所以会访问到越界索引。" not in student_context
    assert "老师，为什么这里会越界？" not in student_context
    assert '"trigger"' in student_context

    forum_events = runtime.memory.forum_events(runtime.session.id)
    user_event = next(item for item in forum_events if item["request_id"] == "teacher-1" and item["source_role"] == "user")
    teacher_event = next(item for item in forum_events if item["request_id"] == "teacher-1" and item["source_role"] == "teacher_agent")
    probe_event = next(item for item in forum_events if item["request_id"] == "teacher-1:student_probe")
    trigger_event = next(event for event in runtime.memory.event_store.events if event.event_type == "agent_trigger")

    assert user_event["target_role"] == "teacher_agent"
    assert teacher_event["reply_to_event_id"] == user_event["event_id"]
    assert teacher_event["parent_request_id"] == "teacher-1"
    assert probe_event["message_kind"] == "student_probe"
    assert probe_event["reply_to_event_id"] == teacher_event["event_id"]
    assert probe_event["parent_request_id"] == "teacher-1"
    assert trigger_event.metadata["trigger"] == {
        "concept": "循环边界",
        "dimension": "edge_case",
        "goal": "检查用户能否解释边界情况",
    }
    assert set(trigger_event.metadata["trigger"]) == {"concept", "dimension", "goal"}
    assert "reference_code" not in json.dumps(trigger_event.metadata, ensure_ascii=False)


def test_student_targeted_explanation_enters_student_context_with_server_side_provenance():
    runtime, model, _ = make_runtime(
        decisions=[
            AgentDecision(tool_calls=[ToolCall("probe-1", "request_student_probe", {
                "concept": "循环边界",
                "dimension": "core",
                "goal": "先检查用户能否解释边界条件",
            })]),
            AgentDecision(message="先看循环边界。"),
            AgentDecision(tool_calls=[ToolCall("ask-trigger", "ask_student_probe", {
                "question": "你先说说为什么最后一个合法索引是 n - 1？",
            })]),
            AgentDecision(tool_calls=[ToolCall("assess-1", "assess_teaching_progress", {
                "assessment": "covered",
                "evidence": "因为 i < n 会在碰到非法索引前停止，所以最后一个合法位置是 n - 1。",
            })]),
            AgentDecision(tool_calls=[ToolCall("ask-1", "ask_student_probe", {
                "question": "你再说说这个边界为什么不会漏掉最后一个元素？",
            })]),
        ],
    )
    orchestrator = Stage3Orchestrator(runtime)

    first = orchestrator.handle_user_message(
        "老师，我先问一下这个边界。",
        target_role=AgentRole.TEACHER_AGENT,
        request_id="teacher-1",
    )
    probe_event_id = next(
        item["event_id"]
        for item in runtime.memory.forum_events(runtime.session.id)
        if item["request_id"] == "teacher-1:student_probe"
    )
    second = orchestrator.handle_user_message(
        "因为 i < n 会在碰到非法索引前停止，所以最后一个合法位置是 n - 1。",
        target_role=Stage3Target.STUDENT_AGENT,
        request_id="student-1",
        reply_to_event_id=probe_event_id,
    )

    assert first.primary.response == "先看循环边界。"
    assert second.primary.success is True
    assert second.primary.response == "你再说说这个边界为什么不会漏掉最后一个元素？"

    student_context = model.calls[3]["context"]
    assert "因为 i < n 会在碰到非法索引前停止，所以最后一个合法位置是 n - 1。" in student_context
    assert "先看循环边界。" not in student_context

    forum_events = runtime.memory.forum_events(runtime.session.id)
    user_event = next(item for item in forum_events if item["request_id"] == "student-1" and item["source_role"] == "user")
    assert user_event["target_role"] == "student_agent"
    assert user_event["reply_to_event_id"] == probe_event_id
    assert user_event["parent_request_id"] == "teacher-1"
    student_reply_event = next(
        item
        for item in forum_events
        if item["request_id"] == "student-1"
        and item["source_role"] == "student_agent"
    )
    assert student_reply_event["reply_to_event_id"] == user_event["event_id"]
    assert student_reply_event["parent_request_id"] == "teacher-1"

    state = runtime.memory.load(runtime.session.id).state
    assert state.concept_coverage[0]["concept"] == "循环边界"
    assert state.concept_coverage[0]["last_evidence_event_id"] == "student-1"


def test_student_text_response_does_not_generate_code_before_coverage_is_ready():
    runtime, _, event_store = make_runtime(
        decisions=[
            AgentDecision(tool_calls=[ToolCall("assess-1", "assess_teaching_progress", {
                "assessment": "partial",
                "evidence": "我知道它会在数组范围内停下，但还不能完整说明原因。",
            })]),
            AgentDecision(message="再解释一下为什么最后一个合法索引不是 n。"),
        ],
        buggy_code_generator=lambda context: {
            "buggy_code": "int main() { return 1; }",
            "bugs": [{"line": 1, "description": "返回值错误", "correct_version": "return 0;"}],
            "message": "内部代码说明",
        },
    )
    orchestrator = Stage3Orchestrator(runtime)
    runtime.memory.append_event(
        runtime.session.id,
        "state_snapshot",
        "student_agent",
        metadata={"state": {
            "concept_coverage": [
                _coverage_entry("循环边界", status="unseen"),
                _coverage_entry("不变量", status="unseen"),
            ],
            "coverage_score": 0.0,
            "unresolved_concepts": ["循环边界", "不变量"],
            "ready_for_code": False,
            "pending_probe": {"concept": "循环边界", "dimension": "core"},
        }},
    )

    result = orchestrator.handle_user_message(
        "我只知道它会在范围内停下，但还说不完整。",
        target_role=AgentRole.STUDENT_AGENT,
        request_id="student-partial-1",
    )

    assert result.primary.success is True
    assert result.primary.ui_action is UIAction.CONTINUE_CHAT
    assert result.primary.ready_for_code is False
    assert result.primary.response == "再解释一下为什么最后一个合法索引不是 n。"
    assert result.interventions == []
    assert [event.event_type for event in event_store.events].count("buggy_attempt") == 0


def test_student_ready_state_auto_generates_buggy_attempt_from_same_request_flow():
    runtime, model, event_store = make_runtime(
        decisions=[
            AgentDecision(tool_calls=[ToolCall("assess-1", "assess_teaching_progress", {
                "assessment": "covered",
                "evidence": "每轮循环都先检查索引是否小于长度，所以到达 length 时就会停下，最后一个合法位置只能是 length - 1。",
            })]),
        ],
        buggy_code_generator=lambda context: {
            "buggy_code": "int main() { return 1; }",
            "bugs": [{"line": 1, "description": "返回值错误", "correct_version": "return 0;"}],
            "message": "不应公开这段内部说明。",
        },
    )
    orchestrator = Stage3Orchestrator(runtime)
    runtime.memory.append_event(
        runtime.session.id,
        "state_snapshot",
        "student_agent",
        metadata={"state": {
            "concept_coverage": [
                _coverage_entry(
                    "循环边界",
                    status="covered",
                    attempts=1,
                    used_dimensions=["core"],
                    attempt_event_ids=["evt-covered"],
                    accepted_evidence_count=1,
                    evidence_event_ids=["evt-covered"],
                    last_evidence_event_id="evt-covered",
                ),
                _coverage_entry("不变量", status="unseen"),
            ],
            "coverage_score": 0.5,
            "unresolved_concepts": ["不变量"],
            "ready_for_code": False,
            "pending_probe": {"concept": "不变量", "dimension": "core"},
        }},
    )

    result = orchestrator.handle_user_message(
        "每轮进入循环前都保证条件成立，等索引到达 length 时就停止，所以不会读到数组外面。",
        target_role=AgentRole.STUDENT_AGENT,
        request_id="student-ready-1",
    )

    assert result.primary.success is True
    assert result.primary.ui_action is UIAction.SHOW_CODE_REVIEW
    assert result.primary.ready_for_code is True
    assert result.primary.response == "我写了一版代码，请帮我检查。"
    assert result.primary.public_content["buggy_code"] == "int main() { return 1; }"
    assert result.interventions == []
    assert [event.event_type for event in event_store.events].count("buggy_attempt") == 1
    assert len(model.calls) == 1
    triggering_event = next(
        item
        for item in runtime.memory.forum_events(runtime.session.id)
        if item["request_id"] == "student-ready-1" and item["source_role"] == "user"
    )
    code_review_event = next(
        item
        for item in runtime.memory.forum_events(runtime.session.id)
        if item["request_id"] == "student-ready-1:generate_buggy_attempt"
        and item["source_role"] == "student_agent"
    )
    assert code_review_event["target_role"] == "user"
    assert code_review_event["reply_to_event_id"] == triggering_event["event_id"]
    assert code_review_event["parent_request_id"] == "student-ready-1"


def test_runtime_signal_boundary_discards_extra_private_signal_keys():
    runtime, _, _ = make_runtime(
        decisions=[
            AgentDecision(tool_calls=[ToolCall("probe-1", "request_student_probe", {
                "concept": "循环边界",
                "dimension": "core",
                "goal": "检查用户能否解释边界情况",
            })]),
            AgentDecision(message="请继续解释。"),
        ],
    )
    original_execute = runtime.tools.execute

    def leaky_execute(role, call, context):
        result = original_execute(role, call, context)
        if call.name != "request_student_probe" or not result.ok:
            return result
        return ToolResult(
            ok=result.ok,
            model_content=dict(result.model_content),
            public_content=dict(result.public_content),
            internal_content={
                **result.internal_content,
                "reference_code": "int secret() { return 1; }",
                "hidden_code": "return 1;",
                "tool_arguments": {"secret": True},
            },
            state_patch=dict(result.state_patch),
            memory_events=list(result.memory_events),
            error_code=result.error_code,
            signal_type=result.signal_type,
            retryable=result.retryable,
        )

    runtime.tools.execute = leaky_execute
    result = runtime.handle_chat(
        AgentRole.TEACHER_AGENT,
        "请继续。",
        request_id="signal-boundary-1",
    )

    assert result.internal_signals == {
        "student_probe": {
            "concept": "循环边界",
            "dimension": "core",
            "goal": "检查用户能否解释边界情况",
        }
    }
    dumped = json.dumps(result.internal_signals, ensure_ascii=False)
    assert "reference_code" not in dumped
    assert "hidden_code" not in dumped
    assert "tool_arguments" not in dumped


def test_forum_turn_result_public_dict_omits_internal_and_private_fields():
    result = ForumTurnResult(
        primary=build_feynman_runtime(
            FakeSession(),
            FakeAssignment(),
            FakePreset(),
            model=SequencedModel([AgentDecision(message="继续。")]),
            callbacks=FeynmanCallbacks(event_store=FakeEventStore(), persist_session=lambda session: None),
        ).handle_chat(
            AgentRole.TEACHER_AGENT,
            "请继续解释。",
            request_id="public-1",
        ),
    )
    result.primary.public_content.update({
        "tool_call": {"id": "secret-call", "arguments": {"hidden": True}},
        "trigger": {"concept": "不应公开"},
        "artifact": {"hidden_bug": "secret"},
        "decision": {"next": "private"},
    })

    public = result.to_public_dict()
    dumped = json.dumps(public, ensure_ascii=False)

    assert public["interventions"] == []
    assert "internal_signals" not in dumped
    assert "tool_call" not in dumped
    assert "trigger" not in dumped
    assert "artifact" not in dumped
    assert "decision" not in dumped
