from pathlib import Path


PROTOCOL = Path("research/guided_learning_paper/simulation_evaluation_protocol.md")


def test_protocol_freezes_scope_counts_and_evidence_boundaries():
    text = PROTOCOL.read_text(encoding="utf-8")
    for phrase in (
        "虚拟学生不是现实学生",
        "同一基础模型",
        "两位教师",
        "96",
        "216",
        "72",
        "288",
        "不得调参后保留旧结果",
        "不能证明真实学习增益",
        "upstream",
    ):
        assert phrase in text


def test_protocol_records_reproducible_commands():
    text = PROTOCOL.read_text(encoding="utf-8")
    for script in (
        "run_guided_learning_simulation.py",
        "score_guided_learning_simulation.py",
        "judge_guided_learning_simulation.py",
        "build_simulation_teacher_packet.py",
        "import_simulation_teacher_ratings.py",
        "analyze_guided_learning_simulation.py",
        "plot_guided_learning_simulation.py",
    ):
        assert script in text
