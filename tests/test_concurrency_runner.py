import json
import hashlib
import threading
import time
from concurrent.futures import Future
from pathlib import Path

import pytest

import research_eval.concurrency.runner as runner_module
from research_eval.concurrency.models import RequestRecord
from research_eval.concurrency.output import JsonlSink
from research_eval.concurrency.runner import run_staircase


def record(level: int, index: int, *, ok: bool = True, status: int = 200) -> RequestRecord:
    return RequestRecord(
        run_id="run-1",
        level=level,
        request_index=index,
        target="fake",
        request_kind="short",
        started_at="2026-07-21T00:00:00Z",
        elapsed_seconds=1.0,
        success=ok,
        status_code=status,
        error_code="",
        retries=0,
        input_chars=1,
        output_chars=1,
    )


def test_staircase_stops_before_next_level(tmp_path):
    seen = []

    def worker(level, index):
        seen.append(level)
        return record(level, index, ok=level < 4, status=200 if level < 4 else 500)

    output = tmp_path / "raw.jsonl"
    summaries = run_staircase(worker, [1, 2, 4, 8], 4, JsonlSink(output))

    assert [summary.level for summary in summaries] == [1, 2, 4]
    assert 8 not in seen
    assert len(output.read_text(encoding="utf-8").splitlines()) == 12


def test_jsonl_sink_flushes_each_record_before_return(tmp_path, monkeypatch):
    class Handle:
        def __init__(self):
            self.lines = []
            self.flushes = 0

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def write(self, line):
            self.lines.append(line)

        def flush(self):
            self.flushes += 1

        def tell(self):
            return 0

        def truncate(self, _offset):
            return 0

    handle = Handle()
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: handle)

    JsonlSink(tmp_path / "raw.jsonl").append(record(1, 0))

    payload = json.loads(handle.lines[0])
    assert payload["run_id"] == "sha256:" + hashlib.sha256(b"run-1").hexdigest()[:16]
    assert payload["target"] == "fake"
    assert payload["request_kind"] == "short"
    assert handle.flushes == 1


def test_jsonl_sink_redacts_sensitive_values_in_free_text(tmp_path):
    sensitive = record(1, 0)
    sensitive = sensitive.__class__(
        **{
            **sensitive.to_dict(),
            "target": (
                "https://example.invalid/evaluate?api_key=query-key-123 "
                "Authorization: Bearer bearer-token-456 "
                "Cookie: session=cookie-value-789"
            ),
            "error_code": "password=pass-value-321; x-api-key: header-key-654",
        }
    )
    output = tmp_path / "raw.jsonl"
    JsonlSink(output).append(sensitive)

    payload = output.read_text(encoding="utf-8")

    for secret in (
        "query-key-123",
        "bearer-token-456",
        "cookie-value-789",
        "pass-value-321",
        "header-key-654",
    ):
        assert secret not in payload
    assert '"target": "redacted_target"' in payload
    assert '"error_code": "redacted_error"' in payload


def test_jsonl_sink_normalizes_url_credentials_query_and_error_body(tmp_path):
    sensitive = record(1, 0)
    sensitive = sensitive.__class__(
        **{
            **sensitive.to_dict(),
            "target": (
                "https://url-user:url-password@api.example.invalid/evaluate"
                "?access_token=access-token-123&client_secret=client-secret-456"
            ),
            "error_code": (
                "upstream body: Authorization: Bearer bearer-token-789; "
                "password=error-password-012; Cookie: session=error-cookie-345"
            ),
        }
    )
    output = tmp_path / "raw.jsonl"
    JsonlSink(output).append(sensitive)

    payload = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, ensure_ascii=False)

    for secret in (
        "url-user",
        "url-password",
        "access-token-123",
        "client-secret-456",
        "bearer-token-789",
        "error-password-012",
        "error-cookie-345",
    ):
        assert secret not in serialized
    assert payload["target"] == "redacted_target"
    assert payload["error_code"] == "redacted_error"


