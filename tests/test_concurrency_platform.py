import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
import requests

import research_eval.concurrency.platform as platform_module
from research_eval.concurrency.platform import (
    PlatformLoginError,
    PlatformTarget,
    load_users,
    validate_users,
)
import scripts.provision_research_load_users as provision_module
from scripts.provision_research_load_users import (
    CONFIRM_LITERAL,
    CredentialPublishError,
    CredentialRecoveryError,
    build_parser,
    main as provision_main,
    provision_users,
    validate_provision_request,
)


class FakeResponse:
    def __init__(self, status_code=200, body=None, *, text="", headers=None):
        self.status_code = status_code
        self._body = body
        self.text = text
        self.headers = headers or {}

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(
        self,
        username,
        *,
        endpoint=None,
        start=None,
        login=None,
        redirect_responses=None,
        delay=0,
    ):
        self.username = username
        self.endpoint_response = endpoint or FakeResponse(200, {"success": True, "hint": "ok"})
        self.start_response = start or FakeResponse(
            200, {"success": True, "session_id": f"session-{username}"}
        )
        self.login_response = login or FakeResponse(302, {}, headers={"Location": "/home"})
        self.redirect_responses = list(redirect_responses or [])
        self.delay = delay
        self.get_calls = []
        self.post_calls = []
        self.active_calls = 0
        self.max_active_calls = 0
        self._activity_lock = threading.Lock()

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        if not urlsplit(url).path.endswith("/login"):
            if self.redirect_responses:
                return self.redirect_responses.pop(0)
            return FakeResponse(200, {}, text="authenticated home")
        return FakeResponse(
            200,
            {},
            text='<form><input type="hidden" name="csrf_token" value="csrf-value"></form>',
        )

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        if url.endswith("/login"):
            return self.login_response
        with self._activity_lock:
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            if self.delay:
                time.sleep(self.delay)
            if url.endswith("/thinking/api/start_session"):
                if isinstance(self.start_response, Exception):
                    raise self.start_response
                return self.start_response
            if isinstance(self.endpoint_response, Exception):
                raise self.endpoint_response
            return self.endpoint_response
        finally:
            with self._activity_lock:
                self.active_calls -= 1


def credentials(count=4):
    return [
        {"username": f"research_load_{index:02d}", "password": f"pw-secret-{index}"}
        for index in range(count)
    ]


def make_target(users=None, *, kind="short", sessions=None, base_url="https://example.test"):
    users = users or credentials()
    sessions = sessions or [FakeSession(row["username"]) for row in users]
    iterator = iter(sessions)
    target = PlatformTarget(
        base_url,
        assignment_id=85,
        request_kind=kind,
        credentials=users,
        run_id="run-platform",
        session_factory=lambda: next(iterator),
    )
    return target, sessions


def test_rejects_nonresearch_users():
    with pytest.raises(ValueError, match="research_load_"):
        validate_users([{"username": "student01", "password": "x"}], 1)


@pytest.mark.parametrize("bad", [[], {}, [{"username": "research_load_01"}]])
def test_rejects_malformed_credentials(bad):
    with pytest.raises(ValueError, match="credentials|password"):
        validate_users(bad, 1)


def test_requires_one_user_per_concurrent_worker():
    with pytest.raises(ValueError, match="at least 4"):
        validate_users(credentials(1), 4)


def test_rejects_duplicate_usernames():
    users = credentials(2)
    users[1]["username"] = users[0]["username"]
    with pytest.raises(ValueError, match="duplicate username"):
        validate_users(users, 2)


def test_load_users_reads_json_list_and_checks_required_count(tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps(credentials(2)), encoding="utf-8")
    assert load_users(path, required_count=2)[1]["username"] == "research_load_01"
    with pytest.raises(ValueError, match="at least 3"):
        load_users(path, required_count=3)


def test_load_users_rejects_invalid_json(tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="valid JSON"):
        load_users(path, required_count=1)


def test_login_happens_once_at_initialization_with_csrf_and_timeout():
    target, sessions = make_target(credentials(2))
    assert target.authenticated_user_count == 2
    for index, session in enumerate(sessions):
        assert len(session.get_calls) == 2
        assert all(kwargs["allow_redirects"] is False for _, kwargs in session.get_calls)
        login_url, kwargs = session.post_calls[0]
        assert login_url == "https://example.test/login"
        assert kwargs["timeout"] == 120
        assert kwargs["allow_redirects"] is False
        assert kwargs["data"] == {
            "username": f"research_load_{index:02d}",
            "password": f"pw-secret-{index}",
            "submit": "登录",
            "csrf_token": "csrf-value",
        }


