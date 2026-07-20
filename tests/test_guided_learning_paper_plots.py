import csv
import json

from PIL import Image

from scripts.plot_guided_learning_paper import create_figures


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_minimal_revised_results(results):
    (results / "analysis_summary.json").write_text(
        json.dumps(
            {
                "usage": {
                    "users": 4,
                    "repeat_users": 2,
                    "cross_assignment_users": 1,
                    "users_with_completed_session": 3,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_csv(
        results / "student_usage.csv",
        [
            {
                "sessions_per_user": 1,
                "users": 2,
                "total_sessions": 2,
                "completed_sessions": 1,
            },
            {
                "sessions_per_user": 4,
                "users": 2,
                "total_sessions": 8,
                "completed_sessions": 6,
            },
        ],
    )
    _write_csv(
        results / "stable_session_paths.csv",
        [
            {
                "path": "no_valid_stage1",
                "label": "未形成第一阶段有效记录",
                "sessions": 2,
                "percent": 20,
            },
            {
                "path": "stage2_incomplete",
                "label": "到达第二阶段但未完成",
                "sessions": 2,
                "percent": 20,
            },
            {
                "path": "stage3_incomplete",
                "label": "完成第二阶段但未完成第三阶段",
                "sessions": 1,
                "percent": 10,
            },
            {
                "path": "all_completed",
                "label": "完成全部阶段",
                "sessions": 5,
                "percent": 50,
            },
        ],
    )
    _write_csv(
        results / "event_transitions.csv",
        [
            {
                "completion_group": "completed",
                "source": "description_submit",
                "target": "stage_pass",
                "count": 12,
                "distinct_sessions": 6,
                "conditional_percent": 60,
                "show_in_main_figure": 1,
            },
            {
                "completion_group": "incomplete",
                "source": "description_submit",
                "target": "hint_request",
                "count": 11,
                "distinct_sessions": 5,
                "conditional_percent": 55,
                "show_in_main_figure": 1,
            },
        ],
    )
    _write_csv(
        results / "version_summary.csv",
        [
            {
                "version": "V1",
                "label": "初始版",
                "sessions": 2,
                "users": 2,
                "assignments": 1,
                "completed_sessions": 1,
                "completion_percent": 50,
            },
            {
                "version": "V5",
                "label": "稳定版",
                "sessions": 8,
                "users": 4,
                "assignments": 3,
                "completed_sessions": 5,
                "completion_percent": 62.5,
            },
        ],
    )


def test_create_figures_writes_revised_nonempty_pngs(tmp_path):
    results = tmp_path / "results"
    figures = tmp_path / "figures"
    results.mkdir()
    _write_minimal_revised_results(results)

    paths = create_figures(results, figures)

    assert {path.name for path in paths} == {
        "activity_chain_evidence.png",
        "adoption_profile.png",
        "stable_session_paths.png",
        "event_transitions.png",
        "appendix_version_timeline.png",
    }
    assert all(path.stat().st_size > 10_000 for path in paths)
    for path in paths:
        with Image.open(path) as image:
            assert min(image.size) >= 1400
