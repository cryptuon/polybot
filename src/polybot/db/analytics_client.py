"""Analytics client for querying the analytics service via NNG.

This client provides a simple interface for API routes to query
analytics data without directly connecting to the database.
All queries are routed through the analytics service via IPC.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from polybot.config import get_settings
from polybot.core.nng import NNGRequester


logger = logging.getLogger(__name__)


class AnalyticsClient:
    """Client for querying the analytics service.

    Uses NNG REQ/REP pattern to send queries to the analytics service
    and receive responses. This avoids direct database access from
    the API and resolves DuckDB locking issues.
    """

    def __init__(self) -> None:
        """Initialize the client."""
        self._settings = get_settings()
        self._requester: Optional[NNGRequester] = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to the analytics service."""
        if self._connected:
            return

        self._requester = NNGRequester(self._settings.nng.analytics_address)
        await self._requester.open()
        self._connected = True
        logger.info("Analytics client connected")

    async def close(self) -> None:
        """Close the connection."""
        if self._requester:
            await self._requester.close()
            self._requester = None
            self._connected = False

    async def _query(self, query_type: str, params: Dict[str, Any]) -> Any:
        """Execute a query against the analytics service.

        Args:
            query_type: Type of query to execute
            params: Query parameters

        Returns:
            Query result

        Raises:
            RuntimeError: If not connected or query fails
        """
        if not self._connected or not self._requester:
            await self.connect()

        request = {
            "query_type": query_type,
            "params": params,
        }

        try:
            response = await self._requester.request(request)

            if not response.get("success"):
                error = response.get("error", "Unknown error")
                raise RuntimeError(f"Analytics query failed: {error}")

            return response.get("data")

        except Exception as e:
            logger.error(f"Analytics query error: {e}")
            raise

    async def get_performance_summary(
        self,
        strategy: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get performance summary.

        Args:
            strategy: Filter by strategy (None for all)
            days: Number of days to analyze

        Returns:
            Performance summary dict
        """
        return await self._query("performance_summary", {
            "strategy": strategy,
            "days": days,
        })

    async def get_daily_stats(
        self,
        strategy: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get daily statistics.

        Args:
            strategy: Filter by strategy (None for all)
            days: Number of days to retrieve

        Returns:
            List of daily stats
        """
        return await self._query("daily_stats", {
            "strategy": strategy,
            "days": days,
        })

    async def get_trade_stats(
        self,
        strategy: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get trade statistics.

        Args:
            strategy: Filter by strategy
            start_time: Start of period
            end_time: End of period

        Returns:
            Trade statistics
        """
        return await self._query("trade_stats", {
            "strategy": strategy,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
        })

    async def get_correlated_markets(
        self,
        market_id: str,
        min_correlation: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Get markets correlated with a given market.

        Args:
            market_id: Market to find correlations for
            min_correlation: Minimum correlation coefficient

        Returns:
            List of correlated markets
        """
        return await self._query("correlations", {
            "market_id": market_id,
            "min_correlation": min_correlation,
        })

    async def get_price_history(
        self,
        market_id: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get OHLCV price history.

        Args:
            market_id: Market ID
            interval: Candle interval
            limit: Number of candles

        Returns:
            List of OHLCV candles
        """
        return await self._query("price_history", {
            "market_id": market_id,
            "interval": interval,
            "limit": limit,
        })

    async def get_all_correlations(
        self,
        min_correlation: float = 0.5,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get all market correlations.

        Args:
            min_correlation: Minimum correlation coefficient
            limit: Maximum pairs to return

        Returns:
            List of correlation pairs
        """
        return await self._query("all_correlations", {
            "min_correlation": min_correlation,
            "limit": limit,
        })

    async def get_market_price_history(
        self,
        market_id: str,
        token_id: str,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get raw price history for a market.

        Args:
            market_id: Market ID
            token_id: Token ID
            hours: Hours of history

        Returns:
            List of price snapshots
        """
        return await self._query("market_price_history", {
            "market_id": market_id,
            "token_id": token_id,
            "hours": hours,
        })


# Module-level client instance for dependency injection
_client: Optional[AnalyticsClient] = None


async def get_analytics_client() -> AnalyticsClient:
    """Get or create the analytics client singleton.

    Returns:
        Connected analytics client
    """
    global _client
    if _client is None:
        _client = AnalyticsClient()
        await _client.connect()
    return _client
