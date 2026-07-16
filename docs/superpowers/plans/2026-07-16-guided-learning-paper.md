# CodeSense 三阶段引导式学习论文写作计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成一篇数据可复核、表述克制的中文研究论文，并为后续英文投稿版准备分析结果、图表和文献依据。

**Architecture:** 将论文工作拆为可复核数据分析、文献证据、正文写作和成稿核验四条链路。分析脚本只读取匿名导出 ZIP，根据 Git 提交时间划分版本，生成正文引用的统计表和图表；中文稿中的每个数字都能追溯到生成结果，研究判断与事实统计分开记录。

**Tech Stack:** Python 3、标准库 `csv/json/zipfile/datetime/statistics`、pandas、statsmodels、matplotlib、pytest、Markdown、Word `.docx`

## Global Constraints

- 研究定位为设计型研究与回顾性学习分析，不写成随机对照实验。
- 参与方式表述为“自主选择进入、受到低门槛课程过程分鼓励”，不得写成完全自愿或强制使用。
- 全量样本为492次引导式学习会话；稳定版本主样本为2026年6月28日00:26（北京时间）以后建立的398次会话。
- Git 提交时间使用北京时间，平台数据时间按 UTC 解析；版本切换允许分钟级部署误差。
- 第二阶段统一称为“代码重构阶段”；只有早期拖拽版本称为 Parsons 型代码块重构。
- 代码提交结果只作探索性关联分析，不作因果解释。
- 不把117个学生账户写成117名引导式学习参与者；实际进入引导式学习的学生为42人。
- 匿名研究 ZIP 不纳入 Git，不复制到仓库。
- 学生原始代码、对话正文、姓名、学号、邮箱和数据库连接信息不得进入论文仓库。
- 中文自然语言初稿完成后使用 `humanizer-zh` 进行二次审阅，技术字段、数字和直接引用保持不变。

---

### Task 1: 建立论文工作目录和数据来源记录

**Files:**
- Create: `research/guided_learning_paper/README.md`
- Create: `research/guided_learning_paper/data_provenance.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-07-16-guided-learning-paper-design.md`
- Consumes: 外部匿名数据包 `C:\Users\amana\Downloads\codesense-research-export-20260716T090300Z.zip`
- Produces: 后续分析和写作统一使用的数据口径、时间口径和目录说明

- [ ] **Step 1: 创建论文目录说明**

在 `research/guided_learning_paper/README.md` 中写明：

```markdown
# 三阶段引导式学习论文工作区

- `manuscript_zh.md`：中文论文正文
- `literature_matrix.md`：相关研究证据表
- `data_provenance.md`：数据来源、版本边界和隐私说明
- `results/`：分析脚本生成的统计结果
- `figures/`：论文图表
- `paper_zh.docx`：经核验的中文 Word 稿

匿名数据 ZIP 保存在仓库外，不提交到 Git。
```

- [ ] **Step 2: 记录数据快照**

在 `data_provenance.md` 中记录导出文件名、导出时间、文件清单、数据库类型、样本行数、研究时间范围、UTC 与北京时间换算规则，以及以下版本提交：

```text
97d71dae  2026-05-12 21:56 +08  三阶段完整系统
6b666d2d  2026-06-18 14:16 +08  模型升级与阶段1/2图像生成
9e68a822  2026-06-24 17:11 +08  阶段1脚手架与50分后台阈值
67fc252e  2026-06-25 13:24 +08  分题作答与防粘贴
8d68b5df  2026-06-26 00:34 +08  阶段2改为逐步选择/填空
65c981d0  2026-06-28 00:26 +08  测验版稳定边界
```

- [ ] **Step 3: 阻止研究数据误提交**

在 `.gitignore` 末尾加入：

```gitignore
# Research datasets contain anonymized but non-public course records
research/guided_learning_paper/data/
research/guided_learning_paper/*.zip
research/guided_learning_paper/results/raw/
```

- [ ] **Step 4: 核验隐私边界**

运行：

```powershell
git diff --check
git status --short
```

预期：只出现本任务创建或修改的三个文件，现有 `.claude/settings.local.json`、`static/images/generated/` 和 `static/uploads/` 保持未暂存。

- [ ] **Step 5: 提交**

