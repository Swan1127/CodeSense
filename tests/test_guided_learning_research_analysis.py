from datetime import datetime

import pandas as pd

from scripts.analyze_guided_learning_research import (
    VersionBoundary,
    active_seconds,
    build_event_transitions,
    build_stable_session_paths,
    build_submission_pairs,
    build_stage_funnel,
    build_student_usage,
    build_version_summary,
    classify_version,
    collapse_event_sequence,
    count_informative_students,
    count_student_users,
    fit_exposure_models,
    parse_platform_timestamp,
    raw_exposure_rates,
    select_sessions_since,
    summarize_stage_friction,
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
            "completed_at": "2026-06-19T23:30:00",
            "status": "completed",
        }
    ]

    pairs = build_submission_pairs(
        submissions,
        sessions,
        post_launch_utc=datetime.fromisoformat("2026-06-18T00:00:00+00:00"),
    )

    assert len(pairs) == 1
    assert pairs.iloc[0]["exposure"] == "completed"
    assert pairs.iloc[0]["guided_before_first"] == 1
    assert pairs.iloc[0]["first_full_pass"] == 0
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


def test_stable_session_paths_use_mutually_exclusive_states():
    sessions = [
        {
            "stage1_score": "",
            "current_stage": "1",
            "stage2_completed": "0",
            "stage3_completed": "0",
        },
        {
            "stage1_score": "50",
            "current_stage": "2",
            "stage2_completed": "0",
            "stage3_completed": "0",
        },
        {
            "stage1_score": "50",
            "current_stage": "3",
            "stage2_completed": "1",
            "stage3_completed": "0",
        },
        {
            "stage1_score": "50",
            "current_stage": "3",
            "stage2_completed": "1",
            "stage3_completed": "1",
        },
    ]

    rows = build_stable_session_paths(sessions)

    assert [row["path"] for row in rows] == [
        "no_valid_stage1",
        "stage2_incomplete",
        "stage3_incomplete",
        "all_completed",
    ]
    assert [row["sessions"] for row in rows] == [1, 1, 1, 1]
    assert sum(row["sessions"] for row in rows) == 4


def test_stage_friction_reports_median_iqr_and_active_minutes():
    sessions = [
        {
            "anonymous_session_id": "s1",
            "status": "completed",
            "stage1_hint_count": "1",
            "stage2_hint_count": "2",
            "stage3_teacher_rounds": "3",
            "stage3_student_rounds": "4",
        }
    ]
    logs = [
        {
            "anonymous_session_id": "s1",
            "stage": "2",
            "event_type": "verify_fail",
            "created_at": "2026-07-01T00:00:00",
        },
        {
            "anonymous_session_id": "s1",
            "stage": "2",
            "event_type": "verify_fail",
            "created_at": "2026-07-01T00:02:00",
        },
        {
            "anonymous_session_id": "s1",
            "stage": "3",
            "event_type": "fix_code",
            "created_at": "2026-07-01T00:03:00",
        },
        {
            "anonymous_session_id": "s1",
            "stage": "3",
            "event_type": "chat",
            "created_at": "2026-07-01T00:13:00",
        },
    ]

    rows = summarize_stage_friction(sessions, logs)
    keyed = {
        (row["completion_group"], row["metric"]): row
        for row in rows
    }

    assert keyed[("completed", "stage2_verify_fail")]["median"] == 2.0
    assert keyed[("completed", "stage3_fix_code")]["median"] == 1.0
    assert keyed[("completed", "stage3_active_minutes")]["median"] == 5.0
    assert keyed[("completed", "stage3_active_minutes")]["n"] == 1


def test_event_sequence_collapses_consecutive_categories():
    logs = [
        {
            "event_type": "chat",
            "stage": "3",
            "created_at": "2026-07-01T00:00:03",
        },
        {
            "event_type": "description_submit",
            "stage": "1",
            "created_at": "2026-07-01T00:00:01",
        },
        {
            "event_type": "description_submit",
            "stage": "1",
            "created_at": "2026-07-01T00:00:02",
        },
        {
            "event_type": "fix_code",
            "stage": "3",
            "created_at": "2026-07-01T00:00:04",
        },
    ]

    assert collapse_event_sequence(logs) == [
        "description_submit",
        "dialogue",
        "fix_code",
    ]


def test_event_transitions_split_completed_and_incomplete_sessions():
    sessions = [
        {"anonymous_session_id": "done", "status": "completed"},
        {"anonymous_session_id": "open", "status": "in_progress"},
    ]
    logs = [
        {
            "anonymous_session_id": "done",
            "event_type": "description_submit",
            "stage": "1",
            "created_at": "2026-07-01T00:00:01",
        },
        {
            "anonymous_session_id": "done",
            "event_type": "stage_pass",
            "stage": "1",
            "created_at": "2026-07-01T00:00:02",
        },
        {
            "anonymous_session_id": "open",
            "event_type": "description_submit",
            "stage": "1",
            "created_at": "2026-07-01T00:00:01",
        },
        {
            "anonymous_session_id": "open",
            "event_type": "hint_request",
            "stage": "1",
            "created_at": "2026-07-01T00:00:02",
        },
    ]

    rows = build_event_transitions(sessions, logs)

    assert {
        (
            row["completion_group"],
            row["source"],
            row["target"],
            row["count"],
        )
        for row in rows
    } == {
        ("completed", "description_submit", "stage_pass", 1),
        ("incomplete", "description_submit", "hint_request", 1),
    }
    assert all(row["distinct_sessions"] == 1 for row in rows)
    assert all(row["conditional_percent"] == 100.0 for row in rows)
    assert all(row["show_in_main_figure"] == 0 for row in rows)


