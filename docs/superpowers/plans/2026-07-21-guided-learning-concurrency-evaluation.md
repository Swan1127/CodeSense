# Guided-Learning Concurrency Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safe, observable staircase load-test tool that separates Zhipu upstream capacity from the complete CodeSense HTTP path and produces auditable paper-ready results.

**Architecture:** Add a research-only Python package with injectable load targets, immutable request records, staircase stopping rules, JSONL/CSV output, and plots. The upstream target calls the Zhipu endpoint with explicit retry instrumentation; the platform target authenticates dedicated load-test users and calls the existing `/thinking/api/*` routes without changing production routes.

**Tech Stack:** Python 3, dataclasses, `concurrent.futures`, `requests`, pandas, NumPy, matplotlib, pytest.

## Global Constraints

- Default concurrency levels are exactly `1,2,4,8,16,24,32`; code must reject automatic levels above 32.
- Each level defaults to 20 valid requests and only starts after the preceding level passes its stop checks.
- Stop when error rate exceeds 5%, 429/1305 rate exceeds 10%, P95 exceeds 60 seconds, a 502/504/worker-timeout appears, or the operator interrupts.
- Also stop when CPU or memory remains above 90% for 30 consecutive seconds.
- The first complete-platform run is capped at concurrency 8 unless `--allow-validated-ramp` is explicitly supplied.
- Request timeout is 120 seconds; Ctrl+C must flush completed records.
- Every target performs three serial warm-up requests, three formal repetitions, and a configurable cool-down between repetitions.
- Short and long requests run separately before an optional mixed workload of exactly 60% short and 40% long requests.
- Credentials, API keys, cookies, passwords, and complete authorization headers must never enter result files.
- Load-test rows must use dedicated accounts, assignments, and the `research_load_` naming prefix.
- No live Zhipu or platform calls run from pytest; external calls require an explicit CLI command.
- This plan implements engineering performance evidence only; it must not generate learning-effect claims.

---

### Task 1: Immutable records, summaries, and stop rules

**Files:**
- Create: `research_eval/__init__.py`
- Create: `research_eval/concurrency/__init__.py`
- Create: `research_eval/concurrency/models.py`
- Create: `research_eval/concurrency/metrics.py`
- Test: `tests/test_concurrency_metrics.py`

**Interfaces:**
- Produces: `RequestRecord`, `LevelSummary`, `StopDecision`, `summarize_level(records)`, and `evaluate_stop(summary)`.
- Consumes: no project services and no network.

- [ ] **Step 1: Write failing tests for percentiles, error classes, and stopping**

```python
from research_eval.concurrency.metrics import evaluate_stop, summarize_level
from research_eval.concurrency.models import RequestRecord


def record(index, elapsed, *, ok=True, status=200, code=""):
    return RequestRecord(
        run_id="run-1", level=4, request_index=index, target="upstream",
        request_kind="short", started_at="2026-07-21T00:00:00Z",
        elapsed_seconds=elapsed, success=ok, status_code=status,
        error_code=code, retries=0, input_chars=20, output_chars=30,
    )


def test_summary_and_rate_limit_stop():
    rows = [record(i, i + 1) for i in range(19)]
    rows += [record(19, 20, ok=False, status=429, code="1305")]
    summary = summarize_level(rows)
    assert summary.total == 20
    assert summary.success_rate == 0.95
    assert summary.rate_limit_rate == 0.05
    assert summary.p95_seconds >= 19
    assert evaluate_stop(summary).stop is False


def test_stop_above_rate_limit_threshold():
    rows = [record(i, 1) for i in range(17)]
    rows += [record(i, 2, ok=False, status=429, code="1305") for i in range(17, 20)]
    assert "rate_limit" in evaluate_stop(summarize_level(rows)).reasons


def test_stop_on_gateway_error():
    summary = summarize_level([record(0, 2, ok=False, status=504)])
    decision = evaluate_stop(summary)
    assert decision.stop is True
    assert "gateway_error" in decision.reasons
```

- [ ] **Step 2: Run the tests and verify the missing package failure**

Run: `py -m pytest tests/test_concurrency_metrics.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'research_eval'`.

- [ ] **Step 3: Implement immutable models and deterministic aggregation**

```python
# research_eval/concurrency/models.py
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
```

