# 三阶段引导式学习论文改版实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从同一份匿名课程数据中重建可复核的行为分析，形成中文核心导向稿、计算机教育实践稿及两份经过逐页检查的Word文档。

**Architecture:** 保留第一版论文和结果作为基线，在现有分析脚本上增加稳定版路径、事件转换、阶段摩擦和首次提交前分级暴露分析。所有正文数字只从冻结的JSON/CSV结果读取；图表和Word文档由脚本重复生成，研究解释与数据处理分离。

**Tech Stack:** Python 3.13、pandas、statsmodels、matplotlib、python-docx、pytest、Git LFS、Microsoft Word COM、Poppler。

## Global Constraints

- 工作分支固定为 `codex/guided-learning-paper-revision`，工作目录为 `E:\CodeSense\源代码\.worktrees\guided-learning-paper-revision`。
- 匿名源数据固定为 `C:\Users\amana\Downloads\codesense-research-export-20260716T090300Z.zip`，不得复制进仓库或提交到Git。
- 保留 `research/guided_learning_paper/manuscript_zh.md` 和 `paper_zh.docx`，不得覆盖第一版。
- 研究对象表述为沈阳航空航天大学2024级网络工程1、2班数据结构课程设计学生。
- 采用情境统一表述为“低门槛成绩激励下的自愿采用”：功能可不使用，相关表现约占课程设计成绩10%，多数学生获得8—9分。
- 稳定版边界固定为V5开始时间 `2026-06-27T16:26:42+00:00`；版本部署时间由Git提交时间近似，不估计版本因果效果。
- 活跃时长主口径把相邻事件间隔截断为300秒。
- 事件转换先折叠连续同类事件；正文只展示两组合计至少10次且涉及至少5个不同会话的转换。
- 首次提交前暴露分为 `none`、`incomplete`、`completed`，必须用首次提交时间之前的 `started_at` 和 `completed_at` 判定。
- 固定效应结果只称为调整后的条件关联，不使用“影响”“提升”“导致”等因果措辞。
- 不把重复使用解释为内在动机，不把事件类型解释为认知质量，不把会话建立解释为有效学习开始。
- 不虚构伦理批件、作者单位、基金、通信作者或利益冲突信息。
- 中文正文和研究说明完成事实初稿后，使用 `humanizer-zh` 进行第二遍自然化审阅。
- Word文档必须逐页渲染检查；LibreOffice当前损坏，优先使用Word COM转PDF，再用Poppler生成页面PNG。
- 仓库已有的未跟踪目录 `static/uploads/` 不属于本任务，不读取、不修改、不提交。

---

## 文件结构

### 修改

- `scripts/analyze_guided_learning_research.py`：新增路径、转换、摩擦、分级暴露和模型分析。
- `scripts/plot_guided_learning_paper.py`：生成四张核心图和一张附录版本图。
- `scripts/build_guided_learning_paper_docx.py`：改为接收Markdown输入和DOCX输出，支持生成两份稿件。
- `tests/test_guided_learning_research_analysis.py`：覆盖新增统计口径。
- `tests/test_guided_learning_paper_plots.py`：覆盖新版图表集合。
- `research/guided_learning_paper/literature_matrix.md`：补充并核验中文和国际研究。
- `research/guided_learning_paper/README.md`：记录可重复生成命令和双轨产物。

### 新建

- `tests/test_guided_learning_paper_docx.py`：验证两份Word文档的结构和元数据。
- `research/guided_learning_paper/results/stable_session_paths.csv`：稳定版会话路径。
- `research/guided_learning_paper/results/stage_friction.csv`：阶段摩擦中位数、四分位距和样本量。
- `research/guided_learning_paper/results/event_transitions.csv`：完成与未完成会话的完整事件转换。
- `research/guided_learning_paper/results/exposure_raw_rates.csv`：三类暴露的原始结果。
- `research/guided_learning_paper/results/exposure_models.csv`：双固定效应模型。
- `research/guided_learning_paper/figures/activity_chain_evidence.png`：活动链及证据边界。
- `research/guided_learning_paper/figures/adoption_profile.png`：采用、重复使用与跨作业使用。
- `research/guided_learning_paper/figures/stable_session_paths.png`：稳定版会话路径。
- `research/guided_learning_paper/figures/event_transitions.png`：完成与未完成会话的主要事件转换。
- `research/guided_learning_paper/figures/appendix_version_timeline.png`：版本时间线附图。
- `research/guided_learning_paper/peer_review_audit_v2.md`：第二轮模拟外审。
- `research/guided_learning_paper/revision_log.md`：主张、证据和改动记录。
- `research/guided_learning_paper/next_study_protocol.md`：下一轮对比研究方案。
- `research/guided_learning_paper/manuscript_core_zh.md`：中文核心导向稿。
- `research/guided_learning_paper/manuscript_practice_zh.md`：计算机教育实践稿。
- `research/guided_learning_paper/paper_core_zh.docx`：核心稿Word版。
- `research/guided_learning_paper/paper_practice_zh.docx`：实践稿Word版。

---

### Task 1: 增加稳定版会话路径与阶段摩擦分析

**Files:**
- Modify: `scripts/analyze_guided_learning_research.py`
- Modify: `tests/test_guided_learning_research_analysis.py`

**Interfaces:**
- Consumes: `sessions: list[dict]`、`logs: list[dict]`，字段来自匿名导出CSV。
- Produces: `classify_session_path(session) -> str`、`build_stable_session_paths(sessions) -> list[dict]`、`summarize_stage_friction(sessions, logs) -> list[dict]`。

- [ ] **Step 1: 写入路径分类失败测试**

```python
def test_stable_session_paths_use_mutually_exclusive_states():
    sessions = [
        {"stage1_score": "", "current_stage": "1", "stage2_completed": "0", "stage3_completed": "0"},
        {"stage1_score": "50", "current_stage": "2", "stage2_completed": "0", "stage3_completed": "0"},
        {"stage1_score": "50", "current_stage": "3", "stage2_completed": "1", "stage3_completed": "0"},
        {"stage1_score": "50", "current_stage": "3", "stage2_completed": "1", "stage3_completed": "1"},
    ]

    rows = build_stable_session_paths(sessions)

    assert [row["path"] for row in rows] == [
        "no_valid_stage1",
        "stage2_incomplete",
        "stage3_incomplete",
        "all_completed",
    ]
    assert sum(row["sessions"] for row in rows) == 4
```

- [ ] **Step 2: 运行路径测试并确认失败**

Run: `py -m pytest tests/test_guided_learning_research_analysis.py::test_stable_session_paths_use_mutually_exclusive_states -v`

Expected: FAIL，提示 `build_stable_session_paths` 尚未定义。

- [ ] **Step 3: 实现互斥路径分类**

