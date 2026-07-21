from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

from .models import RequestRecord
from .runner import REQUEST_TIMEOUT_SECONDS


SHORT_PROMPT = "请给我一个算法思路提示，不要直接给出完整答案。"
LONG_PROMPT = "请检查我的算法解释，并追问一个能暴露理解漏洞的问题。"


class PlatformLoginError(RuntimeError):
    """Raised when a dedicated load-test account cannot authenticate."""


class _HiddenInputParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "input":
            return
        values = {name.lower(): value or "" for name, value in attrs}
        if values.get("type", "").lower() == "hidden" and values.get("name"):
            self.hidden[values["name"]] = values.get("value", "")


def validate_users(users: object, required_count: int) -> list[dict[str, str]]:
    if not isinstance(required_count, int) or isinstance(required_count, bool) or required_count < 1:
        raise ValueError("required credential count must be a positive integer")
    if not isinstance(users, list) or not users:
        raise ValueError("credentials must be a non-empty JSON list")
    if len(users) < required_count:
        raise ValueError(f"credentials must contain at least {required_count} users")

    validated: list[dict[str, str]] = []
    seen: set[str] = set()
    for position, item in enumerate(users):
        if not isinstance(item, dict):
            raise ValueError(f"credentials entry {position} must be an object")
        username = item.get("username")
        password = item.get("password")
        if not isinstance(username, str) or not username.startswith("research_load_"):
            raise ValueError("every username must start with research_load_")
        if not isinstance(password, str) or not password:
            raise ValueError(f"credentials entry {position} must contain a password")
        if username in seen:
            raise ValueError(f"duplicate username: {username}")
        seen.add(username)
        validated.append({"username": username, "password": password})
    return validated


