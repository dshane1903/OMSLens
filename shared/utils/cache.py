import json

import redis

from shared.utils.config import get_settings


def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
    )


def get_cached_json(key: str) -> dict | None:
    try:
        payload = get_redis_client().get(key)
    except redis.RedisError:
        return None

    if not payload:
        return None

    return json.loads(payload)


def set_cached_json(key: str, value: dict) -> None:
    settings = get_settings()
    try:
        get_redis_client().setex(
            key,
            settings.redis_cache_ttl_seconds,
            json.dumps(value),
        )
    except redis.RedisError:
        return None
