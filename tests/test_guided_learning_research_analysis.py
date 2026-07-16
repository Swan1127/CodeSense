from datetime import datetime

from scripts.analyze_guided_learning_research import (
    VersionBoundary,
    active_seconds,
    build_submission_pairs,
    build_stage_funnel,
    build_student_usage,
    build_version_summary,
    classify_version,
    count_student_users,
    parse_platform_timestamp,
    select_sessions_since,
    summarize_usage,
)


def test_platform_timestamp_is_parsed_as_utc():
    value = parse_platform_timestamp("2026-06-27T16:26:42")

    assert value.isoformat() == "2026-06-27T16:26:42+00:00"


def test_classify_version_uses_latest_matching_boundary():
    boundaries = [
        VersionBoundary(
            name="V1",
            starts_at_utc=datetime.fromisoformat("2026-06-18T00:00:00+00:00"),
        ),
        VersionBoundary(
            name="V5",
            starts_at_utc=datetime.fromisoformat("2026-06-27T16:26:42+00:00"),
        ),
    ]

    assert classify_version(
        datetime.fromisoformat("2026-06-27T16:26:42+00:00"),
        boundaries,
    ) == "V5"


def test_usage_summary_counts_repeat_and_cross_assignment_users():
    sessions = [
        {
            "anonymous_session_id": "s1",
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "a1",
            "status": "completed",
        },
        {
            "anonymous_session_id": "s2",
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "a2",
            "status": "in_progress",
        },
        {
            "anonymous_session_id": "s3",
            "anonymous_user_id": "u2",
            "anonymous_assignment_id": "a1",
            "status": "completed",
        },
    ]

    result = summarize_usage(sessions)

    assert result["users"] == 2
    assert result["repeat_users"] == 1
    assert result["cross_assignment_users"] == 1
    assert result["completed_sessions"] == 2


def test_stage_funnel_deduplicates_repeated_stage_pass_logs():
    sessions = [
        {
            "anonymous_session_id": "s1",
            "current_stage": "3",
            "stage1_score": "50.0",
            "stage2_completed": "1",
            "stage3_completed": "1",
        },
        {
            "anonymous_session_id": "s2",
            "current_stage": "1",
            "stage1_score": "",
            "stage2_completed": "0",
            "stage3_completed": "0",
        },
    ]
    logs = [
        {"anonymous_session_id": "s1", "stage": "1", "event_type": "stage_pass"},
        {"anonymous_session_id": "s1", "stage": "1", "event_type": "stage_pass"},
        {"anonymous_session_id": "s1", "stage": "2", "event_type": "stage_pass"},
        {"anonymous_session_id": "s1", "stage": "3", "event_type": "stage_pass"},
    ]

    result = {row["step"]: row["sessions"] for row in build_stage_funnel(sessions, logs)}

    assert result == {
        "stage1_scored": 1,
        "reached_stage2": 1,
        "stage1_pass": 1,
        "stage2_completed": 1,
        "stage3_completed": 1,
    }


def test_version_summary_assigns_sessions_by_started_at():
    boundaries = [
        VersionBoundary(
            name="V1",
            starts_at_utc=datetime.fromisoformat("2026-06-18T00:00:00+00:00"),
        ),
        VersionBoundary(
            name="V5",
            starts_at_utc=datetime.fromisoformat("2026-06-27T16:26:42+00:00"),
        ),
    ]
    sessions = [
        {
            "anonymous_session_id": "s1",
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "a1",
            "status": "completed",
            "started_at": "2026-06-20T00:00:00",
        },
        {
            "anonymous_session_id": "s2",
            "anonymous_user_id": "u2",
            "anonymous_assignment_id": "a1",
            "status": "in_progress",
            "started_at": "2026-06-27T16:26:42",
        },
    ]

    result = {row["version"]: row for row in build_version_summary(sessions, boundaries)}

    assert result["V1"]["sessions"] == 1
    assert result["V1"]["completed_sessions"] == 1
    assert result["V5"]["sessions"] == 1
    assert result["V5"]["users"] == 1


def test_active_seconds_caps_long_idle_gaps():
    events = [
        datetime.fromisoformat("2026-07-01T00:00:00+00:00"),
        datetime.fromisoformat("2026-07-01T00:02:00+00:00"),
        datetime.fromisoformat("2026-07-01T01:02:00+00:00"),
    ]

    assert active_seconds(events, gap_cap_seconds=600) == 720


def test_student_count_accepts_exported_chinese_role():
    users = [
        {"user_role": "学生"},
        {"user_role": "学生"},
        {"user_role": "教师"},
        {"user_role": "管理员"},
    ]

    assert count_student_users(users) == 2


def test_submission_pairs_use_post_launch_rows_and_final_outcome():
    submissions = [
        {
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "old",
            "submitted_at": "2026-06-17T00:00:00",
            "sandbox_status": "passed",
            "sandbox_passed": "1",
            "sandbox_total": "1",
        },
        {
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "a1",
            "submitted_at": "2026-06-20T00:00:00",
            "sandbox_status": "failed",
            "sandbox_passed": "0",
            "sandbox_total": "1",
        },
        {
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "a1",
            "submitted_at": "2026-06-20T00:05:00",
            "sandbox_status": "passed",
            "sandbox_passed": "1",
            "sandbox_total": "1",
        },
    ]
    sessions = [
        {
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "a1",
            "started_at": "2026-06-19T23:00:00",
            "status": "completed",
        }
    ]

    pairs = build_submission_pairs(
        submissions,
        sessions,
        post_launch_utc=datetime.fromisoformat("2026-06-18T00:00:00+00:00"),
    )

    assert len(pairs) == 1
    assert pairs.iloc[0]["guided_before_first"] == 1
    assert pairs.iloc[0]["final_full_pass"] == 1
    assert pairs.iloc[0]["attempts"] == 2


def test_student_usage_is_aggregated_without_anonymous_ids():
    sessions = [
        {
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "a1",
            "status": "completed",
        },
        {
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "a2",
            "status": "in_progress",
        },
        {
            "anonymous_user_id": "u2",
            "anonymous_assignment_id": "a1",
            "status": "completed",
        },
    ]

    result = build_student_usage(sessions)

    assert result == [
        {
            "sessions_per_user": 1,
            "users": 1,
            "total_sessions": 1,
            "completed_sessions": 1,
        },
        {
            "sessions_per_user": 2,
            "users": 1,
            "total_sessions": 2,
            "completed_sessions": 1,
        },
    ]
    assert "anonymous_user_id" not in result[0]


def test_select_sessions_since_returns_matching_logs():
    sessions = [
        {"anonymous_session_id": "old", "started_at": "2026-06-20T00:00:00"},
        {"anonymous_session_id": "new", "started_at": "2026-06-28T00:00:00"},
    ]
    logs = [
        {"anonymous_session_id": "old", "event_type": "stage_pass"},
        {"anonymous_session_id": "new", "event_type": "stage_pass"},
    ]

    selected_sessions, selected_logs = select_sessions_since(
        sessions,
        logs,
        datetime.fromisoformat("2026-06-27T16:26:42+00:00"),
    )

    assert [row["anonymous_session_id"] for row in selected_sessions] == ["new"]
    assert [row["anonymous_session_id"] for row in selected_logs] == ["new"]
