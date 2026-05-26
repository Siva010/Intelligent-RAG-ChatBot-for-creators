import time
from typing import Dict, Any, Optional

class MemoryCache:
    def __init__(self, ttl_seconds: int = 3600, max_size: int = 100):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self.store: Dict[str, Dict[str, Any]] = {}

    def _cleanup_expired(self):
        now = time.time()
        expired_keys = [
            k for k, entry in self.store.items() 
            if now - entry["timestamp"] > self.ttl
        ]
        for k in expired_keys:
            del self.store[k]

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        self._cleanup_expired()
        
        entry = self.store.get(url)
        if entry:
            # Update timestamp for Least Recently Used behavior or just keep it simple
            return entry["data"]
        return None

    def set(self, url: str, data: Dict[str, Any]) -> None:
        self._cleanup_expired()
        
        # Enforce max size limit by removing the oldest entry if full
        if len(self.store) >= self.max_size:
            oldest_key = min(self.store.keys(), key=lambda k: self.store[k]["timestamp"])
            del self.store[oldest_key]
            
        self.store[url] = {
            "timestamp": time.time(),
            "data": data
        }

    def clear(self) -> None:
        self.store.clear()

# Global singleton instance of cache
video_cache = MemoryCache()