```powershell
git add -- .gitignore research/guided_learning_paper/README.md research/guided_learning_paper/data_provenance.md
git commit -m "docs: establish guided learning paper workspace"
```

### Task 2: 实现可复核的数据分析脚本

**Files:**
- Create: `scripts/analyze_guided_learning_research.py`
- Create: `tests/test_guided_learning_research_analysis.py`

**Interfaces:**
- Consumes: ZIP 路径参数 `--input`
- Consumes: 输出目录参数 `--output-dir`
- Produces: `analysis_summary.json`
- Produces: `version_summary.csv`
- Produces: `stage_funnel.csv`
- Produces: `student_usage.csv`
- Produces: `submission_associations.csv`

- [ ] **Step 1: 为时间和版本归类编写失败测试**

测试固定以下接口：

```python
from datetime import datetime

from scripts.analyze_guided_learning_research import (
    VersionBoundary,
    classify_version,
    parse_platform_timestamp,
)


def test_platform_timestamp_is_parsed_as_utc():
    value = parse_platform_timestamp("2026-06-27T16:26:42")
    assert value.tzinfo is not None
    assert value.hour == 16


def test_stable_boundary_starts_at_commit_in_utc():
    boundaries = [
        VersionBoundary(
            name="V5",
            starts_at_utc=datetime.fromisoformat("2026-06-27T16:26:42+00:00"),
        )
    ]
    assert classify_version(
        datetime.fromisoformat("2026-06-27T16:26:42+00:00"),
        boundaries,
    ) == "V5"
```

- [ ] **Step 2: 运行测试并确认失败**

运行：

```powershell
py -3 -m pytest tests/test_guided_learning_research_analysis.py -v
```

预期：因分析模块不存在而在收集阶段失败。

- [ ] **Step 3: 实现时间与版本接口**

实现以下公开接口：

```python
@dataclass(frozen=True)
class VersionBoundary:
    name: str
    starts_at_utc: datetime


def parse_platform_timestamp(value: str) -> datetime:
    """Parse a naive platform timestamp and attach UTC."""


def classify_version(
    timestamp: datetime,
    boundaries: list[VersionBoundary],
) -> str:
    """Return the latest boundary whose start is not after timestamp."""
```

版本边界按北京时间减8小时转换为 UTC，不在函数中使用本机时区。

- [ ] **Step 4: 为会话漏斗和重复使用编写失败测试**

使用内存中的最小 CSV 夹具验证：

```python
def test_usage_summary_counts_repeat_users_and_completion():
    sessions = [
        {"anonymous_session_id": "s1", "anonymous_user_id": "u1", "anonymous_assignment_id": "a1", "status": "completed"},
        {"anonymous_session_id": "s2", "anonymous_user_id": "u1", "anonymous_assignment_id": "a2", "status": "in_progress"},
        {"anonymous_session_id": "s3", "anonymous_user_id": "u2", "anonymous_assignment_id": "a1", "status": "completed"},
    ]
    result = summarize_usage(sessions)
    assert result["users"] == 2
    assert result["repeat_users"] == 1
    assert result["cross_assignment_users"] == 1
    assert result["completed_sessions"] == 2
```

- [ ] **Step 5: 实现 ZIP 读取和描述统计**

脚本使用 `zipfile.ZipFile` 直接读取 CSV，不把原始表释放到磁盘。实现：

