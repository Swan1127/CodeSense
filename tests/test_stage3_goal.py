from utils.agents.goal import build_stage3_user_goal


def test_stage3_user_goal_starts_with_a_concrete_next_action():
    goal = build_stage3_user_goal(
        key_concepts=["循环边界", "不变量"],
        coverage_summary={
            "coverage_score": 0.0,
            "ready_for_code": False,
            "unresolved_concepts": ["循环边界", "不变量"],
            "concept_coverage": [],
        },
    )

    assert goal["title"] == "掌握关键思路并完成一次代码修复"
    assert goal["progress_percent"] == 0
    assert goal["current_milestone"] == "understanding"
    assert goal["next_action"] == "请继续用自己的话说明“循环边界”，小明会换一个角度检查。"
    assert [step["status"] for step in goal["steps"]] == ["active", "todo", "todo", "todo"]


def test_stage3_user_goal_moves_to_code_repair_after_server_readiness():
    goal = build_stage3_user_goal(
        key_concepts=["循环边界"],
        coverage_summary={
            "coverage_score": 1.0,
            "ready_for_code": True,
            "unresolved_concepts": [],
            "concept_coverage": [{"concept": "循环边界", "status": "covered"}],
        },
    )

    assert goal["progress_percent"] == 80
    assert goal["status"] == "ready_for_code"
    assert goal["current_milestone"] == "buggy_code"
    assert goal["covered_concepts"] == 1
    assert goal["next_action"].startswith("关键点已完成多角度检查")
    assert [step["status"] for step in goal["steps"]] == ["done", "done", "todo", "todo"]


def test_stage3_user_goal_reaches_one_hundred_only_after_repair_completion():
    goal = build_stage3_user_goal(
        key_concepts=["循环边界"],
        coverage_summary={
            "coverage_score": 1.0,
            "ready_for_code": True,
            "unresolved_concepts": [],
            "concept_coverage": [{"concept": "循环边界", "status": "covered"}],
        },
        phase="code_review",
        session_status="completed",
        code_review_status="passed",
    )

    assert goal["progress_percent"] == 100
    assert goal["status"] == "complete"
    assert goal["current_milestone"] == "complete"
    assert all(step["status"] == "done" for step in goal["steps"])