```python
PATH_LABELS = {
    "no_valid_stage1": "未形成第一阶段有效记录",
    "stage2_incomplete": "到达第二阶段但未完成",
    "stage3_incomplete": "完成第二阶段但未完成第三阶段",
    "all_completed": "完成全部阶段",
}


def classify_session_path(session: dict) -> str:
    if as_bool(session["stage3_completed"]):
        return "all_completed"
    if as_bool(session["stage2_completed"]):
        return "stage3_incomplete"
    if int(session["current_stage"] or 1) >= 2 or bool(session["stage1_score"]):
        return "stage2_incomplete"
    return "no_valid_stage1"


def build_stable_session_paths(sessions: list[dict]) -> list[dict]:
    counts = {name: 0 for name in PATH_LABELS}
    for session in sessions:
        counts[classify_session_path(session)] += 1
    total = len(sessions)
    return [
        {
            "path": name,
            "label": label,
            "sessions": counts[name],
            "percent": round(100 * counts[name] / total, 2) if total else 0.0,
        }
        for name, label in PATH_LABELS.items()
    ]
```

- [ ] **Step 4: 写入阶段摩擦失败测试**

```python
def test_stage_friction_reports_median_iqr_and_active_minutes():
    sessions = [
        {
            "anonymous_session_id": "s1",
            "status": "completed",
            "stage1_hint_count": "1",
            "stage2_hint_count": "2",
            "stage3_teacher_rounds": "3",
            "stage3_student_rounds": "4",
        }
    ]
    logs = [
        {"anonymous_session_id": "s1", "stage": "2", "event_type": "verify_fail", "created_at": "2026-07-01T00:00:00"},
        {"anonymous_session_id": "s1", "stage": "2", "event_type": "verify_fail", "created_at": "2026-07-01T00:02:00"},
        {"anonymous_session_id": "s1", "stage": "3", "event_type": "fix_code", "created_at": "2026-07-01T00:03:00"},
        {"anonymous_session_id": "s1", "stage": "3", "event_type": "chat", "created_at": "2026-07-01T00:13:00"},
    ]

    rows = summarize_stage_friction(sessions, logs)
    keyed = {(row["completion_group"], row["metric"]): row for row in rows}

    assert keyed[("completed", "stage2_verify_fail")]["median"] == 2.0
    assert keyed[("completed", "stage3_fix_code")]["median"] == 1.0
    assert keyed[("completed", "stage3_active_minutes")]["median"] == 5.0
```

- [ ] **Step 5: 运行摩擦测试并确认失败**

Run: `py -m pytest tests/test_guided_learning_research_analysis.py::test_stage_friction_reports_median_iqr_and_active_minutes -v`

Expected: FAIL，提示 `summarize_stage_friction` 尚未定义。

- [ ] **Step 6: 实现阶段摩擦统计**

```python
def _five_number(values: list[float]) -> tuple[int, float | None, float | None, float | None]:
    if not values:
        return 0, None, None, None
    series = pd.Series(values, dtype=float)
    return (
        len(values),
        round(float(series.median()), 2),
        round(float(series.quantile(0.25)), 2),
        round(float(series.quantile(0.75)), 2),
    )


def summarize_stage_friction(
    sessions: list[dict],
    logs: list[dict],
    gap_cap_seconds: int = 300,
) -> list[dict]:
    logs_by_session: dict[str, list[dict]] = defaultdict(list)
    for row in logs:
        logs_by_session[row["anonymous_session_id"]].append(row)
    metrics: dict[tuple[str, str], list[float]] = defaultdict(list)
    for session in sessions:
        session_id = session["anonymous_session_id"]
        group = "completed" if session["status"].strip().lower() == "completed" else "incomplete"
        session_logs = logs_by_session[session_id]
        fixed = {
            "stage1_hints": float(session["stage1_hint_count"] or 0),
            "stage2_hints": float(session["stage2_hint_count"] or 0),
            "stage2_verify_fail": float(sum(row["event_type"] == "verify_fail" for row in session_logs if row["stage"] == "2")),
            "stage3_dialogue_rounds": float(session["stage3_teacher_rounds"] or 0) + float(session["stage3_student_rounds"] or 0),
            "stage3_fix_code": float(sum(row["event_type"] == "fix_code" for row in session_logs if row["stage"] == "3")),
        }
        for metric, value in fixed.items():
            metrics[(group, metric)].append(value)
        for stage in (1, 2, 3):
            times = [
                parse_platform_timestamp(row["created_at"])
                for row in session_logs
                if int(row["stage"]) == stage
            ]
            if times:
                metrics[(group, f"stage{stage}_active_minutes")].append(
                    active_seconds(times, gap_cap_seconds) / 60
                )
    rows = []
    for (group, metric), values in sorted(metrics.items()):
        n, median, q1, q3 = _five_number(values)
        rows.append({"completion_group": group, "metric": metric, "n": n, "median": median, "q1": q1, "q3": q3})
    return rows
```

- [ ] **Step 7: 运行本任务测试**

Run: `py -m pytest tests/test_guided_learning_research_analysis.py -v`

Expected: 全部PASS。

- [ ] **Step 8: 提交**

```powershell
git add scripts/analyze_guided_learning_research.py tests/test_guided_learning_research_analysis.py
git commit -m "feat: analyze stable guided-learning paths"
```

---

### Task 2: 增加事件折叠与转换分析

**Files:**
- Modify: `scripts/analyze_guided_learning_research.py`
- Modify: `tests/test_guided_learning_research_analysis.py`

**Interfaces:**
- Consumes: 稳定版 `sessions` 与按时间记录的 `logs`。
- Produces: `map_event(row) -> str`、`collapse_event_sequence(rows) -> list[str]`、`build_event_transitions(sessions, logs) -> list[dict]`。

- [ ] **Step 1: 写入事件折叠失败测试**

```python
def test_event_sequence_collapses_consecutive_categories():
    logs = [
        {"event_type": "chat", "stage": "3", "created_at": "2026-07-01T00:00:03"},
        {"event_type": "description_submit", "stage": "1", "created_at": "2026-07-01T00:00:01"},
        {"event_type": "description_submit", "stage": "1", "created_at": "2026-07-01T00:00:02"},
        {"event_type": "fix_code", "stage": "3", "created_at": "2026-07-01T00:00:04"},
    ]

    assert collapse_event_sequence(logs) == [
        "description_submit",
        "dialogue",
        "fix_code",
    ]
```

- [ ] **Step 2: 运行折叠测试并确认失败**

Run: `py -m pytest tests/test_guided_learning_research_analysis.py::test_event_sequence_collapses_consecutive_categories -v`

Expected: FAIL，提示 `collapse_event_sequence` 尚未定义。

- [ ] **Step 3: 实现事件映射和折叠**

