"""
Подключение к Redis (кэширование, сессии).
"""

import redis.asyncio as aioredis

from app.core.config import settings

redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Получить подключение к Redis (singleton)."""
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return redis_client


async def close_redis() -> None:
    """Закрыть подключение к Redis."""
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None