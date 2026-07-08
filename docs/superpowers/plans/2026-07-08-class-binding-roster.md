# Class Binding And Roster Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a closed class binding and roster-based student registration flow.

**Architecture:** Extend the existing `Class` and `User` model flow with a generated class binding code and a `StudentRoster` table. Add focused class routes for teacher binding, unbinding, code reset, and roster import. Registration resolves class membership from roster data instead of trusting free-form class input.

**Tech Stack:** Flask, Flask-Login, SQLAlchemy, Jinja2, pandas/openpyxl, Bootstrap.

## Global Constraints

- Keep the current one-teacher-per-class model using `Class.teacher_id`.
- Do not create student accounts during roster import.
- Keep `User.class_name` synchronized with `User.class_id`.
- Do not run automated tests in this implementation session; provide Anaconda test steps for the user.

---

### Task 1: Model And Schema Support

**Files:**
- Modify: `models.py`

**Interfaces:**
- Produces: `Class.ensure_teacher_bind_code() -> str`
- Produces: `Class.reset_teacher_bind_code() -> str`
- Produces: `StudentRoster`

- [ ] Add binding-code columns to `Class`.
- [ ] Add helper methods for code generation and reset.
- [ ] Add `StudentRoster` model with student ID, name, class, importer, registration state, and timestamps.
- [ ] Extend `init_db()` auto-migration for the new class columns and generate missing codes for existing classes.

### Task 2: Teacher Binding And Roster Import Routes

**Files:**
- Modify: `routes/classes.py`

**Interfaces:**
- Consumes: `Class.ensure_teacher_bind_code()`
- Consumes: `Class.reset_teacher_bind_code()`
- Consumes: `StudentRoster`

- [ ] Add permission helper for class ownership.
- [ ] Add `POST /classes/bind`.
- [ ] Add `POST /classes/<class_id>/unbind`.
- [ ] Add `POST /classes/<class_id>/reset-bind-code`.
- [ ] Add `POST /classes/<class_id>/import-students`.
- [ ] Pass roster counts and binding codes to class pages.

### Task 3: Student Registration From Roster

**Files:**
- Modify: `routes/auth.py`
- Modify: `templates/register.html`

**Interfaces:**
- Consumes: `StudentRoster`

- [ ] Resolve submitted student ID against `StudentRoster`.
- [ ] Reject registration when no roster row exists.
- [ ] Save both `class_id` and `class_name`.
- [ ] Mark the roster row registered and link it to the new user.
- [ ] Update registration copy so students know the class is matched from the teacher-imported roster.

### Task 4: Teacher/Admin UI

**Files:**
- Modify: `templates/classes/class_list.html`
- Modify: `templates/classes/class_detail.html`
- Modify: `templates/teacher_home.html`

**Interfaces:**
- Consumes: `/classes/bind`
- Consumes: `/classes/<class_id>/unbind`
- Consumes: `/classes/<class_id>/reset-bind-code`
- Consumes: `/classes/<class_id>/import-students`

- [ ] Add teacher binding form to class list/dashboard when user is a teacher.
- [ ] Show admin binding code and reset action.
- [ ] Add roster import form to class detail.
- [ ] Add unbind action for owning teacher.

### Task 5: Manual Verification Instructions

**Files:**
- Modify final response only.

**Interfaces:**
- Produces: Anaconda-based manual test steps.

- [ ] Explain database initialization or migration behavior.
- [ ] Explain admin class setup and binding-code reset.
- [ ] Explain teacher binding and roster import.
- [ ] Explain student registration by roster match.
