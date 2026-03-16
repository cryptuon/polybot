"""Analytics service.

Responsible for:
- Tracking performance metrics
- Computing market correlations (for stat arb)
- Generating reports
- Answering analytics queries
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from polybot.config import Settings
from polybot.core.nng import NNGReplier, NNGSubscriber
from polybot.db.duckdb_store import DuckDBStore, get_duckdb_store
from polybot.db.state_client import StateClient, get_state_client
from polybot.models.market import MarketSnapshot
from polybot.models.trade import DailyStats, TradeStats
from polybot.services.base import BaseService


logger = logging.getLogger(__name__)


class AnalyticsService(BaseService):
    """Analytics and reporting service."""

    name = "analytics"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._replier: Optional[NNGReplier] = None
        self._executor_subscriber: Optional[NNGSubscriber] = None
        self._scanner_subscriber: Optional[NNGSubscriber] = None

        self._state_client: Optional[StateClient] = None
        self._duckdb: Optional[DuckDBStore] = None

        # Cached metrics
        self._daily_stats: Dict[str, DailyStats] = {}
        self._correlation_cache: Dict[str, float] = {}

    async def _on_start(self) -> None:
        """Initialize analytics resources."""
        # Initialize state client (queries state service via NNG)
        self._state_client = await get_state_client()
        self._duckdb = get_duckdb_store()

        # Initialize NNG sockets
        self._replier = NNGReplier(self._settings.nng.analytics_address)
        await self._replier.open()

        # Subscribe to executor events for order fills and position updates
        self._executor_subscriber = NNGSubscriber(
            self._settings.nng.service_events_address("executor")
        )
        await self._executor_subscriber.open()

        # Subscribe to scanner events for price snapshots
        self._scanner_subscriber = NNGSubscriber(
            self._settings.nng.service_events_address("scanner")
        )
        await self._scanner_subscriber.open()

        # Initial checkpoint to flush any pending WAL (allows API read-only access)
        if self._duckdb:
            try:
                self._duckdb.checkpoint()
                self._logger.info("Initial checkpoint completed")
            except Exception as e:
                self._logger.warning(f"Initial checkpoint failed: {e}")

        # Compute initial correlations if we have price history
        self._logger.info("Computing initial correlations...")
        try:
            await self._compute_correlations()
        except Exception as e:
            self._logger.warning(f"Initial correlation computation failed: {e}")

    async def _on_stop(self) -> None:
        """Cleanup analytics resources."""
        # Persist any pending stats
        try:
            await self._persist_stats()
        except Exception as e:
            self._logger.error(f"Failed to persist stats on shutdown: {e}")

        # Checkpoint to flush WAL
        if self._duckdb:
            try:
                self._duckdb.checkpoint()
                self._logger.info("Final checkpoint completed")
            except Exception as e:
                self._logger.error(f"Checkpoint on shutdown failed: {e}")

        if self._replier:
            await self._replier.close()

        if self._executor_subscriber:
            await self._executor_subscriber.close()

        if self._scanner_subscriber:
            await self._scanner_subscriber.close()

    async def _run(self) -> None:
        """Main analytics loop."""
        # Start request handler
        request_task = self.create_task(self._handle_requests())

        # Start event listeners
        executor_event_task = self.create_task(self._listen_executor_events())
        scanner_event_task = self.create_task(self._listen_scanner_events())

        # Start correlation computation
        correlation_task = self.create_task(self._compute_correlations_loop())

        # Start daily stats aggregation
        stats_task = self.create_task(self._aggregate_stats_loop())

        # Start checkpoint loop (allows API read-only access)
        checkpoint_task = self.create_task(self._checkpoint_loop())

        await asyncio.gather(
            request_task, executor_event_task, scanner_event_task,
            correlation_task, stats_task, checkpoint_task,
            return_exceptions=True,
        )

    async def _handle_requests(self) -> None:
        """Handle analytics queries via REQ/REP."""
        if not self._replier:
            return

        async for msg in self._replier.requests():
            if not self._running:
                break

            try:
                query_type = msg.get("query_type", "")
                params = msg.get("params", {})

                result = await self._execute_query(query_type, params)
                await self._replier.reply({"success": True, "data": result})

            except Exception as e:
                self._logger.error(f"Query error: {e}")
                await self._replier.reply({"success": False, "error": str(e)})

    async def _execute_query(
        self,
        query_type: str,
        params: Dict[str, Any],
    ) -> Any:
        """Execute an analytics query.

        Args:
            query_type: Type of query
            params: Query parameters

        Returns:
            Query result
        """
        if query_type == "performance_summary":
            return await self.get_performance_summary(
                strategy=params.get("strategy"),
                days=params.get("days", 30),
            )

        elif query_type == "daily_stats":
            return await self.get_daily_stats(
                strategy=params.get("strategy"),
                days=params.get("days", 30),
            )

        elif query_type == "trade_stats":
            return await self.get_trade_stats(
                strategy=params.get("strategy"),
                start_time=params.get("start_time"),
                end_time=params.get("end_time"),
            )

        elif query_type == "correlations":
            return await self.get_correlated_markets(
                market_id=params.get("market_id", ""),
                min_correlation=params.get("min_correlation", 0.7),
            )

        elif query_type == "price_history":
            return await self.get_price_history(
                market_id=params.get("market_id", ""),
                interval=params.get("interval", "1h"),
                limit=params.get("limit", 100),
            )

        elif query_type == "all_correlations":
            return await self.get_all_correlations(
                min_correlation=params.get("min_correlation", 0.5),
                limit=params.get("limit", 50),
            )

        elif query_type == "market_price_history":
            return await self.get_market_price_history(
                market_id=params.get("market_id", ""),
                token_id=params.get("token_id", ""),
                hours=params.get("hours", 24),
            )

        else:
            raise ValueError(f"Unknown query type: {query_type}")

    async def _listen_executor_events(self) -> None:
        """Listen for executor events (order fills, position closes)."""
        if not self._executor_subscriber:
            return

        async for msg in self._executor_subscriber.messages():
            if not self._running:
                break

            try:
                event_type = msg.get("event_type", "")

                if event_type == "order_filled":
                    await self._handle_order_filled(msg.get("data", {}))
                elif event_type == "position_closed":
                    await self._handle_position_closed(msg.get("data", {}))

            except Exception as e:
                self._logger.error(f"Executor event handling error: {e}")

    async def _listen_scanner_events(self) -> None:
        """Listen for scanner events (price snapshots)."""
        if not self._scanner_subscriber:
            return

        async for msg in self._scanner_subscriber.messages():
            if not self._running:
                break

            try:
                event_type = msg.get("event_type", "")

                if event_type == "price_snapshots":
                    await self._handle_price_snapshots(msg.get("data", {}))

            except Exception as e:
                self._logger.error(f"Scanner event handling error: {e}")

    async def _handle_price_snapshots(self, data: Dict[str, Any]) -> None:
        """Store price snapshots from scanner."""
        if not self._duckdb:
            return

        snapshots_data = data.get("snapshots", [])
        if not snapshots_data:
            return

        snapshots = []
        for s in snapshots_data:
            try:
                snapshots.append(MarketSnapshot(
                    market_id=s["market_id"],
                    token_id=s["token_id"],
                    timestamp=datetime.fromisoformat(s["timestamp"]),
                    bid=s["bid"],
                    ask=s["ask"],
                    mid=s["mid"],
                    spread=s["spread"],
                ))
            except (KeyError, ValueError) as e:
                self._logger.warning(f"Invalid snapshot data: {e}")

        if snapshots:
            self._duckdb.insert_price_snapshots(snapshots)

    async def _handle_order_filled(self, data: Dict[str, Any]) -> None:
        """Update metrics on order fill."""
        strategy = data.get("strategy", "unknown")
        today = datetime.utcnow().date()
        key = f"{strategy}:{today}"

        if key not in self._daily_stats:
            self._daily_stats[key] = DailyStats(
                date=datetime.combine(today, datetime.min.time()),
                strategy=strategy,
            )

        stats = self._daily_stats[key]
        stats.trades += 1
        stats.volume += data.get("notional", 0)
        stats.fees += data.get("fee", 0)

    async def _handle_position_closed(self, data: Dict[str, Any]) -> None:
        """Update metrics on position close."""
        strategy = data.get("strategy", "unknown")
        pnl = data.get("pnl", 0)
        today = datetime.utcnow().date()
        key = f"{strategy}:{today}"

        if key not in self._daily_stats:
            self._daily_stats[key] = DailyStats(
                date=datetime.combine(today, datetime.min.time()),
                strategy=strategy,
            )

        stats = self._daily_stats[key]
        stats.pnl += pnl

        if pnl > 0:
            stats.wins += 1
        else:
            stats.losses += 1

    async def _compute_correlations_loop(self) -> None:
        """Periodically compute market correlations."""
        interval = 3600  # 1 hour

        while self._running:
            try:
                await asyncio.sleep(interval)
                await self._compute_correlations()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Correlation computation error: {e}")

    async def _compute_correlations(self) -> None:
        """Compute correlations between markets using price returns.

        Uses percentage price changes (returns) rather than raw prices
        to avoid spurious correlations from trending markets.
        """
        if not self._duckdb or not self._state_client:
            return

        self._logger.info("Computing market correlations...")

        # Get active markets from state service
        markets = await self._state_client.get_active_markets(limit=100)

        if len(markets) < 2:
            self._logger.info("Not enough markets for correlation analysis")
            return

        # Get price history for each market
        lookback = datetime.utcnow() - timedelta(hours=48)  # 48 hours for better sample
        price_data: Dict[str, List[float]] = {}
        timestamps: Dict[str, List[datetime]] = {}

        for market in markets:
            history = self._duckdb.get_price_history(
                market_id=market.id,
                token_id=market.outcome_yes_token,
                start_time=lookback,
                limit=2000,
            )

            if history and len(history) >= 20:  # Need minimum data points
                # Sort by timestamp (oldest first for returns calculation)
                history = sorted(history, key=lambda x: x["timestamp"])
                price_data[market.id] = [h["mid"] for h in history]
                timestamps[market.id] = [h["timestamp"] for h in history]

        self._logger.info(f"Got price data for {len(price_data)} markets")

        # Convert prices to returns (percentage changes)
        returns_data: Dict[str, List[float]] = {}
        for market_id, prices in price_data.items():
            if len(prices) >= 2:
                returns = []
                for i in range(1, len(prices)):
                    if prices[i - 1] > 0:  # Avoid division by zero
                        ret = (prices[i] - prices[i - 1]) / prices[i - 1]
                        returns.append(ret)
                if len(returns) >= 10:
                    returns_data[market_id] = returns

        self._logger.info(f"Computed returns for {len(returns_data)} markets")

        # Compute correlations on returns
        market_ids = list(returns_data.keys())
        correlations_found = 0

        for i, market_a in enumerate(market_ids):
            for market_b in market_ids[i + 1:]:
                returns_a = returns_data[market_a]
                returns_b = returns_data[market_b]

                # Align lengths (use most recent data)
                min_len = min(len(returns_a), len(returns_b))
                if min_len < 10:
                    continue

                # Take the last min_len returns (most recent)
                aligned_a = returns_a[-min_len:]
                aligned_b = returns_b[-min_len:]

                # Compute Pearson correlation on returns
                try:
                    # Check for zero variance (constant returns)
                    std_a = np.std(aligned_a)
                    std_b = np.std(aligned_b)

                    if std_a < 1e-10 or std_b < 1e-10:
                        continue  # Skip if no price movement

                    corr = np.corrcoef(aligned_a, aligned_b)[0, 1]

                    if not np.isnan(corr) and abs(corr) >= 0.5:  # Store if significant
                        self._duckdb.update_correlation(
                            market_a=market_a,
                            market_b=market_b,
                            correlation=float(corr),
                            lookback_hours=48,
                        )
                        self._correlation_cache[f"{market_a}:{market_b}"] = float(corr)
                        correlations_found += 1

                        if abs(corr) >= 0.7:
                            self._logger.debug(
                                f"High correlation: {market_a[:8]}... <-> {market_b[:8]}... = {corr:.3f}"
                            )
                except Exception as e:
                    self._logger.debug(f"Correlation calc error: {e}")

        self._logger.info(
            f"Computed {correlations_found} significant correlations "
            f"(>= 0.5) from {len(market_ids)} markets"
        )

    async def _aggregate_stats_loop(self) -> None:
        """Periodically persist daily stats."""
        interval = 300  # 5 minutes

        while self._running:
            try:
                await asyncio.sleep(interval)
                await self._persist_stats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Stats aggregation error: {e}")

    async def _persist_stats(self) -> None:
        """Persist cached stats to database."""
        if not self._duckdb:
            return

        for key, stats in self._daily_stats.items():
            self._duckdb.update_daily_stats(
                strategy=stats.strategy or "unknown",
                date=stats.date,
                trades=stats.trades,
                wins=stats.wins,
                losses=stats.losses,
                pnl=stats.pnl,
                volume=stats.volume,
                fees=stats.fees,
            )

    async def _checkpoint_loop(self) -> None:
        """Periodically checkpoint DuckDB to allow read-only access from API."""
        interval = 30  # Every 30 seconds

        while self._running:
            try:
                await asyncio.sleep(interval)
                if self._duckdb:
                    self._duckdb.checkpoint()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Checkpoint error: {e}")

    # =========================================================================
    # Public API
    # =========================================================================

    async def get_performance_summary(
        self,
        strategy: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get performance summary.

        Args:
            strategy: Filter by strategy
            days: Number of days

        Returns:
            Performance summary dict
        """
        if not self._duckdb:
            return {}

        return self._duckdb.get_performance_summary(strategy=strategy, days=days)

    async def get_daily_stats(
        self,
        strategy: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get daily statistics.

        Args:
            strategy: Filter by strategy
            days: Number of days

        Returns:
            List of daily stats
        """
        if not self._duckdb:
            return []

        stats = self._duckdb.get_daily_stats(strategy=strategy, days=days)
        # Use mode='json' to ensure datetime is serialized as string for msgpack
        return [s.model_dump(mode='json') for s in stats]

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
            Trade stats dict
        """
        if not self._duckdb:
            return {}

        stats = self._duckdb.get_trade_stats(
            strategy=strategy,
            start_time=start_time,
            end_time=end_time,
        )
        # Use mode='json' to ensure datetime is serialized as string for msgpack
        return stats.model_dump(mode='json')

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
        if not self._duckdb:
            return []

        return self._duckdb.get_correlated_markets(
            market_id=market_id,
            min_correlation=min_correlation,
        )

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
        if not self._duckdb:
            return []

        return self._duckdb.get_ohlcv(
            market_id=market_id,
            interval=interval,
            limit=limit,
        )

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
        if not self._duckdb or not self._duckdb._conn:
            return []

        result = self._duckdb._conn.execute(
            """
            SELECT market_a, market_b, correlation, lookback_hours, calculated_at
            FROM market_correlations
            WHERE ABS(correlation) >= ?
            ORDER BY ABS(correlation) DESC
            LIMIT ?
            """,
            [min_correlation, limit],
        ).fetchall()

        correlations = []
        for row in result:
            correlations.append({
                "market_a": row[0],
                "market_b": row[1],
                "correlation": row[2],
                "lookback_hours": row[3],
                "calculated_at": row[4].isoformat() if row[4] else None,
            })

        return correlations

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
        if not self._duckdb:
            return []

        start_time = datetime.utcnow() - timedelta(hours=hours)
        return self._duckdb.get_price_history(
            market_id=market_id,
            token_id=token_id,
            start_time=start_time,
            limit=1000,
        )
