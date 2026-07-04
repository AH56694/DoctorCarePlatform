import json
import logging
from datetime import datetime, timezone
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class MessageCache:
    def __init__(self, redis_url: str = settings.redis_url, ttl_seconds: int = 86400) -> None:
        self.ttl_seconds = ttl_seconds
        self.client = Redis.from_url(redis_url, decode_responses=True)

    def add_message(
        self,
        namespace: str,
        conversation_id: str,
        payload: dict[str, Any],
    ) -> None:
        if not conversation_id:
            return
        key = self._messages_key(namespace, conversation_id)
        message = {
            **payload,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.client.rpush(key, json.dumps(message, ensure_ascii=False, default=str))
            self.client.expire(key, self.ttl_seconds)
        except RedisError as exc:
            logger.warning("Failed to cache %s message for %s: %s", namespace, conversation_id, exc)

    def get_messages(self, namespace: str, conversation_id: str, limit: int = 200) -> list[dict[str, Any]]:
        if not conversation_id:
            return []
        key = self._messages_key(namespace, conversation_id)
        try:
            raw_messages = self.client.lrange(key, -limit, -1)
        except RedisError as exc:
            logger.warning("Failed to read %s messages for %s: %s", namespace, conversation_id, exc)
            return []
        messages: list[dict[str, Any]] = []
        for raw_message in raw_messages:
            try:
                parsed = json.loads(raw_message)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                messages.append(parsed)
        return messages

    def _messages_key(self, namespace: str, conversation_id: str) -> str:
        return f"{namespace}:conversation:{conversation_id}:messages"


message_cache = MessageCache()