```python
def read_csv_from_zip(archive: ZipFile, filename: str) -> list[dict[str, str]]:
    raw = archive.read(filename).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(raw)))


def summarize_usage(sessions: list[dict]) -> dict[str, int | float]:
    by_user: dict[str, list[dict]] = defaultdict(list)
    for row in sessions:
        by_user[row["anonymous_user_id"]].append(row)
    repeat_users = sum(len(rows) >= 2 for rows in by_user.values())
    cross_assignment_users = sum(
        len({row["anonymous_assignment_id"] for row in rows}) >= 2
        for rows in by_user.values()
    )
    completed_sessions = sum(
        row["status"].strip().lower() == "completed" for row in sessions
    )
    return {
        "users": len(by_user),
        "repeat_users": repeat_users,
        "cross_assignment_users": cross_assignment_users,
        "completed_sessions": completed_sessions,
    }


def build_stage_funnel(sessions: list[dict], logs: list[dict]) -> list[dict]:
    stage_passes: dict[int, set[str]] = {1: set(), 2: set(), 3: set()}
    for row in logs:
        if row["event_type"] == "stage_pass":
            stage_passes[int(row["stage"])].add(row["anonymous_session_id"])
    return [
        {
            "step": "stage1_scored",
            "sessions": sum(bool(row["stage1_score"]) for row in sessions),
        },
        {
            "step": "reached_stage2",
            "sessions": sum(int(row["current_stage"]) >= 2 for row in sessions),
        },
        {"step": "stage1_pass", "sessions": len(stage_passes[1])},
        {
            "step": "stage2_completed",
            "sessions": sum(as_bool(row["stage2_completed"]) for row in sessions),
        },
        {
            "step": "stage3_completed",
            "sessions": sum(as_bool(row["stage3_completed"]) for row in sessions),
        },
    ]


def build_version_summary(
    sessions: list[dict],
    logs: list[dict],
    boundaries: list[VersionBoundary],
) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in sessions:
        started_at = parse_platform_timestamp(row["started_at"])
        grouped[classify_version(started_at, boundaries)].append(row)
    return [
        {
            "version": version,
            "sessions": len(rows),
            "users": len({row["anonymous_user_id"] for row in rows}),
            "assignments": len(
                {row["anonymous_assignment_id"] for row in rows}
            ),
            "completed_sessions": sum(
                row["status"].strip().lower() == "completed" for row in rows
            ),
        }
        for version, rows in grouped.items()
    ]
```

同时实现：

```python
def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}
```

阶段通过按每个会话是否至少出现一次 `stage_pass` 去重，不能直接累计日志条数。

- [ ] **Step 6: 为事件截断活跃时长编写失败测试**

```python
def test_active_seconds_caps_long_idle_gaps():
    events = [
        datetime.fromisoformat("2026-07-01T00:00:00+00:00"),
        datetime.fromisoformat("2026-07-01T00:02:00+00:00"),
        datetime.fromisoformat("2026-07-01T01:02:00+00:00"),
    ]
    assert active_seconds(events, gap_cap_seconds=600) == 720
```

- [ ] **Step 7: 实现活跃时长和命令行输出**

`active_seconds()` 对每个相邻事件间隔取 `min(actual_gap, gap_cap_seconds)`。命令行示例：

```powershell
py -3 scripts/analyze_guided_learning_research.py `
  --input "C:\Users\amana\Downloads\codesense-research-export-20260716T090300Z.zip" `
  --output-dir "research/guided_learning_paper/results"
```

脚本完成时打印输入文件、输出目录、会话数、日志数和稳定版本会话数，不打印任何正文或身份字段。

- [ ] **Step 8: 运行测试**

```powershell
py -3 -m pytest tests/test_guided_learning_research_analysis.py -v
```

预期：全部通过。

- [ ] **Step 9: 提交**

```powershell
git add -- scripts/analyze_guided_learning_research.py tests/test_guided_learning_research_analysis.py
git commit -m "feat: add reproducible guided learning analysis"
```

### Task 3: 冻结统计结果并进行交叉核验

**Files:**
- Create: `research/guided_learning_paper/results/analysis_summary.json`
- Create: `research/guided_learning_paper/results/version_summary.csv`
- Create: `research/guided_learning_paper/results/stage_funnel.csv`
- Create: `research/guided_learning_paper/results/student_usage.csv`
- Create: `research/guided_learning_paper/results/submission_associations.csv`
- Create: `research/guided_learning_paper/results/validation_notes.md`

**Interfaces:**
- Consumes: Task 2 分析脚本
- Produces: 正文唯一允许引用的统计结果集

- [ ] **Step 1: 运行全量分析**

```powershell
py -3 scripts/analyze_guided_learning_research.py `
  --input "C:\Users\amana\Downloads\codesense-research-export-20260716T090300Z.zip" `
  --output-dir "research/guided_learning_paper/results"
```

预期至少复现：

```text
thinking_sessions=492
thinking_stage_logs=9940
guided_users=42
users_with_completed_session=34
stable_version_sessions=398
stable_version_completed_sessions=224
```

- [ ] **Step 2: 核验全量采用统计**

确认并记录：

```text
exactly_one_session_users=5
repeat_users=37
cross_assignment_users=36
users_with_at_least_5_sessions=26
users_with_at_least_10_sessions=18
top_10_user_session_share=57.7%
```

