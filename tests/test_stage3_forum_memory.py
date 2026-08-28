from utils.agents.contracts import AgentRole, Stage3MessageKind
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
        if event.event_id is None:
            event.event_id = str(len(self.events) + 1)
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


def test_forum_events_project_only_public_timeline_messages():
    store = MemoryStore(FakeEventStore([
        event(
            "agent_user_message",
            role="student",
            content="老师，为什么这里会越界？",
            metadata={
                "request_id": "req-1",
                "source_role": "user",
                "target_role": "teacher_agent",
                "message_kind": "user_message",
                "visibility": "public",
            },
        ),
        event(
            "agent_message",
            role="teacher_agent",
            content="因为循环条件把上界也包含进去了。",
            metadata={
                "request_id": "req-1",
                "source_role": "teacher_agent",
                "target_role": "user",
                "message_kind": "agent_message",
                "visibility": "public",
            },
        ),
        event(
            "agent_user_message",
            role="student",
            content="我觉得应该改成 i < n。",
            metadata={
                "request_id": "req-2",
                "source_role": "user",
                "target_role": "student_agent",
                "message_kind": "user_message",
                "visibility": "public",
            },
        ),
        event(
            "agent_message",
            role="student_agent",
            content="你能解释一下为什么 i < n 不会漏掉最后一个元素吗？",
            metadata={
                "request_id": "req-2",
                "source_role": "student_agent",
                "target_role": "user",
                "message_kind": "student_probe",
                "visibility": "public",
            },
        ),
        event(
            "tool_call",
            role="teacher_agent",
            metadata={
                "request_id": "req-1",
                "tool_call": {"id": "call-1", "name": "inspect_learning_state", "arguments": {}},
            },
        ),
        event(
            "tool_result",
            role="teacher_agent",
            metadata={
                "request_id": "req-1",
                "ok": True,
                "public_content": {"message": "公开提示"},
                "artifact": {"standard_answer": "return 42;", "public_hint": "检查边界"},
            },
        ),
    ]))

    projected = store.forum_events(12)

    assert [(item["message_kind"], item["content"]) for item in projected] == [
        ("user_message", "老师，为什么这里会越界？"),
        ("agent_message", "因为循环条件把上界也包含进去了。"),
        ("user_message", "我觉得应该改成 i < n。"),
        ("student_probe", "你能解释一下为什么 i < n 不会漏掉最后一个元素吗？"),
    ]
    assert all(item["visibility"] == "public" for item in projected)
    assert all(item["event_type"] != "tool_call" for item in projected)
    assert all(item["event_type"] != "tool_result" for item in projected)
    assert all("standard_answer" not in str(item) for item in projected)


def test_student_view_only_includes_student_target_messages_and_student_agent_replies():
    store = MemoryStore(FakeEventStore([
        event(
            "agent_user_message",
            role="student",
            content="老师，这个条件为什么错了？",
            metadata={"target_role": "teacher_agent", "message_kind": "user_message"},
        ),
        event(
            "agent_message",
            role="teacher_agent",
            content="因为这样会多访问一次数组。",
            metadata={"target_role": "user", "message_kind": "agent_message"},
        ),
        event(
            "agent_user_message",
            role="student",
            content="我理解成 i < n 才能保证索引不越界。",
            metadata={"target_role": "student_agent", "message_kind": "user_message"},
        ),
        event(
            "agent_message",
            role="student_agent",
            content="再说说为什么最后一个合法索引不是 n。",
            metadata={"target_role": "user", "message_kind": "student_probe"},
        ),
    ]))

    view = store.view_for(store.load(12), AgentRole.STUDENT_AGENT)

    assert [message["content"] for message in view.messages] == [
        "我理解成 i < n 才能保证索引不越界。",
        "再说说为什么最后一个合法索引不是 n。",
    ]
    assert "因为这样会多访问一次数组。" not in str(view.to_prompt_dict())


def test_forum_events_infer_legacy_target_from_panel_metadata():
    store = MemoryStore(FakeEventStore([
        event(
            "chat",
            role="student",
            content="旧学生解释",
            metadata={"panel": "student_agent"},
        ),
        event(
            "chat",
            role="student",
            content="旧老师提问",
            metadata={"panel": "teacher_agent"},
        ),
    ]))

    projected = store.forum_events(12)

    assert [
        (item["content"], item["target_role"], item["message_kind"])
        for item in projected
    ] == [
        ("旧学生解释", "student_agent", "user_message"),
        ("旧老师提问", "teacher_agent", "user_message"),
    ]


