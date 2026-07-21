import csv
import os
import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from .models import ResourceSample


SAMPLE_INTERVAL_SECONDS = 1.0
ResourceReader = Callable[[], tuple[float, float]]


class _SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def wait(self, stop_event: threading.Event, seconds: float) -> bool:
        return stop_event.wait(seconds)


class _ProcResourceReader:
    def __init__(self):
        self._previous_cpu: tuple[int, int] | None = None

    def __call__(self) -> tuple[float, float]:
        current_cpu = self._cpu_times()
        cpu_percent = self._cpu_percent(current_cpu)
        return cpu_percent, self._memory_percent()

    def _cpu_percent(self, current: tuple[int, int] | None) -> float:
        if current is None:
            return 0.0
        previous = self._previous_cpu
        self._previous_cpu = current
        if previous is None:
            return 0.0
        total_delta = current[0] - previous[0]
        idle_delta = current[1] - previous[1]
        if total_delta <= 0:
            return 0.0
        return max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta))

    @staticmethod
    def _cpu_times() -> tuple[int, int] | None:
        try:
            fields = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0].split()
        except (FileNotFoundError, IndexError, OSError):
            return None
        if not fields or fields[0] != "cpu":
            return None
        values = [int(value) for value in fields[1:]]
        return sum(values), values[3] + (values[4] if len(values) > 4 else 0)

    @staticmethod
    def _memory_percent() -> float:
        try:
            values = {
                key.rstrip(":"): int(value)
                for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
                if (parts := line.split()) and len(parts) >= 2
                for key, value in [(parts[0], parts[1])]
            }
            total = values["MemTotal"]
            available = values.get("MemAvailable", values.get("MemFree", 0))
        except (FileNotFoundError, KeyError, OSError, ValueError):
            return 0.0
        return 100.0 * (total - available) / total if total else 0.0


def default_resource_reader() -> ResourceReader:
    try:
        import psutil
    except ImportError:
        return _ProcResourceReader()

    return lambda: (psutil.cpu_percent(interval=None), psutil.virtual_memory().percent)


class ResourceSampler:
    def __init__(
        self,
        reader: ResourceReader | None = None,
        clock: object | None = None,
    ):
        self._reader = reader or default_resource_reader()
        self._clock = clock or _SystemClock()
        self._samples: list[ResourceSample] = []
        self._samples_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_at: float | None = None

    @property
    def samples(self) -> tuple[ResourceSample, ...]:
        with self._samples_lock:
            return tuple(self._samples)

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("ResourceSampler instances can only be started once")
        self._started_at = self._clock.monotonic()
        self._thread = threading.Thread(target=self._sample_until_stopped, daemon=True)
        self._thread.start()

    def stop(self) -> tuple[ResourceSample, ...]:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        return self.samples

    def _sample_until_stopped(self) -> None:
        self._record_sample()
        while not self._clock.wait(self._stop_event, SAMPLE_INTERVAL_SECONDS):
            self._record_sample()

    def _record_sample(self) -> None:
        cpu_percent, memory_percent = self._reader()
        started_at = self._started_at
        if started_at is None:
            raise RuntimeError("ResourceSampler has not started")
        second = int(max(0.0, self._clock.monotonic() - started_at))
        sample = ResourceSample(second, float(cpu_percent), float(memory_percent))
        with self._samples_lock:
            self._samples.append(sample)


def sustained_saturation(
    samples: Iterable[ResourceSample], threshold: float = 90.0, seconds: int = 30
) -> bool:
    streak = 0
    previous_second: int | None = None
    for sample in samples:
        saturated = sample.cpu_percent > threshold or sample.memory_percent > threshold
        consecutive = previous_second is None or sample.second == previous_second + 1
        streak = streak + 1 if saturated and consecutive else int(saturated)
        previous_second = sample.second
        if streak >= seconds:
            return True
    return False


def append_resource_samples(path: Path, samples: Iterable[ResourceSample]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("second", "cpu_percent", "memory_percent"))
        if write_header:
            writer.writeheader()
        for sample in samples:
            writer.writerow(
                {
                    "second": sample.second,
                    "cpu_percent": sample.cpu_percent,
                    "memory_percent": sample.memory_percent,
                }
            )
