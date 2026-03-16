"""Volume Spike Mean Reversion Strategy.

Large volume often causes price overshoot, then reversal.
Trades against extreme moves that are likely to revert.

Key Features:
- Detects unusual volume/volatility
- Trades mean reversion after spikes
- Risk management with stops
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Deque, List, Optional

from polybot.config import Settings
from polybot.models.messages import PriceUpdate, Signal, SignalAction
from polybot.models.position import Position
from polybot.strategies.base import BaseStrategy, StrategyConfig


@dataclass
class VolumeSpikeConfig(StrategyConfig):
    """Volume spike configuration."""

    # Detection thresholds
    price_spike_threshold: float = 0.08  # 8% move to consider a spike
    spread_spike_multiplier: float = 2.0  # Spread narrows to 2x tighter than average

    # Mean reversion
    lookback_window_sec: float = 3600.0  # 1 hour baseline
    spike_window_sec: float = 300.0  # 5 minute spike detection

    # Position sizing
    order_size: float = 25.0

    # Exit conditions
    reversion_target_pct: float = 0.5  # Exit at 50% reversion
    stop_loss_pct: float = 0.08  # Stop if move continues 8%
    max_hold_hours: float = 4.0  # Max 4 hours hold time

    # Rate limiting
    signal_cooldown_sec: float = 600.0
    max_positions: int = 5


@dataclass
class MarketBaseline:
    """Baseline statistics for a market."""

    market_id: str
    price_history: Deque[float] = field(default_factory=lambda: deque(maxlen=500))
    spread_history: Deque[float] = field(default_factory=lambda: deque(maxlen=500))
    timestamps: Deque[float] = field(default_factory=lambda: deque(maxlen=500))

    # Computed baselines
    avg_price: float = 0.0
    price_std: float = 0.0
    avg_spread: float = 0.0

    # Spike detection
    last_spike_time: float = 0.0
    last_signal_time: float = 0.0


class VolumeSpikeStrategy(BaseStrategy):
    """Volume spike mean reversion strategy.

    Detects unusual price spikes and trades the reversion.
    """

    name = "volume_spike"
    description = "Mean reversion after volume-driven price spikes"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._baselines: Dict[str, MarketBaseline] = {}
        self._active_positions: int = 0

    def _get_config(self) -> StrategyConfig:
        """Get volume spike config."""
        return VolumeSpikeConfig()

    @property
    def spike_config(self) -> VolumeSpikeConfig:
        """Get typed config."""
        return self._config  # type: ignore

    async def scan(self, update: PriceUpdate) -> List[Signal]:
        """Scan for volume spike reversion opportunities.

        Args:
            update: Price update

        Returns:
            List of signals
        """
        signals: List[Signal] = []
        now = time.time()

        # Get or create baseline
        if update.market_id not in self._baselines:
            self._baselines[update.market_id] = MarketBaseline(market_id=update.market_id)

        baseline = self._baselines[update.market_id]

        # Update history
        baseline.price_history.append(update.mid)
        baseline.spread_history.append(update.spread)
        baseline.timestamps.append(now)

        # Need minimum history
        if len(baseline.price_history) < 20:
            return signals

        # Calculate baselines
        self._update_baselines(baseline, now)

        # Check cooldown
        if now - baseline.last_signal_time < self.spike_config.signal_cooldown_sec:
            return signals

        # Check position limit
        if self._active_positions >= self.spike_config.max_positions:
            return signals

        # Detect spike
        spike = self._detect_spike(baseline, update, now)

        if spike:
            direction, magnitude = spike

            # Create reversion signal (opposite direction)
            if direction == "UP":
                # Price spiked up - sell for reversion
                if update.bid and update.bid > 0:
                    size = self.spike_config.order_size / update.bid
                    confidence = min(0.8, 0.5 + magnitude)

                    signals.append(Signal(
                        strategy=self.name,
                        market_id=update.market_id,
                        token_id=update.token_id,
                        action=SignalAction.SELL,
                        price=update.bid,
                        size=size,
                        reason=f"Volume spike reversion: UP spike {magnitude*100:.1f}%, expect reversion",
                        confidence=confidence,
                        bid=update.bid,
                        ask=update.ask,
                    ))

            else:  # DOWN spike
                # Price spiked down - buy for reversion
                if update.ask and update.ask > 0:
                    size = self.spike_config.order_size / update.ask
                    confidence = min(0.8, 0.5 + magnitude)

                    signals.append(Signal(
                        strategy=self.name,
                        market_id=update.market_id,
                        token_id=update.token_id,
                        action=SignalAction.BUY,
                        price=update.ask,
                        size=size,
                        reason=f"Volume spike reversion: DOWN spike {magnitude*100:.1f}%, expect reversion",
                        confidence=confidence,
                        bid=update.bid,
                        ask=update.ask,
                    ))

            baseline.last_signal_time = now
            baseline.last_spike_time = now

        return signals

    def _update_baselines(self, baseline: MarketBaseline, now: float) -> None:
        """Update baseline statistics.

        Args:
            baseline: Market baseline to update
            now: Current timestamp
        """
        # Use older data for baseline (exclude recent spike window)
        cutoff = now - self.spike_config.spike_window_sec
        lookback_start = now - self.spike_config.lookback_window_sec

        baseline_prices = []
        baseline_spreads = []

        for i, ts in enumerate(baseline.timestamps):
            if lookback_start <= ts <= cutoff:
                baseline_prices.append(baseline.price_history[i])
                baseline_spreads.append(baseline.spread_history[i])

        if len(baseline_prices) >= 10:
            baseline.avg_price = sum(baseline_prices) / len(baseline_prices)

            # Calculate standard deviation
            variance = sum((p - baseline.avg_price) ** 2 for p in baseline_prices) / len(baseline_prices)
            baseline.price_std = variance ** 0.5

            baseline.avg_spread = sum(baseline_spreads) / len(baseline_spreads)

    def _detect_spike(
        self,
        baseline: MarketBaseline,
        update: PriceUpdate,
        now: float,
    ) -> Optional[tuple]:
        """Detect if there's a price spike.

        Args:
            baseline: Market baseline
            update: Current price update
            now: Current timestamp

        Returns:
            Tuple of (direction, magnitude) if spike detected, None otherwise
        """
        if baseline.avg_price <= 0 or baseline.price_std <= 0:
            return None

        # Calculate recent price change
        recent_start = now - self.spike_config.spike_window_sec

        recent_prices = []
        for i, ts in enumerate(baseline.timestamps):
            if ts >= recent_start:
                recent_prices.append(baseline.price_history[i])

        if len(recent_prices) < 5:
            return None

        # Price at start of spike window
        spike_start_price = recent_prices[0]
        current_price = update.mid

        if spike_start_price <= 0:
            return None

        # Calculate move
        price_change = (current_price - spike_start_price) / spike_start_price

        # Check if move exceeds threshold
        if abs(price_change) < self.spike_config.price_spike_threshold:
            return None

        # Check for volume/activity confirmation (spread narrowing indicates activity)
        recent_spread = update.spread
        if baseline.avg_spread > 0:
            spread_ratio = recent_spread / baseline.avg_spread
            # Tighter spread = more activity
            if spread_ratio > 1.0 / self.spike_config.spread_spike_multiplier:
                # Spread not tight enough - not a volume spike
                return None

        direction = "UP" if price_change > 0 else "DOWN"
        magnitude = abs(price_change)

        self._logger.info(
            f"Spike detected in {update.market_id[:8]}...: {direction} {magnitude*100:.1f}%"
        )

        return (direction, magnitude)

    async def should_exit(self, position: Position, update: PriceUpdate) -> bool:
        """Check if volume spike position should exit.

        Args:
            position: Current position
            update: Price update

        Returns:
            True if should exit
        """
        baseline = self._baselines.get(position.market_id)

        # Time-based exit
        hold_hours = (update.timestamp / 1000 - position.entry_time.timestamp()) / 3600
        if hold_hours > self.spike_config.max_hold_hours:
            self._logger.info(f"Volume spike exit: max hold time reached")
            return True

        # P&L based exits
        if position.side == "BUY":
            # We bought after DOWN spike, expecting UP reversion
            current_price = update.bid if update.bid else update.mid
            pnl_pct = (current_price - position.entry_price) / position.entry_price

            # Take profit on reversion
            if pnl_pct >= self.spike_config.reversion_target_pct * self.spike_config.price_spike_threshold:
                self._logger.info(f"Volume spike exit: reversion target hit {pnl_pct*100:.1f}%")
                return True

            # Stop loss
            if pnl_pct <= -self.spike_config.stop_loss_pct:
                self._logger.info(f"Volume spike exit: stop loss {pnl_pct*100:.1f}%")
                return True

        else:  # SELL position
            # We sold after UP spike, expecting DOWN reversion
            current_price = update.ask if update.ask else update.mid
            pnl_pct = (position.entry_price - current_price) / position.entry_price

            if pnl_pct >= self.spike_config.reversion_target_pct * self.spike_config.price_spike_threshold:
                return True

            if pnl_pct <= -self.spike_config.stop_loss_pct:
                return True

        return False

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        base_stats = super().get_stats()

        # Find markets with recent spikes
        now = time.time()
        recent_spikes = [
            b for b in self._baselines.values()
            if now - b.last_spike_time < 3600
        ]

        base_stats.update({
            "tracked_markets": len(self._baselines),
            "active_positions": self._active_positions,
            "recent_spikes": len(recent_spikes),
        })
        return base_stats
