from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app import create_app
from config import TestingConfig
from models import Assignment, ThinkingSession, ThinkingStageLog, User, db


UTC_NOW = datetime(2026, 9, 14, 12, 0, 0)


def _session(**overrides):
    values = {
        "id": 7,
        "student_id": "student-1",
        "assignment_id": 11,
        "current_stage": 1,
        "stage1_description": None,
        "stage1_score": None,
        "stage1_hint_count": 0,
        "stage2_completed": False,
        "stage2_hint_count": 0,
        "stage3_completed": False,
        "total_time_seconds": 0,
        "started_at": UTC_NOW - timedelta(minutes=5),
        "completed_at": None,
        "status": "in_progress",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_active_and_idle_status_use_latest_activity_and_threshold():
    from services.session_lifecycle import session_lifecycle_status

    assert session_lifecycle_status(
        _session(started_at=UTC_NOW - timedelta(hours=1)),
        now=UTC_NOW,
        last_activity_at=UTC_NOW - timedelta(minutes=30),
    ) == "active"
    assert session_lifecycle_status(
        _session(started_at=UTC_NOW - timedelta(hours=1)),
        now=UTC_NOW,
        last_activity_at=UTC_NOW - timedelta(minutes=30, seconds=1),
    ) == "idle"


@pytest.mark.parametrize(
    ("persisted_status", "expected"),
    [("completed", "completed"), ("abandoned", "abandoned")],
)
def test_terminal_persisted_status_wins_over_clock(persisted_status, expected):
    from services.session_lifecycle import session_lifecycle_status

    assert session_lifecycle_status(
        _session(status=persisted_status),
        now=UTC_NOW,
        last_activity_at=UTC_NOW,
    ) == expected


def test_unknown_or_missing_dates_fail_closed_to_idle():
    from services.session_lifecycle import session_lifecycle_status

    assert session_lifecycle_status(_session(status="legacy", started_at=None), now=UTC_NOW) == "idle"
    assert session_lifecycle_status(_session(started_at=None), now=UTC_NOW) == "idle"


def test_elapsed_projection_handles_future_clock_and_legacy_client_timer():
    from services.session_lifecycle import session_elapsed_details

    future = _session(started_at=UTC_NOW + timedelta(minutes=2))
    assert session_elapsed_details(future, now=UTC_NOW) == {
        "elapsed_seconds": 0,
        "elapsed_source": "server_clock",
    }

    legacy = _session(
        status="completed",
        total_time_seconds=91,
        completed_at=UTC_NOW - timedelta(minutes=1),
    )
    assert session_elapsed_details(legacy, now=UTC_NOW) == {
        "elapsed_seconds": 91,
        "elapsed_source": "stored_client_timer",
    }


def test_elapsed_projection_falls_back_to_terminal_timestamps():
    from services.session_lifecycle import session_elapsed_details

    session = _session(
        status="completed",
        started_at=UTC_NOW - timedelta(minutes=4),
        completed_at=UTC_NOW - timedelta(minutes=1),
    )
    assert session_elapsed_details(session, now=UTC_NOW) == {
        "elapsed_seconds": 180,
        "elapsed_source": "timestamps",
    }


@pytest.mark.parametrize(
    ("updates", "expected_percent", "expected_next"),
    [
        ({}, 0, "完成本阶段的思路描述"),
        ({"current_stage": 2, "stage1_description": "先遍历再输出"}, 33, "完成代码块拼装与校验"),
        ({"current_stage": 3, "stage2_completed": True}, 67, "完成讲解、编写并修复代码"),
        ({"current_stage": 3, "stage2_completed": True, "stage3_completed": True, "status": "completed"}, 100, "查看本次学习记录"),
    ],
)
def test_payload_exposes_stage_progress_and_next_action(updates, expected_percent, expected_next):
    from services.session_lifecycle import session_lifecycle_payload

    payload = session_lifecycle_payload(
        _session(**updates),
        now=UTC_NOW,
        last_activity_at=UTC_NOW,
    )

    assert payload["progress_percent"] == expected_percent
    assert payload["next_action"] == expected_next
    assert len(payload["stages"]) == 3
    assert payload["last_activity_at"].endswith("Z")


def test_latest_session_activity_returns_one_bounded_aggregate_mapping(tmp_path, monkeypatch):
    database_path = tmp_path / "session-lifecycle.db"
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{database_path}")
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        student = User(student_id="student-1", username="student-1", usertype="学生")
        student.password = "password"
        assignment = Assignment(title="聚合测试", description="", creator_id="teacher-1")
        first = ThinkingSession(student_id="student-1", assignment=assignment)
        second = ThinkingSession(student_id="student-1", assignment=assignment)
        db.session.add_all([student, assignment, first, second])
        db.session.flush()
        db.session.add_all([
            ThinkingStageLog(
                session_id=first.id,
                stage=1,
                event_type="session_start",
                role="student",
                content="",
                created_at=UTC_NOW - timedelta(minutes=9),
            ),
            ThinkingStageLog(
                session_id=first.id,
                stage=1,
                event_type="description_submit",
                role="student",
                content="",
                created_at=UTC_NOW - timedelta(minutes=1),
            ),
        ])
        db.session.commit()

        from services.session_lifecycle import latest_session_activity

        statements = []

        def record_statement(connection, cursor, statement, parameters, context, executemany):
            if "thinking_stage_logs" in statement:
                statements.append(statement)

        event.listen(db.engine, "before_cursor_execute", record_statement)
        try:
            activity = latest_session_activity([first.id, second.id, first.id, 999999])
        finally:
            event.remove(db.engine, "before_cursor_execute", record_statement)

        assert activity == {first.id: UTC_NOW - timedelta(minutes=1)}
        assert len(statements) == 1

        db.session.remove()
        db.drop_all()


def test_can_view_session_limits_teacher_to_owner_or_managed_class():
    from services.session_lifecycle import can_view_session

    owner = SimpleNamespace(student_id="student-1", is_admin=False, is_teacher=False)
    teacher = SimpleNamespace(student_id="teacher-1", is_admin=False, is_teacher=True)
    other_teacher = SimpleNamespace(student_id="teacher-2", is_admin=False, is_teacher=True)
    admin = SimpleNamespace(student_id="admin-1", is_admin=True, is_teacher=False)
    assignment = SimpleNamespace(creator_id="teacher-1")
    student = SimpleNamespace(student_id="student-1", class_id=None)
    session = SimpleNamespace(student_id="student-1", student=student, assignment=assignment)

    assert can_view_session(owner, session) is True
    assert can_view_session(admin, session) is True
    assert can_view_session(teacher, session) is True
    assert can_view_session(other_teacher, session) is False