def load_users(path: str | Path, required_count: int) -> list[dict[str, str]]:
    credentials_path = Path(path)
    try:
        raw = json.loads(credentials_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("credentials file must contain valid JSON") from exc
    return validate_users(raw, required_count)


class PlatformTarget:
    """Authenticated complete-platform target with one Session per credential.

    Authentication is completed once during initialization because the production
    login route rotates ``User.current_session_id`` on every successful login.
    Calls deterministically map ``request_index % level`` to one credential and
    serialize access to that credential's Session.
    """

    def __init__(
        self,
        base_url: str,
        assignment_id: int,
        request_kind: str,
        credentials: Sequence[dict[str, str]] | str | Path,
        run_id: str,
        *,
        session_factory: Callable[[], requests.Session | Any] = requests.Session,
    ) -> None:
        if request_kind not in {"short", "long"}:
            raise ValueError("request_kind must be short or long")
        if not isinstance(assignment_id, int) or isinstance(assignment_id, bool) or assignment_id < 1:
            raise ValueError("assignment_id must be a positive integer")
        self._origin = _validate_base_url(base_url)
        raw_users = load_users(credentials, 1) if isinstance(credentials, (str, Path)) else list(credentials)
        self._users = validate_users(raw_users, 1)
        self.assignment_id = assignment_id
        self.request_kind = request_kind
        self.run_id = run_id
        self._sessions = [session_factory() for _ in self._users]
        if any(session is None for session in self._sessions):
            raise ValueError("session_factory must return a session")
        self._session_locks = [threading.Lock() for _ in self._users]
        self._session_ids: list[object | None] = [None for _ in self._users]
        self._session_id_owners: dict[object, int] = {}
        self._ownership_lock = threading.Lock()
        for credential, session in zip(self._users, self._sessions):
            self._login(session, credential)

    @property
    def authenticated_user_count(self) -> int:
        return len(self._sessions)

    def call(self, level: int, index: int) -> RequestRecord:
        validate_users(self._users, level)
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ValueError("request index must be a non-negative integer")
        credential_index = index % level
        with self._session_locks[credential_index]:
            return self._call_with_session(level, index, credential_index)

    def _call_with_session(self, level: int, index: int, credential_index: int) -> RequestRecord:
        started_at = datetime.now(timezone.utc).isoformat()
        started = time.perf_counter()
        input_text = SHORT_PROMPT if self.request_kind == "short" else LONG_PROMPT
        status_code = 0
        error_code = "platform_error"
        output = ""

        start_response, request_error = self._post_json(
            self._sessions[credential_index],
            "/thinking/api/start_session",
            {"assignment_id": self.assignment_id},
        )
        if request_error:
            error_code, status_code = request_error
        else:
            status_code = int(start_response.status_code)
            start_body, error_code = _decode_response(start_response)
            if not error_code and 200 <= status_code < 300 and start_body.get("success") is True:
                session_id = start_body.get("session_id")
                error_code = self._claim_session_id(credential_index, session_id)
                if not error_code:
                    payload = self._endpoint_payload(session_id)
                    endpoint_response, request_error = self._post_json(
                        self._sessions[credential_index], self._endpoint_path(), payload
                    )
                    if request_error:
                        error_code, status_code = request_error
                    else:
                        status_code = int(endpoint_response.status_code)
                        endpoint_body, error_code = _decode_response(endpoint_response)
                        if not error_code and 200 <= status_code < 300:
                            field = "hint" if self.request_kind == "short" else "response"
                            value = endpoint_body.get(field)
                            if endpoint_body.get("success") is True and isinstance(value, str):
                                output = value
                                error_code = ""
                            else:
                                error_code = "platform_error"
            elif not error_code:
                error_code = "platform_error"

        return RequestRecord(
            run_id=self.run_id,
            level=level,
            request_index=index,
            target="platform",
            request_kind=self.request_kind,
            started_at=started_at,
            elapsed_seconds=time.perf_counter() - started,
            success=200 <= status_code < 300 and bool(output) and not error_code,
            status_code=status_code,
            error_code=error_code,
            retries=0,
            input_chars=len(input_text),
            output_chars=len(output),
        )

    def _login(self, session: requests.Session | Any, credential: dict[str, str]) -> None:
        login_url = self._url("/login")
        try:
            page = session.get(login_url, timeout=REQUEST_TIMEOUT_SECONDS)
            if not 200 <= int(page.status_code) < 300:
                raise PlatformLoginError("platform login page was unavailable")
            parser = _HiddenInputParser()
            parser.feed(page.text if isinstance(page.text, str) else "")
            form = dict(parser.hidden)
            form.update(
                {
                    "username": credential["username"],
                    "password": credential["password"],
                    "submit": "登录",
                }
            )
            response = session.post(login_url, data=form, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise PlatformLoginError("platform login request failed") from exc

        final_path = urlsplit(str(getattr(response, "url", login_url))).path.rstrip("/")
        if not 200 <= int(response.status_code) < 400 or final_path == "/login":
            raise PlatformLoginError("platform login was rejected")

    def _post_json(
        self, session: requests.Session | Any, path: str, payload: dict[str, object]
    ) -> tuple[Any | None, tuple[str, int] | None]:
        try:
            response = session.post(
                self._url(path), json=payload, timeout=REQUEST_TIMEOUT_SECONDS
            )
        except requests.Timeout:
            return None, ("timeout", 0)
        except requests.RequestException:
            return None, ("request_error", 0)
        status = int(response.status_code)
        if status in {502, 504}:
            return response, ("gateway_error", status)
        if not 200 <= status < 300:
            return response, ("http_error", status)
        return response, None

    def _claim_session_id(self, credential_index: int, session_id: object) -> str:
        if not isinstance(session_id, (str, int)) or isinstance(session_id, bool) or session_id == "":
            return "platform_error"
        with self._ownership_lock:
            existing = self._session_ids[credential_index]
            if existing is not None and existing != session_id:
                return "session_mismatch"
            owner = self._session_id_owners.get(session_id)
            if owner is not None and owner != credential_index:
                return "cross_user_session"
            self._session_ids[credential_index] = session_id
            self._session_id_owners[session_id] = credential_index
        return ""

    def _endpoint_path(self) -> str:
        return (
            "/thinking/api/stage1/hint"
            if self.request_kind == "short"
            else "/thinking/api/stage3/chat"
        )

    def _endpoint_payload(self, session_id: object) -> dict[str, object]:
        if self.request_kind == "short":
            return {"session_id": session_id, "description": SHORT_PROMPT}
        return {
            "session_id": session_id,
            "messages": [{"role": "user", "content": LONG_PROMPT}],
            "student_state": {"source": "research_load_test"},
        }

    def _url(self, path: str) -> str:
        candidate = urljoin(self._origin + "/", path.lstrip("/"))
        parsed = urlsplit(candidate)
        origin = urlsplit(self._origin)
        if (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc):
            raise ValueError("platform URL must stay on the configured base URL")
        return candidate


def _validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("base URL must be an HTTP(S) origin without credentials, query, or fragment")
    port = f":{parsed.port}" if parsed.port is not None else ""
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return urlunsplit((parsed.scheme, f"{host}{port}", "", "", ""))


def _decode_response(response: Any) -> tuple[dict[str, Any], str]:
    try:
        body = response.json()
    except (TypeError, ValueError):
        return {}, "non_json_response"
    if not isinstance(body, dict):
        return {}, "non_json_response"
    return body, ""