- [ ] **Step 3: 核验全量阶段漏斗**

确认并记录：

```text
stage1_scored_sessions=382
reached_stage2_sessions=376
stage2_completed_sessions=270
stage3_completed_sessions=250
```

如果脚本结果与这些已核验数值不一致，停止写作并检查字段解析、去重规则和版本边界，不手工覆盖生成文件。

- [ ] **Step 4: 核验探索性关联模型**

在 `validation_notes.md` 中记录模型单位、样本筛选、系数、标准误、置信区间和 p 值。至少核验：

```text
首次提交前使用引导 -> 首次完全通过：
coef=-0.0188, p=0.3896, 95% CI=[-0.0616, 0.0240]

首次提交前使用引导 -> 最终沙箱通过率：
coef=-0.0042, p=0.7182, 95% CI=[-0.0273, 0.0188]

首次提交前使用引导 -> 提交尝试次数：
coef=0.1032, p=0.5052
```

- [ ] **Step 5: 检查生成文件**

```powershell
Get-ChildItem research/guided_learning_paper/results | Select-Object Name,Length
git diff --check
```

预期：所有结果文件非空，不含姓名、学号、邮箱、对话正文或代码正文。

- [ ] **Step 6: 提交**

```powershell
git add -- research/guided_learning_paper/results
git commit -m "data: freeze guided learning paper results"
```

### Task 4: 建立相关研究和投稿方向证据表

**Files:**
- Create: `research/guided_learning_paper/literature_matrix.md`
- Create: `research/guided_learning_paper/target_journals.md`

**Interfaces:**
- Consumes: 官方期刊范围页、原始论文和系统综述
- Produces: 引言、相关研究和投稿建议使用的可追溯来源

- [ ] **Step 1: 检索四类相关研究**

只使用论文原文、出版社页面、会议正式页面和期刊官方页面。检索主题：

```text
programming education scaffolding self-explanation
Parsons problems programming systematic review
learning by teaching teachable agents programming education
generative AI pedagogical agents programming education
```

- [ ] **Step 2: 建立文献矩阵**

每篇来源记录：

```markdown
| 来源 | 场景与样本 | 学习活动 | 研究设计 | 主要发现 | 与本文关系 | 可支持的句子 |
```

至少覆盖：

- 一篇 Parsons Problems 系统综述；
- 两篇思路外化或 self-explanation 研究；
- 两篇 learning-by-teaching 或 teachable agent 研究；
- 三篇生成式AI编程教育研究；
- 两篇真实课堂学习分析或设计型研究。

- [ ] **Step 3: 核查投稿期刊**

按最新官方 scope 核查以下期刊：

```text
Education and Information Technologies
Journal of Computer Assisted Learning
Interactive Learning Environments
Computers and Education: Artificial Intelligence
International Journal of Artificial Intelligence in Education
```

记录研究范围契合度、常见文章类型、当前是否接受相关主题，以及本文在补充伦理材料和质性证据前后的适配程度。不得仅凭期刊影响因子排序。

- [ ] **Step 4: 提交**

```powershell
git add -- research/guided_learning_paper/literature_matrix.md research/guided_learning_paper/target_journals.md
git commit -m "docs: add guided learning literature and journal matrix"
```

### Task 5: 起草系统设计与研究方法

**Files:**
- Create: `research/guided_learning_paper/manuscript_zh.md`

**Interfaces:**
- Consumes: 论文设计、数据来源记录、文献矩阵和冻结结果
- Produces: 可独立审阅的第3、4节正文

- [ ] **Step 1: 建立正文骨架**

正文固定使用：

```markdown
# 面向程序设计学习的三阶段引导式学习设计与课堂应用

## 摘要
## 关键词
## 1 引言
## 2 相关研究
## 3 三阶段引导式学习设计
## 4 研究方法
## 5 研究结果
## 6 讨论
## 7 局限与结论
## 参考文献
```

- [ ] **Step 2: 写第3节系统设计**

分别说明设计目标、思路外化、代码重构、角色反转教学、数据记录和版本迭代。每个阶段包括学生任务、AI行为、通过条件和记录字段，不使用产品宣传语。

- [ ] **Step 3: 写第4节研究场景和参与方式**

明确写入学校、年级、专业、两个自然班、数据结构课程设计、可直接编程或自主进入引导、班级群鼓励及10分过程分的宽松执行方式。

