import sys
import os
import json
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.cache import RedisCache

@pytest.fixture
def mock_redis():
    with patch("app.services.cache.redis.Redis.from_url") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client

class TestRedisCache:
    def test_get_miss_returns_none(self, mock_redis):
        mock_redis.get.return_value = None
        cache = RedisCache("redis://dummy")
        assert cache.get("https://not-stored.com") is None

    def test_set_and_get_round_trip(self, mock_redis):
        data = {"video_id": "abc", "title": "Test"}
        mock_redis.get.return_value = json.dumps(data)
        
        cache = RedisCache("redis://dummy")
        cache.set("https://example.com/vid", data)
        
        mock_redis.set.assert_called_once()
        assert cache.get("https://example.com/vid") == data

    def test_clear_empties_the_store(self, mock_redis):
        cache = RedisCache("redis://dummy")
        cache.clear()
        mock_redis.flushdb.assert_called_once()

    def test_redis_connection_error_fallback(self):
        import redis
        with patch("app.services.cache.redis.Redis.from_url", side_effect=redis.ConnectionError("Conn error")):
            cache = RedisCache("redis://dummy")
            assert cache.is_connected is False
            # Should safely ignore operations
            cache.set("a", {"x": 1})
            assert cache.get("a") is None
            cache.clear()
