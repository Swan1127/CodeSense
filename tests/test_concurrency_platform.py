import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import requests

from research_eval.concurrency.platform import (
    PlatformLoginError,
    PlatformTarget,
    load_users,
    validate_users,
)
from scripts.provision_research_load_users import (
    CONFIRM_LITERAL,
    build_parser,
    provision_users,
    validate_provision_request,
)


class FakeResponse:
    def __init__(self, status_code=200, body=None, *, text="", url="https://example.test/home"):
        self.status_code = status_code
        self._body = body
        self.text = text
        self.url = url

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self, username, *, endpoint=None, start=None, login=None, delay=0):
        self.username = username
        self.endpoint_response = endpoint or FakeResponse(200, {"success": True, "hint": "ok"})
        self.start_response = start or FakeResponse(
            200, {"success": True, "session_id": f"session-{username}"}
        )
        self.login_response = login or FakeResponse(200, {}, url="https://example.test/home")
        self.delay = delay
        self.get_calls = []
        self.post_calls = []
        self.active_calls = 0
        self.max_active_calls = 0
        self._activity_lock = threading.Lock()

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse(
            200,
            {},
            text='<form><input type="hidden" name="csrf_token" value="csrf-value"></form>',
            url=url,
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


def make_target(users=None, *, kind="short", sessions=None):
    users = users or credentials()
    sessions = sessions or [FakeSession(row["username"]) for row in users]
    iterator = iter(sessions)
    target = PlatformTarget(
        "https://example.test/base?ignored=no" if False else "https://example.test",
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
        assert len(session.get_calls) == 1
        login_url, kwargs = session.post_calls[0]
        assert login_url == "https://example.test/login"
        assert kwargs["timeout"] == 120
        assert kwargs["data"] == {
            "username": f"research_load_{index:02d}",
            "password": f"pw-secret-{index}",
            "submit": "登录",
            "csrf_token": "csrf-value",
        }


def test_login_failure_is_fail_fast_and_does_not_expose_password():
    session = FakeSession(
        "research_load_00",
        login=FakeResponse(200, {}, url="https://example.test/login"),
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
    assert len(sessions[0].get_calls) == 1
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


def test_rejects_invalid_base_urls_and_never_joins_to_another_origin():
    for url in ["example.test", "https://user:pass@example.test", "https://example.test?a=secret"]:
        with pytest.raises(ValueError, match="base URL"):
            PlatformTarget(url, 85, "short", credentials(1), "run", session_factory=lambda: None)


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
        ({"count": 0}, "between 1 and 32"),
        ({"count": 33}, "between 1 and 32"),
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
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class FakeDB:
    def __init__(self):
        self.session = FakeDBSession()


class FakeUser:
    rows = {}
    query = FakeQuery(rows, "username")

    def __init__(self, **values):
        self.__dict__.update(values)

    @property
    def password(self):
        raise AttributeError

    @password.setter
    def password(self, value):
        self.password_value = value


class FakeAssignment:
    query = FakeQuery({85: object()}, "id")


class Preset:
    def __init__(self, status):
        self.status = status


class FakePreset:
    query = FakeQuery({85: Preset("ready")}, "assignment_id")


def test_provision_creates_only_missing_students_and_writes_secure_credentials(tmp_path):
    FakeUser.rows = {"research_load_01": FakeUser(username="research_load_01", usertype="学生")}
    FakeUser.query = FakeQuery(FakeUser.rows, "username")
    db = FakeDB()
    output = tmp_path / "credentials.json"
    existing = [{"username": "research_load_01", "password": "existing-secret"}]
    output.write_text(json.dumps(existing), encoding="utf-8")

    result = provision_users(
        db=db,
        User=FakeUser,
        Assignment=FakeAssignment,
        AssignmentThinkingPreset=FakePreset,
        prefix="research_load_",
        count=2,
        assignment_id=85,
        output=output,
        password_factory=lambda: "generated-secret",
    )

    assert result == {"created": 1, "existing": 1, "output": str(output.resolve())}
    assert len(db.session.added) == 1
    created = db.session.added[0]
    assert created.username == "research_load_02"
    assert created.usertype == "学生"
    assert created.password_value == "generated-secret"
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved == [
        {"username": "research_load_01", "password": "existing-secret"},
        {"username": "research_load_02", "password": "generated-secret"},
    ]


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
            count=1,
            assignment_id=85,
            output=output,
        )
    assert db.session.added == []
    assert not output.exists()


def test_provision_refuses_existing_user_without_saved_password(tmp_path):
    FakeUser.rows = {"research_load_01": FakeUser(username="research_load_01", usertype="学生")}
    FakeUser.query = FakeQuery(FakeUser.rows, "username")
    with pytest.raises(ValueError, match="existing credentials"):
        provision_users(
            db=FakeDB(),
            User=FakeUser,
            Assignment=FakeAssignment,
            AssignmentThinkingPreset=FakePreset,
            prefix="research_load_",
            count=1,
            assignment_id=85,
            output=tmp_path / "missing.json",
        )