def test_jsonl_sink_uses_safe_fields_for_arbitrary_free_strings(tmp_path):
    secrets = (
        "run-entropy-5d5c8a6f",
        "ftp-user-9c1d",
        "ftp-password-2e4a",
        "ssh-user-7b3f",
        "ssh-password-8a6c",
        "timestamp-secret-4f2b",
        "error-secret-1a9e",
    )
    row = record(1, 0)
    row = row.__class__(
        **{
            **row.to_dict(),
            "run_id": secrets[0],
            "target": f"ftp://{secrets[1]}:{secrets[2]}@host.invalid/path",
            "request_kind": f"ssh://{secrets[3]}:{secrets[4]}@host.invalid",
            "started_at": secrets[5],
            "error_code": secrets[6],
        }
    )
    output = tmp_path / "raw.jsonl"
    JsonlSink(output).append(row)

    payload = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, ensure_ascii=False)

    for secret in secrets:
        assert secret not in serialized
    assert payload["run_id"] == "sha256:" + hashlib.sha256(secrets[0].encode()).hexdigest()[:16]
    assert payload["target"] == "redacted_target"
    assert payload["request_kind"] == "redacted_kind"
    assert payload["started_at"] == "redacted_timestamp"
    assert payload["error_code"] == "redacted_error"


