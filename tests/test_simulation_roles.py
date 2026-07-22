from pathlib import Path

import pytest

from research_eval.simulation.zhipu_roles import RoleClient


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