```python
EVENT_CATEGORY = {
    "description_submit": "description_submit",
    "hint_request": "hint_request",
    "companion_chat": "companion_chat",
    "stage_pass": "stage_pass",
    "verify_fail": "verify_fail",
    "chat": "dialogue",
    "write_code": "generated_error_code",
    "fix_code": "fix_code",
}


def map_event(row: dict) -> str:
    return EVENT_CATEGORY.get(row["event_type"], "other")


def collapse_event_sequence(rows: list[dict]) -> list[str]:
    ordered = sorted(rows, key=lambda row: parse_platform_timestamp(row["created_at"]))
    collapsed: list[str] = []
    for row in ordered:
        category = map_event(row)
        if not collapsed or collapsed[-1] != category:
            collapsed.append(category)
    return collapsed
```

- [ ] **Step 4: 写入转换计数失败测试**

```python
def test_event_transitions_split_completed_and_incomplete_sessions():
    sessions = [
        {"anonymous_session_id": "done", "status": "completed"},
        {"anonymous_session_id": "open", "status": "in_progress"},
    ]
    logs = [
        {"anonymous_session_id": "done", "event_type": "description_submit", "stage": "1", "created_at": "2026-07-01T00:00:01"},
        {"anonymous_session_id": "done", "event_type": "stage_pass", "stage": "1", "created_at": "2026-07-01T00:00:02"},
        {"anonymous_session_id": "open", "event_type": "description_submit", "stage": "1", "created_at": "2026-07-01T00:00:01"},
        {"anonymous_session_id": "open", "event_type": "hint_request", "stage": "1", "created_at": "2026-07-01T00:00:02"},
    ]

    rows = build_event_transitions(sessions, logs)

    assert {(row["completion_group"], row["source"], row["target"], row["count"]) for row in rows} == {
        ("completed", "description_submit", "stage_pass", 1),
        ("incomplete", "description_submit", "hint_request", 1),
    }
    assert all(row["distinct_sessions"] == 1 for row in rows)
```

- [ ] **Step 5: 实现转换频数、会话覆盖与条件比例**

```python
def build_event_transitions(sessions: list[dict], logs: list[dict]) -> list[dict]:
    status = {
        row["anonymous_session_id"]: (
            "completed" if row["status"].strip().lower() == "completed" else "incomplete"
        )
        for row in sessions
    }
    by_session: dict[str, list[dict]] = defaultdict(list)
    for row in logs:
        if row["anonymous_session_id"] in status:
            by_session[row["anonymous_session_id"]].append(row)
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    covered: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    source_totals: dict[tuple[str, str], int] = defaultdict(int)
    for session_id, rows in by_session.items():
        group = status[session_id]
        sequence = collapse_event_sequence(rows)
        for source, target in zip(sequence, sequence[1:]):
            key = (group, source, target)
            counts[key] += 1
            covered[key].add(session_id)
            source_totals[(group, source)] += 1
    return [
        {
            "completion_group": group,
            "source": source,
            "target": target,
            "count": count,
            "distinct_sessions": len(covered[(group, source, target)]),
            "conditional_percent": round(100 * count / source_totals[(group, source)], 2),
            "show_in_main_figure": int(
                sum(counts.get((g, source, target), 0) for g in ("completed", "incomplete")) >= 10
                and len(set().union(*(covered.get((g, source, target), set()) for g in ("completed", "incomplete")))) >= 5
            ),
        }
        for (group, source, target), count in sorted(counts.items())
    ]
```

- [ ] **Step 6: 运行本任务测试**

Run: `py -m pytest tests/test_guided_learning_research_analysis.py -v`

Expected: 全部PASS，且旧分析测试不回归。

- [ ] **Step 7: 提交**

```powershell
git add scripts/analyze_guided_learning_research.py tests/test_guided_learning_research_analysis.py
git commit -m "feat: add guided-learning event transitions"
```

---

### Task 3: 重建首次提交前分级暴露和固定效应模型

**Files:**
- Modify: `scripts/analyze_guided_learning_research.py`
- Modify: `tests/test_guided_learning_research_analysis.py`

**Interfaces:**
- Replaces: `build_submission_pairs(...)` 的旧二元暴露和最终结果口径。
- Produces: `exposure`、`first_full_pass`、`first_pass_rate`、`final_full_pass`、`final_pass_rate`、`attempts`，以及 `fit_exposure_models(pairs, exposure_mode) -> list[dict]`。

- [ ] **Step 1: 写入时间严格性失败测试**

```python
def test_submission_exposure_uses_only_activity_before_first_submission():
    submissions = [
        {"anonymous_user_id": "u1", "anonymous_assignment_id": "a1", "submitted_at": "2026-06-20T00:00:00", "sandbox_status": "failed", "sandbox_passed": "0", "sandbox_total": "2"},
        {"anonymous_user_id": "u1", "anonymous_assignment_id": "a1", "submitted_at": "2026-06-20T01:00:00", "sandbox_status": "passed", "sandbox_passed": "2", "sandbox_total": "2"},
    ]
    sessions = [
        {"anonymous_user_id": "u1", "anonymous_assignment_id": "a1", "started_at": "2026-06-19T23:00:00", "completed_at": "2026-06-20T00:30:00", "status": "completed"}
    ]

    pairs = build_submission_pairs(
        submissions,
        sessions,
        post_launch_utc=datetime.fromisoformat("2026-06-18T00:00:00+00:00"),
    )

    row = pairs.iloc[0]
    assert row["exposure"] == "incomplete"
    assert row["first_full_pass"] == 0
    assert row["first_pass_rate"] == 0.0
    assert row["final_full_pass"] == 1
```

- [ ] **Step 2: 运行严格性测试并确认旧实现失败**

Run: `py -m pytest tests/test_guided_learning_research_analysis.py::test_submission_exposure_uses_only_activity_before_first_submission -v`

Expected: FAIL；旧实现没有 `exposure` 和首次结果字段。

- [ ] **Step 3: 改写提交对构建函数**

```python
def _pass_outcomes(row: dict) -> tuple[int, float | None]:
    total = int(row["sandbox_total"] or 0)
    passed = int(row["sandbox_passed"] or 0)
    rate = passed / total if row["sandbox_status"] and total > 0 else None
    return int(total > 0 and passed == total), rate


def build_submission_pairs(
    submissions: list[dict],
    sessions: list[dict],
    post_launch_utc: datetime,
) -> pd.DataFrame:
    by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in submissions:
        if parse_platform_timestamp(row["submitted_at"]) >= post_launch_utc:
            by_pair[(row["anonymous_user_id"], row["anonymous_assignment_id"])].append(row)
    sessions_by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in sessions:
        sessions_by_pair[(row["anonymous_user_id"], row["anonymous_assignment_id"])].append(row)
    records = []
    for (user_id, assignment_id), rows in by_pair.items():
        ordered = sorted(rows, key=lambda row: parse_platform_timestamp(row["submitted_at"]))
        first, last = ordered[0], ordered[-1]
        first_time = parse_platform_timestamp(first["submitted_at"])
        prior = [
            row for row in sessions_by_pair[(user_id, assignment_id)]
            if parse_platform_timestamp(row["started_at"]) <= first_time
        ]
        completed_before = any(
            row.get("completed_at")
            and parse_platform_timestamp(row["completed_at"]) <= first_time
            and row["status"].strip().lower() == "completed"
            for row in prior
        )
        exposure = "completed" if completed_before else ("incomplete" if prior else "none")
        first_full, first_rate = _pass_outcomes(first)
        final_full, final_rate = _pass_outcomes(last)
        records.append({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "exposure": exposure,
            "guided_before_first": int(exposure != "none"),
            "completed_before_first": int(exposure == "completed"),
            "first_full_pass": first_full,
            "first_pass_rate": first_rate,
            "final_full_pass": final_full,
            "final_pass_rate": final_rate,
            "attempts": len(ordered),
        })
    return pd.DataFrame.from_records(records)
```