def test_login_failure_is_fail_fast_and_does_not_expose_password():
    session = FakeSession(
        "research_load_00",
        login=FakeResponse(200, {}, text="login rejected"),
    )
    with pytest.raises(PlatformLoginError) as caught:
        make_target(credentials(1), sessions=[session])
    assert "pw-secret-0" not in str(caught.value)


def test_short_call_uses_fixed_endpoint_and_payload_without_relogin():
    target, sessions = make_target(credentials(1))
    row = target.call(1, 0)
    assert row.success is True
    assert row.target == "platform"
    assert row.request_kind == "short"
    assert row.output_chars == 2
    assert len(sessions[0].get_calls) == 2
    assert len([call for call in sessions[0].post_calls if call[0].endswith("/login")]) == 1
    start_url, start_kwargs = sessions[0].post_calls[1]
    endpoint_url, endpoint_kwargs = sessions[0].post_calls[2]
    assert start_url == "https://example.test/thinking/api/start_session"
    assert start_kwargs["json"] == {"assignment_id": 85}
    assert start_kwargs["timeout"] == 120
    assert endpoint_url == "https://example.test/thinking/api/stage1/hint"
    assert endpoint_kwargs["json"] == {
        "session_id": "session-research_load_00",
        "description": "请给我一个算法思路提示，不要直接给出完整答案。",
    }
    assert endpoint_kwargs["timeout"] == 120


def test_long_call_uses_stage3_payload():
    users = credentials(1)
    session = FakeSession(
        users[0]["username"],
        endpoint=FakeResponse(200, {"success": True, "response": "explanation"}),
    )
    target, _ = make_target(users, kind="long", sessions=[session])
    row = target.call(1, 0)
    endpoint_url, endpoint_kwargs = session.post_calls[-1]
    assert row.success is True
    assert row.output_chars == len("explanation")
    assert endpoint_url == "https://example.test/thinking/api/stage3/chat"
    assert endpoint_kwargs["json"] == {
        "session_id": "session-research_load_00",
        "messages": [
            {"role": "user", "content": "请检查我的算法解释，并追问一个能暴露理解漏洞的问题。"}
        ],
        "student_state": {"source": "research_load_test"},
    }


@pytest.mark.parametrize(
    ("response", "expected_code", "expected_status"),
    [
        (FakeResponse(502, {}), "gateway_error", 502),
        (FakeResponse(504, {}), "gateway_error", 504),
        (requests.Timeout("secret timeout"), "timeout", 0),
        (FakeResponse(200, ValueError("not json")), "non_json_response", 200),
    ],
)
def test_endpoint_failures_are_classified_without_body_leak(response, expected_code, expected_status):
    users = credentials(1)
    session = FakeSession(users[0]["username"], endpoint=response)
    target, _ = make_target(users, sessions=[session])
    row = target.call(1, 0)
    assert row.success is False
    assert row.error_code == expected_code
    assert row.status_code == expected_status
    assert "secret" not in str(row.to_dict())


def test_start_session_failure_is_classified_and_skips_endpoint():
    users = credentials(1)
    session = FakeSession(users[0]["username"], start=FakeResponse(504, {}))
    target, _ = make_target(users, sessions=[session])
    row = target.call(1, 0)
    assert row.error_code == "gateway_error"
    assert len(session.post_calls) == 2


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("location", ["/thinking/next", "https://evil.test/steal"])
def test_start_session_redirect_is_not_followed_or_exposed(status, location):
    users = credentials(1)
    session = FakeSession(
        users[0]["username"],
        start=FakeResponse(
            status,
            {"secret_response_body": "must-not-escape"},
            headers={"Location": location},
        ),
    )
    target, _ = make_target(users, sessions=[session])
    row = target.call(1, 0)
    business_posts = [
        (url, kwargs) for url, kwargs in session.post_calls if "/thinking/api/" in url
    ]
    assert row.success is False
    assert row.error_code == "unexpected_redirect"
    assert row.status_code == status
    assert len(business_posts) == 1
    assert business_posts[0][1]["allow_redirects"] is False
    assert location not in str(row.to_dict())
    assert "must-not-escape" not in str(row.to_dict())


