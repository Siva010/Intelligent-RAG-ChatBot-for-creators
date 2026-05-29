"""
Unit tests for app/services/cache.py (MemoryCache).
No external dependencies — pure in-memory logic.

Run with: pytest tests/test_cache.py -v
"""
import sys
import os
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.cache import MemoryCache


class TestMemoryCacheBasics:
    def test_get_miss_returns_none(self):
        cache = MemoryCache()
        assert cache.get("https://not-stored.com") is None

    def test_set_and_get_round_trip(self):
        cache = MemoryCache()
        data = {"video_id": "abc", "title": "Test"}
        cache.set("https://example.com/vid", data)
        assert cache.get("https://example.com/vid") == data

    def test_get_returns_exact_data(self):
        cache = MemoryCache()
        payload = {"nested": {"key": [1, 2, 3]}, "number": 42}
        cache.set("url_key", payload)
        assert cache.get("url_key") == payload

    def test_overwrite_existing_key(self):
        cache = MemoryCache()
        cache.set("url", {"v": 1})
        cache.set("url", {"v": 2})
        assert cache.get("url") == {"v": 2}

    def test_clear_empties_the_store(self):
        cache = MemoryCache()
        cache.set("a", {"x": 1})
        cache.set("b", {"x": 2})
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None


class TestMemoryCacheTTL:
    def test_item_expired_after_ttl(self):
        cache = MemoryCache(ttl_seconds=1)
        cache.set("url", {"data": "old"})
        # Manually backdate the stored timestamp
        key = "url"
        cache.store[key]["timestamp"] -= 2   # push it 2s into the past
        assert cache.get("url") is None      # should be expired

    def test_item_valid_before_ttl(self):
        cache = MemoryCache(ttl_seconds=3600)
        cache.set("url", {"data": "fresh"})
        assert cache.get("url") is not None

    def test_expired_items_cleaned_on_set(self):
        cache = MemoryCache(ttl_seconds=1)
        cache.set("url_old", {"data": "old"})
        cache.store["url_old"]["timestamp"] -= 2   # expire it

        cache.set("url_new", {"data": "new"})      # triggers _cleanup_expired
        assert "url_old" not in cache.store
        assert cache.get("url_new") == {"data": "new"}


class TestMemoryCacheMaxSize:
    def test_oldest_entry_evicted_when_full(self):
        cache = MemoryCache(max_size=3)
        cache.set("url1", {"v": 1})
        time.sleep(0.01)
        cache.set("url2", {"v": 2})
        time.sleep(0.01)
        cache.set("url3", {"v": 3})
        time.sleep(0.01)
        # This should evict "url1" (oldest)
        cache.set("url4", {"v": 4})

        assert cache.get("url1") is None        # evicted
        assert cache.get("url4") == {"v": 4}   # new entry present
        assert len(cache.store) == 3

    def test_size_never_exceeds_max(self):
        cache = MemoryCache(max_size=5)
        for i in range(20):
            cache.set(f"url{i}", {"v": i})
            time.sleep(0.001)
        assert len(cache.store) <= 5
