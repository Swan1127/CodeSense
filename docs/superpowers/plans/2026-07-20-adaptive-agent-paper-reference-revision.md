# 自适应智能体论文参照修订实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 参考用户提供的11篇教育智能体与多智能体论文，把两篇现有稿件统一修订为“学习方法为创新对象、状态驱动智能体为调节机制、平台为实现手段”的双轨论文，并重新生成经过视觉核验的Word成稿。

**Architecture:** 先建立外部论文与本研究之间的证据矩阵，再修改活动链总览图和两篇正文。所有“智能体”“自适应”和“学生数据”表述都必须能由当前代码、平台日志或提供的PDF核验；现有统计结果保持冻结，不重新解释为学习效果。最后由同一脚本生成两份DOCX，并执行结构测试和逐页渲染检查。

**Tech Stack:** Markdown、Python 3、python-docx、Matplotlib、Pillow、pytest、LibreOffice、Poppler。

## Global Constraints

- 创新对象是“思路外化—程序构建—讲解纠错”的三阶段引导式学习方法，不是CodeSense平台本身。
- 智能体调节限定为“会话内、状态驱动的微观自适应”；不得声称已经形成跨作业长期学习者画像。
- 可核验的学生状态包括自然语言回答、提示次数、阶段得分、答题进度、错误或未作答步骤、代码块错误、对话历史、讲解内容和代码修正结果。
- 不声称三阶段流程提高了学习成绩、算法思维或迁移能力。
- 117名学生、492次会话、9940条阶段日志及其余冻结统计不得因改写而改变。
- 参考论文只支持相应的概念、设计或比较结论，不把其他场景的实验结果外推到本课程。
- 中文正文经过humanizer-zh二次审阅；代码、数字、公式、文献题名和直接引用保持原样。
- 保留 `manuscript_zh.md` 与 `paper_zh.docx`，只更新核心稿和实践稿。

---

### Task 1: 建立外部论文参照审计并补充证据矩阵

**Files:**
- Create: `research/guided_learning_paper/reference_paper_audit.md`
- Modify: `research/guided_learning_paper/literature_matrix.md`
- Create: `tests/test_guided_learning_paper_content.py`

**Interfaces:**
- Consumes: 用户提供的11篇PDF；现有 `literature_matrix.md`；设计稿中的智能体边界。
- Produces: 经过全文核验的来源分级、可支持主张、不可外推边界，以及后续两篇正文使用的固定参考来源集合。

- [ ] **Step 1: 写入失败的内容约束测试**

```python
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
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `py -m pytest tests/test_guided_learning_paper_content.py -q`

Expected: FAIL because `reference_paper_audit.md` does not exist and the new sources are absent from the matrix.

- [ ] **Step 3: 完成11篇论文的分级审计**

`reference_paper_audit.md`必须逐篇记录：题名、作者、出版信息、研究对象、研究设计、智能体定义、数据和评价方式、可供本文借鉴的写法、不可外推之处。采用以下分级：

- 直接参照：编程课AI智能体准实验、Agent4Edu、Classroom Simulacra、教学对话智能体综述；
- 方法参照：LLM Agents for Education、EduPlanner、MEDCO、SEFL；
- 不建议写入正文：AAAR-1.0、MDAgents、宽泛的个性化学习综述，除非某一具体方法判断确实需要它们。

至少核验以下正式来源：

- Wang et al. (2025), *Education and Information Technologies*, DOI `10.1007/s10639-025-13487-8`；
- Xu et al. (2025), CHI 2025, DOI `10.1145/3706598.3713773`；
- Yusuf, Money, & Daylamani-Zad (2025), *Educational Technology Research and Development*, DOI `10.1007/s11423-025-10447-4`；
- Gao et al. (2025), Agent4Edu, AAAI-25。

- [ ] **Step 4: 更新证据矩阵**

每个新增条目必须包含“可支持的主张”和“不可外推之处”。关于编程课准实验的条目明确记录其45人、6周、实验组与控制组设计，同时写明本研究没有相同的分组和前后测。关于Agent4Edu和Classroom Simulacra的条目明确记录其学习者模拟目标，不把模拟智能体与本研究中的真实学生引导混为一谈。

- [ ] **Step 5: 运行测试并提交**

Run: `py -m pytest tests/test_guided_learning_paper_content.py -q`

Expected: PASS.

```bash
git add research/guided_learning_paper/reference_paper_audit.md research/guided_learning_paper/literature_matrix.md tests/test_guided_learning_paper_content.py
git commit -m "docs: audit educational agent reference papers"
```

### Task 2: 把活动链总览图改为“状态—决策—支架”结构

**Files:**
- Modify: `scripts/plot_guided_learning_paper.py:65-195`
- Modify: `tests/test_guided_learning_paper_plots.py`
- Regenerate: `research/guided_learning_paper/figures/activity_chain_evidence.png`

**Interfaces:**
- Consumes: 三阶段方法、可核验学生状态、现有统计证据边界。
- Produces: 一张同时说明学习活动、角色化智能体、状态输入、自动调整和证据边界的总览图。

- [ ] **Step 1: 扩展图表测试以检查自适应图产物**

```python
def test_activity_chain_figure_is_landscape_and_readable(tmp_path):
    results = tmp_path / "results"
    figures = tmp_path / "figures"
    results.mkdir()
    _write_minimal_revised_results(results)

    create_figures(results, figures)

    with Image.open(figures / "activity_chain_evidence.png") as image:
        assert image.width > image.height
        assert image.width >= 3000
        assert image.height >= 1700
