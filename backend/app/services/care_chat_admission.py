"""Bound work per worker and throttle each account without unbounded waiting."""

import math
import logging
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager

from fastapi import HTTPException
from redis import Redis
from redis.exceptions import RedisError

from backend.app.core.config import settings

read_slots = threading.BoundedSemaphore(settings.care_chat_read_concurrency)
send_slots = threading.BoundedSemaphore(settings.care_chat_send_concurrency)
_lock = threading.Lock()
_buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()
_redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=0.1,
                        socket_timeout=0.1, max_connections=16)
_redis_retry_at = 0.0
_TOKEN_BUCKET = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
local rate, burst = tonumber(ARGV[1]), tonumber(ARGV[2])
local previous = redis.call('HMGET', KEYS[1], 'tokens', 'time')
local tokens = tonumber(previous[1]) or burst
local stamp = tonumber(previous[2]) or now
tokens = math.min(burst, tokens + math.max(0, now - stamp) * rate)
local wait = 0
if tokens >= 1 then tokens = tokens - 1 else wait = math.ceil((1 - tokens) / rate) end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'time', now)
redis.call('EXPIRE', KEYS[1], math.max(2, math.ceil(burst / rate) * 2))
return wait
"""


@contextmanager
def admitted(slots):
    if not slots.acquire(blocking=False):
        raise HTTPException(503, "Chat is busy; please retry", headers={"Retry-After": "1"})
    try:
        yield
    finally:
        slots.release()


def check_send_rate(user_id: str) -> None:
    global _redis_retry_at
    # Always bound local work. Redis supplies the shared account budget when healthy;
    # a short circuit breaker preserves availability with a per-worker fallback.
    now = time.monotonic()
    rate, burst = settings.care_chat_send_rate, settings.care_chat_send_burst
    with _lock:
        if user_id not in _buckets and len(_buckets) >= 10000:
            oldest, (_, timestamp) = next(iter(_buckets.items()))
            if now - timestamp >= burst / rate:
                del _buckets[oldest]
            else:
                raise HTTPException(429, "Too many active senders", headers={"Retry-After": "1"})
        tokens, previous = _buckets.get(user_id, (float(burst), now))
        tokens = min(burst, tokens + (now - previous) * rate)
        _buckets[user_id] = (max(0.0, tokens - 1) if tokens >= 1 else tokens, now)
        _buckets.move_to_end(user_id)
        if tokens < 1:
            raise HTTPException(429, "Sending too quickly",
                                headers={"Retry-After": str(max(1, math.ceil((1 - tokens) / rate)))})
    if now >= _redis_retry_at:
        try:
            wait = int(_redis.eval(_TOKEN_BUCKET, 1, f"care:v2:send-rate:{user_id}", rate, burst))
        except RedisError:
            with _lock:
                if now >= _redis_retry_at:
                    logging.getLogger(__name__).warning("care_chat_rate_limit_local_fallback")
                    _redis_retry_at = time.monotonic() + 10
        else:
            if wait:
                raise HTTPException(429, "Sending too quickly", headers={"Retry-After": str(wait)})
