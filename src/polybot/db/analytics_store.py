"""Abstract analytics store interface.

This module defines the interface for analytics data storage,
allowing different backends (DuckDB, ClickHouse, etc.) to be
used interchangeably.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from polybot.models.market import MarketSnapshot
from polybot.models.trade import DailyStats, TradeStats


class AnalyticsStore(ABC):
    """Abstract base class for analytics data storage.

    Implementations can use DuckDB, ClickHouse, TimescaleDB, or
    other time-series databases.
    """

    @abstractmethod
    def connect(self, read_only: bool = False) -> None:
        """Connect to the database.

        Args:
            read_only: If True, open in read-only mode
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""
        pass

    @abstractmethod
    def checkpoint(self) -> None:
        """Flush any pending writes (if applicable)."""
        pass

    # =========================================================================
    # Price History
    # =========================================================================

    @abstractmethod
    def insert_price_snapshots(self, snapshots: List[MarketSnapshot]) -> None:
        """Insert price snapshots.

        Args:
            snapshots: List of market snapshots to insert
        """
        pass

    @abstractmethod
    def get_price_history(
        self,
        market_id: str,
        token_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Get price history for a market.

        Args:
            market_id: Market ID
            token_id: Token ID
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum records to return

        Returns:
            List of price records
        """
        pass

    @abstractmethod
    def get_ohlcv(
        self,
        market_id: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get OHLCV candles for a market.

        Args:
            market_id: Market ID
            interval: Candle interval (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Maximum candles to return

        Returns:
            List of OHLCV candles
        """
        pass

    # =========================================================================
    # Correlations
    # =========================================================================

    @abstractmethod
    def update_correlation(
        self,
        market_a: str,
        market_b: str,
        correlation: float,
        lookback_hours: int = 24,
    ) -> None:
        """Update correlation between two markets.

        Args:
            market_a: First market ID
            market_b: Second market ID
            correlation: Correlation coefficient
            lookback_hours: Hours of data used
        """
        pass

    @abstractmethod
    def get_correlated_markets(
        self,
        market_id: str,
        min_correlation: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Get markets correlated with a given market.

        Args:
            market_id: Market to find correlations for
            min_correlation: Minimum correlation coefficient

        Returns:
            List of correlated markets with correlation values
        """
        pass

    # =========================================================================
    # Strategy Stats
    # =========================================================================

    @abstractmethod
    def update_daily_stats(
        self,
        strategy: str,
        date: datetime,
        trades: int = 0,
        wins: int = 0,
        losses: int = 0,
        pnl: float = 0,
        volume: float = 0,
        fees: float = 0,
    ) -> None:
        """Update daily statistics for a strategy.

        Args:
            strategy: Strategy name
            date: Date for the stats
            trades: Number of trades
            wins: Number of winning trades
            losses: Number of losing trades
            pnl: Profit/loss
            volume: Trading volume
            fees: Fees paid
        """
        pass

    @abstractmethod
    def get_daily_stats(
        self,
        strategy: Optional[str] = None,
        days: int = 30,
    ) -> List[DailyStats]:
        """Get daily statistics.

        Args:
            strategy: Filter by strategy (None for all)
            days: Number of days to retrieve

        Returns:
            List of daily stats
        """
        pass

    @abstractmethod
    def get_performance_summary(
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
        pass

    @abstractmethod
    def get_trade_stats(
        self,
        strategy: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> TradeStats:
        """Get trade statistics.

        Args:
            strategy: Filter by strategy
            start_time: Start of period
            end_time: End of period

        Returns:
            Trade statistics
        """
        pass
