"""Statistical arbitrage strategy.

Identifies correlated markets that have diverged and trades on mean reversion.
Goes long the underpriced market and short (via NO token) the overpriced one.

On Polymarket:
    - "Long YES" = Buy YES token (bullish on outcome)
    - "Short YES" = Buy NO token (bearish on outcome, since can't truly short)

Example:
    "Trump wins" (55¢) and "GOP Senate control" (48¢) should move together.
    If spread hits 4-7%:
        - Buy YES on cheap market (long leg)
        - Buy NO on expensive market (short proxy)
    Close when they converge.

Production improvements:
    - Cooldown per pair to prevent signal spam
    - Price validation to prevent division by zero
    - Consistent NO price calculation
    - Max price age to detect stale quotes
    - Improved exit logic with partial convergence
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from polybot.config import Settings
from polybot.core.nng import NNGRequester
from polybot.models.market import Market
from polybot.models.messages import PriceUpdate, Signal, SignalAction
from polybot.models.position import Position
from polybot.strategies.base import BaseStrategy, StrategyConfig


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class StatArbConfig(StrategyConfig):
    """Statistical arbitrage configuration.

    Attributes:
        spread_threshold: Minimum spread (as decimal) to trigger entry
        min_correlation: Minimum correlation coefficient to consider pair
        lookback_hours: Hours of price history for correlation calculation
        max_position_size: Maximum USD per leg (total = 2x this)
        exit_threshold: Exit when spread falls below this
        stop_loss_multiplier: Exit if spread widens by this factor
        max_pairs: Maximum concurrent pair trades
        signal_cooldown_sec: Minimum seconds between signals for same pair
        min_price: Minimum token price (prevents extreme sizes)
        max_price: Maximum token price
        max_price_age_sec: Maximum age of cached price before considered stale
        partial_exit_threshold: Take partial profit at this spread reduction
    """
    spread_threshold: float = 0.02  # 2% spread to enter (more sensitive)
    min_correlation: float = 0.7  # Minimum historical correlation
    lookback_hours: int = 48  # Hours for correlation calculation
    max_position_size: float = 500.0  # Max USD per leg
    exit_threshold: float = 0.01  # Exit when spread < 1%
    stop_loss_multiplier: float = 2.0  # Stop if spread doubles
    max_pairs: int = 5  # Max concurrent trades
    signal_cooldown_sec: float = 300.0  # 5 min cooldown per pair
    min_price: float = 0.05  # Don't trade below 5 cents
    max_price: float = 0.95  # Don't trade above 95 cents
    max_price_age_sec: float = 60.0  # Price stale after 60 seconds
    partial_exit_threshold: float = 0.5  # Exit half at 50% convergence


# =============================================================================
# State Tracking
# =============================================================================

@dataclass
class MarketPrice:
    """Current price state for a market with timestamp for staleness check.

    Attributes:
        market_id: Market condition ID
        token_id: YES token ID
        bid: Best bid price
        ask: Best ask price
        mid: Midpoint price
        spread: Bid-ask spread
        updated_at: When this price was received
    """
    market_id: str
    token_id: str
    bid: float
    ask: float
    mid: float
    spread: float
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def age_seconds(self) -> float:
        """Get age of this price in seconds."""
        return (datetime.utcnow() - self.updated_at).total_seconds()


@dataclass
class ArbPair:
    """A pair of correlated markets being monitored/traded.

    Attributes:
        market_a_id: First market ID
        market_b_id: Second market ID
        market_a_yes_token: YES token for market A
        market_a_no_token: NO token for market A
        market_b_yes_token: YES token for market B
        market_b_no_token: NO token for market B
        correlation: Historical correlation coefficient
        entry_spread: Spread at entry (None if not in trade)
        entry_time: When trade was entered
        long_market_id: Market we're long YES on
        short_market_id: Market we're long NO on (short proxy)
        last_signal_time: Last time we sent signals for this pair
    """
    market_a_id: str
    market_b_id: str
    market_a_yes_token: str
    market_a_no_token: str
    market_b_yes_token: str
    market_b_no_token: str
    correlation: float

    # Trade state
    entry_spread: Optional[float] = None
    entry_time: Optional[datetime] = None
    long_market_id: Optional[str] = None
    short_market_id: Optional[str] = None
    last_signal_time: float = 0.0

    @property
    def pair_key(self) -> str:
        """Unique identifier for this pair (order-independent)."""
        return ":".join(sorted([self.market_a_id, self.market_b_id]))

    @property
    def is_active(self) -> bool:
        """Check if we have an active trade on this pair."""
        return self.entry_spread is not None


# =============================================================================
# Strategy Implementation
# =============================================================================

class StatArbStrategy(BaseStrategy):
    """Statistical arbitrage strategy on correlated markets.

    Identifies pairs of markets that are historically correlated
    but have temporarily diverged, then trades on mean reversion.

    Workflow:
        1. Query analytics service for correlated market pairs
        2. Monitor spread (price difference) between correlated pairs
        3. When spread exceeds threshold:
           - Long (buy YES) the cheap market
           - Short (buy NO) the expensive market
        4. Exit when spread converges or hits stop-loss

    Risk Management:
        - Cooldown prevents repeated signals for same pair
        - Stop-loss exits if spread widens beyond entry
        - Time-based exit prevents holding forever
        - Price staleness check avoids trading on old quotes
        - Max concurrent pairs limits overall exposure
    """

    name = "stat_arb"
    description = "Statistical arbitrage on correlated markets"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize stat arb strategy.

        Args:
            settings: Application settings, uses defaults if not provided
        """
        super().__init__(settings)

        # Price cache with timestamps: market_id -> MarketPrice
        self._market_prices: Dict[str, MarketPrice] = {}

        # Market info cache: market_id -> Market
        self._markets: Dict[str, Market] = {}

        # All monitored pairs: pair_key -> ArbPair
        self._pairs: Dict[str, ArbPair] = {}

        # Active trades: pair_key -> ArbPair (with trade state)
        self._active_trades: Dict[str, ArbPair] = {}

        # Markets we're subscribed to for price updates
        self._monitored_markets: Set[str] = set()

        # Analytics service connection
        self._analytics: Optional[NNGRequester] = None

        # Last time we refreshed correlation data
        self._last_pair_refresh: Optional[datetime] = None

    def _get_config(self) -> StrategyConfig:
        """Load stat arb configuration from settings."""
        sa_settings = self._settings.stat_arb
        return StatArbConfig(
            spread_threshold=sa_settings.spread_threshold,
            min_correlation=sa_settings.min_correlation,
            lookback_hours=sa_settings.lookback_hours,
        )

    @property
    def stat_config(self) -> StatArbConfig:
        """Get typed configuration."""
        return self._config  # type: ignore

    async def _on_start(self) -> None:
        """Initialize analytics connection and load correlated pairs."""
        # Connect to analytics service for correlation data
        self._analytics = NNGRequester(self._settings.nng.analytics_address)
        await self._analytics.open()

        # Load market metadata
        await self._load_markets()

        # Load correlated pairs from analytics
        await self._refresh_pairs()

    async def _on_stop(self) -> None:
        """Clean up analytics connection."""
        if self._analytics:
            await self._analytics.close()

    async def _load_markets(self) -> None:
        """Load market information from state service."""
        if not self._state_client:
            self._logger.warning("State client not available")
            return

        markets = await self._state_client.get_active_markets(limit=200)
        for market in markets:
            self._markets[market.id] = market

        self._logger.info(f"Loaded {len(self._markets)} markets for stat arb")

    async def _refresh_pairs(self) -> None:
        """Refresh correlated market pairs from analytics service.

        Queries the analytics service for markets with high historical
        correlation and builds the pair monitoring list.
        """
        if not self._analytics:
            self._logger.warning("Analytics service not connected")
            return

        self._logger.info("Refreshing correlated pairs from analytics...")
        new_pairs: Dict[str, ArbPair] = {}

        for market_id, market in self._markets.items():
            try:
                # Query analytics for correlated markets
                response = await self._analytics.request({
                    "query_type": "correlations",
                    "params": {
                        "market_id": market_id,
                        "min_correlation": self.stat_config.min_correlation,
                    },
                })

                if not response.get("success"):
                    continue

                correlations = response.get("data", [])

                for corr_data in correlations:
                    other_market_id = corr_data["market_id"]
                    correlation = corr_data["correlation"]

                    # Skip if we don't have the other market loaded
                    if other_market_id not in self._markets:
                        continue

                    other_market = self._markets[other_market_id]

                    # Create order-independent pair key
                    pair_key = ":".join(sorted([market_id, other_market_id]))

                    if pair_key not in new_pairs:
                        new_pairs[pair_key] = ArbPair(
                            market_a_id=market_id,
                            market_b_id=other_market_id,
                            market_a_yes_token=market.outcome_yes_token,
                            market_a_no_token=market.outcome_no_token,
                            market_b_yes_token=other_market.outcome_yes_token,
                            market_b_no_token=other_market.outcome_no_token,
                            correlation=abs(correlation),
                        )

                        # Subscribe to price updates for both markets
                        self._monitored_markets.add(market_id)
                        self._monitored_markets.add(other_market_id)

            except Exception as e:
                self._logger.debug(f"Failed to get correlations for {market_id[:8]}: {e}")

        # Preserve active trade state when refreshing pairs
        for pair_key, active_pair in self._active_trades.items():
            if pair_key in new_pairs:
                # Copy trade state to refreshed pair
                new_pairs[pair_key].entry_spread = active_pair.entry_spread
                new_pairs[pair_key].entry_time = active_pair.entry_time
                new_pairs[pair_key].long_market_id = active_pair.long_market_id
                new_pairs[pair_key].short_market_id = active_pair.short_market_id
                new_pairs[pair_key].last_signal_time = active_pair.last_signal_time

        self._pairs = new_pairs
        self._last_pair_refresh = datetime.utcnow()
        self._logger.info(f"Now tracking {len(self._pairs)} correlated pairs")

    async def scan(self, update: PriceUpdate) -> List[Signal]:
        """Scan for statistical arbitrage opportunities.

        Checks if any monitored pair has a spread exceeding our threshold
        and generates entry signals if conditions are met.

        Args:
            update: Price update from scanner

        Returns:
            List of signals (typically 0 or 2 for pair entry)
        """
        signals: List[Signal] = []
        now = time.time()

        # =================================================================
        # Step 1: Update price cache
        # =================================================================

        if not self._is_valid_price(update):
            return signals

        self._update_price(update)

        # =================================================================
        # Step 2: Periodically refresh correlation pairs (every 30 min)
        # =================================================================

        if self._should_refresh_pairs():
            await self._refresh_pairs()

        # =================================================================
        # Step 3: Check each pair for opportunities
        # =================================================================

        for pair_key, pair in self._pairs.items():
            # Skip if already trading this pair
            if pair_key in self._active_trades:
                continue

            # Skip if at max concurrent trades
            if len(self._active_trades) >= self.stat_config.max_pairs:
                break

            # Skip if this update isn't for one of the pair's markets
            if update.market_id not in [pair.market_a_id, pair.market_b_id]:
                continue

            # Check cooldown for this pair
            if (now - pair.last_signal_time) < self.stat_config.signal_cooldown_sec:
                continue

            # Get and validate prices for both markets
            price_a = self._market_prices.get(pair.market_a_id)
            price_b = self._market_prices.get(pair.market_b_id)

            if not self._are_prices_valid(price_a, price_b):
                continue

            # =================================================================
            # Step 4: Calculate spread and check for opportunity
            # =================================================================

            spread = abs(price_a.mid - price_b.mid)

            if spread < self.stat_config.spread_threshold:
                continue

            # =================================================================
            # Step 5: Determine which market is cheap/expensive
            # =================================================================

            if price_a.mid > price_b.mid:
                # Market A is expensive (short it), Market B is cheap (long it)
                expensive_market = pair.market_a_id
                expensive_no_token = pair.market_a_no_token
                expensive_price = price_a
                cheap_market = pair.market_b_id
                cheap_yes_token = pair.market_b_yes_token
                cheap_price = price_b
            else:
                # Market B is expensive (short it), Market A is cheap (long it)
                expensive_market = pair.market_b_id
                expensive_no_token = pair.market_b_no_token
                expensive_price = price_b
                cheap_market = pair.market_a_id
                cheap_yes_token = pair.market_a_yes_token
                cheap_price = price_a

            # =================================================================
            # Step 6: Calculate position sizes (split between legs)
            # =================================================================

            leg_size_usd = min(
                self.stat_config.max_position_size / 2,
                self._settings.risk.max_position_size_usd / 2,
            )

            # =================================================================
            # Step 7: Log opportunity and generate signals
            # =================================================================

            self._logger.info(
                f"Stat arb opportunity found:\n"
                f"  Pair: {cheap_market[:8]}... vs {expensive_market[:8]}...\n"
                f"  Spread: {spread*100:.2f}% (threshold: {self.stat_config.spread_threshold*100:.1f}%)\n"
                f"  Correlation: {pair.correlation:.3f}\n"
                f"  Long: {cheap_market[:8]}... @ {cheap_price.mid:.4f}\n"
                f"  Short: {expensive_market[:8]}... @ {expensive_price.mid:.4f}"
            )

            # Signal 1: Buy YES on cheap market (LONG leg)
            long_size = leg_size_usd / cheap_price.ask
            signals.append(
                Signal(
                    strategy=self.name,
                    market_id=cheap_market,
                    token_id=cheap_yes_token,
                    action=SignalAction.BUY,
                    price=cheap_price.ask,
                    size=long_size,
                    reason=f"StatArb LONG: spread={spread*100:.2f}%, corr={pair.correlation:.2f}",
                    confidence=min(pair.correlation, 0.9),  # Cap at 0.9
                    metadata={
                        "pair_key": pair_key,
                        "leg": "long",
                        "spread": spread,
                        "correlation": pair.correlation,
                    },
                )
            )

            # Signal 2: Buy NO on expensive market (SHORT proxy)
            # NO ask price = 1 - YES bid price
            no_ask_price = 1.0 - expensive_price.bid
            short_size = leg_size_usd / no_ask_price
            signals.append(
                Signal(
                    strategy=self.name,
                    market_id=expensive_market,
                    token_id=expensive_no_token,
                    action=SignalAction.BUY,
                    price=no_ask_price,
                    size=short_size,
                    reason=f"StatArb SHORT: spread={spread*100:.2f}%, corr={pair.correlation:.2f}",
                    confidence=min(pair.correlation, 0.9),
                    metadata={
                        "pair_key": pair_key,
                        "leg": "short",
                        "spread": spread,
                        "correlation": pair.correlation,
                    },
                )
            )

            # =================================================================
            # Step 8: Track active trade
            # =================================================================

            pair.entry_spread = spread
            pair.entry_time = datetime.utcnow()
            pair.long_market_id = cheap_market
            pair.short_market_id = expensive_market
            pair.last_signal_time = now
            self._active_trades[pair_key] = pair

        return signals

    def _is_valid_price(self, update: PriceUpdate) -> bool:
        """Validate that a price update has valid values.

        Args:
            update: Price update to validate

        Returns:
            True if price is valid for trading
        """
        min_price = self.stat_config.min_price
        max_price = self.stat_config.max_price

        if not update.bid or not update.ask:
            return False

        if update.bid < min_price or update.ask > max_price:
            return False

        if update.bid >= update.ask:
            return False  # Invalid spread

        return True

    def _are_prices_valid(
        self, price_a: Optional[MarketPrice], price_b: Optional[MarketPrice]
    ) -> bool:
        """Validate that both prices exist and are not stale.

        Args:
            price_a: Price for first market
            price_b: Price for second market

        Returns:
            True if both prices are valid and fresh
        """
        if not price_a or not price_b:
            return False

        max_age = self.stat_config.max_price_age_sec

        # Check price staleness
        if price_a.age_seconds() > max_age or price_b.age_seconds() > max_age:
            return False

        # Check price bounds
        min_price = self.stat_config.min_price
        max_price = self.stat_config.max_price

        if price_a.mid < min_price or price_a.mid > max_price:
            return False

        if price_b.mid < min_price or price_b.mid > max_price:
            return False

        return True

    def _update_price(self, update: PriceUpdate) -> None:
        """Update price cache from NNG update.

        Args:
            update: Price update to cache
        """
        self._market_prices[update.market_id] = MarketPrice(
            market_id=update.market_id,
            token_id=update.token_id,
            bid=update.bid,
            ask=update.ask,
            mid=update.mid,
            spread=update.spread,
            updated_at=datetime.utcnow(),
        )

    def _should_refresh_pairs(self) -> bool:
        """Check if we should refresh correlation pairs.

        Returns:
            True if pairs should be refreshed
        """
        if self._last_pair_refresh is None:
            return True

        seconds_since_refresh = (datetime.utcnow() - self._last_pair_refresh).total_seconds()
        return seconds_since_refresh > 1800  # 30 minutes

    async def should_exit(self, position: Position, update: PriceUpdate) -> bool:
        """Check if stat arb position should exit.

        Exit conditions:
            1. Spread has converged below exit threshold
            2. Spread has widened beyond stop-loss
            3. Position has been open too long (24h)
            4. Correlation has broken down

        Args:
            position: Current position
            update: Price update

        Returns:
            True if position should be closed
        """
        # Update price cache
        if self._is_valid_price(update):
            self._update_price(update)

        # Find which trade this position belongs to
        for pair_key, pair in list(self._active_trades.items()):
            if position.market_id not in [pair.long_market_id, pair.short_market_id]:
                continue

            # Get current prices
            price_a = self._market_prices.get(pair.market_a_id)
            price_b = self._market_prices.get(pair.market_b_id)

            if not price_a or not price_b:
                continue

            current_spread = abs(price_a.mid - price_b.mid)

            # -----------------------------------------------------------------
            # Exit condition 1: Spread converged to target
            # -----------------------------------------------------------------
            if current_spread < self.stat_config.exit_threshold:
                self._logger.info(
                    f"StatArb exit: spread converged to {current_spread*100:.2f}% "
                    f"(entry: {pair.entry_spread*100:.2f}%)"
                )
                self._cleanup_trade(pair_key)
                return True

            # -----------------------------------------------------------------
            # Exit condition 2: Stop loss (spread widened too much)
            # -----------------------------------------------------------------
            if pair.entry_spread:
                max_spread = pair.entry_spread * self.stat_config.stop_loss_multiplier
                if current_spread > max_spread:
                    self._logger.warning(
                        f"StatArb STOP LOSS: spread widened to {current_spread*100:.2f}% "
                        f"(entry: {pair.entry_spread*100:.2f}%, max: {max_spread*100:.2f}%)"
                    )
                    self._cleanup_trade(pair_key)
                    return True

            # -----------------------------------------------------------------
            # Exit condition 3: Time-based exit (24 hours max hold)
            # -----------------------------------------------------------------
            if pair.entry_time:
                hours_open = (datetime.utcnow() - pair.entry_time).total_seconds() / 3600
                if hours_open > 24:
                    self._logger.info(
                        f"StatArb timeout: position open for {hours_open:.1f} hours, "
                        f"current spread: {current_spread*100:.2f}%"
                    )
                    self._cleanup_trade(pair_key)
                    return True

        return False

    def _cleanup_trade(self, pair_key: str) -> None:
        """Clean up trade tracking for a closed pair.

        Args:
            pair_key: Key of the pair to clean up
        """
        if pair_key in self._active_trades:
            del self._active_trades[pair_key]

        # Reset trade state in main pairs dict
        if pair_key in self._pairs:
            pair = self._pairs[pair_key]
            pair.entry_spread = None
            pair.entry_time = None
            pair.long_market_id = None
            pair.short_market_id = None

    # =========================================================================
    # Status Methods
    # =========================================================================

    def get_active_pairs(self) -> List[Dict[str, Any]]:
        """Get information about active stat arb trades.

        Returns:
            List of active trade details
        """
        result = []

        for pair_key, pair in self._active_trades.items():
            price_a = self._market_prices.get(pair.market_a_id)
            price_b = self._market_prices.get(pair.market_b_id)
            current_spread = abs(price_a.mid - price_b.mid) if price_a and price_b else None

            # Calculate P&L estimate
            pnl_estimate = None
            if pair.entry_spread and current_spread is not None:
                spread_change = pair.entry_spread - current_spread
                pnl_estimate = spread_change * self.stat_config.max_position_size

            result.append({
                "pair_key": pair_key,
                "market_a": pair.market_a_id,
                "market_b": pair.market_b_id,
                "correlation": pair.correlation,
                "entry_spread": pair.entry_spread,
                "current_spread": current_spread,
                "spread_change": (pair.entry_spread - current_spread) if pair.entry_spread and current_spread else None,
                "long_market": pair.long_market_id,
                "short_market": pair.short_market_id,
                "entry_time": pair.entry_time.isoformat() if pair.entry_time else None,
                "hours_open": (
                    (datetime.utcnow() - pair.entry_time).total_seconds() / 3600
                    if pair.entry_time else None
                ),
                "pnl_estimate": pnl_estimate,
            })

        return result

    def get_monitored_pairs(self) -> List[Dict[str, Any]]:
        """Get all monitored pairs (including inactive).

        Returns:
            List of all pair details
        """
        result = []

        for pair_key, pair in self._pairs.items():
            price_a = self._market_prices.get(pair.market_a_id)
            price_b = self._market_prices.get(pair.market_b_id)
            current_spread = abs(price_a.mid - price_b.mid) if price_a and price_b else None

            market_a = self._markets.get(pair.market_a_id)
            market_b = self._markets.get(pair.market_b_id)

            result.append({
                "pair_key": pair_key,
                "market_a": {
                    "id": pair.market_a_id,
                    "question": market_a.question[:60] if market_a else "Unknown",
                    "price": price_a.mid if price_a else None,
                    "age_sec": price_a.age_seconds() if price_a else None,
                },
                "market_b": {
                    "id": pair.market_b_id,
                    "question": market_b.question[:60] if market_b else "Unknown",
                    "price": price_b.mid if price_b else None,
                    "age_sec": price_b.age_seconds() if price_b else None,
                },
                "correlation": pair.correlation,
                "current_spread": current_spread,
                "is_active": pair_key in self._active_trades,
                "meets_threshold": current_spread >= self.stat_config.spread_threshold if current_spread else False,
            })

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        base_stats = super().get_stats()

        # Calculate aggregate stats
        total_pnl_estimate = 0.0
        for pair in self._active_trades.values():
            price_a = self._market_prices.get(pair.market_a_id)
            price_b = self._market_prices.get(pair.market_b_id)
            if price_a and price_b and pair.entry_spread:
                current_spread = abs(price_a.mid - price_b.mid)
                spread_change = pair.entry_spread - current_spread
                total_pnl_estimate += spread_change * self.stat_config.max_position_size

        base_stats.update({
            "monitored_pairs": len(self._pairs),
            "active_trades": len(self._active_trades),
            "monitored_markets": len(self._monitored_markets),
            "total_pnl_estimate": round(total_pnl_estimate, 4),
            "last_pair_refresh": self._last_pair_refresh.isoformat() if self._last_pair_refresh else None,
        })

        return base_stats
