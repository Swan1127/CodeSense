from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "research" / "guided_learning_paper" / "concurrency_evaluation_protocol.md"
README = ROOT / "research" / "guided_learning_paper" / "README.md"

UPSTREAM_COMMAND = (
    "py scripts/run_guided_learning_concurrency.py --mode upstream --request-kind short "
    "--levels 1,2 --requests-per-level 3 "
    "--output-dir research/guided_learning_paper/experiments/concurrency/smoke"
)
CANARY_COMMAND = (
    "py scripts/run_guided_learning_concurrency.py --mode platform --request-kind short "
    "--levels 1,2,4,8 --requests-per-level 20 --base-url http://127.0.0.1:5000 "
    "--credentials-file /var/www/codesense/research_load_users.json --assignment-id 85 "
    "--output-dir research_exports/concurrency/canary"
)
VALIDATED_COMMAND = (
    "py scripts/run_guided_learning_concurrency.py --mode platform --request-kind long "
    "--levels 1,2,4,8,16,24,32 --requests-per-level 20 --allow-validated-ramp "
    "--base-url http://127.0.0.1:5000 "
    "--credentials-file /var/www/codesense/research_load_users.json --assignment-id 85 "
    "--output-dir research_exports/concurrency/validated"
)


def test_protocol_contains_mandatory_gates_and_exact_commands():
    text = PROTOCOL.read_text(encoding="utf-8")

    for phrase in ("低峰期", "专用测试账号", "最高并发 8", "--allow-validated-ramp", "不证明学习效果"):
        assert phrase in text
    for command in (UPSTREAM_COMMAND, CANARY_COMMAND, VALIDATED_COMMAND):
        assert command in text


def test_protocol_requires_assignment_replacement_and_canary_review():
    text = PROTOCOL.read_text(encoding="utf-8")

    assert "85" in text
    assert "替换" in text
    assert "ready preset" in text
    assert "canary 日志" in text
    assert "无正在进行的课程" in text


def test_paper_readme_links_the_protocol():
    text = README.read_text(encoding="utf-8")

    assert "concurrency_evaluation_protocol.md" in text
