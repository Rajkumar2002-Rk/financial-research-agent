import json
import redis.asyncio as aioredis
from typing import List, Dict, Any
from app.utils.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SessionService:

    def __init__(self, settings=None):
        if settings is None:
            settings = get_settings()
        self.redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        self.ttl = settings.REDIS_SESSION_TTL

    async def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        try:
            key = f"session:{session_id}"
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return []
        except Exception as e:
            logger.error("session_get_failed", session_id=session_id, error=str(e))
            return []

    async def add_to_history(self, session_id: str, role: str, content: str) -> None:
        try:
            key = f"session:{session_id}"
            history = await self.get_history(session_id)
            history.append({"role": role, "content": content})

            if len(history) > 20:
                history = history[-20:]

            await self.redis.setex(key, self.ttl, json.dumps(history))
        except Exception as e:
            logger.error("session_add_failed", session_id=session_id, error=str(e))

    async def clear_session(self, session_id: str) -> None:
        try:
            await self.redis.delete(f"session:{session_id}")
            logger.info("session_cleared", session_id=session_id)
        except Exception as e:
            logger.error("session_clear_failed", session_id=session_id, error=str(e))