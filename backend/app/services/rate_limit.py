"""Bounded authentication attempts shared across production workers through Redis."""

import hashlib
import hmac
import threading
import time
from collections import OrderedDict

from fastapi import HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError

from backend.app.core.config import settings

INCREMENT = """
local attempts = redis.call('INCR', KEYS[1])
if attempts == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {attempts, redis.call('TTL', KEYS[1])}
"""


class AuthRateLimiter:
    def __init__(self):
        self.client = Redis.from_url(
            settings.redis_url, socket_connect_timeout=1, socket_timeout=1,
        )
        self._local = OrderedDict()
        self._lock = threading.Lock()

    def _increment(self, key: str, window: int) -> tuple[int, int]:
        try:
            count, ttl = self.client.eval(INCREMENT, 1, key, window)
            return int(count), max(1, int(ttl))
        except RedisError as exc:
            if settings.is_production:
                raise HTTPException(status_code=503, detail="登录服务暂不可用，请稍后重试。") from exc
        # Development may run without Redis. This fallback is never used in production.
        now = time.monotonic()
        with self._lock:
            count, expires = self._local.get(key, (0, now + window))
            if expires <= now:
                count, expires = 0, now + window
            self._local[key] = (count + 1, expires)
            self._local.move_to_end(key)
            while len(self._local) > 10_000:
                self._local.popitem(last=False)
            return count + 1, max(1, int(expires - now))

    def check(self, request: Request, phone: str) -> None:
        if not settings.auth_rate_limit_enabled:
            return
        # IP throttling belongs at the trusted ingress. A backend's peer may be a
        # shared proxy, so counting it here would lock out unrelated users.
        identities = (("account", phone, 1),)
        for kind, identity, multiplier in identities:
            digest = hmac.new(
                settings.auth_secret_key.encode(), identity.encode(), hashlib.sha256,
            ).hexdigest()
            count, ttl = self._increment(
                f"auth:attempts:{kind}:{digest}", settings.auth_rate_limit_window_seconds,
            )
            if count > settings.auth_rate_limit_attempts * multiplier:
                raise HTTPException(
                    status_code=429, detail="操作过于频繁，请稍后重试。",
                    headers={"Retry-After": str(ttl)},
                )


auth_rate_limiter = AuthRateLimiter()