```

- [ ] **Step 2: 运行测试并确认失败或暴露旧图尺寸**

Run: `py -m pytest tests/test_guided_learning_paper_plots.py::test_activity_chain_figure_is_landscape_and_readable -q`

Expected: FAIL until the figure canvas and output dimensions are updated.

- [ ] **Step 3: 重构 `_plot_activity_chain_evidence`**

图中固定呈现四层信息：

1. 学生状态输入：回答、提示次数、当前进度、错误类型、对话历史；
2. 智能体调节：诊断当前状态，选择提示强度、追问对象和反馈内容；
3. 三阶段活动：思路外化、程序构建、讲解纠错；
4. 证据边界：日志能观察采用、推进、回退和退出，不能直接观察认知质量与学习增益。

标题使用“状态驱动的三阶段程序设计引导方法”，图中不把平台名称放在视觉中心。第三阶段可标注“教师角色—真实学生—虚拟学生”，但不画成两个完全自治系统。

- [ ] **Step 4: 生成图并运行图表测试**

Run: `py scripts/plot_guided_learning_paper.py`

Expected: `activity_chain_evidence.png` updated with non-zero size.

Run: `py -m pytest tests/test_guided_learning_paper_plots.py -q`

Expected: PASS.

- [ ] **Step 5: 目视检查图像并提交**

使用本地图片查看工具以原始分辨率检查文字是否截断、箭头是否遮挡、黑白打印时层次是否仍可辨认。

```bash
git add scripts/plot_guided_learning_paper.py tests/test_guided_learning_paper_plots.py research/guided_learning_paper/figures/activity_chain_evidence.png
git commit -m "docs: clarify adaptive guided-learning framework"
```

### Task 3: 修订中文核心导向稿

**Files:**
- Modify: `research/guided_learning_paper/manuscript_core_zh.md`
- Modify: `tests/test_guided_learning_paper_content.py`

**Interfaces:**
- Consumes: Task 1的证据审计、Task 2的总览图、冻结统计结果。
- Produces: 以学习方法为主线、对智能体自适应作操作性定义的核心导向稿。

- [ ] **Step 1: 增加核心稿定位测试**

```python
def test_core_manuscript_uses_bounded_adaptive_agent_claims():
    text = (ROOT / "manuscript_core_zh.md").read_text(encoding="utf-8")
    for required in (
        "状态驱动",
        "会话内",
        "提示次数",
        "错误类型",
        "对话历史",
        "平台只是",
    ):
        assert required in text
    for forbidden in (
        "完全自主决策",
        "长期学习者画像",
        "显著提升算法思维",
        "证明了学习效果",
    ):
        assert forbidden not in text
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `py -m pytest tests/test_guided_learning_paper_content.py::test_core_manuscript_uses_bounded_adaptive_agent_claims -q`

Expected: FAIL because the current manuscript has not yet adopted the new framing.

- [ ] **Step 3: 改写摘要和问题提出**

摘要按“问题—方法—场景与数据—发现—边界”组织。开头不写宏观AI趋势，直接说明生成式AI容易替学生完成编程认知活动，因此本文设计三阶段方法。方法段写清117名学生、492次会话、9940条日志和稳定版398次会话。结尾只报告采用与路径发现，不声称学习增益。

问题提出增加与四篇直接参照论文的对话：已有研究分别评估编程课AI智能体效果、模拟学习者行为或梳理教学对话智能体；本文研究真实学生如何进入和推进一个状态驱动的三阶段活动链。

- [ ] **Step 4: 改写理论与系统部分**

将2.1调整为“从答案生成转向状态驱动的活动调节”。新增操作性定义：

