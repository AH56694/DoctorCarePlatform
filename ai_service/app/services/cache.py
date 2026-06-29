import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from ai_service.app.core.config import settings


def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def cache_hash(*parts: str) -> str:
    raw = "\n".join(normalize_text(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class CacheEntry:
    value: str
    expires_at: float


class L1Cache:
    def __init__(self, max_size: int = 256, ttl_seconds: int = 600) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, CacheEntry] = OrderedDict()

    def get(self, key: str) -> str | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.time():
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return entry.value

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds or self.ttl_seconds
        self._items[key] = CacheEntry(value=value, expires_at=time.time() + ttl)
        self._items.move_to_end(key)
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)


class L2RedisCache:
    def __init__(self) -> None:
        self._client: Any | None = None
        self._available = True

    async def _get_client(self) -> Any | None:
        if not self._available:
            return None
        if self._client is not None:
            return self._client
        try:
            from redis.asyncio import Redis

            self._client = Redis.from_url(settings.redis_url, decode_responses=True)
            await self._client.ping()
            return self._client
        except Exception:
            self._available = False
            return None

    async def get(self, key: str) -> str | None:
        client = await self._get_client()
        if client is None:
            return None
        try:
            return await client.get(key)
        except Exception:
            self._available = False
            return None

    async def set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        client = await self._get_client()
        if client is None:
            return
        try:
            await client.setex(key, ttl_seconds, value)
        except Exception:
            self._available = False


def dumps_cache_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def loads_cache_payload(value: str) -> dict[str, Any] | None:
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


l1_cache = L1Cache()
l2_cache = L2RedisCache()