```python
# research_eval/concurrency/metrics.py
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
    elapsed = [row.elapsed_seconds for row in records]
    successful = sum(row.success for row in records)
    rate_limited = sum(row.status_code == 429 or row.error_code == "1305" for row in records)
    gateway = sum(row.status_code in {502, 504} or row.error_code == "worker_timeout" for row in records)
    wall = max(elapsed)
    return LevelSummary(
        level=records[0].level, total=len(records), successful=successful,
        success_rate=successful / len(records), error_rate=1 - successful / len(records),
        rate_limit_rate=rate_limited / len(records),
        throughput_per_second=successful / wall if wall else 0.0,
        mean_seconds=statistics.fmean(elapsed), p50_seconds=_percentile(elapsed, 0.50),
        p95_seconds=_percentile(elapsed, 0.95), p99_seconds=_percentile(elapsed, 0.99),
        retry_rate=sum(row.retries > 0 for row in records) / len(records),
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
```

- [ ] **Step 4: Run the focused tests**

Run: `py -m pytest tests/test_concurrency_metrics.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit the metric foundation**

```powershell
git add research_eval tests/test_concurrency_metrics.py
git commit -m "test: define concurrency evaluation metrics"
```

### Task 2: Staircase runner with safe interruption and incremental output

**Files:**
- Create: `research_eval/concurrency/runner.py`
- Create: `research_eval/concurrency/output.py`
- Test: `tests/test_concurrency_runner.py`

**Interfaces:**
- Consumes: `Callable[[int, int], RequestRecord]` as a target worker.
- Produces: `run_staircase(worker, levels, requests_per_level, sink) -> list[LevelSummary]` and `JsonlSink.append(record)`.

- [ ] **Step 1: Write failing tests for ramp order, stopping, and incremental JSONL**

```python
import json

from research_eval.concurrency.models import RequestRecord
from research_eval.concurrency.output import JsonlSink
from research_eval.concurrency.runner import run_staircase


def test_staircase_stops_before_next_level(tmp_path):
    seen = []
    def worker(level, index):
        seen.append(level)
        return RequestRecord("r", level, index, "fake", "short", "t", 1.0,
                             level < 4, 200 if level < 4 else 500, "", 0, 1, 1)
    sink = JsonlSink(tmp_path / "raw.jsonl")
    summaries = run_staircase(worker, [1, 2, 4, 8], 4, sink)
    assert [row.level for row in summaries] == [1, 2, 4]
    assert 8 not in seen
    assert len((tmp_path / "raw.jsonl").read_text(encoding="utf-8").splitlines()) == 12
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `py -m pytest tests/test_concurrency_runner.py -v`

Expected: import fails for `research_eval.concurrency.runner`.

- [ ] **Step 3: Implement the sink and staircase runner**

```python
# research_eval/concurrency/output.py
import json
import threading
from pathlib import Path

from .models import RequestRecord


class JsonlSink:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, record: RequestRecord) -> None:
        line = json.dumps(record.to_dict(), ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
```

```python
# research_eval/concurrency/runner.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from .metrics import evaluate_stop, summarize_level
from .models import LevelSummary, RequestRecord
from .output import JsonlSink


def run_staircase(
    worker: Callable[[int, int], RequestRecord],
    levels: list[int],
    requests_per_level: int,
    sink: JsonlSink,
) -> list[LevelSummary]:
    if not levels or min(levels) < 1 or max(levels) > 32:
        raise ValueError("levels must be between 1 and 32")
    summaries = []
    for level in levels:
        records = []
        try:
            with ThreadPoolExecutor(max_workers=level) as pool:
                futures = [pool.submit(worker, level, index) for index in range(requests_per_level)]
                for future in as_completed(futures):
                    record = future.result()
                    records.append(record)
                    sink.append(record)
        except KeyboardInterrupt:
            if records:
                summaries.append(summarize_level(records))
            break
        summary = summarize_level(records)
        summaries.append(summary)
        if evaluate_stop(summary).stop:
            break
    return summaries
```

- [ ] **Step 4: Run runner and metric tests**

Run: `py -m pytest tests/test_concurrency_runner.py tests/test_concurrency_metrics.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit the staircase runner**

```powershell
git add research_eval/concurrency/runner.py research_eval/concurrency/output.py tests/test_concurrency_runner.py
git commit -m "feat: add safe concurrency staircase runner"
```

### Task 3: Resource sampler and sustained saturation stop

**Files:**
- Create: `research_eval/concurrency/resources.py`
- Modify: `research_eval/concurrency/models.py`
- Modify: `research_eval/concurrency/runner.py`
- Test: `tests/test_concurrency_resources.py`

**Interfaces:**
- Produces: `ResourceSample`, `ResourceSampler.start()`, `ResourceSampler.stop()`, and `sustained_saturation(samples, threshold=90, seconds=30)`.
- Consumes: an injectable CPU/memory reader; the production reader uses `psutil` when available and `/proc` fallback on Linux.

- [ ] **Step 1: Write failing tests for the continuous 30-second rule**

```python
from research_eval.concurrency.resources import ResourceSample, sustained_saturation


