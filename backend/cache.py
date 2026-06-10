"""
In-memory cache with TTL support
"""
import time
from typing import Any, Optional


class Cache:
    def __init__(self, ttl: int = 60, max_size: int = 50):
        self.ttl = ttl
        self.max_size = max_size
        self._store: dict = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expires_at = self._store[key]
            if time.time() < expires_at:
                return value
            else:
                del self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (value, time.time() + self.ttl)
        self._cleanup()

    def _cleanup(self) -> None:
        now = time.time()
        # Remove expired
        expired_keys = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired_keys:
            del self._store[k]
        
        # Enforce max size (remove oldest)
        if len(self._store) > self.max_size:
            # Sort by expiration time (oldest expires soonest)
            sorted_items = sorted(self._store.items(), key=lambda x: x[1][1])
            keys_to_delete = [k for k, _ in sorted_items[:len(self._store) - self.max_size]]
            for k in keys_to_delete:
                del self._store[k]

    def clear(self) -> None:
        self._store.clear()

    def size(self) -> int:
        return len(self._store)
