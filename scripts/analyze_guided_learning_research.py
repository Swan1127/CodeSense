"""Rebuild the aggregate results used by the guided-learning paper.

The script reads the anonymized research ZIP in memory. It never writes raw
rows or free text to the output directory.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

import pandas as pd
import statsmodels.formula.api as smf


@dataclass(frozen=True)
class VersionBoundary:
    name: str
    starts_at_utc: datetime
    label: str = ""


VERSION_BOUNDARIES = [
    VersionBoundary(
        "V1",
        datetime.fromisoformat("2026-06-18T00:00:00+00:00"),
        "初始线上版",
    ),
    VersionBoundary(
        "V2",
        datetime.fromisoformat("2026-06-24T09:11:41+00:00"),
        "阶段一脚手架版",
    ),
    VersionBoundary(
        "V3",
        datetime.fromisoformat("2026-06-25T05:24:04+00:00"),
        "分题作答与增强积木版",
    ),
    VersionBoundary(
        "V4",
        datetime.fromisoformat("2026-06-25T16:34:45+00:00"),
        "阶段二测验过渡版",
    ),
    VersionBoundary(
        "V5",
        datetime.fromisoformat("2026-06-27T16:26:42+00:00"),
        "相对稳定测验版",
    ),
]


def parse_platform_timestamp(value: str) -> datetime:
    """Parse a platform timestamp, treating a missing offset as UTC."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def classify_version(
    timestamp: datetime,
    boundaries: list[VersionBoundary] = VERSION_BOUNDARIES,
) -> str:
    """Return the latest version boundary not after ``timestamp``."""
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    matches = [b for b in boundaries if b.starts_at_utc <= timestamp]
    return max(matches, key=lambda item: item.starts_at_utc).name if matches else "pre"


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


PATH_LABELS = {
    "no_valid_stage1": "未形成第一阶段有效记录",
    "stage2_incomplete": "到达第二阶段但未完成",
    "stage3_incomplete": "完成第二阶段但未完成第三阶段",
    "all_completed": "完成全部阶段",
}

EVENT_CATEGORY = {
    "description_submit": "description_submit",
    "hint_request": "hint_request",
    "companion_chat": "companion_chat",
    "stage_pass": "stage_pass",
    "verify_fail": "verify_fail",
    "chat": "dialogue",
    "write_code": "generated_error_code",
    "fix_code": "fix_code",
}


def classify_session_path(session: dict) -> str:
    """Classify a session into one mutually exclusive progress path."""
    if as_bool(session["stage3_completed"]):
        return "all_completed"
    if as_bool(session["stage2_completed"]):
        return "stage3_incomplete"
    if int(session["current_stage"] or 1) >= 2 or bool(session["stage1_score"]):
        return "stage2_incomplete"
    return "no_valid_stage1"


def build_stable_session_paths(sessions: list[dict]) -> list[dict]:
    """Aggregate mutually exclusive progress paths for stable sessions."""
    counts = {name: 0 for name in PATH_LABELS}
    for session in sessions:
        counts[classify_session_path(session)] += 1
    total = len(sessions)
    return [
        {
            "path": name,
            "label": label,
            "sessions": counts[name],
            "percent": round(100 * counts[name] / total, 2) if total else 0.0,
        }
        for name, label in PATH_LABELS.items()
    ]


def map_event(row: dict) -> str:
    """Map a raw platform event to a paper-facing activity category."""
    return EVENT_CATEGORY.get(row["event_type"], "other")


def collapse_event_sequence(rows: list[dict]) -> list[str]:
    """Order events and collapse consecutive runs of the same category."""
    ordered = sorted(
        rows,
        key=lambda row: parse_platform_timestamp(row["created_at"]),
    )
    collapsed: list[str] = []
    for row in ordered:
        category = map_event(row)
        if not collapsed or collapsed[-1] != category:
            collapsed.append(category)
    return collapsed


