"""In-memory sliding-window rate limiter.

Sufficient for a single-process local deployment. For multi-worker/production
deployments replace with a shared store (e.g. Redis); the interface stays the
same.
"""
from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """Return True if the request is allowed, recording the attempt."""
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            dq = self._hits.setdefault(key, deque())
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= max_attempts:
                return False
            dq.append(now)
            return True

    def remaining(self, key: str, max_attempts: int, window_seconds: int) -> int:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            dq = self._hits.get(key, deque())
            return max(0, max_attempts - sum(1 for t in dq if t > cutoff))

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = SlidingWindowLimiter()
otp_limiter = SlidingWindowLimiter()