def test_submission_exposure_uses_only_activity_before_first_submission():
    submissions = [
        {
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "a1",
            "submitted_at": "2026-06-20T00:00:00",
            "sandbox_status": "failed",
            "sandbox_passed": "0",
            "sandbox_total": "2",
        },
        {
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "a1",
            "submitted_at": "2026-06-20T01:00:00",
            "sandbox_status": "passed",
            "sandbox_passed": "2",
            "sandbox_total": "2",
        },
    ]
    sessions = [
        {
            "anonymous_user_id": "u1",
            "anonymous_assignment_id": "a1",
            "started_at": "2026-06-19T23:00:00",
            "completed_at": "2026-06-20T00:30:00",
            "status": "completed",
        }
    ]

    pairs = build_submission_pairs(
        submissions,
        sessions,
        post_launch_utc=datetime.fromisoformat("2026-06-18T00:00:00+00:00"),
    )

    row = pairs.iloc[0]
    assert row["exposure"] == "incomplete"
    assert row["first_full_pass"] == 0
    assert row["first_pass_rate"] == 0.0
    assert row["final_full_pass"] == 1
    assert row["final_pass_rate"] == 1.0


def test_exposure_summary_and_models_report_informative_students():
    pairs = pd.DataFrame(
        [
            {
                "user_id": "u1",
                "assignment_id": "a1",
                "exposure": "none",
                "guided_before_first": 0,
                "first_full_pass": 1,
                "first_pass_rate": 1.0,
                "final_full_pass": 1,
                "final_pass_rate": 1.0,
                "attempts": 1,
            },
            {
                "user_id": "u1",
                "assignment_id": "a2",
                "exposure": "incomplete",
                "guided_before_first": 1,
                "first_full_pass": 0,
                "first_pass_rate": 0.5,
                "final_full_pass": 1,
                "final_pass_rate": 1.0,
                "attempts": 2,
            },
            {
                "user_id": "u1",
                "assignment_id": "a3",
                "exposure": "completed",
                "guided_before_first": 1,
                "first_full_pass": 1,
                "first_pass_rate": 1.0,
                "final_full_pass": 1,
                "final_pass_rate": 1.0,
                "attempts": 1,
            },
            {
                "user_id": "u2",
                "assignment_id": "a1",
                "exposure": "none",
                "guided_before_first": 0,
                "first_full_pass": 0,
                "first_pass_rate": 0.0,
                "final_full_pass": 0,
                "final_pass_rate": 0.5,
                "attempts": 3,
            },
            {
                "user_id": "u2",
                "assignment_id": "a2",
                "exposure": "none",
                "guided_before_first": 0,
                "first_full_pass": 1,
                "first_pass_rate": 1.0,
                "final_full_pass": 1,
                "final_pass_rate": 1.0,
                "attempts": 1,
            },
            {
                "user_id": "u2",
                "assignment_id": "a3",
                "exposure": "none",
                "guided_before_first": 0,
                "first_full_pass": 0,
                "first_pass_rate": 0.5,
                "final_full_pass": 1,
                "final_pass_rate": 1.0,
                "attempts": 2,
            },
        ]
    )
    extra_rows = []
    exposure_patterns = {
        "u3": ("incomplete", "completed", "none"),
        "u4": ("completed", "none", "incomplete"),
    }
    for user_offset, (user_id, exposures) in enumerate(exposure_patterns.items()):
        for assignment_offset, assignment_id in enumerate(("a1", "a2", "a3")):
            first_full_pass = (user_offset + assignment_offset) % 2
            exposure = exposures[assignment_offset]
            extra_rows.append(
                {
                    "user_id": user_id,
                    "assignment_id": assignment_id,
                    "exposure": exposure,
                    "guided_before_first": int(exposure != "none"),
                    "first_full_pass": first_full_pass,
                    "first_pass_rate": 0.5 * first_full_pass,
                    "final_full_pass": 1,
                    "final_pass_rate": 1.0,
                    "attempts": 1 + (1 - first_full_pass),
                }
            )
    pairs = pd.concat([pairs, pd.DataFrame(extra_rows)], ignore_index=True)

    assert count_informative_students(pairs, "exposure") == 3
    assert count_informative_students(pairs, "guided_before_first") == 3

    raw = {row["exposure"]: row for row in raw_exposure_rates(pairs)}
    assert raw["none"]["pairs"] == 6
    assert raw["incomplete"]["pairs"] == 3
    assert raw["completed"]["pairs"] == 3

    three_level = fit_exposure_models(pairs, "three_level")
    binary = fit_exposure_models(pairs, "binary")
    assert {row["outcome"] for row in three_level} == {
        "first_full_pass",
        "first_pass_rate",
        "final_full_pass",
        "final_pass_rate",
        "attempts",
    }
    assert all(row["informative_students"] == 3 for row in three_level)
    assert all(row["informative_students"] == 3 for row in binary)
