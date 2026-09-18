"""Bound synchronous model/tool work without queuing unbounded background jobs."""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from threading import BoundedSemaphore

_workers = ThreadPoolExecutor(max_workers=8, thread_name_prefix="consultation")
_slots = BoundedSemaphore(8)


def call_with_timeout(operation, seconds: float):
    # A timed-out Python thread cannot be killed. Keep its slot occupied until it
    # exits; callers must operate on a private state and discard late results.
    if seconds <= 0:
        raise TimeoutError("Agent execution budget exhausted")
    if not _slots.acquire(blocking=False):
        raise RuntimeError("Agent workers are busy")
    try:
        future = _workers.submit(operation)
    except BaseException:
        _slots.release()
        raise
    future.add_done_callback(lambda _: _slots.release())
    try:
        return future.result(timeout=seconds)
    except FutureTimeout:
        future.cancel()
        raise TimeoutError("Agent step deadline exceeded") from None