def test_requires_thirty_continuous_seconds():
    rows = [ResourceSample(second=i, cpu_percent=95, memory_percent=91) for i in range(29)]
    assert sustained_saturation(rows, threshold=90, seconds=30) is False
    rows.append(ResourceSample(second=29, cpu_percent=95, memory_percent=91))
    assert sustained_saturation(rows, threshold=90, seconds=30) is True
```

- [ ] **Step 2: Run the resource test and verify failure**

Run: `py -m pytest tests/test_concurrency_resources.py -v`

Expected: import fails for `research_eval.concurrency.resources`.

- [ ] **Step 3: Implement one-second sampling and integrate it with each level**

```python
@dataclass(frozen=True)
class ResourceSample:
    second: int
    cpu_percent: float
    memory_percent: float


def sustained_saturation(samples, threshold=90.0, seconds=30):
    streak = 0
    for sample in samples:
        saturated = sample.cpu_percent > threshold or sample.memory_percent > threshold
        streak = streak + 1 if saturated else 0
        if streak >= seconds:
            return True
    return False
```

Start the sampler immediately before submitting a level and stop it after the final future completes. Save all samples to `resource_samples.csv`; append `resource_saturation` to the stop reasons when the function returns true.

- [ ] **Step 4: Run resource, runner, and metric tests**

Run: `py -m pytest tests/test_concurrency_resources.py tests/test_concurrency_runner.py tests/test_concurrency_metrics.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit resource sampling**

```powershell
git add research_eval/concurrency/resources.py research_eval/concurrency/models.py research_eval/concurrency/runner.py tests/test_concurrency_resources.py
git commit -m "feat: stop load tests on sustained saturation"
```

### Task 4: Observable Zhipu upstream target

**Files:**
- Create: `research_eval/concurrency/upstream.py`
- Test: `tests/test_concurrency_upstream.py`

**Interfaces:**
- Consumes: `ZHIPU_API_KEY`, model name `glm-4.5-flash`, request kind, and an injectable `requests.Session`.
- Produces: `ZhipuTarget.call(level, index) -> RequestRecord` with visible 429/1305 retry counts.

- [ ] **Step 1: Write failing tests with fake 429 and success responses**

```python
from research_eval.concurrency.upstream import ZhipuTarget


class Response:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
    def json(self):
        return self._body


class Session:
    def __init__(self):
        self.responses = [Response(429, {"error": {"code": "1305"}}),
                          Response(200, {"choices": [{"message": {"content": "ok"}}]})]
    def post(self, *args, **kwargs):
        return self.responses.pop(0)


def test_upstream_records_retry_without_leaking_key(monkeypatch):
    monkeypatch.setattr("research_eval.concurrency.upstream.time.sleep", lambda _: None)
    target = ZhipuTarget("secret", "run", "short", Session())
    row = target.call(2, 0)
    assert row.success is True
    assert row.retries == 1
    assert "secret" not in str(row.to_dict())
```

- [ ] **Step 2: Run the test and verify the missing target failure**

Run: `py -m pytest tests/test_concurrency_upstream.py -v`

Expected: import fails for `research_eval.concurrency.upstream`.

- [ ] **Step 3: Implement explicit observable retries**

Implement `ZhipuTarget` with five total attempts, exponential delays `2,4,8,16`, `thinking={"type":"disabled"}`, fixed short and long prompts, status/error extraction, and a 120-second timeout. Return a failed `RequestRecord` after the fifth response instead of raising. Never place request headers or the key in the record.

```python
payload = {
    "model": "glm-4.5-flash",
    "messages": [{"role": "user", "content": self.prompt}],
    "thinking": {"type": "disabled"},
    "temperature": 0.2,
    "max_tokens": 800 if self.request_kind == "long" else 300,
}
```

- [ ] **Step 4: Run the upstream tests**

Run: `py -m pytest tests/test_concurrency_upstream.py -v`

