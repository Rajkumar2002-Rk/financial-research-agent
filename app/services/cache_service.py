import redis.asyncio as aioredis
import json
from typing import Optional, Any
from app.utils.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CacheService:

    def __init__(self, settings=None):
        if settings is None:
            settings = get_settings()
        self.redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        self.default_ttl = settings.REDIS_CACHE_TTL

    async def get(self, key: str) -> Optional[Any]:
        try:
            value = await self.redis.get(key)
            if value:
                logger.info("cache_hit", key=key)
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("cache_get_failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        try:
            ttl = ttl or self.default_ttl
            await self.redis.setex(key, ttl, json.dumps(value))
            logger.info("cache_set", key=key, ttl=ttl)
            return True
        except Exception as e:
            logger.error("cache_set_failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error("cache_delete_failed", key=key, error=str(e))
            return False