def test_interrupted_jsonl_write_rolls_back_before_runner_retries(tmp_path, monkeypatch):
    output = tmp_path / "raw.jsonl"
    original_open = Path.open
    interrupted = False

    class HalfWriteHandle:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self.handle, name)

        def write(self, line):
            self.handle.write(line[: max(1, len(line) // 2)])
            self.handle.flush()
            raise KeyboardInterrupt

    def interrupting_open(path, *args, **kwargs):
        nonlocal interrupted
        handle = original_open(path, *args, **kwargs)
        if path == output and args and args[0] == "a" and not interrupted:
            interrupted = True
            return HalfWriteHandle(handle)
        return handle

    class ObservingSink(JsonlSink):
        def append(self, row):
            try:
                super().append(row)
            except KeyboardInterrupt:
                assert output.read_bytes() == b""
                assert self._request_keys == set()
                raise

    monkeypatch.setattr(Path, "open", interrupting_open)
    summaries = run_staircase(
        lambda level, index: record(level, index), [1], 1, ObservingSink(output)
    )

    lines = output.read_text(encoding="utf-8").splitlines()
    assert [summary.total for summary in summaries] == [1]
    assert len(lines) == 1
    assert json.loads(lines[0])["request_index"] == 0


def test_jsonl_sink_skips_duplicate_request_key_after_reopen(tmp_path):
    output = tmp_path / "raw.jsonl"
    row = record(1, 0)

    sink = JsonlSink(output)
    sink.append(row)
    sink.append(row)
    JsonlSink(output).append(row)

    assert len(output.read_text(encoding="utf-8").splitlines()) == 1


def test_interrupt_after_sink_write_reuses_record_without_duplicate_jsonl(tmp_path):
    class InterruptAfterFirstWriteSink(JsonlSink):
        def __init__(self, path):
            super().__init__(path)
            self.interrupted = False

        def append(self, row):
            super().append(row)
            if not self.interrupted:
                self.interrupted = True
                raise KeyboardInterrupt

    output = tmp_path / "raw.jsonl"
    sink = InterruptAfterFirstWriteSink(output)

    summaries = run_staircase(
        lambda level, index: record(level, index), [1], 1, sink
    )

    assert [summary.total for summary in summaries] == [1]
    assert len(output.read_text(encoding="utf-8").splitlines()) == 1


def test_keyboard_interrupt_drains_completed_future_not_yet_yielded(tmp_path, monkeypatch):
    second_completed = threading.Event()
    original_as_completed = runner_module.as_completed
    interrupted = False

    def worker(level, index):
        if index == 1:
            second_completed.set()
        return record(level, index)

    def interrupt_once(futures):
        nonlocal interrupted
        if interrupted:
            yield from original_as_completed(futures)
            return
        interrupted = True
        yield futures[0]
        assert second_completed.wait(timeout=1)
        raise KeyboardInterrupt

    monkeypatch.setattr(runner_module, "as_completed", interrupt_once)
    output = tmp_path / "raw.jsonl"

    summaries = run_staircase(worker, [1], 2, JsonlSink(output))

    assert [summary.total for summary in summaries] == [2]
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2


def test_keyboard_interrupt_waits_for_running_worker_and_finishes_all_writes(
    tmp_path, monkeypatch
):
    release_worker = threading.Event()
    worker_started = threading.Event()
    first_persisted = threading.Event()
    returned = threading.Event()
    original_as_completed = runner_module.as_completed
    interrupted = False
    result = {}

    def worker(level, index):
        if index == 1:
            worker_started.set()
            release_worker.wait(timeout=2)
        return record(level, index)

    class RecordingSink(JsonlSink):
        def append(self, row):
            super().append(row)
            if row.request_index == 0:
                first_persisted.set()

    def interrupt_once(futures):
        nonlocal interrupted
        if interrupted:
            yield from original_as_completed(futures)
            return
        interrupted = True
        yield futures[0]
        raise KeyboardInterrupt

    monkeypatch.setattr(runner_module, "as_completed", interrupt_once)

    def execute():
        result["summaries"] = run_staircase(
            worker, [1], 2, RecordingSink(tmp_path / "raw.jsonl")
        )
        returned.set()

    thread = threading.Thread(target=execute)
    thread.start()
    assert first_persisted.wait(timeout=1)
    assert worker_started.wait(timeout=1)
    try:
        assert not returned.wait(timeout=0.1)
        release_worker.set()
        assert returned.wait(timeout=1)
        thread.join(timeout=1)
        output = tmp_path / "raw.jsonl"
        lines_at_return = output.read_text(encoding="utf-8").splitlines()
        time.sleep(0.05)
        assert output.read_text(encoding="utf-8").splitlines() == lines_at_return
        assert [summary.total for summary in result["summaries"]] == [2]
        assert len(lines_at_return) == 2
    finally:
        release_worker.set()
        thread.join(timeout=2)


def test_keyboard_interrupt_during_submission_cancels_already_submitted_future(
    tmp_path, monkeypatch
):
    submitted = Future()

    class Pool:
        def __init__(self, *_args, **_kwargs):
            self.submit_calls = 0
            self.shutdown_calls = []

        def submit(self, *_args):
            self.submit_calls += 1
            if self.submit_calls == 1:
                return submitted
            raise KeyboardInterrupt

        def shutdown(self, *, wait, cancel_futures=False):
            self.shutdown_calls.append((wait, cancel_futures))

    pool = Pool()
    monkeypatch.setattr(
        runner_module, "ThreadPoolExecutor", lambda *_args, **_kwargs: pool
    )

    summaries = run_staircase(
        lambda level, index: record(level, index),
        [1],
        2,
        JsonlSink(tmp_path / "raw.jsonl"),
    )

    assert summaries == []
    assert submitted.cancelled()
    assert pool.shutdown_calls == [(True, True)]


@pytest.mark.parametrize("levels", [[], [0], [33]])
def test_staircase_rejects_levels_outside_supported_range(tmp_path, levels):
    with pytest.raises(ValueError, match="levels must be between 1 and 32"):
        run_staircase(lambda level, index: record(level, index), levels, 1, JsonlSink(tmp_path / "raw.jsonl"))


@pytest.mark.parametrize("requests_per_level", [0, -1])
def test_staircase_rejects_non_positive_request_counts(tmp_path, requests_per_level):
    with pytest.raises(ValueError, match="requests_per_level must be positive"):
        run_staircase(
            lambda level, index: record(level, index),
            [1],
            requests_per_level,
            JsonlSink(tmp_path / "raw.jsonl"),
        )


def test_staircase_uses_default_levels_and_request_count(tmp_path):
    seen = []

    def worker(level, index):
        seen.append((level, index))
        return record(level, index)

    summaries = run_staircase(worker, sink=JsonlSink(tmp_path / "raw.jsonl"))

    assert [summary.level for summary in summaries] == [1, 2, 4, 8, 16, 24, 32]
    assert len(seen) == 7 * 20


def test_runner_exposes_request_timeout_for_target_adapters():
    assert runner_module.REQUEST_TIMEOUT_SECONDS == 120
