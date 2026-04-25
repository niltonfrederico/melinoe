"""Redis client helper: provides an ARQ-compatible Redis pool."""

from arq import create_pool
from arq.connections import ArqRedis
from arq.connections import RedisSettings

import melinoe.settings as settings


def get_redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.REDIS_URL)


async def get_redis_pool() -> ArqRedis:
    return await create_pool(get_redis_settings())
