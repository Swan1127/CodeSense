import json
import threading
from pathlib import Path

import pytest

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

    handle = Handle()
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: handle)

    JsonlSink(tmp_path / "raw.jsonl").append(record(1, 0))

    assert handle.lines == [json.dumps(record(1, 0).to_dict(), ensure_ascii=False) + "\n"]
    assert handle.flushes == 1


def test_keyboard_interrupt_keeps_completed_record_without_waiting_for_pool(tmp_path):
    class InterruptAfterPersistingSink(JsonlSink):
        def __init__(self, path):
            super().__init__(path)
            self.persisted = threading.Event()

        def append(self, row):
            super().append(row)
            self.persisted.set()
            raise KeyboardInterrupt

    release_worker = threading.Event()
    output = tmp_path / "raw.jsonl"
    sink = InterruptAfterPersistingSink(output)
    result = {}

    def worker(level, index):
        if index == 1:
            release_worker.wait(timeout=5)
        return record(level, index)

    def execute():
        result["summaries"] = run_staircase(worker, [1, 2], 2, sink)

    thread = threading.Thread(target=execute)
    thread.start()
    assert sink.persisted.wait(timeout=1)
    thread.join(timeout=0.5)
    try:
        assert not thread.is_alive()
        assert [summary.total for summary in result["summaries"]] == [1]
        assert len(output.read_text(encoding="utf-8").splitlines()) == 1
    finally:
        release_worker.set()
        thread.join(timeout=2)


@pytest.mark.parametrize("levels", [[], [0], [33]])
def test_staircase_rejects_levels_outside_supported_range(tmp_path, levels):
    with pytest.raises(ValueError, match="levels must be between 1 and 32"):
        run_staircase(lambda level, index: record(level, index), levels, 1, JsonlSink(tmp_path / "raw.jsonl"))
