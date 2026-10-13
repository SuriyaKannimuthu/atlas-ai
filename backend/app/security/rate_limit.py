"""Fixed-window rate limiting, backed by Redis when configured and process memory otherwise."""

from __future__ import annotations

import threading
import time
from typing import Protocol


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window_s: int = 60) -> bool:
        """Record a hit; return False when the caller is over the limit."""
        ...


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, int]] = {}

    def hit(self, key: str, limit: int, window_s: int = 60) -> bool:
        window = int(time.time() // window_s)
        with self._lock:
            current_window, count = self._windows.get(key, (window, 0))
            if current_window != window:
                count = 0
            count += 1
            self._windows[key] = (window, count)
            return count <= limit


class RedisRateLimiter:
    """Shared limiter for multi-instance deployments."""

    def __init__(self, redis_url: str) -> None:
        import redis

        self._redis = redis.Redis.from_url(redis_url)

    def hit(self, key: str, limit: int, window_s: int = 60) -> bool:
        window = int(time.time() // window_s)
        redis_key = f"atlas:ratelimit:{key}:{window}"
        pipe = self._redis.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_s)
        count, _ = pipe.execute()
        return int(count) <= limit


def build_rate_limiter(redis_url: str | None) -> RateLimiter:
    return RedisRateLimiter(redis_url) if redis_url else InMemoryRateLimiter()
