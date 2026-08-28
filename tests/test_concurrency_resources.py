import csv
import threading

import research_eval.concurrency.resources as resources_module
from research_eval.concurrency.resources import (
    ResourceSample,
    ResourceSampler,
    append_resource_samples,
    sustained_saturation,
)


class AdvancingClock:
    def __init__(self):
        self.current = 0.0
        self._waits = 0
        self.first_second_sampled = threading.Event()

    def monotonic(self):
        return self.current

    def wait(self, stop_event, seconds):
        self.current += seconds
        self._waits += 1
        if self._waits == 1:
            return False
        return stop_event.wait(timeout=1)


class BlockingClock:
    def __init__(self):
        self.wait_entered = threading.Event()

    def monotonic(self):
        return 0.0

    def wait(self, stop_event, seconds):
        self.wait_entered.set()
        return stop_event.wait()


def test_requires_thirty_continuous_seconds():
    rows = [ResourceSample(second=index, cpu_percent=95, memory_percent=91) for index in range(29)]

    assert sustained_saturation(rows, threshold=90, seconds=30) is False

    rows.append(ResourceSample(second=29, cpu_percent=95, memory_percent=91))

    assert sustained_saturation(rows, threshold=90, seconds=30) is True


def test_saturation_is_strictly_greater_than_threshold_and_resets_on_safe_sample():
    exactly_at_threshold = [
        ResourceSample(second=index, cpu_percent=90, memory_percent=90)
        for index in range(30)
    ]
    interrupted_streak = [
        ResourceSample(second=index, cpu_percent=95, memory_percent=10)
        for index in range(29)
    ]
    interrupted_streak.append(ResourceSample(second=29, cpu_percent=90, memory_percent=90))
    interrupted_streak.append(ResourceSample(second=30, cpu_percent=10, memory_percent=95))

    assert sustained_saturation(exactly_at_threshold) is False
    assert sustained_saturation(interrupted_streak, seconds=30) is False


def test_saturation_requires_consecutive_one_second_samples():
    rows = [
        ResourceSample(second=index, cpu_percent=95, memory_percent=10)
        for index in range(29)
    ]
    rows.append(ResourceSample(second=31, cpu_percent=95, memory_percent=10))

    assert sustained_saturation(rows, seconds=30) is False


def test_start_waits_for_initial_sample_and_stop_prevents_new_samples():
    clock = BlockingClock()
    reader_entered = threading.Event()
    release_reader = threading.Event()
    start_returned = threading.Event()

    def reader():
        reader_entered.set()
        release_reader.wait()
        return 10.0, 20.0

    sampler = ResourceSampler(
        reader=reader,
        clock=clock,
    )

    start_thread = threading.Thread(
        target=lambda: (sampler.start(), start_returned.set())
    )
    start_thread.start()
    try:
        assert reader_entered.wait(timeout=1)
        assert not start_returned.wait(timeout=0.1)
    finally:
        release_reader.set()
        assert start_returned.wait(timeout=1)
        start_thread.join(timeout=1)

    assert sampler.samples == (ResourceSample(second=0, cpu_percent=10.0, memory_percent=20.0),)
    assert clock.wait_entered.wait(timeout=1)
    sampler.stop()
    samples_after_stop = sampler.samples

    assert sampler.samples == samples_after_stop


def test_stop_does_not_record_after_wait_returns():
    class ObservedStopEvent(threading.Event):
        def __init__(self):
            super().__init__()
            self.set_called = threading.Event()

        def set(self):
            super().set()
            self.set_called.set()

    class ReleaseClock:
        def __init__(self):
            self.wait_entered = threading.Event()
            self.release_wait = threading.Event()

        def monotonic(self):
            return 0.0

        def wait(self, stop_event, seconds):
            self.wait_entered.set()
            self.release_wait.wait()
            return False

    clock = ReleaseClock()
    sampler = ResourceSampler(reader=lambda: (10.0, 20.0), clock=clock)
    sampler._stop_event = ObservedStopEvent()
    sampler.start()
    assert clock.wait_entered.wait(timeout=1)

    stopped = threading.Event()
    stop_thread = threading.Thread(target=lambda: (sampler.stop(), stopped.set()))
    stop_thread.start()
    try:
        assert sampler._stop_event.set_called.wait(timeout=1)
        clock.release_wait.set()
        assert stopped.wait(timeout=1)
    finally:
        clock.release_wait.set()
        stop_thread.join(timeout=1)

    assert sampler.samples == (ResourceSample(second=0, cpu_percent=10.0, memory_percent=20.0),)


def test_sampler_preserves_background_reader_error():
    clock = AdvancingClock()
    error_raised = threading.Event()
    calls = 0

    def reader():
        nonlocal calls
        calls += 1
        if calls == 2:
            error_raised.set()
            raise ValueError("reader failed")
        return 10.0, 20.0

    sampler = ResourceSampler(reader=reader, clock=clock)
    sampler.start()

    assert error_raised.wait(timeout=1)
    sampler.stop()

    assert isinstance(sampler.error, ValueError)
    assert sampler.samples == (ResourceSample(second=0, cpu_percent=10.0, memory_percent=20.0),)


def test_sampler_preserves_proc_parse_value_error(monkeypatch):
    class BrokenProcPath:
        def __init__(self, _path):
            pass

        def read_text(self, **_kwargs):
            return "cpu not-a-number 0\\n"

    monkeypatch.setattr(resources_module, "Path", BrokenProcPath)
    sampler = ResourceSampler(reader=resources_module._ProcResourceReader(), clock=BlockingClock())

    sampler.start()

    assert isinstance(sampler.error, ValueError)
    assert sampler.samples == ()


def test_sampler_uses_injected_reader_and_clock_without_real_sleep():
    clock = AdvancingClock()
    values = iter(((91.0, 10.0), (10.0, 92.0)))
    samples_seen = threading.Event()

    def reader():
        value = next(values)
        if value == (10.0, 92.0):
            samples_seen.set()
        return value

    sampler = ResourceSampler(reader=reader, clock=clock)
    sampler.start()

    assert samples_seen.wait(timeout=1)
    sampler.stop()

    assert sampler.samples == (
        ResourceSample(second=0, cpu_percent=91.0, memory_percent=10.0),
        ResourceSample(second=1, cpu_percent=10.0, memory_percent=92.0),
    )


def test_append_resource_samples_writes_all_rows_to_csv(tmp_path):
    path = tmp_path / "resource_samples.csv"
    samples = (
        ResourceSample(second=0, cpu_percent=10.5, memory_percent=20.5),
        ResourceSample(second=1, cpu_percent=30.5, memory_percent=40.5),
    )

    append_resource_samples(path, samples)
    append_resource_samples(path, (ResourceSample(second=2, cpu_percent=50.5, memory_percent=60.5),))

    with path.open(newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == [
            {"second": "0", "cpu_percent": "10.5", "memory_percent": "20.5"},
            {"second": "1", "cpu_percent": "30.5", "memory_percent": "40.5"},
            {"second": "2", "cpu_percent": "50.5", "memory_percent": "60.5"},
        ]