- [ ] **Step 4: 写入信息学生数和模型失败测试**

```python
def test_exposure_models_report_informative_students():
    pairs = pd.DataFrame([
        {"user_id": "u1", "assignment_id": "a1", "exposure": "none", "guided_before_first": 0, "first_full_pass": 1},
        {"user_id": "u1", "assignment_id": "a2", "exposure": "completed", "guided_before_first": 1, "first_full_pass": 0},
        {"user_id": "u2", "assignment_id": "a1", "exposure": "none", "guided_before_first": 0, "first_full_pass": 1},
        {"user_id": "u2", "assignment_id": "a2", "exposure": "none", "guided_before_first": 0, "first_full_pass": 0},
    ])

    assert count_informative_students(pairs, "exposure") == 1
    assert count_informative_students(pairs, "guided_before_first") == 1
```

- [ ] **Step 5: 实现原始比例、信息学生数和双固定效应模型**

```python
def count_informative_students(pairs: pd.DataFrame, column: str) -> int:
    return int((pairs.groupby("user_id")[column].nunique() >= 2).sum())


def raw_exposure_rates(pairs: pd.DataFrame) -> list[dict]:
    rows = []
    for exposure in ("none", "incomplete", "completed"):
        group = pairs[pairs["exposure"] == exposure]
        rows.append({
            "exposure": exposure,
            "pairs": len(group),
            "students": group["user_id"].nunique(),
            "assignments": group["assignment_id"].nunique(),
            "first_full_pass_percent": round(100 * group["first_full_pass"].mean(), 2),
            "first_pass_rate_percent": round(100 * group["first_pass_rate"].dropna().mean(), 2),
            "final_full_pass_percent": round(100 * group["final_full_pass"].mean(), 2),
            "mean_attempts": round(group["attempts"].mean(), 3),
        })
    return rows


def fit_exposure_models(pairs: pd.DataFrame, exposure_mode: str = "three_level") -> list[dict]:
    outcomes = ("first_full_pass", "first_pass_rate", "final_full_pass", "final_pass_rate", "attempts")
    rows = []
    term_source = "C(exposure, Treatment(reference='none'))" if exposure_mode == "three_level" else "guided_before_first"
    for outcome in outcomes:
        sample = pairs.dropna(subset=[outcome]).copy()
        model = smf.ols(
            f"{outcome} ~ {term_source} + C(user_id) + C(assignment_id)",
            data=sample,
        ).fit(cov_type="cluster", cov_kwds={"groups": sample["user_id"]})
        terms = [term for term in model.params.index if term.startswith(term_source)]
        for term in terms:
            low, high = model.conf_int().loc[term]
            rows.append({
                "model": exposure_mode,
                "outcome": outcome,
                "term": term,
                "n_pairs": int(model.nobs),
                "n_students": sample["user_id"].nunique(),
                "informative_students": count_informative_students(
                    sample,
                    "exposure" if exposure_mode == "three_level" else "guided_before_first",
                ),
                "coefficient": round(float(model.params[term]), 6),
                "standard_error": round(float(model.bse[term]), 6),
                "ci_95_low": round(float(low), 6),
                "ci_95_high": round(float(high), 6),
                "p_value": round(float(model.pvalues[term]), 6),
            })
    return rows
```

- [ ] **Step 6: 更新旧测试断言**

将 `test_submission_pairs_use_post_launch_rows_and_final_outcome` 改为同时断言：

```python
assert pairs.iloc[0]["exposure"] == "completed"
assert pairs.iloc[0]["first_full_pass"] == 0
assert pairs.iloc[0]["final_full_pass"] == 1
assert pairs.iloc[0]["attempts"] == 2
```

- [ ] **Step 7: 运行分析单测**

Run: `py -m pytest tests/test_guided_learning_research_analysis.py -v`

Expected: 全部PASS。

- [ ] **Step 8: 提交**

```powershell
git add scripts/analyze_guided_learning_research.py tests/test_guided_learning_research_analysis.py
git commit -m "feat: measure pre-submission guided exposure"
```

---

### Task 4: 接入完整分析并冻结结果

**Files:**
- Modify: `scripts/analyze_guided_learning_research.py`
- Create: `research/guided_learning_paper/results/stable_session_paths.csv`
- Create: `research/guided_learning_paper/results/stage_friction.csv`
- Create: `research/guided_learning_paper/results/event_transitions.csv`
- Create: `research/guided_learning_paper/results/exposure_raw_rates.csv`
- Create: `research/guided_learning_paper/results/exposure_models.csv`
- Modify: `research/guided_learning_paper/results/analysis_summary.json`
- Modify: `research/guided_learning_paper/results/validation_notes.md`

**Interfaces:**
- Consumes: Task 1—3新增函数和匿名ZIP。
- Produces: 正文与图表唯一允许引用的冻结结果。

- [ ] **Step 1: 在 `analyze()` 中接入稳定版结果**

在取得 `stable_sessions, stable_logs` 后先加入稳定版分析：

```python
stable_paths = build_stable_session_paths(stable_sessions)
stage_friction = summarize_stage_friction(stable_sessions, stable_logs)
event_transitions = build_event_transitions(stable_sessions, stable_logs)
```

在现有 `pairs = build_submission_pairs(...)` 之后、构造 `summary` 之前加入：

```python
raw_exposure = raw_exposure_rates(pairs)
exposure_models = [
    *fit_exposure_models(pairs, "three_level"),
    *fit_exposure_models(pairs, "binary"),
]
```

在 `summary` 中加入：

```python
"stable_paths": {row["path"]: row["sessions"] for row in stable_paths},
"exposure_counts": {row["exposure"]: row["pairs"] for row in raw_exposure},
"informative_students": {
    "three_level": count_informative_students(pairs, "exposure"),
    "binary": count_informative_students(pairs, "guided_before_first"),
},
```

写出：

