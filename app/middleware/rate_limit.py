"""Simple in-memory rate limiter for public Shopify endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter keyed by client IP.

    Only applies to paths starting with ``/api/shopify/public/``.
    """

    def __init__(
        self,
        app,
        *,
        requests_per_minute: int = 60,
        burst: int = 10,
    ):
        super().__init__(app)
        self.rate = requests_per_minute / 60.0  # tokens per second
        self.burst = burst
        self._buckets: dict[str, list[float]] = defaultdict(lambda: [float(burst), time.monotonic()])

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not request.url.path.startswith("/api/shopify/public/"):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        bucket = self._buckets[ip]
        now = time.monotonic()
        elapsed = now - bucket[1]
        bucket[1] = now
        bucket[0] = min(self.burst, bucket[0] + elapsed * self.rate)

        if bucket[0] < 1.0:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": str(int(1.0 / self.rate))},
            )

        bucket[0] -= 1.0
        return await call_next(request)
