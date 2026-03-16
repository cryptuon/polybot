"""Momentum Trading Strategy.

Follows price trends - markets that are moving tend to continue moving.
News takes time to propagate through the market, creating momentum.

Key Features:
- Tracks price changes over multiple timeframes
- Confirms momentum with volume
- Exits when momentum fades
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Deque, List, Optional, Tuple

from polybot.config import Settings
from polybot.models.messages import PriceUpdate, Signal, SignalAction
from polybot.models.position import Position
from polybot.strategies.base import BaseStrategy, StrategyConfig


@dataclass
class MomentumConfig(StrategyConfig):
    """Momentum strategy configuration."""

    # Momentum thresholds
    short_window_sec: float = 300.0  # 5 minute window
    long_window_sec: float = 3600.0  # 1 hour window

    # Entry conditions
    min_price_change_pct: float = 0.05  # 5% move to trigger
    min_volume_multiplier: float = 1.5  # Volume must be 1.5x average

    # Position sizing
    order_size: float = 20.0

    # Exit conditions
    momentum_fade_threshold: float = 0.02  # Exit if momentum drops below 2%
    take_profit_pct: float = 0.10  # Take profit at 10% gain
    stop_loss_pct: float = 0.05  # Stop loss at 5% loss

    # Rate limiting
    signal_cooldown_sec: float = 300.0
    max_positions_per_direction: int = 5


@dataclass
class PricePoint:
    """A single price observation."""

    timestamp: float
    mid: float
    bid: float
    ask: float
    spread: float


@dataclass
class MarketMomentum:
    """Momentum state for a market."""

    market_id: str
    price_history: Deque[PricePoint] = field(default_factory=lambda: deque(maxlen=1000))
    last_signal_time: float = 0.0

    # Computed momentum values
    short_momentum: float = 0.0
    long_momentum: float = 0.0
    volume_ratio: float = 1.0


class MomentumStrategy(BaseStrategy):
    """Momentum trading strategy.

    Trades in the direction of price movement, assuming trends persist.
    """

    name = "momentum"
    description = "Trend following based on price momentum"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._momentum: Dict[str, MarketMomentum] = {}
        self._long_positions: int = 0
        self._short_positions: int = 0

    def _get_config(self) -> StrategyConfig:
        """Get momentum config."""
        return MomentumConfig()

    @property
    def mom_config(self) -> MomentumConfig:
        """Get typed config."""
        return self._config  # type: ignore

    async def scan(self, update: PriceUpdate) -> List[Signal]:
        """Scan for momentum opportunities.

        Args:
            update: Price update

        Returns:
            List of signals
        """
        signals: List[Signal] = []
        now = time.time()

        # Get or create momentum tracker
        if update.market_id not in self._momentum:
            self._momentum[update.market_id] = MarketMomentum(market_id=update.market_id)

        mom = self._momentum[update.market_id]

        # Add price point
        mom.price_history.append(PricePoint(
            timestamp=now,
            mid=update.mid,
            bid=update.bid,
            ask=update.ask,
            spread=update.spread,
        ))

        # Calculate momentum
        self._calculate_momentum(mom, now)

        # Check cooldown
        if now - mom.last_signal_time < self.mom_config.signal_cooldown_sec:
            return signals

        # Check for entry signals
        signal = self._check_entry(update, mom)
        if signal:
            signals.append(signal)
            mom.last_signal_time = now

        return signals

    def _calculate_momentum(self, mom: MarketMomentum, now: float) -> None:
        """Calculate short and long term momentum.

        Args:
            mom: Market momentum state
            now: Current timestamp
        """
        if len(mom.price_history) < 10:
            return

        prices = list(mom.price_history)
        current_price = prices[-1].mid

        # Short-term momentum (5 min)
        short_cutoff = now - self.mom_config.short_window_sec
        short_prices = [p for p in prices if p.timestamp >= short_cutoff]
        if short_prices and short_prices[0].mid > 0:
            mom.short_momentum = (current_price - short_prices[0].mid) / short_prices[0].mid
        else:
            mom.short_momentum = 0.0

        # Long-term momentum (1 hour)
        long_cutoff = now - self.mom_config.long_window_sec
        long_prices = [p for p in prices if p.timestamp >= long_cutoff]
        if long_prices and long_prices[0].mid > 0:
            mom.long_momentum = (current_price - long_prices[0].mid) / long_prices[0].mid
        else:
            mom.long_momentum = 0.0

        # Volume estimation (based on spread narrowing = more activity)
        if len(short_prices) > 1:
            recent_spread = sum(p.spread for p in short_prices[-5:]) / min(5, len(short_prices))
            older_spread = sum(p.spread for p in short_prices[:5]) / min(5, len(short_prices))
            if older_spread > 0:
                # Narrower spread = higher volume
                mom.volume_ratio = older_spread / max(recent_spread, 0.001)
            else:
                mom.volume_ratio = 1.0

    def _check_entry(self, update: PriceUpdate, mom: MarketMomentum) -> Optional[Signal]:
        """Check for momentum entry signals.

        Args:
            update: Price update
            mom: Market momentum state

        Returns:
            Signal if entry conditions met
        """
        # Need both short and long momentum aligned
        if abs(mom.short_momentum) < self.mom_config.min_price_change_pct:
            return None

        # Momentum should be in same direction
        if mom.short_momentum * mom.long_momentum < 0:
            return None  # Conflicting signals

        # Volume confirmation (optional but preferred)
        volume_ok = mom.volume_ratio >= self.mom_config.min_volume_multiplier

        # Determine direction
        if mom.short_momentum > self.mom_config.min_price_change_pct:
            # Bullish momentum - buy
            if self._long_positions >= self.mom_config.max_positions_per_direction:
                return None

            if not update.ask or update.ask <= 0:
                return None

            size = self.mom_config.order_size / update.ask
            confidence = min(0.9, 0.5 + abs(mom.short_momentum) + (0.1 if volume_ok else 0))

            return Signal(
                strategy=self.name,
                market_id=update.market_id,
                token_id=update.token_id,
                action=SignalAction.BUY,
                price=update.ask,
                size=size,
                reason=f"Momentum BUY: short={mom.short_momentum*100:.1f}%, long={mom.long_momentum*100:.1f}%, vol_ratio={mom.volume_ratio:.1f}x",
                confidence=confidence,
                bid=update.bid,
                ask=update.ask,
            )

        elif mom.short_momentum < -self.mom_config.min_price_change_pct:
            # Bearish momentum - sell
            if self._short_positions >= self.mom_config.max_positions_per_direction:
                return None

            if not update.bid or update.bid <= 0:
                return None

            size = self.mom_config.order_size / update.bid
            confidence = min(0.9, 0.5 + abs(mom.short_momentum) + (0.1 if volume_ok else 0))

            return Signal(
                strategy=self.name,
                market_id=update.market_id,
                token_id=update.token_id,
                action=SignalAction.SELL,
                price=update.bid,
                size=size,
                reason=f"Momentum SELL: short={mom.short_momentum*100:.1f}%, long={mom.long_momentum*100:.1f}%, vol_ratio={mom.volume_ratio:.1f}x",
                confidence=confidence,
                bid=update.bid,
                ask=update.ask,
            )

        return None

    async def should_exit(self, position: Position, update: PriceUpdate) -> bool:
        """Check if momentum position should exit.

        Args:
            position: Current position
            update: Price update

        Returns:
            True if should exit
        """
        mom = self._momentum.get(position.market_id)
        if not mom:
            return False

        # Calculate P&L
        if position.side == "BUY":
            current_value = update.bid if update.bid else update.mid
            pnl_pct = (current_value - position.entry_price) / position.entry_price

            # Take profit
            if pnl_pct >= self.mom_config.take_profit_pct:
                self._logger.info(f"Momentum exit: take profit at {pnl_pct*100:.1f}%")
                return True

            # Stop loss
            if pnl_pct <= -self.mom_config.stop_loss_pct:
                self._logger.info(f"Momentum exit: stop loss at {pnl_pct*100:.1f}%")
                return True

            # Momentum fade - exit if momentum reversed
            if mom.short_momentum < -self.mom_config.momentum_fade_threshold:
                self._logger.info(f"Momentum exit: momentum faded to {mom.short_momentum*100:.1f}%")
                return True

        else:  # SELL position
            current_value = update.ask if update.ask else update.mid
            pnl_pct = (position.entry_price - current_value) / position.entry_price

            if pnl_pct >= self.mom_config.take_profit_pct:
                return True
            if pnl_pct <= -self.mom_config.stop_loss_pct:
                return True
            if mom.short_momentum > self.mom_config.momentum_fade_threshold:
                return True

        return False

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        base_stats = super().get_stats()

        # Find strongest momentum markets
        sorted_markets = sorted(
            self._momentum.values(),
            key=lambda m: abs(m.short_momentum),
            reverse=True
        )[:5]

        base_stats.update({
            "tracked_markets": len(self._momentum),
            "long_positions": self._long_positions,
            "short_positions": self._short_positions,
            "top_momentum": [
                {"market": m.market_id[:8], "short": f"{m.short_momentum*100:.1f}%"}
                for m in sorted_markets
            ],
        })
        return base_stats
