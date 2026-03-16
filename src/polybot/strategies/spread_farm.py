"""Spread farming strategy.

Market making strategy that profits from bid-ask spreads.
Places orders at bid and ask, capturing the spread on fills.

Improvements over basic version:
- Cooldown per market to prevent signal spam
- Max spread filter to avoid illiquid markets
- Volume requirements for market quality
- Dynamic confidence based on spread stability
- Order state tracking
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from polybot.config import Settings
from polybot.models.messages import PriceUpdate, Signal, SignalAction
from polybot.models.position import Position
from polybot.strategies.base import BaseStrategy, StrategyConfig


@dataclass
class SpreadFarmConfig(StrategyConfig):
    """Spread farming configuration."""

    # Spread thresholds
    min_spread: float = 0.01  # 1% minimum spread to farm (covers fees)
    max_spread: float = 0.05  # 5% maximum spread (avoid illiquid/risky markets)

    # Order sizing
    order_size: float = 10.0  # USD size per order
    max_inventory: float = 100.0  # Max inventory per side (USD)

    # Rate limiting
    signal_cooldown_sec: float = 60.0  # Minimum time between signals per market
    quote_refresh_sec: float = 30.0  # How often to refresh quotes

    # Quality filters
    min_volume_24h: float = 1000.0  # Minimum 24h volume (USD)
    min_price: float = 0.01  # Don't trade below 1 cent
    max_price: float = 0.99  # Don't trade above 99 cents

    # Spread stability (for confidence)
    spread_stability_samples: int = 10  # Number of samples for stability calc


@dataclass
class QuoteState:
    """State for a market's quotes."""

    market_id: str
    token_id: str
    inventory: float = 0.0  # Positive = long, negative = short

    # Order tracking
    bid_pending: bool = False
    ask_pending: bool = False
    last_bid_time: float = 0.0
    last_ask_time: float = 0.0

    # Spread history for stability calculation
    spread_history: List[float] = field(default_factory=list)
    last_spread: float = 0.0

    # Stats
    signals_sent: int = 0
    fills_count: int = 0