```python
write_csv(output_dir / "stable_session_paths.csv", stable_paths)
write_csv(output_dir / "stage_friction.csv", stage_friction)
write_csv(output_dir / "event_transitions.csv", event_transitions)
write_csv(output_dir / "exposure_raw_rates.csv", raw_exposure)
write_csv(output_dir / "exposure_models.csv", exposure_models)
```

- [ ] **Step 2: 运行完整分析**

Run:

```powershell
py scripts/analyze_guided_learning_research.py --input 'C:\Users\amana\Downloads\codesense-research-export-20260716T090300Z.zip' --output-dir research/guided_learning_paper/results
```

Expected:

```text
thinking_sessions=492
thinking_stage_logs=9940
stable_version_sessions=398
```

- [ ] **Step 3: 用脚本断言冻结计数**

Run:

```powershell
py -c "import json,pathlib; p=pathlib.Path('research/guided_learning_paper/results/analysis_summary.json'); d=json.loads(p.read_text(encoding='utf-8')); assert d['row_counts']['students']==117; assert d['stable_paths']=={'no_valid_stage1':89,'stage2_incomplete':74,'stage3_incomplete':11,'all_completed':224}; assert d['exposure_counts']=={'none':774,'incomplete':37,'completed':183}; assert d['informative_students']=={'three_level':32,'binary':31}; print('FROZEN_RESULTS_OK')"
```

Expected: `FROZEN_RESULTS_OK`。

- [ ] **Step 4: 检查输出不包含匿名标识符**

Run:

```powershell
Select-String -Path 'research\guided_learning_paper\results\*' -Pattern 'use_[0-9a-f]+|ses_[0-9a-f]+|ass_[0-9a-f]+' -AllMatches
```

Expected: 无匹配。

- [ ] **Step 5: 更新验证记录**

在 `validation_notes.md` 记录：

- 源ZIP文件名和SHA-256；
- 117名学生、492次会话、9940条日志；
- 稳定版四类路径总和为398；
- 三类暴露总和为994；
- 三分类和二分类信息学生数分别为32和31；
- 首次提交是主结果，最终提交与尝试次数为敏感性结果；
- 数据为观察性课堂记录，不能支持因果推断。

- [ ] **Step 6: 运行完整测试**

Run: `py -m pytest tests/test_guided_learning_research_analysis.py tests/test_research_data_export.py -q`

Expected: 全部PASS。

- [ ] **Step 7: 提交**

```powershell
git add scripts/analyze_guided_learning_research.py tests/test_guided_learning_research_analysis.py research/guided_learning_paper/results
git commit -m "data: freeze revised paper analyses"
```

---

### Task 5: 生成核心图表并进行像素级检查

**Files:**
- Modify: `scripts/plot_guided_learning_paper.py`
- Modify: `tests/test_guided_learning_paper_plots.py`
- Create: `research/guided_learning_paper/figures/activity_chain_evidence.png`
- Create: `research/guided_learning_paper/figures/adoption_profile.png`
- Create: `research/guided_learning_paper/figures/stable_session_paths.png`
- Create: `research/guided_learning_paper/figures/event_transitions.png`
- Create: `research/guided_learning_paper/figures/appendix_version_timeline.png`

**Interfaces:**
- Consumes: Task 4冻结CSV/JSON。
- Produces: `create_figures(results_dir, output_dir) -> list[Path]`，顺序固定为活动链、采用、路径、转换、附录版本图。

- [ ] **Step 1: 把图表测试改为固定文件集合**

```python
def test_create_figures_writes_revised_nonempty_pngs(tmp_path):
    results = tmp_path / "results"
    figures = tmp_path / "figures"
    results.mkdir()
    _write_minimal_revised_results(results)

    paths = create_figures(results, figures)

    assert {path.name for path in paths} == {
        "activity_chain_evidence.png",
        "adoption_profile.png",
        "stable_session_paths.png",
        "event_transitions.png",
        "appendix_version_timeline.png",
    }
    assert all(path.stat().st_size > 10_000 for path in paths)
```

测试文件顶部增加 `import json`，并加入以下夹具函数：

```python
def _write_minimal_revised_results(results):
    (results / "analysis_summary.json").write_text(
        json.dumps(
            {
                "usage": {
                    "users": 4,
                    "repeat_users": 2,
                    "cross_assignment_users": 1,
                    "users_with_completed_session": 3,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_csv(
        results / "student_usage.csv",
        [
            {"sessions_per_user": 1, "users": 2, "total_sessions": 2, "completed_sessions": 1},
            {"sessions_per_user": 4, "users": 2, "total_sessions": 8, "completed_sessions": 6},
        ],
    )
    _write_csv(
        results / "stable_session_paths.csv",
        [
            {"path": "no_valid_stage1", "label": "未形成第一阶段有效记录", "sessions": 2, "percent": 20},
            {"path": "stage2_incomplete", "label": "到达第二阶段但未完成", "sessions": 2, "percent": 20},
            {"path": "stage3_incomplete", "label": "完成第二阶段但未完成第三阶段", "sessions": 1, "percent": 10},
            {"path": "all_completed", "label": "完成全部阶段", "sessions": 5, "percent": 50},
        ],
    )
    _write_csv(
        results / "event_transitions.csv",
        [
            {"completion_group": "completed", "source": "description_submit", "target": "stage_pass", "count": 12, "distinct_sessions": 6, "conditional_percent": 60, "show_in_main_figure": 1},
            {"completion_group": "incomplete", "source": "description_submit", "target": "hint_request", "count": 11, "distinct_sessions": 5, "conditional_percent": 55, "show_in_main_figure": 1},
        ],
    )
    _write_csv(
        results / "version_summary.csv",
        [
            {"version": "V1", "label": "初始版", "sessions": 2, "users": 2, "assignments": 1, "completed_sessions": 1, "completion_percent": 50},
            {"version": "V5", "label": "稳定版", "sessions": 8, "users": 4, "assignments": 3, "completed_sessions": 5, "completion_percent": 62.5},
        ],
    )
```

- [ ] **Step 2: 运行图表测试并确认失败**

Run: `py -m pytest tests/test_guided_learning_paper_plots.py -v`

Expected: FAIL，返回的仍是第一版五张图。

- [ ] **Step 3: 实现活动链和采用图**

活动链图固定为三栏：

```python
stages = [
    ("思路外化", "自然语言描述算法步骤与边界", "平台证据：描述提交、提示请求"),
    ("代码重构", "把自然语言表征转为程序结构", "平台证据：验证失败、阶段通过"),
    ("讲解纠错", "回应追问并修正错误代码", "平台证据：对话、错误代码修正"),
]
```

图底部单独绘制灰色边界框：

```text
本研究观察到：采用、阶段推进与平台事件
本研究未直接测量：解释质量、认知变化与学习增益
```

采用图从 `analysis_summary.json` 读取 `users`、`repeat_users`、`cross_assignment_users`、`users_with_completed_session`，每个柱体同时标计数和以引导用户为分母的百分比。