def build_event_transitions(
    sessions: list[dict],
    logs: list[dict],
) -> list[dict]:
    """Count adjacent event transitions by session completion group."""
    completion_group = {
        row["anonymous_session_id"]: (
            "completed"
            if row["status"].strip().lower() == "completed"
            else "incomplete"
        )
        for row in sessions
    }
    by_session: dict[str, list[dict]] = defaultdict(list)
    for row in logs:
        if row["anonymous_session_id"] in completion_group:
            by_session[row["anonymous_session_id"]].append(row)

    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    covered: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    source_totals: dict[tuple[str, str], int] = defaultdict(int)
    for session_id, rows in by_session.items():
        group = completion_group[session_id]
        sequence = collapse_event_sequence(rows)
        for source, target in zip(sequence, sequence[1:]):
            key = (group, source, target)
            counts[key] += 1
            covered[key].add(session_id)
            source_totals[(group, source)] += 1

    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    pair_sessions: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (group, source, target), count in counts.items():
        pair = (source, target)
        pair_counts[pair] += count
        pair_sessions[pair].update(covered[(group, source, target)])

    return [
        {
            "completion_group": group,
            "source": source,
            "target": target,
            "count": count,
            "distinct_sessions": len(covered[(group, source, target)]),
            "conditional_percent": round(
                100 * count / source_totals[(group, source)],
                2,
            ),
            "show_in_main_figure": int(
                pair_counts[(source, target)] >= 10
                and len(pair_sessions[(source, target)]) >= 5
            ),
        }
        for (group, source, target), count in sorted(counts.items())
    ]


def count_student_users(users: list[dict]) -> int:
    return sum(row["user_role"] in {"student", "学生"} for row in users)


def read_csv_from_zip(archive: ZipFile, filename: str) -> list[dict[str, str]]:
    raw = archive.read(filename).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(raw)))


def summarize_usage(sessions: list[dict]) -> dict[str, int | float]:
    by_user: dict[str, list[dict]] = defaultdict(list)
    for row in sessions:
        by_user[row["anonymous_user_id"]].append(row)

    counts = sorted((len(rows) for rows in by_user.values()), reverse=True)
    total = len(sessions)
    return {
        "sessions": total,
        "users": len(by_user),
        "completed_sessions": sum(
            row["status"].strip().lower() == "completed" for row in sessions
        ),
        "users_with_completed_session": sum(
            any(row["status"].strip().lower() == "completed" for row in rows)
            for rows in by_user.values()
        ),
        "exactly_one_session_users": sum(value == 1 for value in counts),
        "repeat_users": sum(value >= 2 for value in counts),
        "cross_assignment_users": sum(
            len({row["anonymous_assignment_id"] for row in rows}) >= 2
            for rows in by_user.values()
        ),
        "users_with_at_least_5_sessions": sum(value >= 5 for value in counts),
        "users_with_at_least_10_sessions": sum(value >= 10 for value in counts),
        "sessions_from_repeat_users": sum(value for value in counts if value >= 2),
        "top_10_user_session_share": round(
            100 * sum(counts[:10]) / total if total else 0.0, 1
        ),
    }


