"""Resolution Arbitrage Strategy.

Finds markets where the outcome is already known (event has occurred)
but the market price hasn't fully updated yet. Uses Perplexity for
real-time news to detect resolved events.

Example: "Will X happen before Dec 31?" when X already happened
→ Buy YES at 0.85, collect $1 at resolution

Key Features:
- Uses Perplexity API for real-time event checking
- Caches results to avoid excessive API calls
- High confidence threshold to avoid false positives
- Rate-limited to prevent spam
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from polybot.config import Settings
from polybot.core.perplexity_client import PerplexityClient, get_perplexity_client
from polybot.models.messages import PriceUpdate, Signal, SignalAction
from polybot.models.position import Position
from polybot.strategies.base import BaseStrategy, StrategyConfig


@dataclass
class ResolutionArbConfig(StrategyConfig):
    """Resolution arbitrage configuration."""

    # Minimum edge required (if event resolved, price should be near 1.0)
    min_edge: float = 0.10  # 10% edge minimum (buy at 0.90 or less)

    # Confidence thresholds
    min_resolution_confidence: float = 0.85  # Perplexity must be 85%+ confident
    min_signal_confidence: float = 0.80

    # Position sizing
    order_size: float = 50.0  # Larger size for high-confidence arb

    # Rate limiting
    check_interval_sec: float = 300.0  # Check each market every 5 minutes
    max_checks_per_hour: int = 50  # Limit API calls

    # Cache
    cache_duration_sec: float = 600.0  # Cache results for 10 minutes

    # Filters
    min_volume_24h: float = 1000.0  # Minimum volume
    max_hours_to_resolution: float = 168.0  # Only check markets resolving within 7 days


@dataclass
class MarketCheckResult:
    """Cached result of checking a market."""

    market_id: str
    checked_at: datetime
    resolved: bool
    outcome: str  # "YES", "NO", or "UNKNOWN"
    confidence: float
    evidence: str


class ResolutionArbStrategy(BaseStrategy):
    """Resolution arbitrage strategy.

    Monitors markets for events that have already occurred but
    where the market price hasn't updated. Uses Perplexity's
    real-time search to detect resolved events.
    """

    name = "resolution_arb"
    description = "Arbitrage on markets with known outcomes"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._perplexity: Optional[PerplexityClient] = None
        self._check_cache: Dict[str, MarketCheckResult] = {}
        self._last_check_times: Dict[str, float] = {}
        self._checks_this_hour: int = 0
        self._hour_start: float = time.time()
        self._pending_checks: Set[str] = set()

    def _get_config(self) -> StrategyConfig:
        """Get resolution arb config."""
        return ResolutionArbConfig()

    @property
    def res_config(self) -> ResolutionArbConfig:
        """Get typed config."""
        return self._config  # type: ignore

    async def _on_start(self) -> None:
        """Initialize Perplexity client."""
        self._perplexity = await get_perplexity_client()
        self._logger.info("Resolution arbitrage strategy initialized")

    async def _on_stop(self) -> None:
        """Cleanup."""
        pass  # Perplexity client is shared singleton

    async def scan(self, update: PriceUpdate) -> List[Signal]:
        """Scan for resolution arbitrage opportunities.

        Args:
            update: Price update

        Returns:
            List of signals (0 or 1)
        """
        signals: List[Signal] = []

        # Rate limiting - reset counter every hour
        now = time.time()
        if now - self._hour_start > 3600:
            self._checks_this_hour = 0
            self._hour_start = now

        if self._checks_this_hour >= self.res_config.max_checks_per_hour:
            return signals

        # Check if we need to verify this market
        market_id = update.market_id

        # Skip if checked recently
        last_check = self._last_check_times.get(market_id, 0)
        if now - last_check < self.res_config.check_interval_sec:
            # But still use cached result if available
            cached = self._check_cache.get(market_id)
            if cached and cached.resolved:
                return self._generate_signal_from_cache(cached, update)
            return signals

        # Skip if already checking this market
        if market_id in self._pending_checks:
            return signals

        # Get market info
        if not self._sqlite:
            return signals

        market = await self._sqlite.get_market(market_id)
        if not market:
            return signals

        # Filter: must be resolving soon
        if market.end_date:
            hours_remaining = (market.end_date - datetime.utcnow()).total_seconds() / 3600
            if hours_remaining < 0 or hours_remaining > self.res_config.max_hours_to_resolution:
                return signals

        # Check if there's edge (price significantly below 1.0)
        current_price = update.mid
        if current_price > (1.0 - self.res_config.min_edge):
            # No edge - price already near 1.0
            return signals

        # Schedule async check (don't block price processing)
        self._pending_checks.add(market_id)
        asyncio.create_task(self._check_market_resolution(market_id, market.question, market.description))

        # Use cached result if available
        cached = self._check_cache.get(market_id)
        if cached and cached.resolved:
            return self._generate_signal_from_cache(cached, update)

        return signals

    async def _check_market_resolution(
        self,
        market_id: str,
        question: str,
        description: Optional[str],
    ) -> None:
        """Check if a market's event has already resolved.

        Args:
            market_id: Market ID
            question: Market question
            description: Market description
        """
        try:
            if not self._perplexity:
                return

            self._checks_this_hour += 1
            self._last_check_times[market_id] = time.time()

            result = await self._perplexity.check_event_status(question, description)

            # Cache the result
            self._check_cache[market_id] = MarketCheckResult(
                market_id=market_id,
                checked_at=datetime.utcnow(),
                resolved=result.get("resolved", False),
                outcome=result.get("outcome", "UNKNOWN"),
                confidence=result.get("confidence", 0.0),
                evidence=result.get("evidence", ""),
            )

            if result.get("resolved") and result.get("confidence", 0) >= self.res_config.min_resolution_confidence:
                self._logger.info(
                    f"Resolved market found: {market_id[:8]}...\n"
                    f"  Outcome: {result.get('outcome')}\n"
                    f"  Confidence: {result.get('confidence'):.2f}\n"
                    f"  Evidence: {result.get('evidence', '')[:100]}..."
                )

        except Exception as e:
            self._logger.error(f"Error checking market resolution: {e}")

        finally:
            self._pending_checks.discard(market_id)

    def _generate_signal_from_cache(
        self,
        cached: MarketCheckResult,
        update: PriceUpdate,
    ) -> List[Signal]:
        """Generate signal from cached resolution check.

        Args:
            cached: Cached check result
            update: Current price update

        Returns:
            List with 0 or 1 signal
        """
        if not cached.resolved:
            return []

        if cached.confidence < self.res_config.min_resolution_confidence:
            return []

        # Determine action based on outcome
        if cached.outcome == "YES":
            # Event happened - buy YES if price is low
            if update.ask and update.ask < (1.0 - self.res_config.min_edge):
                edge = 1.0 - update.ask
                size = self.res_config.order_size / update.ask

                return [Signal(
                    strategy=self.name,
                    market_id=update.market_id,
                    token_id=update.token_id,
                    action=SignalAction.BUY,
                    price=update.ask,
                    size=size,
                    reason=f"Resolution arb: {cached.outcome} resolved, edge={edge*100:.1f}%, evidence={cached.evidence[:50]}...",
                    confidence=min(cached.confidence, self.res_config.min_signal_confidence),
                    bid=update.bid,
                    ask=update.ask,
                )]

        elif cached.outcome == "NO":
            # Event didn't happen - sell YES (or buy NO) if YES price is high
            # For simplicity, we signal to sell if we have a position
            # In practice, you'd buy NO token
            pass

        return []

    async def should_exit(self, position: Position, update: PriceUpdate) -> bool:
        """Check if position should exit.

        Resolution arb positions are held until resolution.
        """
        # Exit if price reaches near 1.0 (market caught up)
        if update.bid and update.bid > 0.98:
            self._logger.info(f"Exiting resolution arb: price reached {update.bid:.3f}")
            return True

        return False

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        base_stats = super().get_stats()
        base_stats.update({
            "cached_checks": len(self._check_cache),
            "resolved_markets": sum(1 for c in self._check_cache.values() if c.resolved),
            "checks_this_hour": self._checks_this_hour,
            "pending_checks": len(self._pending_checks),
        })
        return base_stats
