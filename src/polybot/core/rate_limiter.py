"""Rate limiter for Polymarket API compliance.

Implements token bucket rate limiting with endpoint-specific limits
matching Polymarket's documented rate limits.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict


class EndpointType(str, Enum):
    """API endpoint types with different rate limits."""

    # CLOB endpoints
    CLOB_GENERAL = "clob_general"
    CLOB_BOOK = "clob_book"
    CLOB_BOOKS = "clob_books"
    CLOB_PRICE = "clob_price"
    CLOB_PRICES = "clob_prices"
    CLOB_ORDER_POST = "clob_order_post"
    CLOB_ORDER_DELETE = "clob_order_delete"
    CLOB_ORDERS_POST = "clob_orders_post"
    CLOB_ORDERS_DELETE = "clob_orders_delete"
    CLOB_CANCEL_ALL = "clob_cancel_all"

    # Gamma endpoints
    GAMMA_GENERAL = "gamma_general"
    GAMMA_EVENTS = "gamma_events"
    GAMMA_MARKETS = "gamma_markets"
    GAMMA_COMMENTS = "gamma_comments"
    GAMMA_SEARCH = "gamma_search"

    # Data API endpoints
    DATA_GENERAL = "data_general"
    DATA_TRADES = "data_trades"
    DATA_POSITIONS = "data_positions"


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit bucket."""

    requests: int  # Number of requests allowed
    window_seconds: float  # Time window in seconds
    burst_requests: int | None = None  # Optional burst limit per second
    sustained_requests: int | None = None  # Optional sustained limit per 10 minutes


# Rate limits from Polymarket documentation (per 10 seconds unless noted)
RATE_LIMITS: Dict[EndpointType, RateLimitConfig] = {
    # CLOB endpoints
    EndpointType.CLOB_GENERAL: RateLimitConfig(9000, 10),
    EndpointType.CLOB_BOOK: RateLimitConfig(1500, 10),
    EndpointType.CLOB_BOOKS: RateLimitConfig(500, 10),
    EndpointType.CLOB_PRICE: RateLimitConfig(1500, 10),
    EndpointType.CLOB_PRICES: RateLimitConfig(500, 10),
    EndpointType.CLOB_ORDER_POST: RateLimitConfig(3500, 10, burst_requests=500, sustained_requests=36000),
    EndpointType.CLOB_ORDER_DELETE: RateLimitConfig(3000, 10, burst_requests=300, sustained_requests=30000),
    EndpointType.CLOB_ORDERS_POST: RateLimitConfig(1000, 10, sustained_requests=15000),
    EndpointType.CLOB_ORDERS_DELETE: RateLimitConfig(1000, 10, sustained_requests=15000),
    EndpointType.CLOB_CANCEL_ALL: RateLimitConfig(250, 10, sustained_requests=6000),
    # Gamma endpoints
    EndpointType.GAMMA_GENERAL: RateLimitConfig(4000, 10),
    EndpointType.GAMMA_EVENTS: RateLimitConfig(300, 10),
    EndpointType.GAMMA_MARKETS: RateLimitConfig(300, 10),
    EndpointType.GAMMA_COMMENTS: RateLimitConfig(200, 10),
    EndpointType.GAMMA_SEARCH: RateLimitConfig(300, 10),
    # Data API endpoints
    EndpointType.DATA_GENERAL: RateLimitConfig(1000, 10),
    EndpointType.DATA_TRADES: RateLimitConfig(200, 10),
    EndpointType.DATA_POSITIONS: RateLimitConfig(150, 10),
}


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: float
    tokens: float = field(init=False)
    refill_rate: float  # tokens per second
    last_refill: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self.tokens = self.capacity

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    async def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens, waiting if necessary.

        Returns the time waited in seconds.
        """
        async with self.lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0

            # Calculate wait time
            deficit = tokens - self.tokens
            wait_time = deficit / self.refill_rate

            # Wait and then take the tokens
            await asyncio.sleep(wait_time)
            self._refill()
            self.tokens -= tokens
            return wait_time

    def available(self) -> float:
        """Return current available tokens (for monitoring)."""
        self._refill()
        return self.tokens


class RateLimiter:
    """Rate limiter managing multiple endpoint-specific buckets.

    Usage:
        limiter = RateLimiter()
        await limiter.acquire(EndpointType.CLOB_ORDER_POST)
        # Make API request...
    """

    def __init__(self) -> None:
        self._buckets: Dict[EndpointType, TokenBucket] = {}
        self._init_buckets()

    def _init_buckets(self) -> None:
        """Initialize token buckets for each endpoint type."""
        for endpoint_type, config in RATE_LIMITS.items():
            self._buckets[endpoint_type] = TokenBucket(
                capacity=float(config.requests),
                refill_rate=config.requests / config.window_seconds,
            )

    async def acquire(self, endpoint_type: EndpointType, tokens: int = 1) -> float:
        """Acquire rate limit tokens for an endpoint.

        Args:
            endpoint_type: The type of endpoint being called
            tokens: Number of tokens to acquire (usually 1)

        Returns:
            Time waited in seconds (0 if no wait was needed)
        """
        bucket = self._buckets.get(endpoint_type)
        if bucket is None:
            return 0.0
        return await bucket.acquire(tokens)

    def get_available(self, endpoint_type: EndpointType) -> float:
        """Get available tokens for an endpoint (for monitoring)."""
        bucket = self._buckets.get(endpoint_type)
        if bucket is None:
            return float("inf")
        return bucket.available()

    def get_status(self) -> Dict[str, Dict[str, float]]:
        """Get status of all rate limit buckets."""
        return {
            endpoint_type.value: {
                "available": bucket.available(),
                "capacity": bucket.capacity,
                "utilization": 1 - (bucket.available() / bucket.capacity),
            }
            for endpoint_type, bucket in self._buckets.items()
        }


# Module-level rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
