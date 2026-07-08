# Teacher Learning Visuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add immediately scannable visual learning signals for teachers: a 14-day submission trend and a recent-assignment completion matrix.

**Architecture:** Keep data aggregation in `services/teacher_analytics.py`; routes only pass prepared data to templates. Use Chart.js already present on the teacher dashboard, and use server-rendered badge/heatmap cells on class detail to avoid new dependencies.

**Tech Stack:** Flask, SQLAlchemy, Jinja2, Chart.js, pytest through `E:/anaconda/python.exe`.

## Global Constraints

- Use TDD: write failing tests before production changes.
- Keep teacher-facing analytics in `services/teacher_analytics.py`.
- Do not add new frontend dependencies.
- Preserve existing class binding, roster import, and student table behavior.
- Update `docs/teacher_learning_dashboard_checklist.md` as the work progresses.

---

### Task 1: Trend And Matrix Data

**Files:**
- Modify: `tests/test_teacher_analytics.py`
- Modify: `services/teacher_analytics.py`

**Interfaces:**
- Produces: `build_submission_trend(student_ids, days=14, now=None) -> list[dict]`
- Produces: `build_assignment_completion_matrix(cls, students=None, assignment_limit=5) -> dict`
- Produces: `build_teacher_dashboard_data(teacher)['submission_trend']`

- [ ] **Step 1: Write failing tests**

Add tests that assert:
- the trend has 14 daily buckets and counts submissions on the expected dates.
- the matrix marks submitted, low-score, excellent, and missing assignment cells.
- dashboard data includes `submission_trend`.

- [ ] **Step 2: Run target test**

Run: `E:/anaconda/python.exe -m pytest tests/test_teacher_analytics.py -q`
Expected: FAIL because the new analytics functions are not defined.

- [ ] **Step 3: Implement analytics**

Add the two functions in `services/teacher_analytics.py` and include `submission_trend` in the dashboard payload.

- [ ] **Step 4: Run target test**

Run: `E:/anaconda/python.exe -m pytest tests/test_teacher_analytics.py -q`
Expected: PASS.

### Task 2: Teacher Dashboard Visuals

**Files:**
- Modify: `templates/teacher_home.html`

**Interfaces:**
- Consumes: `submission_trend` from `build_teacher_dashboard_data`.

- [ ] **Step 1: Add trend chart UI**

Add a 14-day trend chart card above or beside existing charts.

- [ ] **Step 2: Add Chart.js dataset**

Render `submission_trend` as labels and counts in the existing Chart.js setup.

- [ ] **Step 3: Run render test**

Run: `E:/anaconda/python.exe -m pytest tests/test_teacher_analytics.py::TeacherAnalyticsTestCase::test_teacher_dashboard_renders_learning_summary -q`
Expected: PASS.

### Task 3: Class Detail Matrix

**Files:**
- Modify: `routes/classes.py`
- Modify: `templates/classes/class_detail.html`
- Modify: `tests/test_teacher_analytics.py`

**Interfaces:**
- Consumes: `build_assignment_completion_matrix(cls, students=students.items, assignment_limit=5)`.
- Template receives `assignment_matrix`.

- [ ] **Step 1: Pass matrix from route**

Import and call `build_assignment_completion_matrix` in `class_detail`.

- [ ] **Step 2: Render matrix**

Add a compact red/yellow/green heatmap section with recent assignments as columns and students as rows.

- [ ] **Step 3: Run render test**

Run: `E:/anaconda/python.exe -m pytest tests/test_teacher_analytics.py::TeacherAnalyticsTestCase::test_class_detail_renders_learning_rows -q`
Expected: PASS.

### Task 4: Verification And Publish

**Files:**
- Modify: `docs/teacher_learning_dashboard_checklist.md`

- [ ] **Step 1: Run syntax check**

Run: `E:/anaconda/python.exe -m py_compile services/teacher_analytics.py routes/classes.py routes/main.py tests/test_teacher_analytics.py`
Expected: exit code 0.

- [ ] **Step 2: Run full tests**

Run: `E:/anaconda/python.exe -m pytest tests -q`
Expected: all tests pass.

- [ ] **Step 3: Commit and push**

Commit only related files and push `main` to GitHub.
