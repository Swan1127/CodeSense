# Course Grading Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a teacher/admin course grading statistics page that gives high trial-use scores for students with formal submission or guided learning evidence.

**Architecture:** Keep grading calculation in `services/course_grading.py`; Flask routes gather accessible classes and call the service; templates render computed records only. The current policy is named `trial_usage_friendly_v1` so future grading rules can replace it in one service file.

**Tech Stack:** Flask, SQLAlchemy, Jinja2, unittest/pytest-compatible Python tests, Bootstrap-style existing `layout.html`.

## Global Constraints

- Score is out of 10.
- Students with no formal submission and no guided learning evidence receive 0.
- Any credible formal or guided learning usage should generally score 8 or higher.
- Guided learning evidence includes `ThinkingSession` time/progress and `ThinkingStageLog.created_at`.
- Do not add a database table for this version.
- Teacher sees only managed classes; admin sees all classes.
- Keep unrelated dirty worktree changes out of commits.

---

### Task 1: Grading Service

**Files:**
- Create: `services/course_grading.py`
- Create: `tests/test_course_grading.py`

**Interfaces:**
- Produces: `trial_usage_friendly_v1(student, submissions, thinking_sessions, thinking_log_counts=None) -> dict`
- Produces: `build_gradebook(students, submissions_by_student, thinking_sessions_by_student, thinking_log_counts_by_session=None) -> tuple[list[dict], dict]`

- [ ] **Step 1: Write failing service tests**

Create tests covering no activity, formal-only activity, guided-only activity, completed guided learning, score cap, and combined reason text.

- [ ] **Step 2: Run service tests and verify RED**

Run: `python -m pytest tests/test_course_grading.py -q`
Expected: fails because `services.course_grading` does not exist.

- [ ] **Step 3: Implement minimal service**

Add dataless calculation helpers. Count formal submissions by `student_id`, count distinct formal assignments, use best non-null formal score, count guided sessions, infer guided minutes from `total_time_seconds` or timestamp span, and assign high scores for credible use.

- [ ] **Step 4: Run service tests and verify GREEN**

Run: `python -m pytest tests/test_course_grading.py -q`
Expected: all tests in `test_course_grading.py` pass.

### Task 2: Grades Route

**Files:**
- Create: `routes/grades.py`
- Modify: `app.py`
- Create: `templates/grades.html`
- Modify: `templates/layout.html`
- Test: `tests/test_grades_route.py`

**Interfaces:**
- Consumes: `build_gradebook(...)` from `services.course_grading`.
- Produces: `/grades` teacher/admin page with optional `class_id` query parameter.

- [ ] **Step 1: Write failing route tests**

Create tests that an admin can open `/grades`, a teacher only sees managed class students, and a student cannot access `/grades`.

- [ ] **Step 2: Run route tests and verify RED**

Run: `python -m pytest tests/test_grades_route.py -q`
Expected: fails because the route does not exist.

- [ ] **Step 3: Implement route, blueprint registration, template, and nav link**

Add `grades = Blueprint('grades', __name__)`; use `@login_required` and `@admin_or_teacher_required`; query accessible classes; fetch students, submissions, thinking sessions, and log counts; render summary cards and records table.

- [ ] **Step 4: Run route tests and verify GREEN**

Run: `python -m pytest tests/test_grades_route.py -q`
Expected: all tests in `test_grades_route.py` pass.

### Task 3: Regression Verification

**Files:**
- Existing test suite only.

- [ ] **Step 1: Run focused grading tests**

Run: `python -m pytest tests/test_course_grading.py tests/test_grades_route.py -q`
Expected: all new tests pass.

- [ ] **Step 2: Run existing app tests**

Run: `python -m pytest tests/test_app.py -q`
Expected: existing app tests pass or report pre-existing failures separately.

- [ ] **Step 3: Review changed files**

Run: `git diff -- services/course_grading.py routes/grades.py app.py templates/grades.html templates/layout.html tests/test_course_grading.py tests/test_grades_route.py docs/superpowers/plans/2026-07-06-course-grading-statistics.md`
Expected: diff contains only this feature.