- [ ] **Step 4: 写第4节数据与方法**

定义三种样本口径、四个研究问题、事件去重、活跃时长、版本边界、学生—作业分析单位和固定效应模型。解释为何稳定版本是主分析样本、全量数据用于采用分析。

- [ ] **Step 5: 写伦理和隐私**

说明数据来自正常教学活动、分析发生在课程活动后、导出数据已匿名化、研究不会追溯改变成绩，以及投稿前需确认伦理审查或豁免要求。

- [ ] **Step 6: 数字一致性检查**

```powershell
Select-String -Path research/guided_learning_paper/manuscript_zh.md `
  -Pattern '492|9940|398|224|42|34|117|1858'
```

逐项与 `analysis_summary.json` 核对。

- [ ] **Step 7: 提交**

```powershell
git add -- research/guided_learning_paper/manuscript_zh.md
git commit -m "docs: draft guided learning design and methods"
```

### Task 6: 写作结果并生成论文图表

**Files:**
- Modify: `research/guided_learning_paper/manuscript_zh.md`
- Create: `scripts/plot_guided_learning_paper.py`
- Create: `research/guided_learning_paper/figures/stage_funnel.png`
- Create: `research/guided_learning_paper/figures/version_timeline.png`
- Create: `research/guided_learning_paper/figures/usage_distribution.png`
- Create: `research/guided_learning_paper/figures/sample_flow.png`

**Interfaces:**
- Consumes: Task 3 冻结结果
- Produces: 第5节正文和四张可用于 Word 稿的图

- [ ] **Step 1: 写RQ1结果**

按“42名参与者—37名重复使用者—36名跨作业使用者—会话集中度”的顺序报告。区分人数、会话数和学生—作业对，不用重复使用证明学习效果。

- [ ] **Step 2: 写RQ2结果**

报告全量与稳定版本漏斗、完成率、提示和活跃时长。完成与未完成会话的事件截断活跃时间分别报告中位数：

```text
completed_median_active_minutes=12.54
incomplete_median_active_minutes=7.22
```

- [ ] **Step 3: 写RQ3结果**

报告五个暂定版本的会话数和完成数，并说明早期样本小、使用者重叠以及会话跨界。不能把V5较高完成率写成改版造成的提升。

- [ ] **Step 4: 写RQ4结果**

先报告原始比例，再报告固定效应模型。完整呈现不显著结果和置信区间，并指出首次完全通过率约95%，存在天花板效应。

- [ ] **Step 5: 生成四张图**

绘图脚本统一：

```python
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
```

图像以300 DPI PNG输出，使用色盲友好配色；漏斗图显示人数和比例，版本时间线同时显示功能变化与数据边界，使用分布图避免显示匿名用户ID。

- [ ] **Step 6: 视觉核验**

逐张查看图片，确认中文字体正常、标签不重叠、百分比与CSV一致、没有身份字段。

- [ ] **Step 7: 提交**

```powershell
git add -- scripts/plot_guided_learning_paper.py research/guided_learning_paper/manuscript_zh.md research/guided_learning_paper/figures
git commit -m "docs: add guided learning results and figures"
```

### Task 7: 完成引言、相关研究、讨论和摘要

**Files:**
- Modify: `research/guided_learning_paper/manuscript_zh.md`

**Interfaces:**
- Consumes: 文献矩阵、结果章节和图表
- Produces: 完整中文论文初稿

- [ ] **Step 1: 写相关研究**

按思路外化、Parsons Problems、learning-by-teaching、生成式AI教学智能体四条线索组织。每个研究判断都跟随具体来源，不写“已有大量研究表明”一类模糊归因。

- [ ] **Step 2: 写引言**

引言依次交代程序设计学习问题、现有方法的分散性、三阶段流程、真实课堂研究缺口、研究问题和贡献。创新表述限定为组合设计与部署分析。

- [ ] **Step 3: 写讨论**

讨论采用五个主题：可实施性、重复使用的含义、阶段二改版、成绩激励与自主选择、结果指标天花板效应。每个主题都区分数据支持的判断和研究者解释。

- [ ] **Step 4: 写局限与结论**

必须覆盖单校两班、无对照、自选择、低门槛成绩激励、版本更新、缺少前后测和访谈、提交结果天花板效应。结论不使用“显著提高”“证明有效”等措辞。

- [ ] **Step 5: 最后写摘要**

摘要包含背景、目的、方法、主要样本、核心描述结果和边界。正文未报告的数字不得首次出现在摘要中。

- [ ] **Step 6: 提交**

```powershell
git add -- research/guided_learning_paper/manuscript_zh.md
git commit -m "docs: complete guided learning manuscript draft"
```

### Task 8: 全文事实核验和自然化审阅

**Files:**
- Modify: `research/guided_learning_paper/manuscript_zh.md`
- Create: `research/guided_learning_paper/manuscript_audit.md`

**Interfaces:**
- Consumes: 完整中文初稿、冻结结果和文献矩阵
- Produces: 数字、引用、术语和语气一致的中文定稿

- [ ] **Step 1: 建立主张核验表**

`manuscript_audit.md` 逐项记录：

```markdown
| 正文主张 | 类型 | 证据文件或来源 | 核验结果 |
|---|---|---|---|
```

类型限定为数据事实、代码事实、课堂事实、文献判断和研究解释。

- [ ] **Step 2: 扫描高风险措辞**

```powershell
Select-String -Path research/guided_learning_paper/manuscript_zh.md `
  -Pattern '证明|导致|显著提高|完全自愿|强制使用|所有学生|Parsons Problem'
```