- [ ] **Step 4: 实现路径和事件转换图**

路径图按 `no_valid_stage1 → stage2_incomplete → stage3_incomplete → all_completed` 展示计数和占398次会话比例。

事件转换图仅读取 `show_in_main_figure == 1` 的记录，分别绘制完成组和未完成组。线宽映射 `conditional_percent`，标签显示 `count`；颜色之外同时使用实线/虚线区分组别，保证黑白打印可辨认。

- [ ] **Step 5: 运行图表脚本**

Run:

```powershell
py scripts/plot_guided_learning_paper.py --results-dir research/guided_learning_paper/results --output-dir research/guided_learning_paper/figures
```

Expected: 输出五个非空PNG文件。

- [ ] **Step 6: 视觉检查**

逐张使用图像查看工具检查：

- 中文字体无方框和乱码；
- 标题、图例、数据标签不重叠；
- 分母清楚；
- 活动链明确区分已观察与未测量；
- 转换图不因节点或连线过多失去可读性；
- 300 DPI导出后最短边不少于1400像素。

- [ ] **Step 7: 运行图表测试**

Run: `py -m pytest tests/test_guided_learning_paper_plots.py -v`

Expected: 全部PASS。

- [ ] **Step 8: 提交**

```powershell
git add scripts/plot_guided_learning_paper.py tests/test_guided_learning_paper_plots.py research/guided_learning_paper/figures
git commit -m "feat: rebuild guided-learning paper figures"
```

---

### Task 6: 完成文献核验、模拟外审和下一轮研究方案

**Files:**
- Modify: `research/guided_learning_paper/literature_matrix.md`
- Create: `research/guided_learning_paper/peer_review_audit_v2.md`
- Create: `research/guided_learning_paper/revision_log.md`
- Create: `research/guided_learning_paper/next_study_protocol.md`

**Interfaces:**
- Consumes: 设计稿、冻结结果、第一版论文及可核验文献元数据。
- Produces: 两篇正文的论证依据和投稿风险清单。

- [ ] **Step 1: 建立文献纳入规则**

`literature_matrix.md` 每条记录必须包含：

```text
作者与年份 | 完整题名 | 期刊/会议 | 卷期页码 | DOI或官方链接 | 研究对象与样本 | 方法 | 可支持的主张 | 不可外推之处 | 核验状态
```

纳入25—30篇，其中中文研究至少覆盖生成式AI编程学习行为、学习分析、作业与评价、人机协同、教育伦理五类；英文研究覆盖自我解释、表征转换/Parsons Problems、learning-by-teaching/可教智能体、生成式AI编程教育和真实课堂日志分析。

- [ ] **Step 2: 逐条核验元数据**

优先使用期刊官网、Crossref、DOI落地页和原始论文；技术问题只依赖官方文档。每条文献核对作者、题名、年份、期刊、卷期、页码和DOI，不从搜索摘要推断研究结论。

- [ ] **Step 3: 写第二轮模拟外审**

`peer_review_audit_v2.md` 固定包含：

1. 总体评价与建议处理结果；
2. 创新性：三阶段活动链的新颖性与已有研究边界；
3. 理论：概念是否形成递进关系；
4. 方法：样本、日志、时间边界和重复测量；
5. 结果：路径、转换、摩擦和提交关联；
6. 效度威胁：自选择、成绩激励、版本迭代、单校单课程；
7. 伦理与可投稿性；
8. 针对中文核心稿和实践稿的不同修改意见；
9. 模拟结论：大修后再审。

- [ ] **Step 4: 写下一轮研究方案**

`next_study_protocol.md` 明确：

- 首选班级或作业层面的阶梯楔形设计，避免同班学生功能串扰；
- 最低限度加入前测、后测、延迟测和代码迁移题；
- 记录是否接受引导、实际完成阶段和教师提醒；
- 主要结果为盲评算法解释质量与迁移题成绩；
- 次要结果为首次提交表现、调试次数和阶段行为；
- 预注册主要假设、排除规则、缺失处理和分析模型；
- 课程成绩激励与研究同意分离；
- 先完成伦理审查再开始研究性采集。

- [ ] **Step 5: 写修订记录**

`revision_log.md` 按“第一版问题—改动—证据文件—剩余限制”记录每一项关键变化，至少覆盖主线、理论链、版本RQ、日志利用、暴露口径、中文文献、伦理和双轨稿件。

- [ ] **Step 6: 运行引用与占位符检查**

Run:

```powershell
Select-String -Path 'research\guided_learning_paper\literature_matrix.md','research\guided_learning_paper\peer_review_audit_v2.md','research\guided_learning_paper\next_study_protocol.md' -Pattern 'TBD|TODO|待补|待定|据称|有研究表明'
```

Expected: 无未经解释的占位符或模糊归因。

- [ ] **Step 7: 使用 humanizer-zh 完成第二遍审阅并提交**

重点删除宣传性措辞、机械三段式、模糊归因和没有证据的“创新”“有效”等判断，同时保留统计术语、文献题名和直接引用原样。

```powershell
git add research/guided_learning_paper/literature_matrix.md research/guided_learning_paper/peer_review_audit_v2.md research/guided_learning_paper/revision_log.md research/guided_learning_paper/next_study_protocol.md
git commit -m "docs: audit evidence for revised guided-learning paper"
```

---

### Task 7: 写中文核心导向稿

**Files:**
- Create: `research/guided_learning_paper/manuscript_core_zh.md`

**Interfaces:**
- Consumes: Task 4冻结结果、Task 5图表、Task 6文献矩阵。
- Produces: 六部分结构、四图三表、25—30条GB/T 7714参考文献的核心稿。

- [ ] **Step 1: 建立固定结构**

```markdown
# 生成式AI支持的三阶段程序设计引导：活动设计、课堂采用与行为路径

## 摘要
## 关键词
## 1 问题提出
## 2 理论基础与活动设计
### 2.1 从答案生成转向学习活动组织
### 2.2 思路外化
### 2.3 代码重构
### 2.4 讲解纠错
### 2.5 研究问题
## 3 研究设计
### 3.1 教学情境与参与方式
### 3.2 系统与三阶段活动
### 3.3 数据来源与样本
### 3.4 指标与分析方法
### 3.5 伦理和数据保护
## 4 研究结果
### 4.1 采用、重复使用与跨作业使用
### 4.2 稳定版阶段路径与过程摩擦
### 4.3 完成与未完成会话的事件转换
### 4.4 分级暴露与首次提交表现
## 5 讨论
### 5.1 三阶段活动链的设计意义
### 5.2 真实课堂中的推进、回退与退出
### 5.3 成绩激励、自选择与结果解释
### 5.4 教学启示
## 6 结论与局限
## 参考文献
## 附录
```

- [ ] **Step 2: 写方法和结果**

