"""Disposable, complete latest pages. Redis is never the message source of truth."""

import json
import logging
import threading
import time

from redis import Redis
from redis.exceptions import RedisError

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class LatestPageCache:
    def __init__(self) -> None:
        self.client = Redis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=0.1,
            socket_timeout=0.1, max_connections=16,
        )
        self._retry_at = 0.0
        self._lock = threading.Lock()

    def _available(self) -> bool:
        return settings.care_chat_cache_enabled and time.monotonic() >= self._retry_at

    def _failed(self) -> None:
        with self._lock:
            if time.monotonic() >= self._retry_at:
                logger.warning("care_chat_cache_unavailable")
            self._retry_at = time.monotonic() + 10

    @staticmethod
    def _key(conversation_id: str, version: int, limit: int) -> str:
        return f"care:v2:latest:{conversation_id}:{version}:{limit}"

    def get(self, conversation_id: str, version: int, limit: int) -> dict | None:
        if not self._available():
            return None
        try:
            value = self.client.get(self._key(conversation_id, version, limit))
            result = json.loads(value) if value else None
            return result if isinstance(result, dict) else None
        except (RedisError, ValueError, TypeError):
            self._failed()
            return None

    def set(self, conversation_id: str, version: int, limit: int, payload: dict) -> None:
        if not self._available():
            return
        try:
            self.client.set(self._key(conversation_id, version, limit), json.dumps(payload), ex=30)
        except RedisError:
            self._failed()


latest_page_cache = LatestPageCache()
