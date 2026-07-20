from pathlib import Path


ROOT = Path("research/guided_learning_paper")


def test_reference_audit_covers_direct_comparators():
    text = (ROOT / "reference_paper_audit.md").read_text(encoding="utf-8")
    for title in (
        "Agent4Edu",
        "Classroom Simulacra",
        "Impact of AI-agent-supported collaborative learning",
        "Pedagogical AI conversational agents in higher education",
    ):
        assert title in text
    assert "直接参照" in text
    assert "方法参照" in text
    assert "不建议写入正文" in text


def test_literature_matrix_records_agent_boundaries():
    text = (ROOT / "literature_matrix.md").read_text(encoding="utf-8")
    assert "会话内" in text
    assert "跨作业" in text
    assert "10.1007/s10639-025-13487-8" in text
    assert "10.1145/3706598.3713773" in text
