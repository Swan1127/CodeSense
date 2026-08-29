import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from app import create_app
from config import TestingConfig as _TestingConfig
from models import (
    Assignment,
    AssignmentThinkingPreset,
    ThinkingSession,
    ThinkingStageLog,
    User,
    db,
)
from routes import thinking as thinking_routes
from utils.agents.contracts import AgentDecision, AgentResult, AgentRole, UIAction
from utils.agents.feynman import FeynmanCallbacks, build_feynman_runtime


class FakeRuntime:
    def __init__(self, *, chat_result=None, fix_result=None, session_id=1):
        self.chat_result = chat_result
        self.fix_result = fix_result
        self.chat_messages = []
        self.fixed_codes = []
        self.session = SimpleNamespace(id=session_id)
        self.memory = SimpleNamespace(
            forum_events=lambda session_id: [],
            find_request_result=lambda session_id, request_id: None,
        )

    def handle_chat(self, role, message, *, request_id, event_metadata=None):
        self.chat_messages.append((role, message, request_id, dict(event_metadata or {})))
        return self.chat_result

    def evaluate_fix(self, fixed_code, *, request_id):
        self.fixed_codes.append((fixed_code, request_id))
        return self.fix_result


class RecordingModel:
    def __init__(self, message="我想知道循环何时结束。"):
        self.message = message
        self.calls = 0

    def decide(self, **kwargs):
        self.calls += 1
        return AgentDecision(message=self.message)


