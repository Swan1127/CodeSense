import json
from pathlib import Path

import pytest

from research_eval.simulation.tasks import (
    freeze_files,
    load_task_manifest,
    validate_task_manifest,
)


def make_row(index, split, difficulty, topic):
    return {
        "task_id": f"T{index:02d}",
        "source_assignment_id": index,
        "split": split,
        "topic": topic,
        "difficulty": difficulty,
        "title": f"任务{index}",
        "description": "完成一个数据结构算法任务。",
        "key_steps": ["读取输入", "执行算法", "输出结果"],
        "reference_code": "int main(){return 0;}",
        "quiz_steps": [{"step": 1, "prompt": "选择下一步"}],
    }


def valid_rows():
    rows = [
        make_row(1, "development", "easy", "linear"),
        make_row(2, "development", "medium", "tree"),
    ]
    topics = ["linear", "tree", "graph", "search_sort"]
    index = 3
    for difficulty in ("easy", "medium", "hard"):
        for topic in topics:
            rows.append(make_row(index, "formal", difficulty, topic))
            index += 1
    return rows


def test_formal_manifest_has_balanced_difficulty_and_topic_coverage():
    rows = valid_rows()

    validate_task_manifest(rows)

    formal = [row for row in rows if row["split"] == "formal"]
    assert {level: sum(row["difficulty"] == level for row in formal)
            for level in ("easy", "medium", "hard")} == {
                "easy": 4,
                "medium": 4,
                "hard": 4,
            }


def test_manifest_rejects_duplicate_ids():
    rows = valid_rows()
    rows[-1]["task_id"] = rows[0]["task_id"]

    with pytest.raises(ValueError, match="unique"):
        validate_task_manifest(rows)


def test_manifest_rejects_missing_topic_coverage():
    rows = valid_rows()
    for row in rows:
        if row["topic"] == "graph":
            row["topic"] = "linear"

    with pytest.raises(ValueError, match="topic"):
        validate_task_manifest(rows)


def test_load_and_freeze_manifest(tmp_path):
    tasks_path = tmp_path / "tasks.json"
    personas_path = tmp_path / "personas.json"
    tasks_path.write_text(json.dumps(valid_rows(), ensure_ascii=False), encoding="utf-8")
    personas_path.write_text("[]", encoding="utf-8")

    assert len(load_task_manifest(tasks_path)) == 14
    frozen = freeze_files({"tasks": tasks_path, "personas": personas_path})

    assert set(frozen) == {"tasks", "personas"}
    assert all(len(value) == 64 for value in frozen.values())


def test_repository_manifest_and_hashes_are_frozen():
    root = Path("research/guided_learning_paper/experiments/simulation/config")
    tasks_path = root / "tasks.json"
    personas_path = root / "personas.json"
    freeze_path = root / "freeze_manifest.json"

    tasks = load_task_manifest(tasks_path)
    frozen = json.loads(freeze_path.read_text(encoding="utf-8"))
    actual_hashes = freeze_files({"tasks": tasks_path, "personas": personas_path})

    assert len(tasks) == 14
    assert frozen["frozen_files"] == actual_hashes
    assert frozen["formal_task_ids"] == [f"F{index:02d}" for index in range(1, 13)]
    assert len(frozen["ablation_task_ids"]) == 6
    assert len(frozen["ablation_persona_ids"]) == 4
