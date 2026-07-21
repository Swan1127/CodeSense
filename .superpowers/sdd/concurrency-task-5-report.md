# Concurrency evaluation Task 5 report

## Scope

Task 5 adds a guarded provisioning command and an offline-testable complete-platform HTTP target. No live platform, production database, or real user account was accessed while implementing or testing it.

Files in scope:

- `scripts/provision_research_load_users.py`
- `research_eval/concurrency/platform.py`
- `tests/test_concurrency_platform.py`

## Route and model evidence checked

The implementation was based on the current repository rather than assumed endpoints:

- `routes/auth.py`: `/login` accepts `username` and `password`, rotates `User.current_session_id`, and triggers the ability-trend asynchronous task after successful login.
- `forms.py` and `templates/login.html`: the form includes `username`, `password`, `submit`, and a hidden CSRF token.
- `routes/thinking.py`: session creation uses `POST /thinking/api/start_session` with `assignment_id`; stage 1 hint uses `session_id` and `description`; stage 3 chat uses `session_id`, `messages`, and optional `student_state`.
- `models.py`: dedicated accounts are student `User` rows, and the selected assignment must have an `AssignmentThinkingPreset` whose status is `ready`.

## TDD evidence

RED:

```text
py -m pytest tests/test_concurrency_platform.py -v
ModuleNotFoundError: No module named 'research_eval.concurrency.platform'
```

GREEN after the minimal implementation:

```text
py -m pytest tests/test_concurrency_platform.py -v
32 passed in 0.56s
```

Task 1-5 regression before final submission:

```text
py -m pytest tests/test_concurrency_metrics.py tests/test_concurrency_runner.py tests/test_concurrency_resources.py tests/test_concurrency_upstream.py tests/test_concurrency_platform.py -v
90 passed in 1.19s
```

## Implemented safeguards

- Credentials must be a JSON list with enough unique usernames, all beginning with `research_load_`, and non-empty passwords.
- Provisioning requires all command-line guards, including the exact confirmation text `CREATE_RESEARCH_LOAD_USERS`; the output path must be outside a Git worktree.
- Provisioning refuses a missing assignment, a preset not in `ready` state, a non-student collision, or an existing account whose saved credential is unavailable. It creates only missing users and never prints passwords.
- Credential output is replaced atomically. On POSIX systems it is written with mode `0600`.
- `PlatformTarget` creates and authenticates one Session per credential during initialization. `call()` never logs in again.
- Request index and credential index have a deterministic mapping. An account-level lock prevents concurrent use of the same Session, and server session IDs cannot move between credentials or change silently.
- Login and API requests use a 120-second timeout. Gateway errors, timeouts, request failures, non-JSON responses, HTTP failures, and cross-user session IDs are represented by allowlisted error codes; response bodies and credentials do not enter `RequestRecord`.
- URL construction accepts only an HTTP(S) origin without embedded credentials, query, or fragment, and API paths cannot change origin.

## Remaining risks

- Tests use fake Sessions and fake model/query objects. They verify the adapter contract but do not prove the deployed login redirect, CSRF configuration, database enum, or response schema matches the checked source at execution time.
- Initializing 32 credentials performs 32 sequential logins. In production, each successful login also schedules an ability-trend task. The platform canary therefore still requires the low-usage and explicit-approval gates in later tasks.
- A separate login to any dedicated account rotates its single-sign-on identifier and invalidates the prepared Session. These accounts must remain exclusive to the evaluation during a run.
- POSIX mode `0600` is enforced on Linux. Windows ACL hardening is outside this script, so the credential file is intended for the Linux server path described by the protocol.
- Existing users can be reused only when the existing external credential file is available. The script deliberately refuses to reset an unknown password.
