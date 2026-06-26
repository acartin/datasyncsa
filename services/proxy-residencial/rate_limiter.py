from __future__ import annotations

import time
import threading
from collections import defaultdict


class TokenBucket:
    """Token bucket rate limiter por dominio.

    Uso:
        limiter = TokenBucket(rate=5.0)
        limiter.wait("instaleap.io")   # bloquea hasta tener token
        hacer_request()
    """

    def __init__(self, rate: float = 5.0, burst: int = 1) -> None:
        if rate <= 0:
            raise ValueError("rate debe ser > 0")
        self.rate = rate
        self.burst = burst
        self._lock = threading.Lock()
        self._buckets: dict[str, float] = defaultdict(lambda: float(burst))
        self._last: dict[str, float] = defaultdict(time.monotonic)

    def wait(self, key: str = "default") -> float:
        """Bloquea hasta obtener un token. Retorna el tiempo de espera en segundos."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last[key]
            bucket = min(self._buckets[key] + elapsed * self.rate, float(self.burst))
            if bucket >= 1.0:
                self._buckets[key] = bucket - 1.0
                self._last[key] = now
                return 0.0
            sleep_needed = (1.0 - bucket) / self.rate
            self._buckets[key] = 0.0
            self._last[key] = now + sleep_needed

        time.sleep(sleep_needed)
        return sleep_needed

    def peak_rate(self, key: str = "default") -> float:
        """Retorna la tasa actual efectiva para una clave (debug)."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last[key]
            bucket = min(self._buckets[key] + elapsed * self.rate, float(self.burst))
            return bucket
