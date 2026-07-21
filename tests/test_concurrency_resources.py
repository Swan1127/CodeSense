import csv
import threading

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
