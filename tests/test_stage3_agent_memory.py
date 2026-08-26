import json

from utils.agents.contracts import AgentRole
from utils.agents.memory import EventRecord, MemoryStore


class FakeEventStore:
    def __init__(self, events=()):
        self.events = list(events)

    def list_events(self, session_id, stage=3):
        return [
            item
            for item in self.events
            if item.session_id == session_id and item.stage == stage
        ]

    def append(self, event):
        self.events.append(event)
        return event


def event(event_type, role="system", content="", metadata=None, session_id=12, stage=3):
    return EventRecord(
        session_id=session_id,
        stage=stage,
        event_type=event_type,
        role=role,
        content=content,
        metadata=metadata or {},
    )


def test_memory_store_reduces_state_snapshot_and_agent_messages():
    store = MemoryStore(FakeEventStore([
        event("state_snapshot", metadata={
            "state": {"phase": "student_dialogue", "student_rounds": 2}
        }),
        event("agent_user_message", role="student", content="我解释了循环"),
        event("agent_message", role="student_agent", content="那边界条件呢？"),
    ]))

    snapshot = store.load(session_id=12)

    assert snapshot.state.phase == "student_dialogue"
    assert snapshot.state.student_rounds == 2
    assert snapshot.agent_messages[AgentRole.STUDENT_AGENT][-1]["content"] == "那边界条件呢？"


def test_student_memory_view_hides_bug_artifacts():
    store = MemoryStore(FakeEventStore([
        event("tool_result", role="student_agent", metadata={
            "artifact": {
                "buggy_code": "int x = 0;",
                "bugs": [{"description": "hidden"}],
            }
        })
    ]))

    view = store.view_for(store.load(12), AgentRole.STUDENT_AGENT)
    prompt = json.dumps(view.to_prompt_dict(), ensure_ascii=False)

    assert "buggy_code" not in prompt
    assert "hidden" not in prompt


def test_memory_store_limits_each_agent_to_ten_recent_messages():
    store = MemoryStore(FakeEventStore([
        event("agent_message", role="teacher_agent", content=str(index))
        for index in range(12)
    ]))

    snapshot = store.load(12)

    assert [message["content"] for message in snapshot.agent_messages[AgentRole.TEACHER_AGENT]] == [
        str(index) for index in range(2, 12)
    ]


def test_memory_view_keeps_visible_messages_in_event_order():
    store = MemoryStore(FakeEventStore([
        event("agent_user_message", role="student", content="第一句"),
        event("agent_message", role="student_agent", content="第二句"),
        event("agent_user_message", role="student", content="第三句"),
    ]))

    view = store.view_for(store.load(12), AgentRole.STUDENT_AGENT)

    assert [message["content"] for message in view.messages] == ["第一句", "第二句", "第三句"]


def test_student_memory_view_excludes_teacher_messages_and_solution_artifacts():
    store = MemoryStore(FakeEventStore([
        event("agent_user_message", role="student", content="我的想法"),
        event("agent_message", role="teacher_agent", content="教师内部提示"),
        event("agent_message", role="student_agent", content="你能再解释一下吗？"),
        event("tool_result", role="teacher_agent", metadata={
            "artifact": {
                "standard_answer": "return 42;",
                "correct_fix": "replace i < n",
                "public_hint": "检查循环条件",
            }
        }),
    ]))

    view = store.view_for(store.load(12), AgentRole.STUDENT_AGENT)
    prompt = json.dumps(view.to_prompt_dict(), ensure_ascii=False)

    assert "我的想法" in prompt
    assert "你能再解释一下吗？" in prompt
    assert "教师内部提示" not in prompt
    assert "return 42;" not in prompt
    assert "replace i < n" not in prompt
    assert "检查循环条件" in prompt


def test_find_request_result_reuses_completed_public_agent_message():
    store = MemoryStore(FakeEventStore([
        event(
            "agent_message",
            role="teacher_agent",
            content="请先说说循环不变量。",
            metadata={"request_id": "request-1", "ready_for_code": True},
        )
    ]))

    result = store.find_request_result(12, "request-1")

    assert result is not None
    assert result.agent is AgentRole.TEACHER_AGENT
    assert result.response == "请先说说循环不变量。"
    assert result.ready_for_code is True