方法必须明确117名学生、492次会话、9940条日志、398次稳定版会话和994个学生—作业对。结果严格按RQ1—RQ3组织，每个计数标出分母；固定效应表报告样本量、信息学生数、系数、聚类标准误、95%置信区间和p值。

- [ ] **Step 3: 写理论、讨论和局限**

活动链使用“设计概括”而非“新理论”。讨论必须分别处理：

- 89次会话没有形成第一阶段有效记录；
- 路径和转换只反映平台行为；
- 学生可自愿进入但存在约10%的低门槛成绩激励；
- 困难学生可能更倾向寻求引导；
- 单校、单课程、边更新边部署限制外部效度；
- 没有对照实验、前后测和解释质量编码，不能声称学习增益。

- [ ] **Step 4: 插入四图三表**

正文图表路径固定为：

```text
figures/activity_chain_evidence.png
figures/adoption_profile.png
figures/stable_session_paths.png
figures/event_transitions.png
```

表1写教学场景、样本和数据；表2从 `stage_friction.csv` 转录；表3从 `exposure_raw_rates.csv` 和主模型记录转录。附录放版本时间线和完整模型。

- [ ] **Step 5: 做数字一致性检查**

Run:

```powershell
py -c "from pathlib import Path; t=Path('research/guided_learning_paper/manuscript_core_zh.md').read_text(encoding='utf-8'); required=['117','492','9940','398','89','74','11','224','994','774','37','183','32','31']; missing=[x for x in required if x not in t]; assert not missing, missing; print('CORE_FACTS_OK')"
```

Expected: `CORE_FACTS_OK`。

- [ ] **Step 6: 做高风险措辞和引用检查**

Run:

```powershell
Select-String -Path 'research\guided_learning_paper\manuscript_core_zh.md' -Pattern '显著提升|有效提高|证明了|导致了|内在动机|深层认知|高阶思维|完全自愿|强制使用|TBD|TODO|待补'
```

逐项人工判断并删除无证据表述；伦理说明允许明确写“投稿前需由研究团队确认伦理程序”，不得写成已审批。

- [ ] **Step 7: 使用 humanizer-zh 审阅全文**

保持统计数字、术语、参考文献和图表题名不变，压缩重复的背景段与结论排比，使正文读起来像中文教育技术研究者撰写，而非模板化生成文本。

- [ ] **Step 8: 提交**

```powershell
git add research/guided_learning_paper/manuscript_core_zh.md
git commit -m "docs: write core-journal guided-learning manuscript"
```

---

### Task 8: 写计算机教育实践稿

**Files:**
- Create: `research/guided_learning_paper/manuscript_practice_zh.md`

**Interfaces:**
- Consumes: 同一冻结结果和系统事实。
- Produces: 面向专业教学期刊、突出可复用教学流程的独立稿件。

- [ ] **Step 1: 建立实践稿结构**

```markdown
# 三阶段引导式学习在数据结构课程设计中的设计与应用

## 摘要
## 关键词
## 1 问题与设计目标
## 2 三阶段引导式学习的系统实现
## 3 课程组织与实施
## 4 使用情况与过程特征
## 5 教学反思与改进建议
## 6 结语
## 参考文献
```

- [ ] **Step 2: 写系统和课程实施**

说明学生可以直接编码，也可以进入引导入口；教师在群内鼓励尝试；相关表现约占课程设计成绩10%，一次体验通常可获得大部分分数；系统边更新边应用。增加教师部署、活动入口、三阶段任务和课堂使用建议，但不泄露内部密钥、服务器地址或学生数据。

- [ ] **Step 3: 写描述性证据**

保留采用、稳定版路径、阶段摩擦和首次提交原始比例。固定效应模型压缩为一段或附表，明确其作用仅是控制学生和作业不变差异，不能处理自选择。

- [ ] **Step 4: 写可复用建议**

建议必须与数据或实施事实相连，覆盖：

- 入口说明与退出自由；
- 低门槛激励的透明告知；
- 第一阶段有效开始的监测；
- 第二阶段验证失败的支架；
- 第三阶段对话和错误代码修正；
- 系统更新期间的版本记录；
- 研究使用前的伦理与同意程序。

- [ ] **Step 5: 检查两稿非机械删节**

Run:

```powershell
py -c "from pathlib import Path; import difflib; a=Path('research/guided_learning_paper/manuscript_core_zh.md').read_text(encoding='utf-8'); b=Path('research/guided_learning_paper/manuscript_practice_zh.md').read_text(encoding='utf-8'); ratio=difflib.SequenceMatcher(None,a,b).ratio(); print(f'SIMILARITY={ratio:.3f}'); assert ratio < 0.70"
```

Expected: `SIMILARITY` 小于0.700。

- [ ] **Step 6: 使用 humanizer-zh 审阅并提交**

实践稿使用具体课堂语言，减少抽象理论堆叠，但保留证据边界和伦理限制。

```powershell
git add research/guided_learning_paper/manuscript_practice_zh.md
git commit -m "docs: write practice-oriented guided-learning manuscript"
```

---

### Task 9: 泛化Word生成器并生成两份DOCX

**Files:**
- Modify: `scripts/build_guided_learning_paper_docx.py`
- Create: `tests/test_guided_learning_paper_docx.py`
- Create: `research/guided_learning_paper/paper_core_zh.docx`
- Create: `research/guided_learning_paper/paper_practice_zh.docx`
- Modify: `research/guided_learning_paper/README.md`

**Interfaces:**
- Produces: `build(manuscript_path: Path, output_path: Path) -> Path`。
- CLI: `--input-md`、`--output-docx`。

- [ ] **Step 1: 写Word生成失败测试**

```python
from docx import Document
from scripts.build_guided_learning_paper_docx import build


def test_build_accepts_explicit_input_and_output(tmp_path):
    source = tmp_path / "paper.md"
    target = tmp_path / "paper.docx"
    source.write_text("# 测试论文\n\n## 摘要\n\n这是摘要。\n\n## 参考文献\n\n[1] 测试文献。", encoding="utf-8")

    result = build(source, target)
    doc = Document(result)

    assert result == target
    assert target.exists()
    assert doc.paragraphs[0].text == "测试论文"
    assert doc.core_properties.author == ""
    assert doc.core_properties.last_modified_by == ""
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `py -m pytest tests/test_guided_learning_paper_docx.py -v`

Expected: FAIL；旧 `build()` 不接收参数。

- [ ] **Step 3: 泛化生成器**

删除 `SOURCE` 和 `OUTPUT` 两个固定路径常量，在文件顶部增加 `import argparse`。把现有 `build()` 的函数头和输入输出位置精确替换为：

```python
def build(manuscript_path: Path, output_path: Path) -> Path:
    lines = manuscript_path.read_text(encoding="utf-8").splitlines()
    doc = Document()
    configure_document(doc)
