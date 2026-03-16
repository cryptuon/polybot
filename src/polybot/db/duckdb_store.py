"""DuckDB store for analytics data.

Handles storage and querying of time-series data, trade statistics,
and performance analytics.

Implements the AnalyticsStore interface for database abstraction.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb

from polybot.config import get_settings
from polybot.db.analytics_store import AnalyticsStore
from polybot.models.market import MarketSnapshot
from polybot.models.trade import DailyStats, TradeStats


logger = logging.getLogger(__name__)

SCHEMA = """
-- Price history (time-series)
CREATE TABLE IF NOT EXISTS price_history (
    market_id VARCHAR,
    token_id VARCHAR,
    timestamp TIMESTAMP,
    bid DOUBLE,
    ask DOUBLE,
    mid DOUBLE,
    spread DOUBLE,
    volume DOUBLE
);

-- Trade history
CREATE TABLE IF NOT EXISTS trade_history (
    id VARCHAR,
    market_id VARCHAR,
    strategy VARCHAR,
    side VARCHAR,
    price DOUBLE,
    size DOUBLE,
    fee DOUBLE,
    notional DOUBLE,
    timestamp TIMESTAMP
);

-- Strategy performance stats
CREATE TABLE IF NOT EXISTS strategy_stats (
    strategy VARCHAR,
    date DATE,
    trades INTEGER,
    wins INTEGER,
    losses INTEGER,
    pnl DOUBLE,
    volume DOUBLE,
    fees DOUBLE
);

