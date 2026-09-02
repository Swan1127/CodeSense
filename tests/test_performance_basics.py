import queue

from utils.async_tasks import AsyncTaskManager


def test_async_task_deduplication_is_atomic_and_queue_is_bounded():
    manager = AsyncTaskManager()
    manager.task_queue = queue.Queue(maxsize=1)

    first_id = manager.add_task(
        'generate_thinking_preset',
        assignment_id=1,
        _dedupe_key='preset:1',
    )
    duplicate_id = manager.add_task(
        'generate_thinking_preset',
        assignment_id=1,
        _dedupe_key='preset:1',
    )
    rejected_id = manager.add_task(
        'generate_thinking_preset',
        assignment_id=2,
        _dedupe_key='preset:2',
    )

    assert first_id
    assert duplicate_id == first_id
    assert rejected_id is None
    assert manager.task_queue.qsize() == 1

    task = manager.task_queue.get_nowait()
    manager.task_queue.task_done()
    manager._release_dedupe_key(task)

    next_id = manager.add_task(
        'generate_thinking_preset',
        assignment_id=1,
        _dedupe_key='preset:1',
    )
    assert next_id and next_id != first_id