def test_find_request_result_reuses_agent_result_snapshot():
    store = MemoryStore(FakeEventStore([
        event("state_snapshot", metadata={
            "request_id": "request-2",
            "agent_result": {
                "agent": "student_agent",
                "response": "我还不确定。",
                "success": True,
            },
        })
    ]))

    result = store.find_request_result(12, "request-2")

    assert result is not None
    assert result.agent is AgentRole.STUDENT_AGENT
    assert result.response == "我还不确定。"


def test_student_memory_view_removes_solution_artifact_key_variants():
    store = MemoryStore(FakeEventStore([
        event("tool_result", metadata={
            "artifact": {
                "standard_answers": ["return total;"],
                "hidden_bug_details": "off by one",
                "correct_fixes": ["use <="],
                "public_hint": "比较循环条件和数组长度",
            }
        })
    ]))

    prompt = json.dumps(
        store.view_for(store.load(12), AgentRole.STUDENT_AGENT).to_prompt_dict(),
        ensure_ascii=False,
    )

    assert "return total;" not in prompt
    assert "off by one" not in prompt
    assert "use <=" not in prompt
    assert "比较循环条件和数组长度" in prompt


def test_student_memory_view_projects_only_explicitly_safe_artifact_fields():
    store = MemoryStore(FakeEventStore([
        event("tool_result", metadata={
            "artifact": {
                "public_hint": "从循环条件开始检查。",
                "internal_notes": "标准答案使用 <=。",
                "expected_output": "42",
                "arbitrary_payload": {"correct_code": "return 42;"},
            }
        })
    ]))

    prompt = json.dumps(
        store.view_for(store.load(12), AgentRole.STUDENT_AGENT).to_prompt_dict(),
        ensure_ascii=False,
    )

    assert "从循环条件开始检查。" in prompt
    assert "internal_notes" not in prompt
    assert "标准答案使用" not in prompt
    assert "expected_output" not in prompt
    assert "42" not in prompt
    assert "arbitrary_payload" not in prompt


def test_failed_tool_result_deduplication_clears_learning_advancement():
    store = MemoryStore(FakeEventStore([
        event(
            "tool_result",
            role="student_agent",
            content="工具调用失败。",
            metadata={
                "request_id": "request-tool-failure",
                "ok": False,
                "error_code": "tool_timeout",
                "ready_for_code": True,
                "ui_action": "show_code_review",
                "state": {"phase": "code_review"},
            },
        )
    ]))

    result = store.find_request_result(12, "request-tool-failure")

    assert result is not None
    assert result.success is False
    assert result.error_code == "tool_timeout"
    assert result.ready_for_code is False
    assert result.ui_action.value == "continue_chat"
    assert result.state == {}


def test_empty_corrupt_and_legacy_events_degrade_safely():
    store = MemoryStore(FakeEventStore([
        event("state_snapshot", metadata={"state": "not-an-object"}),
        event("chat", role="student", content="旧消息"),
        event("write_code", role="student_agent", content="旧代码"),
        event("fix_code", role="teacher_agent", content="旧修复"),
    ]))

    snapshot = store.load(12)

    assert snapshot.state.phase == "student_dialogue"
    assert snapshot.agent_messages[AgentRole.STUDENT_AGENT] == []
    assert MemoryStore(FakeEventStore()).load(12).agent_messages[AgentRole.TEACHER_AGENT] == []


def test_corrupt_newer_state_snapshot_preserves_last_valid_state():
    store = MemoryStore(FakeEventStore([
        event("state_snapshot", metadata={"state": {"phase": "code_review", "teacher_rounds": 3}}),
        event("state_snapshot", metadata={"state": "corrupt"}),
    ]))

    snapshot = store.load(12)

    assert snapshot.state.phase == "code_review"
    assert snapshot.state.teacher_rounds == 3


def test_malformed_agent_state_enum_degrades_without_interrupting_load():
    store = MemoryStore(FakeEventStore([
        event("state_snapshot", metadata={
            "state": {"phase": "student_dialogue"},
            "agent_states": {"student_agent": {"goal_status": {"bad": "value"}}},
        }),
    ]))

    snapshot = store.load(12)

    assert snapshot.state.phase == "student_dialogue"
    assert snapshot.agent_states[AgentRole.STUDENT_AGENT].goal_status.value == "in_progress"