def build_student_usage(sessions: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in sessions:
        grouped[row["anonymous_user_id"]].append(row)
    distribution: dict[int, dict[str, int]] = defaultdict(
        lambda: {"users": 0, "total_sessions": 0, "completed_sessions": 0}
    )
    for rows in grouped.values():
        count = len(rows)
        distribution[count]["users"] += 1
        distribution[count]["total_sessions"] += count
        distribution[count]["completed_sessions"] += sum(
            row["status"].strip().lower() == "completed" for row in rows
        )
    return [
        {"sessions_per_user": count, **distribution[count]}
        for count in sorted(distribution)
    ]


def build_stage_funnel(sessions: list[dict], logs: list[dict]) -> list[dict]:
    stage_passes: dict[int, set[str]] = {1: set(), 2: set(), 3: set()}
    for row in logs:
        if row["event_type"] == "stage_pass":
            stage_passes[int(row["stage"])].add(row["anonymous_session_id"])
    total = len(sessions)
    values = [
        ("stage1_scored", sum(bool(row["stage1_score"]) for row in sessions)),
        ("reached_stage2", sum(int(row["current_stage"]) >= 2 for row in sessions)),
        ("stage1_pass", len(stage_passes[1])),
        (
            "stage2_completed",
            sum(as_bool(row["stage2_completed"]) for row in sessions),
        ),
        (
            "stage3_completed",
            sum(as_bool(row["stage3_completed"]) for row in sessions),
        ),
    ]
    return [
        {
            "step": step,
            "sessions": count,
            "percent_of_started": round(100 * count / total, 2) if total else 0.0,
        }
        for step, count in values
    ]


def build_version_summary(
    sessions: list[dict],
    boundaries: list[VersionBoundary] = VERSION_BOUNDARIES,
) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in sessions:
        version = classify_version(
            parse_platform_timestamp(row["started_at"]), boundaries
        )
        grouped[version].append(row)
    labels = {boundary.name: boundary.label for boundary in boundaries}
    return [
        {
            "version": boundary.name,
            "label": labels[boundary.name],
            "sessions": len(grouped[boundary.name]),
            "users": len(
                {row["anonymous_user_id"] for row in grouped[boundary.name]}
            ),
            "assignments": len(
                {
                    row["anonymous_assignment_id"]
                    for row in grouped[boundary.name]
                }
            ),
            "completed_sessions": sum(
                row["status"].strip().lower() == "completed"
                for row in grouped[boundary.name]
            ),
            "completion_percent": round(
                100
                * sum(
                    row["status"].strip().lower() == "completed"
                    for row in grouped[boundary.name]
                )
                / len(grouped[boundary.name]),
                2,
            )
            if grouped[boundary.name]
            else 0.0,
        }
        for boundary in boundaries
    ]


def active_seconds(
    events: Iterable[datetime],
    gap_cap_seconds: int = 600,
) -> int:
    ordered = sorted(events)
    return int(
        sum(
            min((later - earlier).total_seconds(), gap_cap_seconds)
            for earlier, later in zip(ordered, ordered[1:])
        )
    )


def summarize_active_time(sessions: list[dict], logs: list[dict]) -> dict[str, float]:
    by_session: dict[str, list[datetime]] = defaultdict(list)
    for row in logs:
        by_session[row["anonymous_session_id"]].append(
            parse_platform_timestamp(row["created_at"])
        )
    completed_ids = {
        row["anonymous_session_id"]
        for row in sessions
        if row["status"].strip().lower() == "completed"
    }
    completed = [
        active_seconds(events, gap_cap_seconds=300) / 60
        for session_id, events in by_session.items()
        if session_id in completed_ids
    ]
    incomplete = [
        active_seconds(events, gap_cap_seconds=300) / 60
        for session_id, events in by_session.items()
        if session_id not in completed_ids
    ]
    return {
        "gap_cap_seconds": 300,
        "completed_sessions_with_events": len(completed),
        "incomplete_sessions_with_events": len(incomplete),
        "completed_median_active_minutes": round(statistics.median(completed), 2),
        "incomplete_median_active_minutes": round(statistics.median(incomplete), 2),
    }


def _five_number(
    values: list[float],
) -> tuple[int, float | None, float | None, float | None]:
    if not values:
        return 0, None, None, None
    series = pd.Series(values, dtype=float)
    return (
        len(values),
        round(float(series.median()), 2),
        round(float(series.quantile(0.25)), 2),
        round(float(series.quantile(0.75)), 2),
    )


def summarize_stage_friction(
    sessions: list[dict],
    logs: list[dict],
    gap_cap_seconds: int = 300,
) -> list[dict]:
    """Summarize per-session process friction without assuming independence."""
    logs_by_session: dict[str, list[dict]] = defaultdict(list)
    for row in logs:
        logs_by_session[row["anonymous_session_id"]].append(row)

    metrics: dict[tuple[str, str], list[float]] = defaultdict(list)
    for session in sessions:
        session_id = session["anonymous_session_id"]
        group = (
            "completed"
            if session["status"].strip().lower() == "completed"
            else "incomplete"
        )
        session_logs = logs_by_session[session_id]
        fixed = {
            "stage1_hints": float(session["stage1_hint_count"] or 0),
            "stage2_hints": float(session["stage2_hint_count"] or 0),
            "stage2_verify_fail": float(
                sum(
                    row["event_type"] == "verify_fail" and int(row["stage"]) == 2
                    for row in session_logs
                )
            ),
            "stage3_dialogue_rounds": float(
                session["stage3_teacher_rounds"] or 0
            )
            + float(session["stage3_student_rounds"] or 0),
            "stage3_fix_code": float(
                sum(
                    row["event_type"] == "fix_code" and int(row["stage"]) == 3
                    for row in session_logs
                )
            ),
        }
        for metric, value in fixed.items():
            metrics[(group, metric)].append(value)

        for stage in (1, 2, 3):
            times = [
                parse_platform_timestamp(row["created_at"])
                for row in session_logs
                if int(row["stage"]) == stage
            ]
            if times:
                metrics[(group, f"stage{stage}_active_minutes")].append(
                    active_seconds(times, gap_cap_seconds) / 60
                )

    rows = []
    for (group, metric), values in sorted(metrics.items()):
        n, median, q1, q3 = _five_number(values)
        rows.append(
            {
                "completion_group": group,
                "metric": metric,
                "n": n,
                "median": median,
                "q1": q1,
                "q3": q3,
            }
        )
    return rows


def crossing_sessions(
    logs: list[dict],
    boundary: datetime,
) -> int:
    by_session: dict[str, list[datetime]] = defaultdict(list)
    for row in logs:
        by_session[row["anonymous_session_id"]].append(
            parse_platform_timestamp(row["created_at"])
        )
    return sum(
        min(events) < boundary <= max(events)
        for events in by_session.values()
        if events
    )


def select_sessions_since(
    sessions: list[dict],
    logs: list[dict],
    starts_at_utc: datetime,
) -> tuple[list[dict], list[dict]]:
    selected_sessions = [
        row
        for row in sessions
        if parse_platform_timestamp(row["started_at"]) >= starts_at_utc
    ]
    selected_ids = {
        row["anonymous_session_id"] for row in selected_sessions
    }
    selected_logs = [
        row for row in logs if row["anonymous_session_id"] in selected_ids
    ]
    return selected_sessions, selected_logs


def build_submission_pairs(
    submissions: list[dict],
    sessions: list[dict],
    post_launch_utc: datetime,
) -> pd.DataFrame:
    by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in submissions:
        if parse_platform_timestamp(row["submitted_at"]) < post_launch_utc:
            continue
        by_pair[
            (row["anonymous_user_id"], row["anonymous_assignment_id"])
        ].append(row)

    sessions_by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in sessions:
        pair = (row["anonymous_user_id"], row["anonymous_assignment_id"])
        sessions_by_pair[pair].append(row)

    records = []
    for (user_id, assignment_id), rows in by_pair.items():
        ordered = sorted(
            rows,
            key=lambda row: parse_platform_timestamp(row["submitted_at"]),
        )
        first = ordered[0]
        last = ordered[-1]
        first_time = parse_platform_timestamp(first["submitted_at"])
        prior_sessions = [
            row
            for row in sessions_by_pair[(user_id, assignment_id)]
            if parse_platform_timestamp(row["started_at"]) <= first_time
        ]
        completed_before_first = any(
            row.get("completed_at")
            and row["status"].strip().lower() == "completed"
            and parse_platform_timestamp(row["completed_at"]) <= first_time
            for row in prior_sessions
        )
        exposure = (
            "completed"
            if completed_before_first
            else "incomplete"
            if prior_sessions
            else "none"
        )
        first_full_pass, first_pass_rate = _pass_outcomes(first)
        final_full_pass, final_pass_rate = _pass_outcomes(last)
        records.append(
            {
                "user_id": user_id,
                "assignment_id": assignment_id,
                "exposure": exposure,
                "guided_before_first": int(exposure != "none"),
                "completed_before_first": int(exposure == "completed"),
                "attempts": len(ordered),
                "first_full_pass": first_full_pass,
                "first_pass_rate": first_pass_rate,
                "final_full_pass": final_full_pass,
                "final_pass_rate": final_pass_rate,
            }
        )
    return pd.DataFrame.from_records(records)


def _pass_outcomes(row: dict) -> tuple[int, float | None]:
    total = int(row["sandbox_total"] or 0)
    passed = int(row["sandbox_passed"] or 0)
    pass_rate = (
        passed / total
        if row["sandbox_status"] and total > 0
        else None
    )
    return int(total > 0 and passed == total), pass_rate


def count_informative_students(pairs: pd.DataFrame, column: str) -> int:
    """Count students whose records vary on the requested exposure field."""
    return int((pairs.groupby("user_id")[column].nunique() >= 2).sum())


def raw_exposure_rates(pairs: pd.DataFrame) -> list[dict]:
    """Summarize unadjusted outcomes for the three time-ordered exposures."""
    rows = []
    for exposure in ("none", "incomplete", "completed"):
        group = pairs[pairs["exposure"] == exposure]
        rows.append(
            {
                "exposure": exposure,
                "pairs": int(len(group)),
                "students": int(group["user_id"].nunique()),
                "assignments": int(group["assignment_id"].nunique()),
                "first_full_pass_percent": round(
                    100 * float(group["first_full_pass"].mean()),
                    2,
                ),
                "first_pass_rate_percent": round(
                    100 * float(group["first_pass_rate"].dropna().mean()),
                    2,
                ),
                "final_full_pass_percent": round(
                    100 * float(group["final_full_pass"].mean()),
                    2,
                ),
                "final_pass_rate_percent": round(
                    100 * float(group["final_pass_rate"].dropna().mean()),
                    2,
                ),
                "mean_attempts": round(float(group["attempts"].mean()), 3),
            }
        )
    return rows


def fit_exposure_models(
    pairs: pd.DataFrame,
    exposure_mode: str = "three_level",
) -> list[dict]:
    """Fit student and assignment fixed-effects association models."""
    if exposure_mode not in {"three_level", "binary"}:
        raise ValueError("exposure_mode must be 'three_level' or 'binary'")

    outcomes = (
        "first_full_pass",
        "first_pass_rate",
        "final_full_pass",
        "final_pass_rate",
        "attempts",
    )
    term_source = (
        "C(exposure, Treatment(reference='none'))"
        if exposure_mode == "three_level"
        else "guided_before_first"
    )
    informative_column = (
        "exposure" if exposure_mode == "three_level" else "guided_before_first"
    )
    rows = []
    for outcome in outcomes:
        sample = pairs.dropna(subset=[outcome]).copy()
        model = smf.ols(
            f"{outcome} ~ {term_source} + C(user_id) + C(assignment_id)",
            data=sample,
        ).fit(
            cov_type="cluster",
            cov_kwds={"groups": sample["user_id"]},
        )
        terms = [
            term
            for term in model.params.index
            if term.startswith(term_source)
        ]
        for term in terms:
            low, high = model.conf_int().loc[term]
            rows.append(
                {
                    "model": exposure_mode,
                    "outcome": outcome,
                    "term": term,
                    "n_pairs": int(model.nobs),
                    "n_students": int(sample["user_id"].nunique()),
                    "informative_students": count_informative_students(
                        sample,
                        informative_column,
                    ),
                    "coefficient": round(float(model.params[term]), 6),
                    "standard_error": round(float(model.bse[term]), 6),
                    "ci_95_low": round(float(low), 6),
                    "ci_95_high": round(float(high), 6),
                    "p_value": round(float(model.pvalues[term]), 6),
                }
            )
    return rows


def fit_association_models(pairs: pd.DataFrame) -> list[dict]:
    outcomes = [
        ("final_full_pass", "最终完全通过"),
        ("final_pass_rate", "最终沙箱通过率"),
        ("attempts", "提交尝试次数"),
    ]
    rows = []
    for outcome, label in outcomes:
        sample = pairs.dropna(subset=[outcome]).copy()
        model = smf.ols(
            f"{outcome} ~ guided_before_first + C(user_id) + C(assignment_id)",
            data=sample,
        ).fit(
            cov_type="cluster",
            cov_kwds={"groups": sample["user_id"]},
        )
        estimate = model.params["guided_before_first"]
        low, high = model.conf_int().loc["guided_before_first"]
        rows.append(
            {
                "outcome": outcome,
                "label": label,
                "n_student_assignment_pairs": int(model.nobs),
                "coefficient": round(float(estimate), 6),
                "standard_error": round(
                    float(model.bse["guided_before_first"]), 6
                ),
                "p_value": round(float(model.pvalues["guided_before_first"]), 6),
                "ci_95_low": round(float(low), 6),
                "ci_95_high": round(float(high), 6),
            }
        )
    return rows


def raw_association_rates(pairs: pd.DataFrame) -> dict[str, dict[str, float]]:
    result = {}
    for guided_value, name in [(0, "no_guided_before_first"), (1, "guided_before_first")]:
        group = pairs[pairs["guided_before_first"] == guided_value]
        result[name] = {
            "pairs": int(len(group)),
            "final_full_pass_percent": round(
                100 * float(group["final_full_pass"].dropna().mean()), 2
            ),
            "final_pass_rate_percent": round(
                100 * float(group["final_pass_rate"].dropna().mean()), 2
            ),
            "mean_attempts": round(float(group["attempts"].mean()), 3),
        }
    return result


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def analyze(input_path: Path, output_dir: Path) -> dict:
    with ZipFile(input_path) as archive:
        users = read_csv_from_zip(archive, "users.csv")
        assignments = read_csv_from_zip(archive, "assignments.csv")
        submissions = read_csv_from_zip(archive, "submissions.csv")
        sessions = read_csv_from_zip(archive, "thinking_sessions.csv")
        logs = read_csv_from_zip(archive, "thinking_stage_logs.csv")
        presets = read_csv_from_zip(archive, "thinking_presets.csv")

    usage = summarize_usage(sessions)
    funnel = build_stage_funnel(sessions, logs)
    stable_sessions, stable_logs = select_sessions_since(
        sessions,
        logs,
        VERSION_BOUNDARIES[-1].starts_at_utc,
    )
    stable_funnel = build_stage_funnel(stable_sessions, stable_logs)
    stable_paths = build_stable_session_paths(stable_sessions)
    stage_friction = summarize_stage_friction(stable_sessions, stable_logs)
    event_transitions = build_event_transitions(stable_sessions, stable_logs)
    versions = build_version_summary(sessions)
    active_time = summarize_active_time(sessions, logs)
    pairs = build_submission_pairs(
        submissions,
        sessions,
        post_launch_utc=datetime.fromisoformat("2026-06-18T00:00:00+00:00"),
    )
    raw_exposure = raw_exposure_rates(pairs)
    exposure_models = [
        *fit_exposure_models(pairs, "three_level"),
        *fit_exposure_models(pairs, "binary"),
    ]

    stable = next(row for row in versions if row["version"] == "V5")
    summary = {
        "source_file": input_path.name,
        "row_counts": {
            "users": len(users),
            "students": count_student_users(users),
            "assignments": len(assignments),
            "submissions": len(submissions),
            "thinking_sessions": len(sessions),
            "thinking_stage_logs": len(logs),
            "thinking_presets": len(presets),
        },
        "usage": usage,
        "stable_version": stable,
        "stable_paths": {
            row["path"]: row["sessions"] for row in stable_paths
        },
        "active_time": active_time,
        "crossing_sessions": {
            boundary.name: crossing_sessions(logs, boundary.starts_at_utc)
            for boundary in VERSION_BOUNDARIES[1:]
        },
        "student_assignment_pairs": len(pairs),
        "exposure_counts": {
            row["exposure"]: row["pairs"] for row in raw_exposure
        },
        "informative_students": {
            "three_level": count_informative_students(pairs, "exposure"),
            "binary": count_informative_students(
                pairs,
                "guided_before_first",
            ),
        },
        "raw_exposure_rates": raw_exposure,
        "raw_associations": raw_association_rates(pairs),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(output_dir / "version_summary.csv", versions)
    write_csv(output_dir / "stage_funnel.csv", funnel)
    write_csv(output_dir / "stable_stage_funnel.csv", stable_funnel)
    write_csv(output_dir / "stable_session_paths.csv", stable_paths)
    write_csv(output_dir / "stage_friction.csv", stage_friction)
    write_csv(output_dir / "event_transitions.csv", event_transitions)
    write_csv(output_dir / "student_usage.csv", build_student_usage(sessions))
    write_csv(output_dir / "exposure_raw_rates.csv", raw_exposure)
    write_csv(output_dir / "exposure_models.csv", exposure_models)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary = analyze(args.input, args.output_dir)
    print(f"input={args.input}")
    print(f"output_dir={args.output_dir}")
    print(f"thinking_sessions={summary['row_counts']['thinking_sessions']}")
    print(
        "thinking_stage_logs="
        f"{summary['row_counts']['thinking_stage_logs']}"
    )
    print(f"guided_users={summary['usage']['users']}")
    print(
        "stable_version_sessions="
        f"{summary['stable_version']['sessions']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
