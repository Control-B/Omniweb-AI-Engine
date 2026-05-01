"""Redis client and helpers for job queue and caching."""
import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

_redis_client: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    """Return a shared Redis client (created lazily)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def redis_set(key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
    r = get_redis()
    serialized = json.dumps(value) if not isinstance(value, str) else value
    if ttl_seconds:
        await r.setex(key, ttl_seconds, serialized)
    else:
        await r.set(key, serialized)


async def redis_get(key: str) -> Optional[Any]:
    r = get_redis()
    val = await r.get(key)
    if val is None:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return val


async def redis_delete(key: str) -> None:
    r = get_redis()
    await r.delete(key)


async def redis_publish(channel: str, message: Any) -> None:
    """Publish an event to a Redis pub/sub channel."""
    r = get_redis()
    payload = json.dumps(message) if not isinstance(message, str) else message
    await r.publish(channel, payload)