> 本文所称智能体，是在既定教学角色与活动规则下，读取学生当前会话状态，并据此生成提示、诊断或追问的生成式人工智能组件。其自适应发生在单次会话内部，不等同于跨作业学习者建模。

3.2按“状态输入—调节规则—学习者动作—日志证据”写三个阶段。平台功能名称、接口和技术栈放在说明性位置，不作为创新结论。

- [ ] **Step 5: 改写讨论和参考文献**

讨论增加三点：状态驱动调节与固定提示的差别；本研究与学习者模拟智能体的边界；下一轮如何把会话内状态扩展为经过同意的纵向学生模型。对编程课准实验只作方法比较，明确本研究没有其对照条件。

参考文献按正文首次引用顺序重新编号，逐项核对作者、年份、期刊或会议、页码和DOI。不得保留正文未引用的新增来源。

- [ ] **Step 6: 运行内容测试、人工核对数字并提交**

Run: `py -m pytest tests/test_guided_learning_paper_content.py -q`

Expected: PASS.

Run: `Select-String -Path research/guided_learning_paper/manuscript_core_zh.md -Pattern '117|492|9940|398|224|89|74|11'`

Expected: all frozen sample counts remain present in their correct contexts.

```bash
git add research/guided_learning_paper/manuscript_core_zh.md tests/test_guided_learning_paper_content.py
git commit -m "docs: reframe core paper around adaptive guidance"
```

### Task 4: 修订计算机教育实践稿

**Files:**
- Modify: `research/guided_learning_paper/manuscript_practice_zh.md`
- Modify: `tests/test_guided_learning_paper_content.py`

**Interfaces:**
- Consumes: 与核心稿相同的事实和参考文献，但降低统计模型篇幅，强化课程实施与可复用规则。
- Produces: 面向程序设计教师、能够说明“如何根据学生状态调整支架”的实践稿。

- [ ] **Step 1: 增加实践稿定位测试**

```python
def test_practice_manuscript_explains_teacher_reusable_adaptation():
    text = (ROOT / "manuscript_practice_zh.md").read_text(encoding="utf-8")
    for required in (
        "学生状态",
        "提示强度",
        "验证失败",
        "讲解质量",
        "会话内",
    ):
        assert required in text
    assert "系统创新" not in text
    assert "学习方法" in text
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `py -m pytest tests/test_guided_learning_paper_content.py::test_practice_manuscript_explains_teacher_reusable_adaptation -q`

Expected: FAIL until the practice manuscript is revised.

- [ ] **Step 3: 重写实践稿的设计与实施部分**

第2节不再按页面功能罗列，而是用一张“状态—调节—学习动作”表解释每一阶段：教师预先定义什么、智能体读取什么、系统自动调整什么、学生必须完成什么。明确第一阶段提示随请求次数递进，第二阶段按错误步骤或验证失败诊断，第三阶段按最近讲解继续追问并生成需要修正的错误代码。

- [ ] **Step 4: 重写教学反思**

把现有六条建议收束为四个可操作原则：入口解释与低门槛开始；失败后的支架升级；讲解和纠错的双动作保留；激励、伦理和版本记录分开管理。每条原则至少连接一个平台过程指标，不使用抽象的“促进深度学习”。

- [ ] **Step 5: 更新参考文献、运行测试并提交**

实践稿优先引用编程课AI智能体准实验和教育智能体综述；Agent4Edu与Classroom Simulacra只在解释智能体差异时简短出现。

Run: `py -m pytest tests/test_guided_learning_paper_content.py -q`

Expected: PASS.

```bash
git add research/guided_learning_paper/manuscript_practice_zh.md tests/test_guided_learning_paper_content.py
git commit -m "docs: strengthen adaptive guidance in practice paper"
```

### Task 5: 人性化审阅、同行评审复盘与修订记录

**Files:**
- Modify: `research/guided_learning_paper/peer_review_audit_v2.md`
- Modify: `research/guided_learning_paper/revision_log.md`
- Modify: `research/guided_learning_paper/next_study_protocol.md`
- Modify: `research/guided_learning_paper/README.md`

**Interfaces:**
- Consumes: Task 3和Task 4的定稿文本。
- Produces: 能追踪新增文献、智能体定义、措辞变化和下一轮实验需求的审计记录。

- [ ] **Step 1: 执行高风险措辞扫描**

Run:

```powershell
Select-String -Path research\guided_learning_paper\manuscript_*_zh.md -Pattern '证明|导致|显著提升|完全自主|长期画像|深度理解|算法思维得到提升|革命性|开创性'
```

Expected: every match is either removed or immediately bounded by evidence and study design.

- [ ] **Step 2: 按humanizer-zh逐段审阅两篇正文**

重点删除宣传性语言、模糊归因、机械三段式、否定式排比、重复的“此外”和不必要的破折号。保留学术语气，不把正文改成口语文章；数字、公式、参考文献和方法术语不改写。

- [ ] **Step 3: 更新同行评审审计和修订记录**

新增“智能体定义是否可由系统实现核验”“会话内自适应是否被误写为长期个性化”“外部论文是否被不当外推”三个检查项。修订记录列明吸收了哪些论文的哪种写法，并注明没有采纳哪些强主张。

- [ ] **Step 4: 更新下一轮研究方案**

下一轮方案增加自适应机制消融：固定提示组与状态驱动提示组；记录提示强度、错误类型、解释质量和迁移任务；若计划跨作业建模，必须另行取得研究同意并规定数据最小化和退出机制。

- [ ] **Step 5: 运行内容测试并提交**

Run: `py -m pytest tests/test_guided_learning_paper_content.py -q`

Expected: PASS.

```bash
git add research/guided_learning_paper/peer_review_audit_v2.md research/guided_learning_paper/revision_log.md research/guided_learning_paper/next_study_protocol.md research/guided_learning_paper/README.md
git commit -m "docs: audit adaptive agent paper claims"
```

### Task 6: 重建两份Word并完成视觉验收

**Files:**
- Regenerate: `research/guided_learning_paper/paper_core_zh.docx`
- Regenerate: `research/guided_learning_paper/paper_practice_zh.docx`
- Test: `tests/test_guided_learning_paper_docx.py`

**Interfaces:**
- Consumes: 最终Markdown稿和更新后的图表。
- Produces: 两份结构、内容和版式一致的可投稿Word稿。

- [ ] **Step 1: 运行全部自动化测试**

Run: `py -m pytest tests -q --disable-warnings`

Expected: all tests pass before DOCX regeneration.

- [ ] **Step 2: 生成两份Word**

```powershell
py scripts\build_guided_learning_paper_docx.py --input-md research\guided_learning_paper\manuscript_core_zh.md --output-docx research\guided_learning_paper\paper_core_zh.docx
py scripts\build_guided_learning_paper_docx.py --input-md research\guided_learning_paper\manuscript_practice_zh.md --output-docx research\guided_learning_paper\paper_practice_zh.docx
```

Expected: both commands exit 0 and both files are larger than 100 KB.

- [ ] **Step 3: 检查DOCX结构**

```python
from pathlib import Path
from docx import Document