@pytest.fixture
def stage3_context(tmp_path, monkeypatch):
    database_path = tmp_path / "stage3.db"
    monkeypatch.setattr(_TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{database_path}")
    app = create_app("testing")
    with app.app_context():
        assert db.engine.url.database == str(database_path)
        db.create_all()
        student = User(student_id="student-1", username="student-1", usertype="学生")
        student.password = "password"
        assignment = Assignment(
            title="循环练习",
            description="解释循环边界并修复错误代码",
            creator_id="student-1",
        )
        preset = AssignmentThinkingPreset(
            assignment=assignment,
            reference_code="int main() { return 0; }",
            key_steps=json.dumps(["输入", "循环边界", "输出"], ensure_ascii=False),
            difficulty_config=json.dumps({"feynman_rounds": 3}),
            quiz_steps='[{"step": "循环边界"}]',
            status="ready",
        )
        session = ThinkingSession(
            student=student,
            assignment=assignment,
            current_stage=3,
            stage2_completed=True,
        )
        db.session.add_all([student, assignment, preset, session])
        db.session.commit()
        session_id = session.id
    client = app.test_client()
    client.post("/login", data={"username": "student-1", "password": "password"})
    yield app, client, session_id
    with app.app_context():
        db.session.remove()
        db.drop_all()


def _mark_stage3_ready(app, session_id):
    with app.app_context():
        db.session.add(ThinkingStageLog(
            session_id=session_id,
            stage=3,
            event_type="state_snapshot",
            role="student_agent",
            metadata_json=json.dumps({"state": {
                "phase": "student_dialogue",
                "ready_for_code": True,
            }}, ensure_ascii=False),
        ))
        db.session.commit()


def test_stage3_chat_requires_authenticated_user(stage3_context):
    app, _, session_id = stage3_context
    response = app.test_client().post("/thinking/api/stage3/chat", json={"session_id": session_id, "message": "当前消息"})
    assert response.status_code in {302, 401}


def test_stage3_event_order_is_stable_for_equal_timestamps():
    created_at = datetime(2026, 8, 28, 12, 0, 0)
    logs = [
        SimpleNamespace(id=3, created_at=created_at),
        SimpleNamespace(id=1, created_at=created_at),
        SimpleNamespace(id=2, created_at=created_at),
    ]

    ordered = thinking_routes._stable_event_order(logs)

    assert [log.id for log in ordered] == [1, 2, 3]


@pytest.mark.parametrize("endpoint,payload", [
    ("/thinking/api/stage3/chat", {"message": "请解释循环边界。"}),
    ("/thinking/api/stage3/teach", {"message": "循环要在边界前停止。"}),
    ("/thinking/api/stage3/write_code", {}),
    ("/thinking/api/stage3/fix_code", {"fixed_code": "修复后的代码"}),
])
@pytest.mark.parametrize("session_updates", [
    {"current_stage": 2},
    {"stage2_completed": False},
    {"status": "completed"},
])
def test_every_stage3_endpoint_rejects_sessions_outside_active_stage3(
    stage3_context, monkeypatch, endpoint, payload, session_updates,
):
    """The route gate must run before any Stage 3 runtime construction."""
    app, client, session_id = stage3_context
    with app.app_context():
        thinking_session = db.session.get(ThinkingSession, session_id)
        for field, value in session_updates.items():
            setattr(thinking_session, field, value)
        db.session.commit()

    monkeypatch.setattr(
        thinking_routes,
        "build_feynman_runtime",
        lambda *args, **kwargs: pytest.fail("Stage 3 runtime must not be constructed"),
    )
    response = client.post(endpoint, json={
        "session_id": session_id,
        "request_id": f"blocked-{endpoint.rsplit('/', 1)[-1]}",
        **payload,
    })

    assert response.status_code == 409
    assert response.json["error_code"] == "STAGE3_NOT_ACTIVE"


def test_complete_session_cannot_grant_stage3_completion_by_itself(stage3_context):
    """This compatibility endpoint may save timing only after a verified runtime completion."""
    app, client, session_id = stage3_context

    response = client.post("/thinking/api/complete_session", json={
        "session_id": session_id,
        "total_time_seconds": 123,
    })

    assert response.status_code == 409
    assert response.json["error_code"] == "STAGE3_COMPLETION_NOT_VERIFIED"
    with app.app_context():
        saved = db.session.get(ThinkingSession, session_id)
        assert saved.status == "in_progress"
        assert saved.stage3_completed is False
        assert saved.total_time_seconds == 0


def test_stage3_chat_uses_current_message_not_client_history(stage3_context, monkeypatch):
    _, client, session_id = stage3_context
    fake_runtime = FakeRuntime(
        chat_result=AgentResult(success=True, agent=AgentRole.TEACHER_AGENT, response="请解释边界。", ui_action=UIAction.CONTINUE_CHAT),
        session_id=session_id,
    )
    monkeypatch.setattr(thinking_routes, "build_feynman_runtime", lambda *args, **kwargs: fake_runtime)

    response = client.post("/thinking/api/stage3/chat", json={"session_id": session_id, "message": "当前消息", "messages": [{"role": "user", "content": "篡改历史"}], "student_state": {"trusted": True}, "request_id": "route-r1"})

    assert response.status_code == 200
    assert fake_runtime.chat_messages == [(
        AgentRole.TEACHER_AGENT,
        "当前消息",
        "route-r1",
        {
            "source_role": "user",
            "target_role": "teacher_agent",
            "message_kind": "user_message",
            "visibility": "public",
            "reply_to_event_id": None,
            "parent_request_id": None,
        },
    )]
    assert response.json["response"] == "请解释边界。"


def test_stage3_chat_uses_last_old_user_message_as_fallback(stage3_context, monkeypatch):
    _, client, session_id = stage3_context
    fake_runtime = FakeRuntime(
        chat_result=AgentResult(success=True, agent=AgentRole.TEACHER_AGENT, response="继续。"),
        session_id=session_id,
    )
    monkeypatch.setattr(thinking_routes, "build_feynman_runtime", lambda *args, **kwargs: fake_runtime)

    response = client.post("/thinking/api/stage3/chat", json={"session_id": session_id, "messages": [{"role": "user", "content": "旧消息"}, {"role": "assistant", "content": "忽略"}, {"role": "user", "content": "最后的旧消息"}], "request_id": "old-r1"})

    assert response.status_code == 200
    assert fake_runtime.chat_messages == [(
        AgentRole.TEACHER_AGENT,
        "最后的旧消息",
        "old-r1",
        {
            "source_role": "user",
            "target_role": "teacher_agent",
            "message_kind": "user_message",
            "visibility": "public",
            "reply_to_event_id": None,
            "parent_request_id": None,
        },
    )]


def test_stage3_session_ownership_is_checked_before_runtime(stage3_context, monkeypatch):
    app, _, session_id = stage3_context
    with app.app_context():
        other = User(student_id="student-2", username="student-2", usertype="学生")
        other.password = "password"
        db.session.add(other)
        db.session.commit()
    other_client = app.test_client()
    other_client.post("/login", data={"username": "student-2", "password": "password"})
    monkeypatch.setattr(thinking_routes, "build_feynman_runtime", lambda *args, **kwargs: pytest.fail("runtime must not be constructed"))

    response = other_client.post("/thinking/api/stage3/chat", json={"session_id": session_id, "message": "无权访问", "request_id": "owner-r1"})

    assert response.status_code == 403


def test_fix_code_ignores_client_buggy_code_and_returns_feedback(stage3_context, monkeypatch):
    _, client, session_id = stage3_context
    fake_runtime = FakeRuntime(fix_result=AgentResult(success=True, agent=AgentRole.STUDENT_AGENT, public_content={"correct": False, "feedback": "还需要检查边界。"}))
    monkeypatch.setattr(thinking_routes, "build_feynman_runtime", lambda *args, **kwargs: fake_runtime)

    response = client.post("/thinking/api/stage3/fix_code", json={"session_id": session_id, "buggy_code": "伪造的代码", "fixed_code": "用户提交的修复", "request_id": "route-fix-1"})

    assert response.status_code == 200
    assert response.json["correct"] is False
    assert response.json["feedback"] == "还需要检查边界。"
    assert fake_runtime.fixed_codes == [("用户提交的修复", "route-fix-1")]


def test_write_code_persists_hidden_bugs_and_deduplicates_request(stage3_context, monkeypatch):
    app, client, session_id = stage3_context
    calls = []

    def runtime_factory(session, assignment, preset):
        callbacks = FeynmanCallbacks(
            buggy_code_generator=lambda context: calls.append(context) or {
                "buggy_code": "while (i <= n) { ++i; }",
                "bugs": [{"description": "隐藏 Bug", "fix": "正确修复"}],
                "message": "检查循环。",
            },
        )
        return build_feynman_runtime(session, assignment, preset, callbacks=callbacks)

    monkeypatch.setattr(thinking_routes, "build_feynman_runtime", runtime_factory)
    _mark_stage3_ready(app, session_id)
    payload = {"session_id": session_id, "request_id": "code-r1"}
    first = client.post("/thinking/api/stage3/write_code", json=payload)
    second = client.post("/thinking/api/stage3/write_code", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json == second.json
    assert len(calls) == 1
    assert "隐藏 Bug" not in json.dumps(first.json, ensure_ascii=False)
    assert "正确修复" not in json.dumps(first.json, ensure_ascii=False)
    with app.app_context():
        events = ThinkingStageLog.query.filter_by(session_id=session_id, stage=3).all()
        artifacts = [event.get_metadata()["artifact"] for event in events if event.event_type == "buggy_attempt"]
    assert artifacts == [{"buggy_code": "while (i <= n) { ++i; }", "bugs": [{"description": "隐藏 Bug", "fix": "正确修复"}]}]


def test_stage3_teach_retries_completed_request_before_repetition_guard(stage3_context, monkeypatch):
    _, client, session_id = stage3_context
    model = RecordingModel()

    def runtime_factory(session, assignment, preset):
        return build_feynman_runtime(session, assignment, preset, model=model)

    monkeypatch.setattr(thinking_routes, "build_feynman_runtime", runtime_factory)
    payload = {"session_id": session_id, "message": "循环结束条件需要判断。", "request_id": "teach-retry-1"}
    first = client.post("/thinking/api/stage3/teach", json=payload)
    second = client.post("/thinking/api/stage3/teach", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json == second.json
    assert model.calls == 1


def test_start_session_uses_public_tool_result_without_internal_buggy_attempt(stage3_context, monkeypatch):
    app, client, session_id = stage3_context

    def runtime_factory(session, assignment, preset):
        return build_feynman_runtime(
            session,
            assignment,
            preset,
            callbacks=FeynmanCallbacks(buggy_code_generator=lambda context: {
                "buggy_code": "while (i <= n) { ++i; }",
                "bugs": [{"description": "隐藏 Bug", "fix": "正确修复"}],
                "message": "内部生成说明，不应显示。",
            }),
        )

    monkeypatch.setattr(thinking_routes, "build_feynman_runtime", runtime_factory)
    _mark_stage3_ready(app, session_id)
    client.post("/thinking/api/stage3/write_code", json={"session_id": session_id, "request_id": "restore-code-1"})
    response = client.post("/thinking/api/start_session", json={"assignment_id": 1})

    assert response.status_code == 200
    assert response.json["buggy_code_info"]["buggy_code"] == "while (i <= n) { ++i; }"
    student_contents = [item["content"] for item in response.json["student_history"]]
    assert student_contents.count("我写了一版代码，请帮我检查。") == 1
    assert "内部生成说明，不应显示。" not in student_contents


def test_runtime_user_events_are_attributed_to_their_terminal_agent(stage3_context, monkeypatch):
    app, client, session_id = stage3_context
    with app.app_context():
        db.session.add_all([
            ThinkingStageLog(session_id=session_id, stage=3, event_type="agent_user_message", role="student", content="老师面板提问", metadata_json=json.dumps({"request_id": "teacher-r", "input_kind": "chat"})),
            ThinkingStageLog(session_id=session_id, stage=3, event_type="agent_message", role="teacher_agent", content="老师回答", metadata_json=json.dumps({"request_id": "teacher-r"})),
            ThinkingStageLog(session_id=session_id, stage=3, event_type="agent_user_message", role="student", content="学生面板提问", metadata_json=json.dumps({"request_id": "student-r", "input_kind": "chat"})),
            ThinkingStageLog(session_id=session_id, stage=3, event_type="agent_message", role="student_agent", content="学生回答", metadata_json=json.dumps({"request_id": "student-r"})),
        ])
        db.session.commit()

    restored = client.post("/thinking/api/start_session", json={"assignment_id": 1})
    assert [item["content"] for item in restored.json["teacher_history"]] == ["老师面板提问", "老师回答"]
    assert [item["content"] for item in restored.json["student_history"]] == ["学生面板提问", "学生回答"]

    fake_runtime = FakeRuntime(
        chat_result=AgentResult(success=True, agent=AgentRole.STUDENT_AGENT, response="继续解释。"),
        session_id=session_id,
    )
    monkeypatch.setattr(thinking_routes, "build_feynman_runtime", lambda *args, **kwargs: fake_runtime)
    response = client.post("/thinking/api/stage3/teach", json={"session_id": session_id, "message": "老师面板提问", "request_id": "student-new"})

    assert response.status_code == 200
    assert fake_runtime.chat_messages == [(
        AgentRole.STUDENT_AGENT,
        "老师面板提问",
        "student-new",
        {
            "source_role": "user",
            "target_role": "student_agent",
            "message_kind": "user_message",
            "visibility": "public",
            "reply_to_event_id": None,
            "parent_request_id": None,
        },
    )]


@pytest.mark.parametrize("correct", [False, True])
def test_fix_code_persists_evaluation_and_updates_completion(stage3_context, monkeypatch, correct):
    app, client, session_id = stage3_context
    fixed_codes = []

    def runtime_factory(session, assignment, preset):
        callbacks = FeynmanCallbacks(
            buggy_code_generator=lambda context: {
                "buggy_code": "while (i <= n) { ++i; }",
                "bugs": [{"description": "边界错误", "correct_version": "i < n"}],
                "message": "检查。",
            },
            fix_evaluator=lambda context, fixed_code: fixed_codes.append(fixed_code) or {"correct": correct, "feedback": "内部反馈"},
        )
        return build_feynman_runtime(session, assignment, preset, callbacks=callbacks)

    monkeypatch.setattr(thinking_routes, "build_feynman_runtime", runtime_factory)
    _mark_stage3_ready(app, session_id)
    client.post("/thinking/api/stage3/write_code", json={"session_id": session_id, "request_id": f"code-{correct}"})
    with app.app_context():
        db.session.add(ThinkingStageLog(
            session_id=session_id,
            stage=3,
            event_type="state_snapshot",
            role="system",
            metadata_json=json.dumps({"state": {
                "phase": "code_review",
                "code_review_status": "pending",
                "learning_evidence": [{
                    "concept": "循环边界",
                    "evidence": "能够解释边界条件为什么能避免越界。",
                }],
            }}, ensure_ascii=False),
        ))
        db.session.commit()
    response = client.post("/thinking/api/stage3/fix_code", json={"session_id": session_id, "buggy_code": "客户端伪造", "fixed_code": "提交修复", "request_id": f"fix-{correct}"})

    assert response.status_code == 200
    assert response.json["correct"] is correct
    assert fixed_codes == ["提交修复"]
    with app.app_context():
        saved = db.session.get(ThinkingSession, session_id)
    assert saved.stage3_completed is correct
    assert saved.status == ("completed" if correct else "in_progress")


def test_start_session_restores_legacy_and_runtime_stage3_history(stage3_context):
    app, client, session_id = stage3_context
    with app.app_context():
        db.session.add_all([
            ThinkingStageLog(session_id=session_id, stage=3, event_type="chat", role="student", content="旧老师提问", metadata_json=json.dumps({"panel": "teacher_agent"})),
            ThinkingStageLog(session_id=session_id, stage=3, event_type="agent_user_message", role="student", content="新提问", metadata_json="{}"),
            ThinkingStageLog(session_id=session_id, stage=3, event_type="agent_message", role="teacher_agent", content="新回答", metadata_json="{}"),
            ThinkingStageLog(session_id=session_id, stage=3, event_type="tool_result", role="student_agent", content="代码说明", metadata_json=json.dumps({"public_content": {"buggy_code": "buggy", "message": "代码说明"}})),
            ThinkingStageLog(session_id=session_id, stage=3, event_type="fix_code", role="student", content="修复代码", metadata_json="{}"),
        ])
        db.session.commit()
        assignment_id = db.session.get(ThinkingSession, session_id).assignment_id

    response = client.post("/thinking/api/start_session", json={"assignment_id": assignment_id})

    assert response.status_code == 200
    assert response.json["resumed"] is True
    assert {item["content"] for item in response.json["teacher_history"]} >= {"旧老师提问", "新提问", "新回答"}
    assert {item["content"] for item in response.json["student_history"]} >= {"代码说明", "【提交代码修复】\n修复代码"}
    assert response.json["buggy_code_info"] == {"buggy_code": "buggy", "message": "代码说明"}