逐处核验；保留统计学语境中有正式检验依据的“显著”，删除因果暗示。

- [ ] **Step 3: 核验全部数字**

从正文提取数字，与 `analysis_summary.json`、CSV和模型记录逐项核对。版本时间统一为北京时间，数据时间范围注明由 UTC 转换。

- [ ] **Step 4: 核验引用**

每条参考文献在正文至少被引用一次，每个文献性判断都有来源；删除只出现在参考文献表但正文未使用的来源。

- [ ] **Step 5: 使用 humanizer-zh 二次审阅**

删除宣传性语言、模糊归因、过度排比和模板化连接词。保留学术语气、统计数字、模型名、字段名和直接引用原文。

- [ ] **Step 6: 提交**

```powershell
git add -- research/guided_learning_paper/manuscript_zh.md research/guided_learning_paper/manuscript_audit.md
git commit -m "docs: audit and polish guided learning manuscript"
```

### Task 9: 生成并核验中文 Word 稿

**Files:**
- Create: `research/guided_learning_paper/paper_zh.docx`
- Create: `research/guided_learning_paper/rendered/`

**Interfaces:**
- Consumes: 审阅完成的 `manuscript_zh.md` 和四张图
- Produces: 可提交审阅的中文 `.docx`

- [ ] **Step 1: 按通用中文学术稿式生成 Word**

使用A4页面、宋体正文、小四字号、1.5倍行距、连续页码；题目、摘要、关键词、一级和二级标题使用一致样式。图题置于图下，表题置于表上。

- [ ] **Step 2: 插入图表和参考文献**

图表编号与正文引用一致。图片使用原始300 DPI文件，不使用屏幕截图。参考文献格式在确定目标期刊前采用统一的作者—年份工作格式。

- [ ] **Step 3: 渲染检查**

使用文档渲染脚本生成逐页 PNG 和 PDF预览，检查：

- 标题与正文无孤行；
- 图表不跨页断裂；
- 表格不超出页边距；
- 中文字体无替换或乱码；
- 参考文献悬挂缩进一致；
- 页码连续。

- [ ] **Step 4: 修正并再次渲染**

任何布局问题都在 Word 源文件中修正，重新渲染后再检查受影响页面。

- [ ] **Step 5: 提交**

```powershell
git add -- research/guided_learning_paper/paper_zh.docx
git commit -m "docs: add rendered guided learning paper"
```

`rendered/` 只用于视觉核验，不提交到 Git。

## 完成判据

- 分析脚本可从匿名 ZIP 一次性重建全部正文统计结果。
- 正文中的数字与冻结结果逐项一致。
- 四个研究问题均有方法、结果和讨论对应。
- 论文不包含身份信息、原始对话或学生代码。
- 观察性结果没有被表述为因果效果。
- 第二阶段的两个版本得到明确区分。
- 课程过程分的影响得到如实说明。
- 中文 Markdown 稿和经渲染核验的 Word 稿均可供人工审阅。