root = Path("research/guided_learning_paper")
for name in ("paper_core_zh.docx", "paper_practice_zh.docx"):
    path = root / name
    doc = Document(path)
    assert path.stat().st_size > 100_000
    assert doc.core_properties.author == ""
    assert doc.core_properties.last_modified_by == ""
    assert len(doc.inline_shapes) >= 3
```

- [ ] **Step 4: 渲染并逐页检查**

优先运行文档技能的 `render_docx.py`。若包装脚本仍因Poppler批处理路径失效而卡住，使用已验证的LibreOffice独立配置目录把DOCX转成PDF，再直接调用：

`C:\Users\amana\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe`

以120 DPI生成每页PNG。逐页检查标题层级、公式、表格、图题、参考文献、分页、缺字和大面积空白。任何正文或版式修改后都必须重新生成并重新渲染。

- [ ] **Step 5: 最终测试、差异检查并提交**

Run: `py -m pytest tests -q --disable-warnings`

Expected: all tests pass.

Run: `git diff --check`

Expected: no whitespace errors.

```bash
git add research/guided_learning_paper/paper_core_zh.docx research/guided_learning_paper/paper_practice_zh.docx
git commit -m "docs: rebuild adaptive guided-learning papers"
```

## Final Verification

- [ ] `reference_paper_audit.md`完整覆盖11篇用户提供的论文并说明采用层级。
- [ ] 两篇正文都把学习方法放在平台之前，把智能体定义为会话内状态驱动调节机制。
- [ ] 两篇正文没有新增因果性学习效果主张。
- [ ] 图1能够直接看出“学生状态—智能体调节—三阶段活动—日志证据边界”。
- [ ] 冻结统计与 `analysis_summary.json`、CSV结果一致。
- [ ] 两份DOCX通过结构检查和逐页视觉检查。
- [ ] `py -m pytest tests -q --disable-warnings`全部通过。
- [ ] Git提交不包含 `.tmp/` 和 `static/uploads/`。