@pytest.mark.parametrize("kind", ["short", "long"])
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("location", ["/thinking/next", "https://evil.test/steal"])
def test_stage_business_redirect_is_not_followed_or_exposed(kind, status, location):
    users = credentials(1)
    session = FakeSession(
        users[0]["username"],
        endpoint=FakeResponse(
            status,
            {"secret_response_body": "must-not-escape"},
            headers={"Location": location},
        ),
    )
    target, _ = make_target(users, kind=kind, sessions=[session])
    row = target.call(1, 0)
    business_posts = [
        (url, kwargs) for url, kwargs in session.post_calls if "/thinking/api/" in url
    ]
    assert row.success is False
    assert row.error_code == "unexpected_redirect"
    assert row.status_code == status
    assert len(business_posts) == 2
    assert all(kwargs["allow_redirects"] is False for _, kwargs in business_posts)
    assert location not in str(row.to_dict())
    assert "must-not-escape" not in str(row.to_dict())


def test_rejects_invalid_base_urls_and_never_joins_to_another_origin():
    for url in [
        "example.test",
        "https://user:pass@example.test",
        "https://example.test?a=secret",
        "https://example.test/app#fragment",
    ]:
        with pytest.raises(ValueError, match="base URL"):
            PlatformTarget(url, 85, "short", credentials(1), "run", session_factory=lambda: None)


@pytest.mark.parametrize(
    "location",
    [
        "https://evil.test/home",
        "//evil.test/home",
        "https://user@example.test/home",
        "https://example.test:444/app/home",
        "https://example.test:bad/app/home",
        "/outside-prefix/home",
        "/app/%2e%2e/outside-prefix/home",
        "/app/%252e%252e/outside-prefix/home",
        "/app/safe%252foutside-prefix/home",
        "/app/safe%255coutside-prefix/home",
        "/app/%2525252525252e%2525252525252e/outside-prefix/home",
    ],
)
def test_login_rejects_unsafe_redirects_without_following_them(location):
    session = FakeSession(
        "research_load_00", login=FakeResponse(302, {}, headers={"Location": location})
    )
    with pytest.raises(PlatformLoginError):
        make_target(credentials(1), sessions=[session], base_url="https://example.test/app")
    assert len(session.get_calls) == 1
    assert len(session.post_calls) == 1


@pytest.mark.parametrize("status", [307, 308])
def test_login_rejects_redirects_that_could_repost_credentials(status):
    session = FakeSession(
        "research_load_00",
        login=FakeResponse(status, {}, headers={"Location": "/home"}),
    )
    with pytest.raises(PlatformLoginError):
        make_target(credentials(1), sessions=[session])
    assert len(session.post_calls) == 1
    assert len(session.get_calls) == 1


def test_login_follows_only_bounded_safe_302_and_303_redirects():
    session = FakeSession(
        "research_load_00",
        login=FakeResponse(303, {}, headers={"Location": "home"}),
        redirect_responses=[FakeResponse(302, {}, headers={"Location": "dashboard"})],
    )
    target, _ = make_target(
        credentials(1), sessions=[session], base_url="https://example.test/app/"
    )
    assert target.authenticated_user_count == 1
    assert [url for url, _ in session.get_calls] == [
        "https://example.test/app/login",
        "https://example.test/app/home",
        "https://example.test/app/dashboard",
    ]


def test_login_accepts_explicit_default_port_as_same_origin():
    session = FakeSession(
        "research_load_00",
        login=FakeResponse(
            302,
            {},
            headers={"Location": "https://example.test:443/app/home"},
        ),
    )
    target, _ = make_target(
        credentials(1), sessions=[session], base_url="https://example.test/app"
    )
    assert target.authenticated_user_count == 1


@pytest.mark.parametrize(
    "location",
    [
        "/app/%E4%B8%AD%E6%96%87/home",
        "/app/100%25/home",
        "/app/100%2525/home",
    ],
)
def test_login_allows_normal_unicode_and_literal_percent_paths(location):
    session = FakeSession(
        "research_load_00",
        login=FakeResponse(302, {}, headers={"Location": location}),
    )
    target, _ = make_target(
        credentials(1), sessions=[session], base_url="https://example.test/app"
    )
    assert target.authenticated_user_count == 1


