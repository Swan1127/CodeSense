from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable, Sequence
from dataclasses import replace

from .metrics import evaluate_stop, summarize_level
from .models import LevelSummary, RequestRecord
from .output import JsonlSink
from .resources import ResourceReader, ResourceSampler, append_resource_samples, sustained_saturation


DEFAULT_LEVELS = (1, 2, 4, 8, 16, 24, 32)
REQUEST_TIMEOUT_SECONDS = 120


def run_staircase(
    worker: Callable[[int, int], RequestRecord],
    levels: Sequence[int] = DEFAULT_LEVELS,
    requests_per_level: int = 20,
    sink: JsonlSink | None = None,
    resource_reader: ResourceReader | None = None,
    resource_clock: object | None = None,
) -> list[LevelSummary]:
    if not levels or min(levels) < 1 or max(levels) > 32:
        raise ValueError("levels must be between 1 and 32")
    if requests_per_level <= 0:
        raise ValueError("requests_per_level must be positive")
    if sink is None:
        raise ValueError("sink is required")

    summaries = []
    for level in levels:
        records = []
        pool = ThreadPoolExecutor(max_workers=level)
        handled_futures = set()
        sampler = ResourceSampler(reader=resource_reader, clock=resource_clock)
        interrupted = False

        def store_result(future) -> None:
            if future in handled_futures or future.cancelled():
                return
            record = future.result()
            sink.append(record)
            records.append(record)
            handled_futures.add(future)

        futures = []
        sampler.start()
        try:
            for index in range(requests_per_level):
                futures.append(pool.submit(worker, level, index))
            for future in as_completed(futures):
                store_result(future)
        except KeyboardInterrupt:
            for future in futures:
                future.cancel()
            pool.shutdown(wait=True, cancel_futures=True)
            for future in futures:
                store_result(future)
            interrupted = True
        except BaseException:
            pool.shutdown(wait=True, cancel_futures=True)
            raise
        else:
            pool.shutdown(wait=True)
        finally:
            samples = sampler.stop()
            append_resource_samples(sink.path.with_name("resource_samples.csv"), samples)

        if not records:
            if interrupted:
                break
            continue

        summary = summarize_level(records)
        metric_decision = evaluate_stop(summary)
        resource_saturated = sustained_saturation(samples)
        reasons = metric_decision.reasons
        if resource_saturated:
            reasons += ("resource_saturation",)
        summary = replace(summary, stop_reasons=reasons)
        summaries.append(summary)
        if interrupted or reasons:
            break

    return summaries
