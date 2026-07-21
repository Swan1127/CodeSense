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

The first Task 5 implementation began with a missing-module RED. The review fixes also began with failing tests. The main review RED results were:

```text
py -m pytest tests/test_concurrency_platform.py -v
ImportError: cannot import name 'CredentialPublishError'
```

After adding the new interfaces, the first run collected 55 tests. Four failures came from an incorrect test assertion; the production checks had rejected the bad accounts as intended. The assertion was corrected before continuing. Two later targeted RED runs reproduced encoded redirect traversal, unexpected credential truncation, and the unsafe post-replace chmod.

Final Task 5 verification:

```text
py -m pytest tests/test_concurrency_platform.py -v
61 passed in 0.61s
```

Final Task 1-5 regression:

```text
py -m pytest tests/test_concurrency_metrics.py tests/test_concurrency_runner.py tests/test_concurrency_resources.py tests/test_concurrency_upstream.py tests/test_concurrency_platform.py -v
119 passed in 1.18s
```

## Implemented safeguards

- Credentials must be a JSON list with enough unique usernames, all beginning with `research_load_`, and non-empty passwords.
- Provisioning requires exactly 32 accounts and the confirmation text `CREATE_RESEARCH_LOAD_USERS`; the output path must be outside a Git worktree. Counts from 1 through 31 are rejected before the application module is imported.
- The CLI sets `FLASK_CONFIG` before importing `app`, then uses the module-level `app` instance. It does not call `create_app` a second time.
- Reused accounts must match the expected username, student ID, student user type, and `research_load_test` class namespace. The saved password must pass the real model's `verify_password` method. A mismatch is rejected without resetting the account.
- Credentials are first written to a mode-`0600` temporary file. The database is committed only after staging succeeds, and the final path is changed with one atomic replace. A failed DB commit rolls back and removes the staged file without changing an existing output file.
- If the atomic replace fails after user creation, the script deletes only users created by that invocation and commits the compensation. If compensation also fails, it rolls back the failed delete transaction, preserves the mode-`0600` staged credentials, and reports only the recovery path.
- Existing credential entries outside the expected 32-account namespace are rejected, so rewriting cannot silently discard them.
- `PlatformTarget` creates and authenticates one Session per credential during initialization. `call()` never logs in again.
- Request index and credential index have a deterministic mapping. An account-level lock prevents concurrent use of the same Session, and server session IDs cannot move between credentials or change silently.
- Login and API requests use a 120-second timeout. Gateway errors, timeouts, request failures, non-JSON responses, HTTP failures, and cross-user session IDs are represented by allowlisted error codes; response bodies and credentials do not enter `RequestRecord`.
- Login POST disables automatic redirects. Only manually followed 302/303 redirects on the same effective scheme, host, and port are accepted; 307/308, scheme-relative, userinfo, cross-origin, cross-port, malformed-port, encoded traversal, and base-path escapes are rejected. Redirect GETs are also bounded and use `allow_redirects=False`.
- A normalized base URL keeps its path prefix for login and thinking endpoints. Root paths, trailing slashes, subpaths, and IPv6 authorities are covered by offline tests; query, fragment, and userinfo are rejected.

## Remaining risks

- Tests use fake Sessions and fake model/query objects. They verify the adapter contract but do not prove the deployed login redirect, CSRF configuration, database enum, or response schema matches the checked source at execution time.
- Initializing 32 credentials performs 32 sequential logins. In production, each successful login also schedules an ability-trend task. The platform canary therefore still requires the low-usage and explicit-approval gates in later tasks.
- A separate login to any dedicated account rotates its single-sign-on identifier and invalidates the prepared Session. These accounts must remain exclusive to the evaluation during a run.
- Mode `0600` is applied to the staged credential file before the database commit. Windows ACL hardening remains outside this script, so the credential file is intended for the Linux server path described by the protocol.
- Existing users can be reused only when the existing external credential file is available. The script deliberately refuses to reset an unknown password.