Expected: all tests pass and no external request occurs.

- [ ] **Step 5: Commit the upstream target**

```powershell
git add research_eval/concurrency/upstream.py tests/test_concurrency_upstream.py
git commit -m "feat: instrument zhipu concurrency target"
```

### Task 5: Dedicated platform users and complete HTTP target

**Files:**
- Create: `scripts/provision_research_load_users.py`
- Create: `research_eval/concurrency/platform.py`
- Test: `tests/test_concurrency_platform.py`

**Interfaces:**
- Consumes: a credentials JSON file outside Git, base URL, assignment ID, and request kind.
- Produces: one authenticated session per dedicated user and `PlatformTarget.call(level, index) -> RequestRecord`.

- [ ] **Step 1: Write tests for prefix guard, credential count, login, and endpoint payloads**

```python
import pytest
from research_eval.concurrency.platform import PlatformTarget, validate_users


def test_rejects_nonresearch_users():
    with pytest.raises(ValueError, match="research_load_"):
        validate_users([{"username": "student01", "password": "x"}], 1)


def test_requires_one_user_per_concurrent_worker():
    with pytest.raises(ValueError, match="at least 4"):
        validate_users([{"username": "research_load_01", "password": "x"}], 4)
```

- [ ] **Step 2: Run the platform tests and verify failure**

Run: `py -m pytest tests/test_concurrency_platform.py -v`

Expected: import fails for `research_eval.concurrency.platform`.

- [ ] **Step 3: Implement guarded user provisioning**

The provisioning script must require `--prefix research_load_`, `--count 32`, `--assignment-id`, `--output`, and `--confirm`. It runs inside `app.app_context()`, creates only missing student users with generated passwords, verifies the assignment has a ready `AssignmentThinkingPreset`, writes the credentials file, and applies mode `0600` on Linux. It must refuse prefixes not starting with `research_load_` and never print passwords.

- [ ] **Step 4: Implement the HTTP target**

`PlatformTarget` creates a separate `requests.Session` for each credential, performs `GET /login`, posts `username`, `password`, `submit`, and any hidden CSRF token, then posts `/thinking/api/start_session`. For `short`, call `/thinking/api/stage1/hint`; for `long`, call `/thinking/api/stage3/chat`. Use only the assigned user's session ID and classify 502/504/timeouts explicitly.

- [ ] **Step 5: Run platform target tests with fake sessions**

Run: `py -m pytest tests/test_concurrency_platform.py -v`

Expected: all tests pass and no network or database is used.

- [ ] **Step 6: Commit the platform target**

```powershell
git add scripts/provision_research_load_users.py research_eval/concurrency/platform.py tests/test_concurrency_platform.py
git commit -m "feat: add isolated platform load target"
```

### Task 6: CLI, repetitions, mixed workload, and paper-ready outputs

**Files:**
- Create: `research_eval/concurrency/cli.py`
- Create: `scripts/run_guided_learning_concurrency.py`
- Create: `scripts/plot_guided_learning_concurrency.py`
- Test: `tests/test_concurrency_cli.py`

**Interfaces:**
- Consumes: `upstream` or `platform` mode and the parameters defined in the spec.
- Produces: `raw_requests.jsonl`, `level_summary.csv`, `run_config.json`, and three PNG figures.

- [ ] **Step 1: Write CLI parsing and output tests**

Test that the default levels parse to `[1,2,4,8,16,24,32]`, platform mode without `--allow-validated-ramp` rejects `--max-concurrency 16`, three warm-ups and three repetitions are scheduled, mixed mode produces exactly 12 short and 8 long requests per 20-request level, and output JSON excludes values matching `key`, `password`, `cookie`, or `authorization` field names.

- [ ] **Step 2: Run the CLI tests and verify failure**

Run: `py -m pytest tests/test_concurrency_cli.py -v`

Expected: import fails for `research_eval.concurrency.cli`.

- [ ] **Step 3: Implement CLI and snapshots**

The CLI accepts `--mode`, `--request-kind short|long|mixed`, `--levels`, `--requests-per-level`, `--warmups` (default 3), `--repetitions` (default 3), `--cooldown-seconds`, `--output-dir`, `--base-url`, `--credentials-file`, `--assignment-id`, and `--allow-validated-ramp`. Snapshot Python version, hostname, CPU count, model, target URL without query secrets, Gunicorn config values, and UTC time. Write dataclass summaries with `csv.DictWriter`, preserving repetition IDs rather than pooling requests before aggregation.

