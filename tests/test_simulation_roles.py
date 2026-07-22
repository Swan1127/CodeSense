from pathlib import Path
import json

import pytest
import requests

from research_eval.simulation.zhipu_roles import BACKOFF_SECONDS, MAX_ATTEMPTS, RoleClient


class FakeResponse:
    status_code = 200

    @staticmethod
    def json():
        return {"choices": [{"message": {"content": "ok"}}]}


class FakeTransport:
    def __init__(self):
        self.payloads = []
        self.headers = []
        self.timeouts = []

    def post(self, url, *, headers, json, timeout):
        self.payloads.append(json)
        self.headers.append(headers)
        self.timeouts.append(timeout)
        return FakeResponse()


def test_role_calls_do_not_share_messages():
    transport = FakeTransport()
    client = RoleClient("secret", transport=transport)

    client.complete(
        "learner", "learner prompt", [{"role": "user", "content": "learner-only"}], 0.6, 400
    )
    client.complete(
        "judge", "judge prompt", [{"role": "user", "content": "judge-only"}], 0.0, 500
    )

    first, second = transport.payloads
    assert "judge-only" not in str(first)
    assert "learner-only" not in str(second)
    assert first["messages"] is not second["messages"]


def test_learner_and_judge_payloads_reject_condition_labels():
    client = RoleClient("secret", transport=FakeTransport())

    with pytest.raises(ValueError, match="condition label"):
        client.complete(
            "judge", "judge prompt", [{"role": "user", "content": "This is C2"}], 0.0, 500
        )


def test_role_response_and_payload_exclude_credentials():
    transport = FakeTransport()
    client = RoleClient("secret", transport=transport)

    response = client.complete(
        "learner", "learner prompt", [{"role": "user", "content": "task"}], 0.6, 400
    )

    assert response.content == "ok"
    assert "secret" not in repr(response)
    assert transport.payloads[0]["model"] == "glm-4.5-flash"
    assert transport.payloads[0]["thinking"] == {"type": "disabled"}
    assert transport.timeouts == [120]


def test_prompt_files_define_strict_role_boundaries():
    root = Path("research/guided_learning_paper/experiments/simulation/prompts")
    learner = (root / "learner.txt").read_text(encoding="utf-8")
    judge = (root / "judge.txt").read_text(encoding="utf-8")

    assert "state_before" in learner
    assert "applied_transition" in learner
    assert "不得凭空掌握" in learner
    assert "条件编号" in judge
    assert "证据" in judge


class SequencedTransport:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def post(self, url, *, headers, json, timeout):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class StatusResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body

    def json(self):
        return self.body


def test_transient_503_is_retried_before_success():
    transport = SequencedTransport(
        [
            StatusResponse(503, {"error": {"code": "service_unavailable"}}),
            StatusResponse(200, {"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    sleeps = []
    client = RoleClient("secret", transport=transport, sleep_fn=sleeps.append)

    response = client.complete(
        "learner", "prompt", [{"role": "user", "content": "task"}], 0.6, 400
    )

    assert response.success is True
    assert response.retries == 1
    assert transport.calls == 2
    assert sleeps == [2]


def test_connection_error_is_retried_before_success():
    transport = SequencedTransport(
        [
            requests.ConnectionError("temporary"),
            StatusResponse(200, {"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    client = RoleClient("secret", transport=transport, sleep_fn=lambda _: None)

    response = client.complete(
        "learner", "prompt", [{"role": "user", "content": "task"}], 0.6, 400
    )

    assert response.success is True
    assert response.retries == 1
    assert transport.calls == 2


def test_retry_policy_is_recorded_in_freeze_manifest():
    path = Path("research/guided_learning_paper/experiments/simulation/config/freeze_manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    policy = manifest["role_parameters"]["retry_policy"]

    assert policy["max_attempts"] == MAX_ATTEMPTS
    assert tuple(policy["backoff_seconds"]) == BACKOFF_SECONDS
    assert policy["retry_on_connection_error"] is True
    assert policy["retry_on_empty_success"] is True
