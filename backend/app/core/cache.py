import json
from typing import Any

import redis

from app.core.config import settings

_client: redis.Redis | None = None
_redis_unavailable = False
_hits = 0
_misses = 0


def reset_cache_client() -> None:
    global _client, _redis_unavailable, _hits, _misses
    _client = None
    _redis_unavailable = False
    _hits = 0
    _misses = 0


def mark_redis_unavailable() -> None:
    global _redis_unavailable, _client
    _redis_unavailable = True
    _client = None


def get_redis() -> redis.Redis | None:
    global _client, _redis_unavailable
    if _redis_unavailable or not settings.redis_url:
        return None
    if _client is None:
        try:
            _client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
            )
            _client.ping()
        except redis.RedisError:
            _client = None
            _redis_unavailable = True
            return None
    return _client


def redis_available() -> bool:
    return get_redis() is not None


def cache_get(key: str) -> Any | None:
    global _hits, _misses
    client = get_redis()
    if not client:
        _misses += 1
        return None
    try:
        value = client.get(key)
        if value is None:
            _misses += 1
            return None
        _hits += 1
        return json.loads(value)
    except (redis.RedisError, json.JSONDecodeError):
        _misses += 1
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 120) -> None:
    client = get_redis()
    if not client:
        return
    try:
        client.setex(key, ttl_seconds, json.dumps(value))
    except (redis.RedisError, TypeError):
        return


def cache_delete(key: str) -> None:
    client = get_redis()
    if not client:
        return
    try:
        client.delete(key)
    except redis.RedisError:
        return


def cache_stats() -> dict:
    total = _hits + _misses
    return {
        "hits": _hits,
        "misses": _misses,
        "hitRate": round(_hits / total, 3) if total else 0,
        "available": redis_available(),
    }