def test_redirect_path_decoding_is_bounded_against_deep_encoding_and_long_input(
    monkeypatch,
):
    calls = 0
    real_unquote = platform_module.unquote

    def counting_unquote(value):
        nonlocal calls
        calls += 1
        return real_unquote(value)

    monkeypatch.setattr(platform_module, "unquote", counting_unquote)

    assert platform_module._has_unsafe_path_segment(
        "/app/%2525252525252e%2525252525252e/home"
    )
    assert calls == platform_module.MAX_PATH_DECODE_ROUNDS
    assert platform_module._has_unsafe_path_segment(
        "/app/" + "a" * platform_module.MAX_REDIRECT_PATH_CHARS
    )
    assert calls == platform_module.MAX_PATH_DECODE_ROUNDS


@pytest.mark.parametrize(
    ("base_url", "login_url", "api_url"),
    [
        (
            "https://example.test/app",
            "https://example.test/app/login",
            "https://example.test/app/thinking/api/start_session",
        ),
        (
            "https://example.test/app/",
            "https://example.test/app/login",
            "https://example.test/app/thinking/api/start_session",
        ),
        (
            "https://[2001:db8::1]:8443/app/",
            "https://[2001:db8::1]:8443/app/login",
            "https://[2001:db8::1]:8443/app/thinking/api/start_session",
        ),
    ],
)
def test_base_url_preserves_normalized_path_prefix(base_url, login_url, api_url):
    session = FakeSession(
        "research_load_00",
        login=FakeResponse(302, {}, headers={"Location": "home"}),
    )
    target, _ = make_target(credentials(1), sessions=[session], base_url=base_url)
    target.call(1, 0)
    assert session.get_calls[0][0] == login_url
    assert session.post_calls[1][0] == api_url


def test_rejects_unsupported_request_kind_before_login():
    with pytest.raises(ValueError, match="short or long"):
        make_target(credentials(1), kind="mixed")


def test_call_rejects_level_above_available_credentials():
    target, _ = make_target(credentials(1))
    with pytest.raises(ValueError, match="at least 2"):
        target.call(2, 0)


def test_credential_index_has_fixed_user_session_mapping_under_concurrency():
    users = credentials(4)
    sessions = [FakeSession(row["username"], delay=0.01) for row in users]
    target, _ = make_target(users, sessions=sessions)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda index: target.call(4, index), range(20)))
    assert all(row.success for row in rows)
    for index, session in enumerate(sessions):
        expected_session = f"session-research_load_{index:02d}"
        api_calls = [kwargs["json"] for url, kwargs in session.post_calls if "/thinking/api/" in url]
        assert api_calls
        assert all(
            payload.get("session_id", expected_session) == expected_session for payload in api_calls
        )
        assert session.max_active_calls == 1
        assert len([url for url, _ in session.post_calls if url.endswith("/login")]) == 1


def test_detects_server_session_id_shared_by_two_users():
    users = credentials(2)
    sessions = [
        FakeSession(row["username"], start=FakeResponse(200, {"success": True, "session_id": "shared"}))
        for row in users
    ]
    target, _ = make_target(users, sessions=sessions)
    assert target.call(2, 0).success is True
    second = target.call(2, 1)
    assert second.success is False
    assert second.error_code == "cross_user_session"
    assert len(sessions[1].post_calls) == 2


def test_password_never_enters_request_record():
    target, _ = make_target(credentials(1))
    row = target.call(1, 0)
    assert "pw-secret" not in str(row.to_dict())


def test_provision_parser_requires_every_guard_argument():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"prefix": "student_"}, "research_load_"),
        ({"count": 0}, "exactly 32"),
        ({"count": 31}, "exactly 32"),
        ({"count": 33}, "exactly 32"),
        ({"assignment_id": 0}, "assignment"),
        ({"confirm": "yes"}, CONFIRM_LITERAL),
    ],
)
def test_provision_guard_rejects_unsafe_values(tmp_path, kwargs, message):
    values = {
        "prefix": "research_load_",
        "count": 32,
        "assignment_id": 85,
        "output": tmp_path / "credentials.json",
        "confirm": CONFIRM_LITERAL,
    }
    values.update(kwargs)
    with pytest.raises(ValueError, match=message):
        validate_provision_request(**values)