- [ ] **Step 4: Implement figures**

Generate `latency_by_concurrency.png`, `throughput_by_concurrency.png`, and `error_rate_by_concurrency.png` at 200 DPI with target, request kind, model, and run time in the caption. Plot measured points only; do not extrapolate capacity beyond the final level.

- [ ] **Step 5: Run all offline concurrency tests**

Run: `py -m pytest tests/test_concurrency_*.py -v`

Expected: all concurrency tests pass.

- [ ] **Step 6: Commit the CLI and reports**

```powershell
git add research_eval/concurrency/cli.py scripts/run_guided_learning_concurrency.py scripts/plot_guided_learning_concurrency.py tests/test_concurrency_cli.py
git commit -m "feat: publish concurrency evaluation artifacts"
```

### Task 7: Controlled execution gates and validation guide

**Files:**
- Create: `research/guided_learning_paper/concurrency_evaluation_protocol.md`
- Modify: `research/guided_learning_paper/README.md`
- Test: `tests/test_concurrency_protocol.py`

**Interfaces:**
- Consumes: the implemented CLI.
- Produces: exact dry-run, upstream, canary, and validated-ramp commands.

- [ ] **Step 1: Write a documentation test for mandatory warnings and commands**

Assert that the protocol contains `低峰期`, `专用测试账号`, `最高并发 8`, `--allow-validated-ramp`, `不证明学习效果`, and the three commands below.

- [ ] **Step 2: Write the protocol with exact execution sequence**

```powershell
py scripts/run_guided_learning_concurrency.py --mode upstream --request-kind short --levels 1,2 --requests-per-level 3 --output-dir research/guided_learning_paper/experiments/concurrency/smoke
py scripts/run_guided_learning_concurrency.py --mode platform --request-kind short --levels 1,2,4,8 --requests-per-level 20 --base-url http://127.0.0.1:5000 --credentials-file /var/www/codesense/research_load_users.json --assignment-id 85 --output-dir research_exports/concurrency/canary
py scripts/run_guided_learning_concurrency.py --mode platform --request-kind long --levels 1,2,4,8,16,24,32 --requests-per-level 20 --allow-validated-ramp --base-url http://127.0.0.1:5000 --credentials-file /var/www/codesense/research_load_users.json --assignment-id 85 --output-dir research_exports/concurrency/validated
```

The protocol must say that `85` is replaced by the dedicated ready-preset assignment selected during execution and that the validated command runs only after reviewing the canary logs and confirming no active course session.

- [ ] **Step 3: Run tests and the full existing paper test subset**

Run: `py -m pytest tests/test_concurrency_*.py tests/test_guided_learning_paper_content.py tests/test_guided_learning_paper_plots.py -v`

Expected: all selected tests pass.

- [ ] **Step 4: Commit the execution protocol**

```powershell
git add research/guided_learning_paper/concurrency_evaluation_protocol.md research/guided_learning_paper/README.md tests/test_concurrency_protocol.py
git commit -m "docs: add guarded concurrency execution protocol"
```

### Task 8: Execute smoke tests, then stop for explicit online approval

**Files:**
- Output only: `research/guided_learning_paper/experiments/concurrency/smoke/`

**Interfaces:**
- Consumes: local environment and explicit external-call authorization.
- Produces: a smoke-test evidence bundle; does not run the full ramp.

- [ ] **Step 1: Run all offline tests**

Run: `py -m pytest tests/test_concurrency_*.py -v`

Expected: all tests pass with zero external requests.

- [ ] **Step 2: Confirm the key without displaying it**

Run: `py -c "import os; print('ZHIPU_API_KEY_SET=' + str(bool(os.getenv('ZHIPU_API_KEY'))))"`

Expected: `ZHIPU_API_KEY_SET=True` on the server.

- [ ] **Step 3: Request explicit approval before external smoke traffic**

Do not proceed until the user confirms the server is in a low-usage window and authorizes the `1,2` upstream smoke run.

- [ ] **Step 4: Run only the approved smoke command and inspect artifacts**

Run the first command in the protocol, then verify the JSONL row count, CSV levels, absence of secrets, and plots. Do not start the platform canary in the same approval step.

- [ ] **Step 5: Commit only reproducible code and protocol, not credentials or raw online results**

If paper-ready aggregate results are later approved for version control, commit CSV summaries and figures in a separate evidence commit after checking that they contain no credentials or personal data.
