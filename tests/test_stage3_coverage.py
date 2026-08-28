import pytest

from utils.agents.contracts import FeynmanState
from utils.agents.coverage import (
    CoverageConfig,
    apply_coverage_assessment,
    load_coverage_config,
)


def merged_state(base: FeynmanState, patch):
    values = {**base.__dict__, **patch}
    return FeynmanState(**values)


def test_load_coverage_config_uses_safe_defaults_when_legacy_config_has_no_coverage():
    config = load_coverage_config({"feynman_rounds": 5, "student_persona": "curious"}, ["循环边界", "不变量"])

    assert config == CoverageConfig()


def test_covered_concept_completes_immediately_and_advances_to_next_concept():
    state = FeynmanState(session_id=12)
    decision = apply_coverage_assessment(
        state,
        ["循环边界", "不变量"],
        config=CoverageConfig(),
        concept="循环边界",
        dimension="core",
        assessment="covered",
        evidence="我能解释为什么循环条件必须排除越界索引。",
        event_id="evt-1",
    )

    assert decision.concept_status == "covered"
    assert decision.attempts == 1
    assert decision.next_concept == "不变量"
    assert decision.next_dimension == "core"
    assert decision.ready_for_code is False
    assert decision.coverage_score == 0.5
    assert decision.state_patch["pending_probe"] == {
        "concept": "不变量",
        "dimension": "core",
    }
    assert decision.state_patch["unresolved_concepts"] == ["不变量"]
    assert decision.state_patch["concept_coverage"] == [{
        "concept": "循环边界",
        "status": "covered",
        "attempts": 1,
        "used_dimensions": ["core"],
        "attempt_event_ids": ["evt-1"],
        "accepted_evidence_count": 1,
        "evidence_event_ids": ["evt-1"],
        "last_evidence_event_id": "evt-1",
    }, {
        "concept": "不变量",
        "status": "unseen",
        "attempts": 0,
        "used_dimensions": [],
        "attempt_event_ids": [],
        "accepted_evidence_count": 0,
        "evidence_event_ids": [],
        "last_evidence_event_id": None,
    }]


def test_partial_attempts_require_distinct_dimensions_and_stop_after_max_attempts():
    state = FeynmanState(session_id=12)
    first = apply_coverage_assessment(
        state,
        ["循环边界", "不变量"],
        config=CoverageConfig(),
        concept="循环边界",
        dimension="core",
        assessment="partial",
        evidence="我只知道它和索引范围有关，但原因说不完整。",
        event_id="evt-1",
    )
    second_state = merged_state(state, first.state_patch)

    with pytest.raises(ValueError, match="dimension"):
        apply_coverage_assessment(
            second_state,
            ["循环边界", "不变量"],
            config=CoverageConfig(),
            concept="循环边界",
            dimension="core",
            assessment="partial",
            evidence="我还是只会重复上一句。",
            event_id="evt-2",
        )

    second = apply_coverage_assessment(
        second_state,
        ["循环边界", "不变量"],
        config=CoverageConfig(),
        concept="循环边界",
        dimension="edge_case",
        assessment="partial",
        evidence="我能补充空数组时为什么不能访问第一个元素，但还不会迁移到一般情况。",
        event_id="evt-2",
    )
    third_state = merged_state(second_state, second.state_patch)

    assert second.concept_status == "partial"
    assert second.attempts == 2
    assert second.next_concept == "不变量"
    assert second.next_dimension == "core"
    assert second.state_patch["pending_probe"] == {
        "concept": "不变量",
        "dimension": "core",
    }

    with pytest.raises(ValueError, match="max probes"):
        apply_coverage_assessment(
            third_state,
            ["循环边界", "不变量"],
            config=CoverageConfig(),
            concept="循环边界",
            dimension="application",
            assessment="partial",
            evidence="第三次还想继续同一个概念。",
            event_id="evt-3",
        )


def test_off_topic_consumes_attempt_without_marking_covered():
    state = FeynmanState(session_id=12)

    decision = apply_coverage_assessment(
        state,
        ["循环边界", "不变量"],
        config=CoverageConfig(),
        concept="循环边界",
        dimension="core",
        assessment="off_topic",
        evidence="我一直在说变量命名风格，没有解释循环边界。",
        event_id="evt-1",
    )

    assert decision.concept_status == "off_topic"
    assert decision.attempts == 1
    assert decision.coverage_score == 0.0
    assert decision.state_patch["concept_coverage"][0]["accepted_evidence_count"] == 0
    assert decision.state_patch["pending_probe"] == {
        "concept": "循环边界",
        "dimension": "edge_case",
    }


def test_empty_evidence_is_rejected_before_state_changes():
    state = FeynmanState(session_id=12)

    with pytest.raises(ValueError, match="evidence"):
        apply_coverage_assessment(
            state,
            ["循环边界"],
            config=CoverageConfig(),
            concept="循环边界",
            dimension="core",
            assessment="covered",
            evidence="   ",
            event_id="evt-1",
        )

    assert state.concept_coverage == []
    assert state.coverage_score == 0.0
    assert state.pending_probe is None


def test_ready_for_code_requires_minimum_score_and_no_pending_probe():
    config = CoverageConfig(min_coverage=1.0)
    state = FeynmanState(session_id=12)

    first = apply_coverage_assessment(
        state,
        ["循环边界", "不变量"],
        config=config,
        concept="循环边界",
        dimension="core",
        assessment="covered",
        evidence="我能解释索引上界为什么是开区间。",
        event_id="evt-1",
    )
    second = apply_coverage_assessment(
        merged_state(state, first.state_patch),
        ["循环边界", "不变量"],
        config=config,
        concept="不变量",
        dimension="core",
        assessment="covered",
        evidence="我能说明每轮循环前后都保持的条件。",
        event_id="evt-2",
    )

    assert first.ready_for_code is False
    assert second.ready_for_code is True
    assert second.coverage_score == 1.0
    assert second.state_patch["pending_probe"] is None
    assert second.state_patch["unresolved_concepts"] == []


def test_coverage_score_uses_deterministic_equal_weights_and_stays_bounded():
    config = CoverageConfig(min_coverage=0.34)
    state = FeynmanState(session_id=12)

    first = apply_coverage_assessment(
        state,
        ["循环边界", "不变量", "终止条件"],
        config=config,
        concept="循环边界",
        dimension="core",
        assessment="covered",
        evidence="我能解释为什么最后一个有效索引是 n - 1。",
        event_id="evt-1",
    )
    second = apply_coverage_assessment(
        merged_state(state, first.state_patch),
        ["循环边界", "不变量", "终止条件"],
        config=config,
        concept="不变量",
        dimension="core",
        assessment="partial",
        evidence="我知道它每轮都要成立，但还说不清具体内容。",
        event_id="evt-2",
    )

    assert first.coverage_score == pytest.approx(1 / 3)
    assert second.coverage_score == pytest.approx(0.5)
    assert 0.0 <= second.coverage_score <= 1.0
