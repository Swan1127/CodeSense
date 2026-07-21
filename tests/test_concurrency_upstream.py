from __future__ import annotations

from collections import deque

import pytest
import requests

from research_eval.concurrency.runner import REQUEST_TIMEOUT_SECONDS
from research_eval.concurrency.upstream import ZhipuTarget


class FakeResponse:
    def __init__(self, status_code: int, body: object = None, *, json_error: Exception | None = None):
        self.status_code = status_code
        self._body = body
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._body


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = deque(outcomes)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        outcome = self.outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def success_response(content: str = "ok") -> FakeResponse:
    return FakeResponse(
        200,
        {
            "id": "chatcmpl-test",
            "created": 1,
            "model": "glm-4.5-flash",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": content}}
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )


def test_retries_429_and_records_retry_without_leaking_key(monkeypatch):
    sleeps = []
    monkeypatch.setattr("research_eval.concurrency.upstream.time.sleep", sleeps.append)
    session = FakeSession(
        [
            FakeResponse(429, {"error": {"code": "1305", "message": "busy"}}),
            success_response(),
        ]
    )

    row = ZhipuTarget("secret-api-key", "run-1", "short", session).call(2, 0)

    assert row.success is True
    assert row.status_code == 200
    assert row.error_code == ""
    assert row.retries == 1
    assert row.level == 2
    assert row.request_index == 0
    assert sleeps == [2]
    assert "secret-api-key" not in str(row.to_dict())


def test_retries_json_error_code_1305_even_when_http_status_is_200(monkeypatch):
    sleeps = []
    monkeypatch.setattr("research_eval.concurrency.upstream.time.sleep", sleeps.append)
    session = FakeSession(
        [
            FakeResponse(200, {"error": {"code": 1305, "message": "rate limited"}}),
            success_response("recovered"),
        ]
    )

    row = ZhipuTarget("test-key", "run-2", "long", session).call(4, 3)

    assert row.success is True
    assert row.retries == 1
    assert row.output_chars == len("recovered")
    assert sleeps == [2]


def test_stops_after_five_attempts_with_exponential_backoff(monkeypatch):
    sleeps = []
    monkeypatch.setattr("research_eval.concurrency.upstream.time.sleep", sleeps.append)
    session = FakeSession(
        [FakeResponse(429, {"error": {"code": "1305"}}) for _ in range(5)]
    )

    row = ZhipuTarget("test-key", "run-3", "short", session).call(8, 5)

    assert row.success is False
    assert row.status_code == 429
    assert row.error_code == "1305"
    assert row.retries == 4
    assert len(session.calls) == 5
    assert sleeps == [2, 4, 8, 16]


@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [
        (requests.Timeout("timed out with secret-api-key"), "timeout"),
        (requests.ConnectionError("failed with secret-api-key"), "connection_error"),
        (requests.RequestException("request contains secret-api-key"), "request_error"),
    ],
)
def test_retries_transport_failures_and_sanitizes_exception_text(
    monkeypatch, failure, expected_error
):
    sleeps = []
    monkeypatch.setattr("research_eval.concurrency.upstream.time.sleep", sleeps.append)
    session = FakeSession([failure, failure, failure, failure, failure])

    row = ZhipuTarget("secret-api-key", "run-4", "short", session).call(1, 0)

    assert row.success is False
    assert row.status_code == 0
    assert row.error_code == expected_error
    assert row.retries == 4
    assert sleeps == [2, 4, 8, 16]
    assert "secret-api-key" not in str(row.to_dict())


def test_non_json_response_returns_sanitized_failure_without_raising(monkeypatch):
    sleeps = []
    monkeypatch.setattr("research_eval.concurrency.upstream.time.sleep", sleeps.append)
    session = FakeSession(
        [FakeResponse(502, json_error=ValueError("HTML body with secret-api-key"))]
    )

    row = ZhipuTarget("secret-api-key", "run-5", "long", session).call(1, 0)

    assert row.success is False
    assert row.status_code == 502
    assert row.error_code == "non_json_response"
    assert row.retries == 0
    assert sleeps == []
    assert "secret-api-key" not in str(row.to_dict())


@pytest.mark.parametrize(("request_kind", "max_tokens"), [("short", 300), ("long", 800)])
def test_posts_expected_payload_headers_and_timeout(request_kind, max_tokens):
    session = FakeSession([success_response("answer")])
    target = ZhipuTarget("test-key", "run-6", request_kind, session)

    row = target.call(3, 7)

    assert row.success is True
    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert url == "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    assert kwargs["timeout"] == REQUEST_TIMEOUT_SECONDS == 120
    assert kwargs["headers"] == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
    }
    assert kwargs["json"] == {
        "model": "glm-4.5-flash",
        "messages": [{"role": "user", "content": target.prompt}],
        "thinking": {"type": "disabled"},
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    assert row.input_chars == len(target.prompt)
    assert "test-key" not in str(row.to_dict())


def test_rejects_unknown_request_kind_without_making_a_request():
    session = FakeSession([success_response()])

    with pytest.raises(ValueError, match="short or long"):
        ZhipuTarget("test-key", "run-7", "mixed", session)

    assert session.calls == []
