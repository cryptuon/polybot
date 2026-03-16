"""Binance API rate limiter.

Implements weight-based rate limiting for Binance API endpoints.
Binance uses request weight system where different endpoints have
different costs.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict


class BinanceRateLimitType(str, Enum):
    """Binance rate limit types."""

    REQUEST_WEIGHT = "REQUEST_WEIGHT"  # Most endpoints
    ORDERS = "ORDERS"  # Order placement/cancellation
    RAW_REQUESTS = "RAW_REQUESTS"  # Raw request count


@dataclass
class BinanceRateLimitConfig:
    """Configuration for a rate limit bucket."""

    limit: int
    interval_ms: int  # Typically 1min = 60000ms


@dataclass
class WeightedBucket:
    """Token bucket with weight support.

    Tracks usage over a sliding window and provides
    rate limiting with weight-based costs.
    """

    capacity: int
    interval_ms: int
    used: int = 0
    last_reset: float = field(default_factory=time.monotonic)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self, weight: int = 1) -> float:
        """Acquire rate limit capacity.

        Args:
            weight: Cost of this request

        Returns:
            Time waited in seconds (0 if no wait needed)
        """
        async with self._lock:
            now = time.monotonic()
            elapsed_ms = (now - self.last_reset) * 1000

            # Reset if interval has passed
            if elapsed_ms >= self.interval_ms:
                self.used = 0
                self.last_reset = now

            # Check if we have capacity
            if self.used + weight <= self.capacity:
                self.used += weight
                return 0.0

            # Calculate wait time until reset
            wait_ms = self.interval_ms - elapsed_ms
            wait_sec = wait_ms / 1000

            # Wait for reset
            await asyncio.sleep(wait_sec)

            # Reset and acquire
            self.used = weight
            self.last_reset = time.monotonic()
            return wait_sec

    @property
    def remaining(self) -> int:
        """Get remaining capacity."""
        return max(0, self.capacity - self.used)

    @property
    def utilization(self) -> float:
        """Get utilization percentage."""
        return self.used / self.capacity if self.capacity > 0 else 0


class BinanceRateLimiter:
    """Rate limiter for Binance API with weight-based limits.

    Manages multiple rate limit buckets based on Binance's
    rate limit system.

    Default limits (can be updated from exchange info):
    - REQUEST_WEIGHT: 1200/min
    - ORDERS: 10/sec
    - RAW_REQUESTS: 5000/5min
    """

    # Default limits
    DEFAULT_LIMITS: Dict[BinanceRateLimitType, BinanceRateLimitConfig] = {
        BinanceRateLimitType.REQUEST_WEIGHT: BinanceRateLimitConfig(1200, 60000),
        BinanceRateLimitType.ORDERS: BinanceRateLimitConfig(10, 1000),
        BinanceRateLimitType.RAW_REQUESTS: BinanceRateLimitConfig(5000, 300000),
    }

    # Endpoint weights for common endpoints
    ENDPOINT_WEIGHTS: Dict[str, int] = {
        # Spot
        "/api/v3/exchangeInfo": 10,
        "/api/v3/ticker/24hr": 40,  # All symbols
        "/api/v3/ticker/price": 1,
        "/api/v3/depth": 50,  # limit=100
        "/api/v3/order": 1,
        "/api/v3/openOrders": 3,
        "/api/v3/account": 10,
        "/api/v3/myTrades": 10,
        # Futures
        "/fapi/v1/exchangeInfo": 1,
        "/fapi/v1/ticker/24hr": 1,
        "/fapi/v1/depth": 20,
        "/fapi/v1/order": 1,
        "/fapi/v1/account": 5,
        "/fapi/v2/positionRisk": 5,
    }

    def __init__(self) -> None:
        """Initialize rate limiter with default buckets."""
        self._buckets: Dict[BinanceRateLimitType, WeightedBucket] = {}
        self._init_buckets()

    def _init_buckets(self) -> None:
        """Initialize rate limit buckets."""
        for limit_type, config in self.DEFAULT_LIMITS.items():
            self._buckets[limit_type] = WeightedBucket(
                capacity=config.limit,
                interval_ms=config.interval_ms,
            )

    async def acquire(
        self,
        limit_type: BinanceRateLimitType = BinanceRateLimitType.REQUEST_WEIGHT,
        weight: int = 1,
    ) -> float:
        """Acquire rate limit for a request.

        Args:
            limit_type: Type of rate limit
            weight: Request weight/cost

        Returns:
            Time waited in seconds
        """
        bucket = self._buckets.get(limit_type)
        if bucket:
            return await bucket.acquire(weight)
        return 0.0

    async def acquire_for_endpoint(self, endpoint: str) -> float:
        """Acquire rate limit for a specific endpoint.

        Uses known endpoint weights or defaults to 1.

        Args:
            endpoint: API endpoint path

        Returns:
            Time waited in seconds
        """
        weight = self.ENDPOINT_WEIGHTS.get(endpoint, 1)
        return await self.acquire(BinanceRateLimitType.REQUEST_WEIGHT, weight)

    async def acquire_order(self) -> float:
        """Acquire rate limit for order operations.

        Acquires both REQUEST_WEIGHT and ORDERS limits.

        Returns:
            Total time waited in seconds
        """
        waited = 0.0
        waited += await self.acquire(BinanceRateLimitType.REQUEST_WEIGHT, 1)
        waited += await self.acquire(BinanceRateLimitType.ORDERS, 1)
        return waited

    def update_limits(
        self,
        limit_type: BinanceRateLimitType,
        limit: int,
        interval_ms: int,
    ) -> None:
        """Update limits from exchange info response.

        Call this after getting exchange info to use actual limits.

        Args:
            limit_type: Type of rate limit
            limit: New limit value
            interval_ms: New interval in milliseconds
        """
        if limit_type in self._buckets:
            old_bucket = self._buckets[limit_type]
            self._buckets[limit_type] = WeightedBucket(
                capacity=limit,
                interval_ms=interval_ms,
                used=old_bucket.used,
                last_reset=old_bucket.last_reset,
            )

    def update_from_headers(self, headers: Dict[str, str]) -> None:
        """Update used weight from response headers.

        Binance returns current usage in headers:
        - X-MBX-USED-WEIGHT-1M: Weight used in last minute

        Args:
            headers: Response headers
        """
        # Extract used weight if present
        used_weight = headers.get("X-MBX-USED-WEIGHT-1M")
        if used_weight:
            try:
                bucket = self._buckets.get(BinanceRateLimitType.REQUEST_WEIGHT)
                if bucket:
                    bucket.used = int(used_weight)
            except ValueError:
                pass

    def get_status(self) -> Dict[str, Dict[str, float]]:
        """Get current rate limit status.

        Returns:
            Dict mapping limit type to remaining/utilization
        """
        return {
            limit_type.value: {
                "remaining": bucket.remaining,
                "utilization": bucket.utilization,
            }
            for limit_type, bucket in self._buckets.items()
        }
