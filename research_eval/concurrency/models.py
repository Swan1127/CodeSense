from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RequestRecord:
    run_id: str
    level: int
    request_index: int
    target: str
    request_kind: str
    started_at: str
    elapsed_seconds: float
    success: bool
    status_code: int
    error_code: str
    retries: int
    input_chars: int
    output_chars: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class LevelSummary:
    level: int
    total: int
    successful: int
    success_rate: float
    error_rate: float
    rate_limit_rate: float
    throughput_per_second: float
    mean_seconds: float
    p50_seconds: float
    p95_seconds: float
    p99_seconds: float
    retry_rate: float
    gateway_errors: int


@dataclass(frozen=True)
class StopDecision:
    stop: bool
    reasons: tuple[str, ...]
