from dataclasses import FrozenInstanceError, replace

import pytest

from research_eval.concurrency.metrics import evaluate_stop, summarize_level
from research_eval.concurrency.models import RequestRecord


def record(index, elapsed, *, ok=True, status=200, code="", retries=0):
    return RequestRecord(
        run_id="run-1",
        level=4,
        request_index=index,
        target="upstream",
        request_kind="short",
        started_at="2026-07-21T00:00:00Z",
        elapsed_seconds=elapsed,
        success=ok,
        status_code=status,
        error_code=code,
        retries=retries,
        input_chars=20,
        output_chars=30,
    )


def test_request_record_is_immutable_and_serializable():
    row = record(0, 1.5)

    assert row.to_dict()["request_index"] == 0
    with pytest.raises(FrozenInstanceError):
        row.success = False


def test_summary_and_rate_limit_stop():
    rows = [record(i, i + 1) for i in range(19)]
    rows += [record(19, 20, ok=False, status=429, code="1305")]

    summary = summarize_level(rows)

    assert summary.total == 20
    assert summary.success_rate == 0.95
    assert summary.error_rate == 1 / 20
    assert summary.rate_limit_rate == 0.05
    assert summary.p95_seconds >= 19
    assert evaluate_stop(summary).stop is False


def test_stop_above_rate_limit_threshold():
    rows = [record(i, 1) for i in range(17)]
    rows += [record(i, 2, ok=False, status=429, code="1305") for i in range(17, 20)]

    assert "rate_limit" in evaluate_stop(summarize_level(rows)).reasons


def test_rate_limit_threshold_is_strictly_greater_than_ten_percent():
    rows = [record(i, 1) for i in range(18)]
    rows += [record(i, 1, ok=False, status=429) for i in range(18, 20)]

    decision = evaluate_stop(summarize_level(rows))

    assert summarize_level(rows).rate_limit_rate == 0.1
    assert "rate_limit" not in decision.reasons


def test_stop_on_gateway_error():
    summary = summarize_level([record(0, 2, ok=False, status=504)])

    decision = evaluate_stop(summary)

    assert decision.stop is True
    assert "gateway_error" in decision.reasons


def test_worker_timeout_counts_as_gateway_error():
    summary = summarize_level([record(0, 2, ok=False, code="worker_timeout")])

    assert summary.gateway_errors == 1
    assert "gateway_error" in evaluate_stop(summary).reasons


def test_error_threshold_is_strictly_greater_than_five_percent():
    rows = [record(i, 1) for i in range(19)]
    rows.append(record(19, 1, ok=False, status=400))

    decision = evaluate_stop(summarize_level(rows))

    assert summarize_level(rows).error_rate == 1 / 20
    assert "error_rate" not in decision.reasons


def test_summary_reports_retry_rate_and_throughput():
    rows = [record(0, 2, retries=1), record(1, 4)]

    summary = summarize_level(rows)

    assert summary.retry_rate == 0.5
    assert summary.throughput_per_second == 0.5
    assert summary.mean_seconds == 3


def test_empty_records_are_rejected():
    with pytest.raises(ValueError, match="records must not be empty"):
        summarize_level([])


def test_summary_rejects_mixed_levels():
    rows = [record(0, 1), replace(record(1, 1), level=5)]

    with pytest.raises(ValueError, match="same level"):
        summarize_level(rows)