class FakeQuery:
    def __init__(self, rows, key):
        self.rows = rows
        self.key = key

    def get(self, value):
        return self.rows.get(value)

    def filter_by(self, **values):
        key = values[self.key]
        return FakeQuery({key: self.rows.get(key)}, self.key)

    def first(self):
        return next((row for row in self.rows.values() if row is not None), None)


class FakeDBSession:
    def __init__(self, commit_outcomes=None):
        self.added = []
        self.deleted = []
        self.commits = 0
        self.rollbacks = 0
        self.commit_outcomes = list(commit_outcomes or [])

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1
        if self.commit_outcomes:
            outcome = self.commit_outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome

    def rollback(self):
        self.rollbacks += 1

    def delete(self, row):
        self.deleted.append(row)


class FakeDB:
    def __init__(self, commit_outcomes=None):
        self.session = FakeDBSession(commit_outcomes)


class FakeUser:
    rows = {}
    query = FakeQuery(rows, "username")

    def __init__(self, **values):
        self.__dict__.update(values)
        self.verification_attempts = []

    @property
    def password(self):
        raise AttributeError

    @password.setter
    def password(self, value):
        self.password_value = value

    def verify_password(self, value):
        self.verification_attempts.append(value)
        return value == getattr(self, "password_value", None)


class FakeAssignment:
    query = FakeQuery({85: object()}, "id")


class Preset:
    def __init__(self, status):
        self.status = status


class FakePreset:
    query = FakeQuery({85: Preset("ready")}, "assignment_id")


def existing_user(index, password=None):
    username = f"research_load_{index:02d}"
    user = FakeUser(
        username=username,
        student_id=username,
        usertype="学生",
        class_name="research_load_test",
    )
    user.password_value = password or f"saved-secret-{index}"
    return user


def existing_state(count=32):
    users = [existing_user(index) for index in range(1, count + 1)]
    rows = {user.username: user for user in users}
    saved = [
        {"username": user.username, "password": user.password_value} for user in users
    ]
    return rows, saved


def configure_fake_users(rows):
    FakeUser.rows = rows
    FakeUser.query = FakeQuery(FakeUser.rows, "username")


def test_provision_creates_only_missing_students_and_writes_secure_credentials(tmp_path):
    rows, existing = existing_state(31)
    configure_fake_users(rows)
    db = FakeDB()
    output = tmp_path / "credentials.json"
    output.write_text(json.dumps(existing), encoding="utf-8")

    result = provision_users(
        db=db,
        User=FakeUser,
        Assignment=FakeAssignment,
        AssignmentThinkingPreset=FakePreset,
        prefix="research_load_",
        count=32,
        assignment_id=85,
        output=output,
        password_factory=lambda: "generated-secret",
    )

    assert result == {"created": 1, "existing": 31, "output": str(output.resolve())}
    assert len(db.session.added) == 1
    created = db.session.added[0]
    assert created.username == "research_load_32"
    assert created.student_id == "research_load_32"
    assert created.usertype == "学生"
    assert created.class_name == "research_load_test"
    assert created.password_value == "generated-secret"
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert len(saved) == 32
    assert saved[-1] == {
        "username": "research_load_32",
        "password": "generated-secret",
    }
    assert all(user.verification_attempts == [user.password_value] for user in rows.values())


def test_provision_refuses_nonready_preset_without_creating_or_writing(tmp_path):
    class NotReadyPreset:
        query = FakeQuery({85: Preset("generating")}, "assignment_id")

    db = FakeDB()
    output = tmp_path / "credentials.json"
    with pytest.raises(ValueError, match="ready"):
        provision_users(
            db=db,
            User=FakeUser,
            Assignment=FakeAssignment,
            AssignmentThinkingPreset=NotReadyPreset,
            prefix="research_load_",
            count=32,
            assignment_id=85,
            output=output,
        )
    assert db.session.added == []
    assert not output.exists()


def test_provision_refuses_existing_user_without_saved_password(tmp_path):
    configure_fake_users({"research_load_01": existing_user(1)})
    with pytest.raises(ValueError, match="existing credentials"):
        provision_users(
            db=FakeDB(),
            User=FakeUser,
            Assignment=FakeAssignment,
            AssignmentThinkingPreset=FakePreset,
            prefix="research_load_",
            count=32,
            assignment_id=85,
            output=tmp_path / "missing.json",
        )