-- Market correlations (for statistical arbitrage)
CREATE TABLE IF NOT EXISTS market_correlations (
    market_a VARCHAR,
    market_b VARCHAR,
    correlation DOUBLE,
    lookback_hours INTEGER,
    calculated_at TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_price_history_market_time
    ON price_history(market_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_trade_history_strategy_time
    ON trade_history(strategy, timestamp);
CREATE INDEX IF NOT EXISTS idx_strategy_stats_strategy_date
    ON strategy_stats(strategy, date);
"""


class DuckDBStore(AnalyticsStore):
    """DuckDB implementation of the analytics store."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize the store.

        Args:
            db_path: Path to DuckDB database file
        """
        settings = get_settings()
        self._db_path = db_path or settings.database.duckdb_path
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self, read_only: bool = False) -> None:
        """Connect to database and initialize schema.

        Args:
            read_only: If True, open in read-only mode (no lock required)
        """
        # Ensure directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = duckdb.connect(str(self._db_path), read_only=read_only)

        # Initialize schema (only if not read-only)
        if not read_only:
            self._conn.execute(SCHEMA)

        logger.info(f"Connected to DuckDB database: {self._db_path} (read_only={read_only})")

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def checkpoint(self) -> None:
        """Force a checkpoint to flush WAL to main database.

        This allows read-only connections from other processes to see
        the latest data. Should be called periodically.
        """
        if self._conn:
            self._conn.execute("CHECKPOINT")
            logger.debug("DuckDB checkpoint completed")

    def __enter__(self) -> "DuckDBStore":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # =========================================================================
    # Price History
    # =========================================================================

    def insert_price_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Insert a price snapshot."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        self._conn.execute(
            """
            INSERT INTO price_history (
                market_id, token_id, timestamp,
                bid, ask, mid, spread, volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                snapshot.market_id,
                snapshot.token_id,
                snapshot.timestamp,
                snapshot.bid,
                snapshot.ask,
                snapshot.mid,
                snapshot.spread,
                snapshot.volume,
            ],
        )

    def insert_price_snapshots(self, snapshots: List[MarketSnapshot]) -> None:
        """Batch insert price snapshots."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        if not snapshots:
            return

        data = [
            (s.market_id, s.token_id, s.timestamp, s.bid, s.ask, s.mid, s.spread, s.volume)
            for s in snapshots
        ]

        self._conn.executemany(
            """
            INSERT INTO price_history (
                market_id, token_id, timestamp,
                bid, ask, mid, spread, volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )

    def get_price_history(
        self,
        market_id: str,
        token_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Get price history for a market.

        Args:
            market_id: Market condition ID
            token_id: Specific token ID (optional)
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of records

        Returns:
            List of price records
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = "SELECT * FROM price_history WHERE market_id = ?"
        params: List[Any] = [market_id]

        if token_id:
            query += " AND token_id = ?"
            params.append(token_id)

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        result = self._conn.execute(query, params).fetchall()
        columns = ["market_id", "token_id", "timestamp", "bid", "ask", "mid", "spread", "volume"]

        return [dict(zip(columns, row)) for row in result]

    def get_ohlcv(
        self,
        market_id: str,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get OHLCV candles for a market.

        Args:
            market_id: Market condition ID
            interval: Time interval ('1m', '5m', '15m', '1h', '4h', '1d')
            start_time: Start of time range
            limit: Maximum number of candles

        Returns:
            List of OHLCV candles
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        # Map interval to DuckDB interval
        interval_map = {
            "1m": "1 minute",
            "5m": "5 minutes",
            "15m": "15 minutes",
            "1h": "1 hour",
            "4h": "4 hours",
            "1d": "1 day",
        }
        db_interval = interval_map.get(interval, "1 hour")

        query = f"""
        SELECT
            time_bucket(INTERVAL '{db_interval}', timestamp) as time,
            FIRST(mid) as open,
            MAX(mid) as high,
            MIN(mid) as low,
            LAST(mid) as close,
            SUM(volume) as volume
        FROM price_history
        WHERE market_id = ?
        """
        params: List[Any] = [market_id]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        query += f" GROUP BY time ORDER BY time DESC LIMIT {limit}"

        result = self._conn.execute(query, params).fetchall()
        columns = ["time", "open", "high", "low", "close", "volume"]

        return [dict(zip(columns, row)) for row in result]

    # =========================================================================
    # Trade History
    # =========================================================================

    def insert_trade(
        self,
        trade_id: str,
        market_id: str,
        strategy: str,
        side: str,
        price: float,
        size: float,
        fee: float,
        notional: float,
        timestamp: datetime,
    ) -> None:
        """Insert a trade record."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        self._conn.execute(
            """
            INSERT INTO trade_history (
                id, market_id, strategy, side, price, size, fee, notional, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [trade_id, market_id, strategy, side, price, size, fee, notional, timestamp],
        )

    def get_trade_stats(
        self,
        strategy: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> TradeStats:
        """Get aggregated trade statistics.

        Args:
            strategy: Filter by strategy name
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Aggregated trade statistics
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = """
        SELECT
            COUNT(*) as total_trades,
            SUM(CASE WHEN side = 'BUY' THEN notional ELSE 0 END) as buy_volume,
            SUM(CASE WHEN side = 'SELL' THEN notional ELSE 0 END) as sell_volume,
            SUM(notional) as total_volume,
            SUM(fee) as total_fees
        FROM trade_history
        WHERE 1=1
        """
        params: List[Any] = []

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        result = self._conn.execute(query, params).fetchone()

        return TradeStats(
            strategy=strategy,
            period_start=start_time,
            period_end=end_time,
            total_trades=result[0] or 0,
            buy_volume=result[1] or 0,
            sell_volume=result[2] or 0,
            total_volume=result[3] or 0,
            total_fees=result[4] or 0,
        )

    # =========================================================================
    # Strategy Stats
    # =========================================================================

    def update_daily_stats(
        self,
        strategy: str,
        date: datetime,
        trades: int,
        wins: int,
        losses: int,
        pnl: float,
        volume: float,
        fees: float,
    ) -> None:
        """Update or insert daily strategy stats."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        # Delete existing record for this day
        self._conn.execute(
            "DELETE FROM strategy_stats WHERE strategy = ? AND date = ?",
            [strategy, date.date()],
        )

        # Insert new record
        self._conn.execute(
            """
            INSERT INTO strategy_stats (strategy, date, trades, wins, losses, pnl, volume, fees)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [strategy, date.date(), trades, wins, losses, pnl, volume, fees],
        )

    def get_daily_stats(
        self,
        strategy: Optional[str] = None,
        days: int = 30,
    ) -> List[DailyStats]:
        """Get daily statistics.

        Args:
            strategy: Filter by strategy name
            days: Number of days to retrieve

        Returns:
            List of daily stats
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = """
        SELECT strategy, date, trades, wins, losses, pnl, volume, fees
        FROM strategy_stats
        WHERE date >= ?
        """
        params: List[Any] = [datetime.utcnow().date() - timedelta(days=days)]

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        query += " ORDER BY date DESC"

        result = self._conn.execute(query, params).fetchall()

        return [
            DailyStats(
                date=row[1],
                strategy=row[0],
                trades=row[2],
                wins=row[3],
                losses=row[4],
                pnl=row[5],
                volume=row[6],
                fees=row[7],
            )
            for row in result
        ]

    # =========================================================================
    # Market Correlations
    # =========================================================================

    def update_correlation(
        self,
        market_a: str,
        market_b: str,
        correlation: float,
        lookback_hours: int,
    ) -> None:
        """Update or insert market correlation."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        # Delete existing
        self._conn.execute(
            """
            DELETE FROM market_correlations
            WHERE (market_a = ? AND market_b = ?) OR (market_a = ? AND market_b = ?)
            """,
            [market_a, market_b, market_b, market_a],
        )

        # Insert new
        self._conn.execute(
            """
            INSERT INTO market_correlations (market_a, market_b, correlation, lookback_hours, calculated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [market_a, market_b, correlation, lookback_hours, datetime.utcnow()],
        )

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
        if not self._conn:
            raise RuntimeError("Database not connected")

        result = self._conn.execute(
            """
            SELECT
                CASE WHEN market_a = ? THEN market_b ELSE market_a END as other_market,
                correlation,
                calculated_at
            FROM market_correlations
            WHERE (market_a = ? OR market_b = ?) AND ABS(correlation) >= ?
            ORDER BY ABS(correlation) DESC
            """,
            [market_id, market_id, market_id, min_correlation],
        ).fetchall()

        return [
            {"market_id": row[0], "correlation": row[1], "calculated_at": row[2]}
            for row in result
        ]

    # =========================================================================
    # Performance Analytics
    # =========================================================================

    def get_performance_summary(
        self,
        strategy: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get performance summary.

        Args:
            strategy: Filter by strategy name
            days: Number of days to analyze

        Returns:
            Performance summary dict
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = """
        SELECT
            SUM(trades) as total_trades,
            SUM(wins) as total_wins,
            SUM(losses) as total_losses,
            SUM(pnl) as total_pnl,
            SUM(volume) as total_volume,
            SUM(fees) as total_fees,
            AVG(pnl) as avg_daily_pnl,
            MAX(pnl) as best_day,
            MIN(pnl) as worst_day
        FROM strategy_stats
        WHERE date >= ?
        """
        params: List[Any] = [datetime.utcnow().date() - timedelta(days=days)]

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        result = self._conn.execute(query, params).fetchone()

        total_trades = result[0] or 0
        total_wins = result[1] or 0

        return {
            "total_trades": total_trades,
            "total_wins": total_wins,
            "total_losses": result[2] or 0,
            "win_rate": total_wins / total_trades if total_trades > 0 else 0,
            "total_pnl": result[3] or 0,
            "total_volume": result[4] or 0,
            "total_fees": result[5] or 0,
            "avg_daily_pnl": result[6] or 0,
            "best_day": result[7] or 0,
            "worst_day": result[8] or 0,
        }


# Global store instance
_store: Optional[DuckDBStore] = None


def get_duckdb_store() -> DuckDBStore:
    """Get the global DuckDB store instance."""
    global _store
    if _store is None:
        _store = DuckDBStore()
        _store.connect()
    return _store
