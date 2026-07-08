# Account Basics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add practical account basics: email login, profile email/avatar editing, and logged-in password changes.

**Architecture:** Extend the existing `User` model and `init_db()` migration shim, then keep account routes in the existing `auth` and `users` blueprints. Use focused tests around login, profile update, avatar upload, and password change behavior.

**Tech Stack:** Flask, Flask-Login, Flask-WTF, SQLAlchemy, Werkzeug file upload helpers, pytest/unittest.

## Global Constraints

- Keep existing username/password login working.
- Add email as optional so existing users and tests still work.
- Do not implement social OAuth in this phase.
- Use TDD and run targeted plus full tests before committing.
- Commit and push verified changes to GitHub when implementation is complete.

---

### Task 1: Account Model Fields

**Files:**
- Modify: `models.py`

**Interfaces:**
- Produces: `User.email`
- Produces: `User.avatar_path`
- Produces: `User.password_changed_at`

- [ ] Add nullable `email`, `avatar_path`, and `password_changed_at` fields.
- [ ] Extend `init_db()` with safe `ALTER TABLE users ADD COLUMN ...` statements.

### Task 2: Email Login And Registration/Profile Email

**Files:**
- Modify: `forms.py`
- Modify: `routes/auth.py`
- Modify: `routes/users.py`
- Modify: login/register/profile templates

**Interfaces:**
- Consumes: `User.email`

- [ ] Allow login by username or email.
- [ ] Add optional email fields to student and teacher registration.
- [ ] Add email editing with uniqueness checks.

### Task 3: Password Change

**Files:**
- Modify: `forms.py`
- Modify: `routes/users.py`
- Create: `templates/change_password.html`

**Interfaces:**
- Produces: `users.change_password`

- [ ] Add a change-password form requiring current password and matching new password.
- [ ] Verify the old password before changing.
- [ ] Update `password_changed_at`.

### Task 4: Avatar Upload

**Files:**
- Modify: `forms.py`
- Modify: `routes/users.py`
- Modify: profile templates

**Interfaces:**
- Consumes: `User.avatar_path`

- [ ] Accept jpg/jpeg/png/gif/webp uploads.
- [ ] Save avatars under `static/uploads/avatars`.
- [ ] Render uploaded avatars when present, otherwise keep the existing icon fallback.

### Task 5: Verification And GitHub Push

**Files:**
- Modify: tests

**Interfaces:**
- Produces: committed and pushed branch state

- [ ] Run targeted account tests.
- [ ] Run all tests.
- [ ] Stage only intentional files.
- [ ] Commit and push to GitHub.