def test_teacher_answer_does_not_become_student_agent_evidence():
    store = MemoryStore(FakeEventStore([
        event(
            "agent_user_message",
            role="student",
            content="我觉得终止条件应该更严格。",
            metadata={"target_role": "student_agent", "message_kind": "user_message"},
        ),
        event(
            "agent_message",
            role="teacher_agent",
            content="标准答案是把 <= 改成 <。",
            metadata={"target_role": "user", "message_kind": "agent_message"},
        ),
        event(
            "state_snapshot",
            role="student_agent",
            metadata={"target_role": "student_agent", "source_role": "student_agent", "state": {
                "learning_evidence": [{"concept": "循环边界", "evidence": "来自学生自己的解释"}],
            }},
        ),
    ]))

    view = store.view_for(store.load(12), AgentRole.STUDENT_AGENT)

    assert [message["content"] for message in view.messages] == ["我觉得终止条件应该更严格。"]
    assert "标准答案是把 <= 改成 <。" not in str(view.to_prompt_dict())
    assert view.state.learning_evidence == [{"concept": "循环边界", "evidence": "来自学生自己的解释"}]
    assert Stage3MessageKind.STUDENT_PROBE.value not in [message["content"] for message in view.messages]


def test_student_view_ignores_teacher_state_snapshot_learning_evidence():
    store = MemoryStore(FakeEventStore([
        event(
            "agent_user_message",
            role="student",
            content="我已经解释过为什么最后一个索引是 n - 1。",
            metadata={"target_role": "student_agent", "message_kind": "user_message"},
        ),
        event(
            "state_snapshot",
            role="teacher_agent",
            metadata={"state": {
                "learning_evidence": [{"concept": "循环边界", "evidence": "老师总结的证据"}],
            }},
        ),
    ]))

    snapshot = store.load(12)
    student_view = store.view_for(snapshot, AgentRole.STUDENT_AGENT)
    teacher_view = store.view_for(snapshot, AgentRole.TEACHER_AGENT)

    assert student_view.state.learning_evidence == []
    assert "老师总结的证据" not in str(student_view.to_prompt_dict())
    assert teacher_view.state.learning_evidence == [{"concept": "循环边界", "evidence": "老师总结的证据"}]


def test_student_view_ignores_teacher_tool_result_learning_evidence_patch():
    store = MemoryStore(FakeEventStore([
        event(
            "agent_user_message",
            role="student",
            content="我认为 i < n 才不会访问到 n 这个非法索引。",
            metadata={"target_role": "student_agent", "message_kind": "user_message"},
        ),
        event(
            "tool_result",
            role="teacher_agent",
            metadata={
                "request_id": "teacher-1",
                "target_role": "user",
                "state_patch": {
                    "learning_evidence": [{
                        "concept": "循环边界",
                        "evidence": "老师给出了正确答案",
                    }],
                },
            },
        ),
    ]))

    snapshot = store.load(12)
    student_view = store.view_for(snapshot, AgentRole.STUDENT_AGENT)
    teacher_view = store.view_for(snapshot, AgentRole.TEACHER_AGENT)

    assert student_view.state.learning_evidence == []
    assert "老师给出了正确答案" not in str(student_view.to_prompt_dict())
    assert teacher_view.state.learning_evidence == [{
        "concept": "循环边界",
        "evidence": "老师给出了正确答案",
    }]


def test_legacy_chat_events_recover_in_view_for_and_forum_events():
    store = MemoryStore(FakeEventStore([
        event(
            "chat",
            role="student",
            content="旧学生解释：i < n 才不会越界。",
            metadata={"panel": "student_agent"},
        ),
        event(
            "chat",
            role="student",
            content="旧老师提问：为什么不是 i <= n？",
            metadata={"panel": "teacher_agent"},
        ),
    ]))

    snapshot = store.load(12)
    student_view = store.view_for(snapshot, AgentRole.STUDENT_AGENT)
    teacher_view = store.view_for(snapshot, AgentRole.TEACHER_AGENT)
    projected = store.forum_events(12)

    assert [message["content"] for message in student_view.messages] == [
        "旧学生解释：i < n 才不会越界。",
    ]
    assert [message["content"] for message in teacher_view.messages] == [
        "旧老师提问：为什么不是 i <= n？",
    ]
    assert [item["content"] for item in projected] == [
        "旧学生解释：i < n 才不会越界。",
        "旧老师提问：为什么不是 i <= n？",
    ]