```

紧接 `configure_document(doc)` 的仍是当前 `in_code`、`code_lines`、`in_references`、`index` 初始化和完整 `while index < len(lines)` 解析分支，不重写第二套解析器。把图像函数和调用精确改为：

```python
def add_figure(doc: Document, image_path: str | Path, caption: str) -> None:
    image_path = Path(image_path)
```

这两行之后直接接当前函数从 `paragraph = doc.add_paragraph()` 开始的全部格式、图片宽度和题注语句；删除旧的 `image_path = SOURCE.parent / relative_path`。

```python
add_figure(
    doc,
    (manuscript_path.parent / match.group(2)).resolve(),
    match.group(1),
)
```

将当前固定元数据和保存语句替换为：

```python
    core = doc.core_properties
    core.title = next(
        (line[2:].strip() for line in lines if line.startswith("# ")),
        manuscript_path.stem,
    )
    core.subject = "中文研究论文内部审阅稿"
    core.author = ""
    core.last_modified_by = ""
    core.comments = "内部研究稿；正式投稿前需由研究团队确认伦理程序。"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    return output_path
```

文件末尾的CLI精确替换为：

```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-md", required=True, type=Path)
    parser.add_argument("--output-docx", required=True, type=Path)
    args = parser.parse_args()
    print(build(args.input_md, args.output_docx))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行Word单测**

Run: `py -m pytest tests/test_guided_learning_paper_docx.py -v`

Expected: PASS。

- [ ] **Step 5: 生成两份Word稿**

Run:

```powershell
py scripts/build_guided_learning_paper_docx.py --input-md research/guided_learning_paper/manuscript_core_zh.md --output-docx research/guided_learning_paper/paper_core_zh.docx
py scripts/build_guided_learning_paper_docx.py --input-md research/guided_learning_paper/manuscript_practice_zh.md --output-docx research/guided_learning_paper/paper_practice_zh.docx
```

Expected: 两个DOCX均存在且文件大小大于200 KB。

- [ ] **Step 6: 做结构检查**

Run:

```powershell
py -c "from docx import Document; from pathlib import Path; files=[Path('research/guided_learning_paper/paper_core_zh.docx'),Path('research/guided_learning_paper/paper_practice_zh.docx')]; [(lambda d,p: (print(p.name,len(d.paragraphs),len(d.tables),len(d.inline_shapes)), (_ for _ in ()).throw(AssertionError(p)) if len(d.paragraphs)<50 or len(d.inline_shapes)<2 else None))(Document(p),p) for p in files]"
```

Expected: 核心稿至少4幅图，实践稿至少2幅图；两稿均有表格和完整参考文献。

- [ ] **Step 7: 更新README**

写明分析、绘图、两稿DOCX生成命令，列出匿名数据不可公开、伦理信息需要团队确认、第一版未覆盖。

- [ ] **Step 8: 提交**

```powershell
git add scripts/build_guided_learning_paper_docx.py tests/test_guided_learning_paper_docx.py research/guided_learning_paper/paper_core_zh.docx research/guided_learning_paper/paper_practice_zh.docx research/guided_learning_paper/README.md
git commit -m "feat: build dual-track guided-learning papers"
```

---

### Task 10: 逐页渲染、总体验证和交付复盘

**Files:**
- Modify: `research/guided_learning_paper/peer_review_audit_v2.md`
- Modify: `research/guided_learning_paper/revision_log.md`

**Interfaces:**
- Consumes: 两份最终DOCX和全部测试。
- Produces: 逐页视觉检查结论、最终外审结论和可交付分支。

- [ ] **Step 1: 用Word COM转为PDF**

为每份DOCX使用独立输出文件，Word以不可见方式打开并导出PDF。若Word COM失败，先检查是否残留 `WINWORD.EXE` 和文件锁；不得回退到已损坏的LibreOffice安装并宣称验证成功。

Expected: `paper_core_zh.pdf` 和 `paper_practice_zh.pdf` 可正常打开，页数大于0。

- [ ] **Step 2: 用Poppler渲染所有页面**

Run:

```powershell
pdftoppm -png -r 150 paper_core_zh.pdf render_core/page
pdftoppm -png -r 150 paper_practice_zh.pdf render_practice/page
```

Expected: PNG数量分别等于两份PDF页数。

- [ ] **Step 3: 逐页视觉检查**

检查每一页：

- 中文字体、英文缩写和数学符号正常；
- 标题层级连续；
- 图、表、题注不跨页错位；
- 表格不超出页边距；
- 图片和标签清晰；
- 参考文献没有悬挂错乱或异常空白；
- 页码连续；
- 无批注、修订痕迹、无关作者元数据。

发现问题后回到Task 9修改生成器并重新生成、转PDF和逐页检查，直到两份文档全部通过。

- [ ] **Step 4: 运行全量测试**

Run: `py -m pytest -q`

Expected: 至少保持基线的63项测试全部通过，新增测试同时通过；无FAIL或ERROR。

- [ ] **Step 5: 检查Git差异范围**

Run:

```powershell
git status --short
git diff --check
git diff --stat main...HEAD
```

Expected: 只有本计划列出的论文、脚本、测试、结果和图表文件；`static/uploads/` 仍保持未跟踪且未提交。

- [ ] **Step 6: 更新最终审计和修订记录**

在 `peer_review_audit_v2.md` 末尾加入“最终复核”，记录：

- 哪些外审问题已经解决；
- 哪些因数据结构无法解决；
- 哪些投稿信息仍需作者团队补充；
- 核心稿与实践稿各自更适合的期刊层级；
- 仍不建议使用因果措辞。

在 `revision_log.md` 记录最终测试数量、DOCX页数、渲染方式和视觉检查日期。

- [ ] **Step 7: 最终提交**

```powershell
git add research/guided_learning_paper/peer_review_audit_v2.md research/guided_learning_paper/revision_log.md
git commit -m "docs: complete guided-learning paper review"
```

- [ ] **Step 8: 使用 verification-before-completion 完成交付**

重新读取最近一次测试、Git状态、DOCX结构和渲染结果。只有这些证据仍然有效时，才能向用户报告完成，并列出尚需团队确认的伦理、作者和基金信息。

---

## 完成判据

- 新分析可以从指定匿名ZIP一键重建，输出中不含匿名行级标识。
- 稳定版路径为89、74、11、224，总和398。
- 分级暴露为774、37、183，总和994；信息学生数为三分类32、二分类31。
- 首次提交表现是主要结果，最终结果仅作为敏感性分析。
- 四张核心图和一张附录图完成视觉检查。
- 两篇稿件结构、重点和目标读者不同，不是机械删节。
- 两份DOCX由同一生成器重复生成，逐页检查无版式问题。
- 全量测试通过，Git差异不包含用户的 `static/uploads/`。
- 外审文件明确区分已解决问题、数据固有限制和投稿前阻断项。
