import csv

from scripts.plot_guided_learning_paper import create_figures


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_create_figures_writes_four_nonempty_pngs(tmp_path):
    results = tmp_path / "results"
    figures = tmp_path / "figures"
    results.mkdir()
    _write_csv(
        results / "stable_stage_funnel.csv",
        [
            {"step": "stage1_scored", "sessions": 8, "percent_of_started": 80},
            {"step": "stage2_completed", "sessions": 6, "percent_of_started": 60},
            {"step": "stage3_completed", "sessions": 5, "percent_of_started": 50},
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
                "users": 1,
                "total_sessions": 4,
                "completed_sessions": 3,
            },
        ],
    )

    created = create_figures(results, figures)

    assert {path.name for path in created} == {
        "sample_flow.png",
        "stage_funnel.png",
        "usage_distribution.png",
        "version_timeline.png",
    }
    assert all(path.stat().st_size > 1000 for path in created)
