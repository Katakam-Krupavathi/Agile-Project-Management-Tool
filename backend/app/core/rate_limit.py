from collections import defaultdict, deque
from collections.abc import Callable
from math import ceil
from threading import Lock
from time import monotonic


class SlidingWindowRateLimiter:
    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, bucket: deque[float], now: float, window_seconds: int) -> None:
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

    def check(self, key: str, max_attempts: int, window_seconds: int) -> int | None:
        now = self._clock()
        with self._lock:
            bucket = self._attempts[key]
            self._prune(bucket, now, window_seconds)
            if len(bucket) >= max_attempts:
                retry_after = max(1, ceil(bucket[0] + window_seconds - now))
                return retry_after
            return None

    def record_attempt(self, key: str, window_seconds: int) -> None:
        now = self._clock()
        with self._lock:
            bucket = self._attempts[key]
            self._prune(bucket, now, window_seconds)
            bucket.append(now)

    def compute_backoff_delay(
        self,
        key: str,
        base_seconds: float,
        max_seconds: float,
        window_seconds: int,
    ) -> float:
        if base_seconds <= 0 or max_seconds <= 0:
            return 0.0
        now = self._clock()
        with self._lock:
            bucket = self._attempts[key]
            self._prune(bucket, now, window_seconds)
            failures = len(bucket)
            if failures == 0:
                return 0.0
            delay = base_seconds * (2 ** (failures - 1))
            return float(min(delay, max_seconds))

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()


login_rate_limiter = SlidingWindowRateLimiter()
