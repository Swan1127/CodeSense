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
        pool = ThreadPoolExecutor(max_workers=level)
        try:
            futures = [
                pool.submit(worker, level, index)
                for index in range(requests_per_level)
            ]
            for future in as_completed(futures):
                record = future.result()
                records.append(record)
                sink.append(record)
        except KeyboardInterrupt:
            pool.shutdown(wait=False, cancel_futures=True)
            if records:
                summaries.append(summarize_level(records))
            break
        except BaseException:
            pool.shutdown(wait=True, cancel_futures=True)
            raise
        else:
            pool.shutdown(wait=True)

        summary = summarize_level(records)
        summaries.append(summary)
        if evaluate_stop(summary).stop:
            break

    return summaries
