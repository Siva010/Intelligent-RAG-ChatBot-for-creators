import json
import logging
from typing import Dict, Any, Optional
import redis
from app.config import settings

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self, redis_url: str, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        try:
            self.client: Optional[redis.Redis] = redis.Redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.client.ping()
            self.is_connected = True
            logger.info(f"Connected to Redis cache at {redis_url}")
        except redis.ConnectionError as e:
            logger.warning(f"Failed to connect to Redis at {redis_url}: {e}. Falling back to a dummy cache.")
            self.is_connected = False
            self.client = None

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        if not self.is_connected or not self.client:
            return None
        try:
            data_str = self.client.get(url)
            if isinstance(data_str, (str, bytes, bytearray)):
                return json.loads(data_str)
            return None
        except Exception as e:
            logger.error(f"Redis get error for {url}: {e}")
            return None

    def set(self, url: str, data: Dict[str, Any]) -> None:
        if not self.is_connected or not self.client:
            return
        try:
            data_str = json.dumps(data)
            self.client.set(url, data_str, ex=self.ttl)
        except Exception as e:
            logger.error(f"Redis set error for {url}: {e}")

    def clear(self) -> None:
        if not self.is_connected or not self.client:
            return
        try:
            self.client.flushdb()
        except Exception as e:
            logger.error(f"Redis clear error: {e}")

# Global singleton instance of cache
video_cache = RedisCache(redis_url=settings.redis_url, ttl_seconds=settings.cache_expiry_seconds)
