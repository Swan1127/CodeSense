import math
import statistics

from .models import LevelSummary, RequestRecord, StopDecision


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize_level(records: list[RequestRecord]) -> LevelSummary:
    if not records:
        raise ValueError("records must not be empty")

    total = len(records)
    elapsed = [row.elapsed_seconds for row in records]
    successful = sum(row.success for row in records)
    failed = sum(not row.success for row in records)
    rate_limited = sum(
        row.status_code == 429 or row.error_code == "1305" for row in records
    )
    gateway = sum(
        row.status_code in {502, 504} or row.error_code == "worker_timeout"
        for row in records
    )
    wall = max(elapsed)

    return LevelSummary(
        level=records[0].level,
        total=total,
        successful=successful,
        success_rate=successful / total,
        error_rate=failed / total,
        rate_limit_rate=rate_limited / total,
        throughput_per_second=successful / wall if wall else 0.0,
        mean_seconds=statistics.fmean(elapsed),
        p50_seconds=_percentile(elapsed, 0.50),
        p95_seconds=_percentile(elapsed, 0.95),
        p99_seconds=_percentile(elapsed, 0.99),
        retry_rate=sum(row.retries > 0 for row in records) / total,
        gateway_errors=gateway,
    )


def evaluate_stop(summary: LevelSummary) -> StopDecision:
    reasons = []
    if summary.error_rate > 0.05:
        reasons.append("error_rate")
    if summary.rate_limit_rate > 0.10:
        reasons.append("rate_limit")
    if summary.p95_seconds > 60:
        reasons.append("p95_latency")
    if summary.gateway_errors:
        reasons.append("gateway_error")
    return StopDecision(bool(reasons), tuple(reasons))
