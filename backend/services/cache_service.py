"""Cache service — simple in-memory cache with TTL."""
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CacheService:
    """Simple in-memory cache with TTL support."""

    _cache: Dict[str, Any] = {}
    _expiry: Dict[str, float] = {}

    @classmethod
    async def get(cls, key: str) -> Optional[Any]:
        if key in cls._expiry and time.time() > cls._expiry[key]:
            del cls._cache[key]
            del cls._expiry[key]
            return None
        return cls._cache.get(key)

    @classmethod
    async def set(cls, key: str, value: Any, ttl: int = 300) -> None:
        cls._cache[key] = value
        cls._expiry[key] = time.time() + ttl

    @classmethod
    async def delete(cls, key: str) -> None:
        cls._cache.pop(key, None)
        cls._expiry.pop(key, None)

    @classmethod
    async def clear(cls) -> None:
        cls._cache.clear()
        cls._expiry.clear()
