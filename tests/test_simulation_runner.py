import json
from pathlib import Path

from research_eval.simulation.conditions import SystemStep
from research_eval.simulation.matrix import (
    TrajectorySpec,
    build_ablation_matrix,
    build_core_matrix,
    filter_completed,
)
from research_eval.simulation.models import load_personas
from research_eval.simulation.runner import JsonlSink, run_trajectory
from research_eval.simulation.tasks import load_task_manifest
from research_eval.simulation.zhipu_roles import RoleResponse


CONFIG = Path("research/guided_learning_paper/experiments/simulation/config")


class FakeLearnerClient:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def complete(self, role, system_prompt, messages, temperature, max_tokens):
        self.calls.append((role, list(messages)))
        content = self.contents.pop(0)
        return RoleResponse(
            role=role,
            content=content,
            model="glm-4.5-flash",
            status_code=200,
            error_code="",
            retries=0,
            elapsed_seconds=0.01,
            timestamp_utc="2026-07-22T00:00:00+00:00",
        )


class TwoTurnAdapter:
    def __init__(self):
        self.calls = 0

    def respond(self, state, learner_response):
        self.calls += 1
        state.system_turns += 1
        return SystemStep(
            content=f"system-{self.calls}",
            stage=1,
            completed=self.calls >= 2,
            event_type="fake_system",
        )


def valid_learner_json(response="我先说明目标"):
    return json.dumps(
        {
            "response": response,
            "state_before": "无计划",
            "state_after": "形成目标",
            "applied_transition": "P1_T1|教师要求复述目标与输入输出后：从无计划转为能说出问题目标",
        },
        ensure_ascii=False,
    )


def test_matrix_sizes_and_order_are_exact():
    tasks = load_task_manifest(CONFIG / "tasks.json")
    personas = load_personas(CONFIG / "personas.json")
    frozen = json.loads((CONFIG / "freeze_manifest.json").read_text(encoding="utf-8"))

    core = build_core_matrix(tasks, personas, "freeze-a")
    ablation = build_ablation_matrix(
        tasks,
        personas,
        "freeze-a",
        frozen["ablation_task_ids"],
        frozen["ablation_persona_ids"],
    )

    assert len(core) == 648
    assert len(ablation) == 216
    assert core == sorted(
        core,
        key=lambda row: (row.task_id, row.persona_id, row.condition, row.repeat),
    )


def test_resume_skips_only_matching_freeze_hash():
    specs = [
        TrajectorySpec("T01", "P1", "C0", 1, "hash-a"),
        TrajectorySpec("T01", "P1", "C0", 1, "hash-b"),
    ]
    completed = {("T01", "P1", "C0", 1, "hash-a")}

    pending = filter_completed(specs, completed)

    assert [row.freeze_hash for row in pending] == ["hash-b"]


def test_runner_appends_turns_and_summary(tmp_path):
    task = load_task_manifest(CONFIG / "tasks.json")[0]
    persona = load_personas(CONFIG / "personas.json")[0]
    spec = TrajectorySpec(task.task_id, persona.persona_id, "C0", 1, "hash-a")
    learner = FakeLearnerClient([valid_learner_json(), valid_learner_json("第二轮")])
    turn_sink = JsonlSink(tmp_path / "turns.jsonl")
    trajectory_sink = JsonlSink(tmp_path / "trajectories.jsonl")

    trajectory = run_trajectory(
        spec,
        task,
        persona,
        learner,
        TwoTurnAdapter(),
        "learner prompt",
        {"learner": "prompt-hash"},
        turn_sink,
        trajectory_sink,
    )

    assert trajectory.completed is True
    assert len((tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()) == 4
    summaries = (tmp_path / "trajectories.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(summaries) == 1


def test_malformed_learner_json_gets_one_format_retry(tmp_path):
    task = load_task_manifest(CONFIG / "tasks.json")[0]
    persona = load_personas(CONFIG / "personas.json")[0]
    spec = TrajectorySpec(task.task_id, persona.persona_id, "C0", 1, "hash-a")
    learner = FakeLearnerClient(
        ["not-json", valid_learner_json(), valid_learner_json("第二轮")]
    )

    trajectory = run_trajectory(
        spec,
        task,
        persona,
        learner,
        TwoTurnAdapter(),
        "learner prompt",
        {"learner": "prompt-hash"},
        JsonlSink(tmp_path / "turns.jsonl"),
        JsonlSink(tmp_path / "trajectories.jsonl"),
    )

    assert len(learner.calls) >= 2
    assert trajectory.invalid_reason == ""


def test_second_malformed_response_marks_trajectory_invalid(tmp_path):
    task = load_task_manifest(CONFIG / "tasks.json")[0]
    persona = load_personas(CONFIG / "personas.json")[0]
    spec = TrajectorySpec(task.task_id, persona.persona_id, "C0", 1, "hash-a")
    learner = FakeLearnerClient(["not-json", "still-not-json"])

    trajectory = run_trajectory(
        spec,
        task,
        persona,
        learner,
        TwoTurnAdapter(),
        "learner prompt",
        {"learner": "prompt-hash"},
        JsonlSink(tmp_path / "turns.jsonl"),
        JsonlSink(tmp_path / "trajectories.jsonl"),
    )

    assert trajectory.completed is False
    assert trajectory.invalid_reason == "learner_format_invalid"