def test_core_rejects_smaller_count_without_truncating_existing_output(tmp_path):
    _, saved = existing_state(32)
    output = tmp_path / "credentials.json"
    original = json.dumps(saved)
    output.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError, match="exactly 32"):
        provision_users(
            db=FakeDB(),
            User=FakeUser,
            Assignment=FakeAssignment,
            AssignmentThinkingPreset=FakePreset,
            prefix="research_load_",
            count=31,
            assignment_id=85,
            output=output,
        )
    assert output.read_text(encoding="utf-8") == original


def test_provision_refuses_unexpected_saved_username_without_rewriting_file(tmp_path):
    _, saved = existing_state(32)
    saved.append({"username": "research_load_99", "password": "do-not-drop"})
    output = tmp_path / "credentials.json"
    original = json.dumps(saved)
    output.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError, match="outside the expected 32-account namespace"):
        provision_users(
            db=FakeDB(),
            User=FakeUser,
            Assignment=FakeAssignment,
            AssignmentThinkingPreset=FakePreset,
            prefix="research_load_",
            count=32,
            assignment_id=85,
            output=output,
        )
    assert output.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("username", "research_load_other", "username"),
        ("student_id", "different-id", "student_id"),
        ("usertype", "教师", "student"),
        ("class_name", "real-course", "class_name"),
        ("password_value", "wrong-password", "password"),
    ],
)
def test_reused_account_must_match_full_dedicated_identity(tmp_path, field, value, message):
    rows, saved = existing_state(32)
    tested_user = rows["research_load_01"]
    original_password = tested_user.password_value
    setattr(tested_user, field, value)
    expected_password = value if field == "password_value" else original_password
    configure_fake_users(rows)
    output = tmp_path / "credentials.json"
    output.write_text(json.dumps(saved), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        provision_users(
            db=FakeDB(),
            User=FakeUser,
            Assignment=FakeAssignment,
            AssignmentThinkingPreset=FakePreset,
            prefix="research_load_",
            count=32,
            assignment_id=85,
            output=output,
        )
    assert tested_user.password_value == expected_password


def test_staging_failure_does_not_add_users_or_change_existing_output(tmp_path, monkeypatch):
    configure_fake_users({})
    db = FakeDB()
    output = tmp_path / "credentials.json"
    original = json.dumps(existing_state(32)[1])
    output.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        provision_module,
        "_stage_credentials",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(CredentialPublishError, match="stage"):
        provision_users(
            db=db,
            User=FakeUser,
            Assignment=FakeAssignment,
            AssignmentThinkingPreset=FakePreset,
            prefix="research_load_",
            count=32,
            assignment_id=85,
            output=output,
        )
    assert db.session.added == []
    assert db.session.commits == 0
    assert output.read_text(encoding="utf-8") == original


def test_commit_failure_rolls_back_and_removes_staged_credentials(tmp_path):
    configure_fake_users({})
    db = FakeDB([RuntimeError("db unavailable")])
    output = tmp_path / "credentials.json"
    original = json.dumps(existing_state(32)[1])
    output.write_text(original, encoding="utf-8")
    with pytest.raises(CredentialPublishError, match="database commit"):
        provision_users(
            db=db,
            User=FakeUser,
            Assignment=FakeAssignment,
            AssignmentThinkingPreset=FakePreset,
            prefix="research_load_",
            count=32,
            assignment_id=85,
            output=output,
        )
    assert len(db.session.added) == 32
    assert db.session.rollbacks == 1
    assert output.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".credentials.json.*")) == []


def test_replace_failure_compensates_new_users_and_preserves_output(tmp_path, monkeypatch):
    configure_fake_users({})
    db = FakeDB([None, None])
    output = tmp_path / "credentials.json"
    original = json.dumps(existing_state(32)[1])
    output.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        provision_module,
        "_replace_staged_credentials",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("replace denied")),
    )
    with pytest.raises(CredentialPublishError, match="compensated"):
        provision_users(
            db=db,
            User=FakeUser,
            Assignment=FakeAssignment,
            AssignmentThinkingPreset=FakePreset,
            prefix="research_load_",
            count=32,
            assignment_id=85,
            output=output,
        )
    assert len(db.session.deleted) == 32
    assert db.session.commits == 2
    assert output.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".credentials.json.*")) == []


