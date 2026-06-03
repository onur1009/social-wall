"""
In-memory cache with TTL support
"""
import time
from typing import Any, Optional


class Cache:
    def __init__(self, ttl: int = 60):
        self.ttl = ttl
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

    def clear(self) -> None:
        self._store.clear()

    def size(self) -> int:
        return len(self._store)
