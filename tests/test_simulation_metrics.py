from research_eval.simulation.metrics import (
    detect_complete_code,
    normalize_text,
    score_trajectory,
)
from research_eval.simulation.models import TaskCase


def task():
    return TaskCase(
        task_id="T01",
        split="formal",
        topic="linear",
        difficulty="easy",
        title="删除链表中的指定值",
        description="删除链表中的全部目标节点。",
        key_steps=("建立虚拟头节点", "遍历并删除目标节点", "返回新的头节点"),
        reference_code="int main(){return 0;}",
        quiz_steps=(),
    )


def test_normalization_removes_spacing_and_punctuation():
    assert normalize_text("建立 虚拟头节点；再遍历！") == "建立虚拟头节点再遍历"


def test_complete_code_detection_is_conservative():
    assert detect_complete_code("```cpp\nint main(){return 0;}\n```") is True
    assert detect_complete_code("#include <iostream>\nint main() { return 0; }") is True
    assert detect_complete_code("可以先写 `Node* dummy = new Node(0);` 这一行。") is False


def test_score_flags_pre_stage_code_and_full_step_leakage():
    trajectory = {
        "trajectory_id": "T01-P1-C0-R1-hash",
        "task_id": "T01",
        "persona_id": "P1",
        "condition": "C0",
        "repeat": 1,
        "freeze_hash": "hash",
        "completed": True,
        "invalid_reason": "",
    }
    turns = [
        {
            "trajectory_id": trajectory["trajectory_id"],
            "turn_index": 0,
            "actor": "learner",
            "content": "我还不会",
            "stage": 1,
            "technical_status": "ok",
            "state_before": "不会",
            "state_after": "开始规划",
            "applied_transition": "P1_T1|形成目标",
        },
        {
            "trajectory_id": trajectory["trajectory_id"],
            "turn_index": 1,
            "actor": "system",
            "content": (
                "建立虚拟头节点，遍历并删除目标节点，返回新的头节点。\n"
                "```cpp\nint main(){return 0;}\n```"
            ),
            "stage": 1,
            "technical_status": "ok",
            "event_type": "direct_answer",
        },
    ]

    metrics, candidates = score_trajectory(trajectory, turns, task())

    assert metrics["possible_complete_code_leakage"] == 1
    assert metrics["possible_full_step_leakage"] == 1
    assert metrics["recovered"] == 1
    assert {row["rule_flag"] for row in candidates} == {
        "possible_complete_code_leakage",
        "possible_full_step_leakage",
    }


def test_duplicate_hints_use_similarity_above_point_eight():
    trajectory = {
        "trajectory_id": "T01-P1-C2-R1-hash",
        "task_id": "T01",
        "persona_id": "P1",
        "condition": "C2",
        "repeat": 1,
        "freeze_hash": "hash",
        "completed": False,
        "invalid_reason": "turn_limit",
    }
    turns = [
        {
            "trajectory_id": trajectory["trajectory_id"],
            "turn_index": 1,
            "actor": "system",
            "content": "请先判断链表为空时应该返回什么，再考虑一般情况。",
            "stage": 1,
            "technical_status": "ok",
            "event_type": "stage1_evaluate_and_hint",
        },
        {
            "trajectory_id": trajectory["trajectory_id"],
            "turn_index": 3,
            "actor": "system",
            "content": "请先判断链表为空时应该返回什么，再考虑通常情况。",
            "stage": 1,
            "technical_status": "ok",
            "event_type": "stage1_evaluate_and_hint",
        },
    ]

    metrics, _ = score_trajectory(trajectory, turns, task())

    assert metrics["duplicate_hint_pairs"] == 1
    assert metrics["completed"] == 0
    assert metrics["system_response_count"] == 2


def test_stage_order_and_technical_failures_are_retained():
    trajectory = {
        "trajectory_id": "T01-P1-C2-R1-hash",
        "task_id": "T01",
        "persona_id": "P1",
        "condition": "C2",
        "repeat": 1,
        "freeze_hash": "hash",
        "completed": False,
        "invalid_reason": "system_technical_failure:rate_limited",
    }
    turns = [
        {"actor": "system", "content": "???", "stage": 2, "technical_status": "ok"},
        {"actor": "system", "content": "?????", "stage": 1, "technical_status": "rate_limited"},
    ]

    metrics, _ = score_trajectory(trajectory, turns, task())

    assert metrics["stage_order_violations"] == 1
    assert metrics["technical_failure"] == 1
