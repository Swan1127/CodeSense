from pathlib import Path

from research_eval.simulation.models import (
    Condition,
    Trajectory,
    content_sha256,
    load_personas,
)


PERSONA_PATH = Path(
    "research/guided_learning_paper/experiments/simulation/config/personas.json"
)
EXPECTED_IDS = {
    "P1_NO_PLAN",
    "P2_CONCEPT_MISCONCEPTION",
    "P3_BOUNDARY_OMISSION",
    "P4_COMPLEXITY_GAP",
    "P5_ANSWER_SEEKING",
    "P6_LOCAL_REASONING_ERROR",
}


def test_persona_manifest_has_six_unique_profiles():
    personas = load_personas(PERSONA_PATH)

    assert len(personas) == 6
    assert {row.persona_id for row in personas} == EXPECTED_IDS
    assert all(row.hidden_state and row.observable_behavior for row in personas)
    assert all(row.transition_rules and row.forbidden_knowledge for row in personas)


def test_condition_values_are_frozen():
    assert [row.value for row in Condition] == ["C0", "C1", "C2", "A1", "A2", "A3"]


def test_content_hash_changes_when_bytes_change(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("a", encoding="utf-8")
    first = content_sha256(path)
    path.write_text("b", encoding="utf-8")

    assert len(first) == 64
    assert content_sha256(path) != first


def test_trajectory_serialization_preserves_prompt_hashes():
    row = Trajectory(
        trajectory_id="T01-P1-C0-R1",
        task_id="T01",
        persona_id="P1",
        condition="C0",
        repeat=1,
        prompt_hashes={"learner": "abc"},
    )

    assert row.to_dict()["prompt_hashes"] == {"learner": "abc"}
    assert row.to_dict()["turns"] == []