def test_atomic_replace_does_not_run_a_fallible_chmod_after_publication(tmp_path, monkeypatch):
    output = tmp_path / "credentials.json"
    output.write_text("old", encoding="utf-8")
    staged = tmp_path / ".credentials.json.staged"
    staged.write_text("new", encoding="utf-8")
    os.chmod(staged, 0o600)
    monkeypatch.setattr(
        provision_module.os,
        "chmod",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("late chmod failure")),
    )
    provision_module._replace_staged_credentials(staged, output)
    assert output.read_text(encoding="utf-8") == "new"
    assert not staged.exists()


def test_failed_compensation_keeps_secure_recovery_file(tmp_path, monkeypatch):
    configure_fake_users({})
    db = FakeDB([None, RuntimeError("compensation unavailable")])
    output = tmp_path / "credentials.json"
    original = json.dumps(existing_state(32)[1])
    output.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        provision_module,
        "_replace_staged_credentials",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("replace denied")),
    )
    with pytest.raises(CredentialRecoveryError) as caught:
        provision_users(
            db=db,
            User=FakeUser,
            Assignment=FakeAssignment,
            AssignmentThinkingPreset=FakePreset,
            prefix="research_load_",
            count=32,
            assignment_id=85,
            output=output,
        )
    recovery_path = caught.value.recovery_path
    assert recovery_path.exists()
    assert str(recovery_path) in str(caught.value)
    assert "saved-secret" not in str(caught.value)
    assert db.session.rollbacks == 1
    assert output.read_text(encoding="utf-8") == original
    recovery_path.unlink()


class FakeAppContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeApp:
    def app_context(self):
        return FakeAppContext()


def test_cli_sets_config_before_single_app_import_and_uses_created_app(tmp_path, monkeypatch):
    events = []
    fake_app = FakeApp()

    def forbidden_factory(*args, **kwargs):
        raise AssertionError("create_app must not be called by provisioning CLI")

    def fake_import(name):
        events.append((name, os.environ.get("FLASK_CONFIG")))
        if name == "app":
            return SimpleNamespace(app=fake_app, create_app=forbidden_factory)
        if name == "models":
            return SimpleNamespace(
                db=object(),
                User=object(),
                Assignment=object(),
                AssignmentThinkingPreset=object(),
            )
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.delenv("FLASK_CONFIG", raising=False)
    monkeypatch.setattr(provision_module.importlib, "import_module", fake_import)
    monkeypatch.setattr(
        provision_module,
        "provision_users",
        lambda **kwargs: {"created": 32, "existing": 0, "output": str(tmp_path / "users.json")},
    )
    result = provision_main(
        [
            "--prefix",
            "research_load_",
            "--count",
            "32",
            "--assignment-id",
            "85",
            "--output",
            str(tmp_path / "users.json"),
            "--confirm",
            CONFIRM_LITERAL,
            "--config",
            "production",
        ]
    )
    assert result == 0
    assert events == [("app", "production"), ("models", "production")]


def test_cli_rejects_non32_count_before_importing_app(tmp_path, monkeypatch):
    imported = []
    monkeypatch.setattr(
        provision_module.importlib,
        "import_module",
        lambda name: imported.append(name),
    )
    with pytest.raises(ValueError, match="exactly 32"):
        provision_main(
            [
                "--prefix",
                "research_load_",
                "--count",
                "31",
                "--assignment-id",
                "85",
                "--output",
                str(tmp_path / "users.json"),
                "--confirm",
                CONFIRM_LITERAL,
            ]
        )
    assert imported == []

def test_call_kind_reuses_authenticated_slot_without_mutating_default_kind():
    target = object.__new__(PlatformTarget)
    target.request_kind = "short"
    target._users = [{"username": "research_load_01", "password": "x"}]
    target._session_locks = [threading.Lock()]
    seen = []

    def fake_call(level, index, credential_index, request_kind):
        seen.append((level, index, credential_index, request_kind))
        return SimpleNamespace(request_kind=request_kind)

    target._call_with_session = fake_call

    row = target.call_kind(1, 0, "long")

    assert row.request_kind == "long"
    assert target.request_kind == "short"
    assert seen == [(1, 0, 0, "long")]
    with pytest.raises(ValueError, match="short or long"):
        target.call_kind(1, 0, "mixed")
