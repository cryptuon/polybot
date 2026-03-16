"""API middleware for PolyBot.

Provides rate limiting, correlation IDs, and request tracking.
"""

import logging
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar
from datetime import datetime
from typing import Callable, Dict, Optional, Tuple

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger(__name__)

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """Get or create correlation ID for current context."""
    cid = correlation_id_var.get()
    if cid is None:
        cid = str(uuid.uuid4())[:8]
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current context."""
    correlation_id_var.set(cid)


class RateLimiter:
    """Token bucket rate limiter.

    Implements a sliding window token bucket algorithm for rate limiting.
    """

    def __init__(
        self,
        requests_per_minute: int = 120,
        burst_size: int = 20,
    ):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Sustained rate limit
            burst_size: Maximum burst above sustained rate
        """
        self.rate = requests_per_minute / 60.0  # Tokens per second
        self.burst_size = burst_size
        self._buckets: Dict[str, Tuple[float, float]] = defaultdict(
            lambda: (burst_size, time.time())
        )

    def is_allowed(self, key: str) -> Tuple[bool, float]:
        """Check if request is allowed.

        Args:
            key: Client identifier (IP or API key)

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        tokens, last_update = self._buckets[key]
        now = time.time()

        # Refill tokens based on time elapsed
        elapsed = now - last_update
        tokens = min(self.burst_size, tokens + elapsed * self.rate)

        if tokens >= 1:
            self._buckets[key] = (tokens - 1, now)
            return True, 0.0

        # Calculate retry-after
        retry_after = (1 - tokens) / self.rate
        self._buckets[key] = (tokens, now)
        return False, retry_after

    def get_status(self, key: str) -> Dict[str, float]:
        """Get rate limit status for a client.

        Args:
            key: Client identifier

        Returns:
            Status dict with tokens remaining and utilization
        """
        tokens, last_update = self._buckets.get(key, (self.burst_size, time.time()))
        now = time.time()
        elapsed = now - last_update
        current_tokens = min(self.burst_size, tokens + elapsed * self.rate)

        return {
            "tokens_remaining": current_tokens,
            "burst_limit": self.burst_size,
            "rate_per_minute": self.rate * 60,
            "utilization": 1 - (current_tokens / self.burst_size),
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for FastAPI.

    Limits requests per client based on IP address or API key.
    """

    # Paths excluded from rate limiting
    EXCLUDED_PATHS = {"/health", "/health/live", "/health/ready", "/metrics", "/"}

    def __init__(
        self,
        app,
        requests_per_minute: int = 120,
        burst_size: int = 20,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute, burst_size)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip if disabled or excluded path
        if not self.enabled or request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Get client identifier (API key preferred over IP)
        api_key = request.headers.get("X-API-Key", "")
        client_ip = request.client.host if request.client else "unknown"
        client_id = api_key[:16] if api_key else client_ip

        # Check rate limit
        allowed, retry_after = self.limiter.is_allowed(client_id)

        if not allowed:
            logger.warning(
                f"Rate limit exceeded for {client_id} on {request.url.path}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        # Add rate limit headers to response
        response = await call_next(request)
        status_info = self.limiter.get_status(client_id)
        response.headers["X-RateLimit-Limit"] = str(int(status_info["rate_per_minute"]))
        response.headers["X-RateLimit-Remaining"] = str(int(status_info["tokens_remaining"]))

        return response


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to extract or generate correlation IDs.

    Correlation IDs are used to trace requests across services and logs.
    """

    CORRELATION_ID_HEADER = "X-Correlation-ID"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with correlation ID."""
        # Get correlation ID from header or generate new one
        correlation_id = request.headers.get(
            self.CORRELATION_ID_HEADER, str(uuid.uuid4())[:8]
        )

        # Set in context for logging
        set_correlation_id(correlation_id)

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers[self.CORRELATION_ID_HEADER] = correlation_id

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests."""

    # Paths to exclude from logging
    EXCLUDED_PATHS = {"/health", "/health/live", "/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        start_time = time.time()
        correlation_id = get_correlation_id()

        # Log request
        logger.info(
            f"[{correlation_id}] {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            # Log response
            logger.info(
                f"[{correlation_id}] {request.method} {request.url.path} "
                f"-> {response.status_code} ({duration_ms:.2f}ms)"
            )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[{correlation_id}] {request.method} {request.url.path} "
                f"-> ERROR: {e} ({duration_ms:.2f}ms)"
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Remove server header if present
        if "server" in response.headers:
            del response.headers["server"]

        return response