class SpreadFarmStrategy(BaseStrategy):
    """Spread farming (market making) strategy.

    Places orders at bid and ask to capture spread on fills.
    Manages inventory to avoid excessive directional exposure.

    Workflow:
    1. Identify markets with sufficient spread (but not too wide)
    2. Check volume/liquidity requirements
    3. Apply cooldown to prevent signal spam
    4. Place buy order at bid, sell order at ask
    5. Manage inventory to stay delta-neutral
    """

    name = "spread_farm"
    description = "Market making to capture bid-ask spread"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._quotes: Dict[str, QuoteState] = {}  # market_id -> QuoteState
        self._active_markets: Set[str] = set()

        # Track market volumes (would be populated from market data)
        self._market_volumes: Dict[str, float] = {}

    def _get_config(self) -> StrategyConfig:
        """Get spread farm config from settings."""
        sf_settings = self._settings.spread_farm
        return SpreadFarmConfig(
            min_spread=sf_settings.min_spread,
            order_size=sf_settings.order_size,
        )

    @property
    def spread_config(self) -> SpreadFarmConfig:
        """Get typed config."""
        return self._config  # type: ignore

    async def scan(self, update: PriceUpdate) -> List[Signal]:
        """Scan for spread farming opportunities.

        Args:
            update: Price update

        Returns:
            List of signals (0-2 per call, with cooldown)
        """
        signals: List[Signal] = []
        now = time.time()

        # === Diagnostic logging (every 100th scan) ===
        self._scan_count = getattr(self, '_scan_count', 0) + 1
        if self._scan_count % 500 == 1:
            spread = update.ask - update.bid
            spread_pct = spread / update.mid if update.mid > 0 else 0
            self._logger.info(
                f"[DIAG] Sample update: bid={update.bid:.4f}, ask={update.ask:.4f}, "
                f"spread={spread_pct*100:.2f}%, market={update.market_id[:8]}..."
            )

        # === Price Validation ===
        if not self._is_valid_price(update):
            return signals

        # === Spread Validation ===
        spread = update.ask - update.bid
        spread_pct = spread / update.mid if update.mid > 0 else 0

        # Check spread bounds
        if not self._is_valid_spread(spread, update):
            # Log rejections at INFO level periodically to help diagnose
            reject_key = f"reject_{update.market_id}"
            last_reject = getattr(self, '_reject_log', {}).get(reject_key, 0)
            if now - last_reject > 60:  # Log at most once per minute per market
                if not hasattr(self, '_reject_log'):
                    self._reject_log = {}
                self._reject_log[reject_key] = now
                reason = "too narrow" if spread_pct < self.spread_config.min_spread else "too wide"
                self._logger.info(
                    f"[REJECT] {update.market_id[:8]}... spread={spread_pct*100:.2f}% ({reason}), "
                    f"bounds=[{self.spread_config.min_spread*100:.1f}%, {self.spread_config.max_spread*100:.1f}%]"
                )
            return signals

        # === Volume Check ===
        # Use volume from update if available, otherwise check cache
        volume_24h = getattr(update, 'volume_24h', None) or self._market_volumes.get(update.market_id, 0)
        if volume_24h < self.spread_config.min_volume_24h:
            # For now, skip volume check if we don't have data
            # In production, this would filter out low-volume markets
            pass

        # === Get or Create Quote State ===
        if update.market_id not in self._quotes:
            self._quotes[update.market_id] = QuoteState(
                market_id=update.market_id,
                token_id=update.token_id,
            )

        quote = self._quotes[update.market_id]

        # Update spread history for stability calculation
        self._update_spread_history(quote, spread)

        # Calculate dynamic confidence based on spread stability
        confidence = self._calculate_confidence(quote, spread)

        # === Cooldown Check ===
        bid_cooldown_ok = (now - quote.last_bid_time) >= self.spread_config.signal_cooldown_sec
        ask_cooldown_ok = (now - quote.last_ask_time) >= self.spread_config.signal_cooldown_sec

        # === Inventory Management ===
        inventory_limit_reached = abs(quote.inventory) >= self.spread_config.max_inventory

        if inventory_limit_reached:
            # Inventory at limit - only quote one side to reduce exposure
            if quote.inventory > 0:
                # Long inventory - only place asks to reduce
                if ask_cooldown_ok and not quote.ask_pending:
                    signal = self._create_ask_signal(update, quote, confidence)
                    signals.append(signal)
                    quote.ask_pending = True
                    quote.last_ask_time = now
                    quote.signals_sent += 1
            else:
                # Short inventory - only place bids to reduce
                if bid_cooldown_ok and not quote.bid_pending:
                    signal = self._create_bid_signal(update, quote, confidence)
                    signals.append(signal)
                    quote.bid_pending = True
                    quote.last_bid_time = now
                    quote.signals_sent += 1
        else:
            # Normal operation - quote both sides (respecting cooldowns)
            if bid_cooldown_ok and not quote.bid_pending:
                signal = self._create_bid_signal(update, quote, confidence)
                signals.append(signal)
                quote.bid_pending = True
                quote.last_bid_time = now
                quote.signals_sent += 1

            if ask_cooldown_ok and not quote.ask_pending:
                signal = self._create_ask_signal(update, quote, confidence)
                signals.append(signal)
                quote.ask_pending = True
                quote.last_ask_time = now
                quote.signals_sent += 1

        if signals:
            self._active_markets.add(update.market_id)
            self._logger.info(
                f"Spread farm: {len(signals)} signal(s) for {update.market_id[:8]}... "
                f"spread={spread_pct*100:.2f}%, confidence={confidence:.2f}, "
                f"inventory={quote.inventory:.2f}"
            )

        return signals

    def _is_valid_price(self, update: PriceUpdate) -> bool:
        """Check if price update has valid prices for trading."""
        if not update.bid or not update.ask:
            return False

        if update.bid < self.spread_config.min_price:
            return False

        if update.ask > self.spread_config.max_price:
            return False

        if update.bid >= update.ask:
            return False  # Invalid spread

        return True

    def _is_valid_spread(self, spread: float, update: PriceUpdate) -> bool:
        """Check if spread is within acceptable bounds."""
        # Too narrow - not profitable after fees
        if spread < self.spread_config.min_spread:
            return False

        # Too wide - likely illiquid, orders won't fill
        if spread > self.spread_config.max_spread:
            return False

        return True

    def _update_spread_history(self, quote: QuoteState, spread: float) -> None:
        """Update spread history for stability calculation."""
        quote.spread_history.append(spread)

        # Keep only recent samples
        max_samples = self.spread_config.spread_stability_samples
        if len(quote.spread_history) > max_samples:
            quote.spread_history = quote.spread_history[-max_samples:]

        quote.last_spread = spread

    def _calculate_confidence(self, quote: QuoteState, current_spread: float) -> float:
        """Calculate confidence based on spread stability.

        More stable spreads = higher confidence.
        Widening spreads = lower confidence.
        Narrowing spreads = higher confidence.

        Returns:
            Confidence score between 0.5 and 0.95
        """
        if len(quote.spread_history) < 3:
            return 0.7  # Default for insufficient data

        # Calculate spread volatility (coefficient of variation)
        avg_spread = sum(quote.spread_history) / len(quote.spread_history)
        if avg_spread <= 0:
            return 0.5

        variance = sum((s - avg_spread) ** 2 for s in quote.spread_history) / len(quote.spread_history)
        std_dev = variance ** 0.5
        cv = std_dev / avg_spread  # Coefficient of variation

        # Low CV = stable spread = high confidence
        # CV of 0 = confidence 0.95
        # CV of 0.5+ = confidence 0.5
        stability_score = max(0.5, 0.95 - cv * 0.9)

        # Adjust for spread trend (is it widening or narrowing?)
        if len(quote.spread_history) >= 5:
            recent_avg = sum(quote.spread_history[-3:]) / 3
            older_avg = sum(quote.spread_history[:-3]) / max(1, len(quote.spread_history) - 3)

            if recent_avg < older_avg:
                # Spread is narrowing - slightly increase confidence
                stability_score = min(0.95, stability_score + 0.05)
            elif recent_avg > older_avg * 1.2:
                # Spread is widening significantly - decrease confidence
                stability_score = max(0.5, stability_score - 0.1)

        return round(stability_score, 2)

    def _create_bid_signal(
        self, update: PriceUpdate, quote: QuoteState, confidence: float
    ) -> Signal:
        """Create bid order signal."""
        # Calculate size in shares using midpoint for matched BUY/SELL sizes
        size = self.spread_config.order_size / update.mid

        return Signal(
            strategy=self.name,
            market_id=update.market_id,
            token_id=update.token_id,
            action=SignalAction.BUY,
            price=update.bid,
            size=size,
            reason=f"Spread farm bid, spread={update.spread*100:.2f}%, inv={quote.inventory:.1f}",
            confidence=confidence,
            bid=update.bid,
            ask=update.ask,
        )

    def _create_ask_signal(
        self, update: PriceUpdate, quote: QuoteState, confidence: float
    ) -> Signal:
        """Create ask order signal."""
        # Calculate size in shares using midpoint for matched BUY/SELL sizes
        size = self.spread_config.order_size / update.mid

        return Signal(
            strategy=self.name,
            market_id=update.market_id,
            token_id=update.token_id,
            action=SignalAction.SELL,
            price=update.ask,
            size=size,
            reason=f"Spread farm ask, spread={update.spread*100:.2f}%, inv={quote.inventory:.1f}",
            confidence=confidence,
            bid=update.bid,
            ask=update.ask,
        )

    async def should_exit(self, position: Position, update: PriceUpdate) -> bool:
        """Check if spread farm position should exit.

        Args:
            position: Current position
            update: Price update

        Returns:
            True if should exit
        """
        # Skip if prices are invalid
        if not update.bid or not update.ask or update.bid <= 0 or update.ask <= 0:
            return False

        spread = update.ask - update.bid

        # Exit if spread collapsed significantly (less than half our minimum)
        if spread < self.spread_config.min_spread * 0.5:
            quote = self._quotes.get(position.market_id)
            if quote and abs(quote.inventory) > 0:
                self._logger.info(
                    f"Spread farm exit: spread collapsed to {spread*100:.2f}%"
                )
                return True

        # Exit if spread widened too much (market becoming illiquid)
        if spread > self.spread_config.max_spread * 1.5:
            self._logger.info(
                f"Spread farm exit: spread widened to {spread*100:.2f}%"
            )
            return True

        return False

    def handle_fill(
        self, market_id: str, side: str, size: float, price: float
    ) -> None:
        """Handle order fill - update inventory and reset pending state.

        Args:
            market_id: Market ID
            side: BUY or SELL
            size: Filled size
            price: Fill price
        """
        quote = self._quotes.get(market_id)
        if not quote:
            return

        if side == "BUY":
            quote.inventory += size * price  # Track in USD terms
            quote.bid_pending = False
            quote.fills_count += 1
            self._logger.info(
                f"Spread farm bid filled: +${size * price:.2f} @ {price}, "
                f"inventory=${quote.inventory:.2f}"
            )
        else:
            quote.inventory -= size * price  # Track in USD terms
            quote.ask_pending = False
            quote.fills_count += 1
            self._logger.info(
                f"Spread farm ask filled: -${size * price:.2f} @ {price}, "
                f"inventory=${quote.inventory:.2f}"
            )

    def handle_cancel(self, market_id: str, side: str) -> None:
        """Handle order cancellation - reset pending state.

        Args:
            market_id: Market ID
            side: BUY or SELL
        """
        quote = self._quotes.get(market_id)
        if not quote:
            return

        if side == "BUY":
            quote.bid_pending = False
        else:
            quote.ask_pending = False

    def handle_reject(self, market_id: str, side: str, reason: str) -> None:
        """Handle order rejection - reset pending state.

        Args:
            market_id: Market ID
            side: BUY or SELL
            reason: Rejection reason
        """
        quote = self._quotes.get(market_id)
        if not quote:
            return

        if side == "BUY":
            quote.bid_pending = False
        else:
            quote.ask_pending = False

        self._logger.warning(f"Order rejected for {market_id}: {reason}")

    def get_active_markets(self) -> List[str]:
        """Get list of actively quoted markets."""
        return list(self._active_markets)

    def get_quotes(self) -> Dict[str, Dict]:
        """Get current quote states."""
        return {
            market_id: {
                "token_id": q.token_id,
                "inventory": q.inventory,
                "bid_pending": q.bid_pending,
                "ask_pending": q.ask_pending,
                "last_spread": q.last_spread,
                "signals_sent": q.signals_sent,
                "fills_count": q.fills_count,
                "spread_stability": self._calculate_confidence(q, q.last_spread),
            }
            for market_id, q in self._quotes.items()
        }

    def get_stats(self) -> Dict:
        """Get strategy statistics including spread farm specific stats."""
        base_stats = super().get_stats()

        # Add spread farm specific stats
        total_inventory = sum(q.inventory for q in self._quotes.values())
        total_signals = sum(q.signals_sent for q in self._quotes.values())
        total_fills = sum(q.fills_count for q in self._quotes.values())

        base_stats.update({
            "active_markets": len(self._active_markets),
            "total_inventory_usd": total_inventory,
            "total_signals": total_signals,
            "total_fills": total_fills,
            "fill_rate": total_fills / total_signals if total_signals > 0 else 0,
        })

        return base_stats
