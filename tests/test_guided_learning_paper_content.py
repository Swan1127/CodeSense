import re
from pathlib import Path


ROOT = Path("research/guided_learning_paper")

AUDITED_PAPERS = (
    "Impact of AI-agent-supported collaborative learning",
    "Agent4Edu",
    "Classroom Simulacra",
    "Pedagogical AI conversational agents in higher education",
    "LLM Agents for Education",
    "EduPlanner",
    "MEDCO",
    "SEFL",
    "AAAR-1.0",
    "The role of large language models in personalized learning",
    "MDAgents",
)

AUDIT_FIELDS = (
    "作者与出版信息",
    "研究设计",
    "智能体定义",
    "数据和评价",
    "可借鉴写法",
    "不可外推之处",
)


def test_reference_audit_covers_direct_comparators():
    text = (ROOT / "reference_paper_audit.md").read_text(encoding="utf-8")
    for title in AUDITED_PAPERS:
        assert title in text


def test_reference_audit_uses_complete_stable_entry_fields():
    text = (ROOT / "reference_paper_audit.md").read_text(encoding="utf-8")
    entries = re.split(r"^### \d+\. ", text, flags=re.MULTILINE)[1:]
    assert len(entries) == len(AUDITED_PAPERS)
    for entry in entries:
        for field in AUDIT_FIELDS:
            assert f"- **{field}：**" in entry


def test_reference_audit_keeps_classification_sets():
    text = (ROOT / "reference_paper_audit.md").read_text(encoding="utf-8")
    direct, methods, excluded = (
        text.split("## 直接参照", 1)[1].split("## 方法参照", 1)[0],
        text.split("## 方法参照", 1)[1].split("## 不建议写入正文", 1)[0],
        text.split("## 不建议写入正文", 1)[1].split("## 审计结论", 1)[0],
    )
    for title in AUDITED_PAPERS[:4]:
        assert title in direct
    for title in AUDITED_PAPERS[4:8]:
        assert title in methods
    for title in AUDITED_PAPERS[8:]:
        assert title in excluded


def test_literature_matrix_records_agent_boundaries():
    text = (ROOT / "literature_matrix.md").read_text(encoding="utf-8")
    assert "10.1007/s10639-025-13487-8" in text
    assert "10.1145/3706598.3713773" in text
    for term in (
        "会话内、状态驱动的微观自适应",
        "自然语言回答",
        "提示次数",
        "阶段得分/进度",
        "错误或未答步骤",
        "代码块错误",
        "对话与讲解记录",
        "代码修正结果",
        "可支持的主张",
        "不可外推之处",
    ):
        assert term in text


def _parse_pipe_table(text: str, section_heading: str) -> list[dict[str, str]]:
    section = text.split(section_heading, 1)[1]
    lines = [line for line in section.splitlines() if line.startswith("|")]
    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def test_new_matrix_rows_keep_claim_and_boundary_cells():
    text = (ROOT / "literature_matrix.md").read_text(encoding="utf-8")
    rows = _parse_pipe_table(text, "## 四、外部智能体来源与证据边界")
    assert len(rows) == len(AUDITED_PAPERS)
    for title, row in zip(AUDITED_PAPERS, rows, strict=True):
        assert title in row["完整题名"]
        assert row["可支持的主张"]
        assert row["不可外推之处"]
