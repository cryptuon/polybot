"""Arbitrage strategy.

Exploits pricing inefficiencies where YES + NO prices sum to less than $1.
When detected, buys both outcomes to lock in guaranteed profit at market resolution.

Example:
    YES at 48¢ + NO at 49¢ = 97¢ total
    Buy $1 of each -> guaranteed $0.03 profit regardless of outcome

Production improvements:
- Cooldown per market to prevent signal spam
- Price validation to prevent division by zero
- Max concurrent positions limit
- Order confirmation tracking
- Dynamic profit threshold based on fees
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from polybot.config import Settings
from polybot.models.messages import PriceUpdate, Signal, SignalAction
from polybot.models.position import Position
from polybot.strategies.base import BaseStrategy, StrategyConfig


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ArbitrageConfig(StrategyConfig):
    """Arbitrage strategy configuration.

    Attributes:
        min_profit_pct: Minimum profit percentage to trigger (accounts for fees)
        max_position_size: Maximum USD to allocate per arb opportunity
        poll_interval_sec: How often to poll for opportunities
        signal_cooldown_sec: Minimum time between signals for same market
        max_concurrent_arbs: Maximum number of simultaneous arb positions
        min_price: Minimum token price to consider (prevents extreme sizes)
        max_price: Maximum token price to consider
        fee_bps: Estimated trading fees in basis points (for profit calculation)
    """
    min_profit_pct: float = 0.005  # 0.5% minimum profit after fees (covers 2-leg costs)
    max_position_size: float = 100.0  # Max USD per market
    poll_interval_sec: float = 2.0
    signal_cooldown_sec: float = 300.0  # 5 minute cooldown per market
    max_concurrent_arbs: int = 5  # Max simultaneous arb positions
    min_price: float = 0.01  # Don't trade below 1 cent
    max_price: float = 0.99  # Don't trade above 99 cents
    fee_bps: float = 50.0  # 0.5% estimated round-trip fees


# =============================================================================
# State Tracking
# =============================================================================

@dataclass
class ArbOpportunity:
    """Tracks an arbitrage opportunity and its execution state.

    Attributes:
        market_id: The market condition ID
        yes_token: YES token ID
        no_token: NO token ID
        entry_cost: Combined cost (YES ask + NO ask) at entry
        profit_pct: Expected profit percentage
        yes_size: Number of YES shares to buy
        no_size: Number of NO shares to buy
        yes_filled: Whether YES order has filled
        no_filled: Whether NO order has filled
        created_at: When opportunity was detected
        last_signal_time: Last time we sent a signal for this market
    """
    market_id: str
    yes_token: str
    no_token: str
    entry_cost: float
    profit_pct: float
    yes_size: float = 0.0
    no_size: float = 0.0
    yes_filled: bool = False
    no_filled: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_signal_time: float = 0.0

    @property
    def is_complete(self) -> bool:
        """Check if both legs have filled."""
        return self.yes_filled and self.no_filled

    @property
    def expected_profit_usd(self) -> float:
        """Calculate expected profit in USD."""
        if self.entry_cost >= 1.0:
            return 0.0
        # Each share pays $1 at resolution, we paid entry_cost
        avg_shares = (self.yes_size + self.no_size) / 2
        return (1.0 - self.entry_cost) * avg_shares


# =============================================================================
# Strategy Implementation
# =============================================================================

class ArbitrageStrategy(BaseStrategy):
    """Arbitrage strategy - buy YES + NO when sum < $1.

    This strategy monitors all markets for arbitrage opportunities
    where the combined price of YES and NO outcomes is less than $1,
    guaranteeing a risk-free profit at market resolution.

    Workflow:
        1. Monitor price updates for all tokens
        2. For each market, check if YES_ask + NO_ask < (1 - min_profit)
        3. If opportunity exists and passes filters, signal to buy both outcomes
        4. Track order fills for both legs
        5. Hold until market resolves (guaranteed profit)

    Risk Management:
        - Cooldown prevents repeated signals for same market
        - Max concurrent positions limits capital allocation
        - Price bounds prevent extreme position sizes
        - Fee calculation ensures profit after costs
    """

    name = "arbitrage"
    description = "YES/NO arbitrage when combined price < $1"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize arbitrage strategy.

        Args:
            settings: Application settings, uses defaults if not provided
        """
        super().__init__(settings)

        # Token pair mappings for quick lookup
        # Maps YES token -> NO token for each market
        self._token_pairs: Dict[str, str] = {}

        # Reverse mapping: token -> market_id
        self._market_for_token: Dict[str, str] = {}

        # Active arb opportunities: market_id -> ArbOpportunity
        self._arb_positions: Dict[str, ArbOpportunity] = {}

        # Cooldown tracking: market_id -> last_signal_timestamp
        self._last_signal_time: Dict[str, float] = {}

    def _get_config(self) -> StrategyConfig:
        """Load arbitrage configuration from settings."""
        arb_settings = self._settings.arbitrage
        return ArbitrageConfig(
            min_profit_pct=arb_settings.min_profit_pct,
            poll_interval_sec=arb_settings.poll_interval_sec,
            max_position_size=arb_settings.max_position_size,
        )

    @property
    def arb_config(self) -> ArbitrageConfig:
        """Get typed configuration."""
        return self._config  # type: ignore

    async def _on_start(self) -> None:
        """Initialize token pair mappings from market data.

        Builds lookup tables for YES/NO token pairs to enable
        quick arbitrage opportunity detection.
        """
        if not self._sqlite:
            self._logger.warning("SQLite not available, cannot load markets")
            return

        # Load market data to build token pairs
        markets = await self._sqlite.get_active_markets(limit=500)

        for market in markets:
            # Map YES token to NO token
            self._token_pairs[market.outcome_yes_token] = market.outcome_no_token

            # Map both tokens to market ID for reverse lookup
            self._market_for_token[market.outcome_yes_token] = market.id
            self._market_for_token[market.outcome_no_token] = market.id

        self._logger.info(f"Tracking {len(self._token_pairs)} market pairs for arbitrage")

    async def scan(self, update: PriceUpdate) -> List[Signal]:
        """Scan for arbitrage opportunities.

        Checks if the current price update creates an arbitrage opportunity
        where buying both YES and NO tokens would guarantee profit.

        Args:
            update: Price update from the scanner

        Returns:
            List of signals (typically 0 or 2 - both YES and NO legs)
        """
        signals: List[Signal] = []
        now = time.time()

        # =================================================================
        # Step 1: Find the token pair for this update
        # =================================================================

        yes_token, no_token = self._resolve_token_pair(update.token_id)
        if not yes_token or not no_token:
            return signals

        market_id = self._market_for_token.get(yes_token)
        if not market_id:
            return signals

        # =================================================================
        # Step 2: Check if we already have an arb position here
        # =================================================================

        if market_id in self._arb_positions:
            # Already tracking this arb, wait for fills
            return signals

        # =================================================================
        # Step 3: Check max concurrent positions limit
        # =================================================================

        if len(self._arb_positions) >= self.arb_config.max_concurrent_arbs:
            return signals

        # =================================================================
        # Step 4: Check cooldown for this market
        # =================================================================

        last_signal = self._last_signal_time.get(market_id, 0)
        if (now - last_signal) < self.arb_config.signal_cooldown_sec:
            return signals

        # =================================================================
        # Step 5: Get prices for both tokens
        # =================================================================

        yes_price = self._prices.get(yes_token)
        no_price = self._prices.get(no_token)

        if not yes_price or not no_price:
            # Need both prices to calculate arb
            return signals

        # =================================================================
        # Diagnostic logging (every 200th scan with both prices)
        # =================================================================
        self._scan_count = getattr(self, '_scan_count', 0) + 1
        if self._scan_count % 500 == 1:
            total = yes_price.ask + no_price.ask
            gap = 1.0 - total
            self._logger.info(
                f"[DIAG] Arb check: YES ask={yes_price.ask:.4f}, NO ask={no_price.ask:.4f}, "
                f"sum={total:.4f}, gap={gap*100:.3f}%, market={market_id[:8]}..."
            )

        # =================================================================
        # Step 6: Validate prices are within acceptable bounds
        # =================================================================

        if not self._validate_prices(yes_price.ask, no_price.ask):
            return signals

        # =================================================================
        # Step 7: Calculate arbitrage opportunity
        # =================================================================

        # Total cost to buy both outcomes (use ask prices - what we pay)
        total_cost = yes_price.ask + no_price.ask

        # Must sum to less than $1 to have arb
        if total_cost >= 1.0:
            return signals

        # Calculate profit after estimated fees
        gross_profit_pct = (1.0 - total_cost) / total_cost
        fee_cost = self.arb_config.fee_bps / 10000 * 2  # Round trip on both legs
        net_profit_pct = gross_profit_pct - fee_cost

        if net_profit_pct < self.arb_config.min_profit_pct:
            return signals

        # =================================================================
        # Step 8: Calculate position sizes
        # =================================================================

        # Limit by config and risk settings
        position_size_usd = min(
            self.arb_config.max_position_size,
            self._settings.risk.max_position_size_usd,
        )

        # For true arbitrage, we need EQUAL SHARES of YES and NO
        # Cost per share pair = yes_ask + no_ask (= total_cost)
        # Total shares we can buy = budget / cost_per_pair
        shares = position_size_usd / total_cost
        yes_shares = shares
        no_shares = shares

        # =================================================================
        # Step 9: Log opportunity and create signals
        # =================================================================

        self._logger.info(
            f"Arb opportunity detected:\n"
            f"  Market: {market_id[:16]}...\n"
            f"  YES @ {yes_price.ask:.4f} + NO @ {no_price.ask:.4f} = {total_cost:.4f}\n"
            f"  Gross profit: {gross_profit_pct*100:.2f}%\n"
            f"  Net profit (after fees): {net_profit_pct*100:.2f}%\n"
            f"  Position: ${position_size_usd:.2f} per side"
        )

        # Signal to buy YES
        signals.append(
            Signal(
                strategy=self.name,
                market_id=market_id,
                token_id=yes_token,
                action=SignalAction.BUY,
                price=yes_price.ask,
                size=yes_shares,
                reason=f"Arb YES: sum={total_cost:.3f}, profit={net_profit_pct*100:.2f}%",
                confidence=1.0,  # Arb is mathematically risk-free
                metadata={
                    "arb_type": "yes_no",
                    "leg": "yes",
                    "total_cost": total_cost,
                    "profit_pct": net_profit_pct,
                },
            )
        )

        # Signal to buy NO
        signals.append(
            Signal(
                strategy=self.name,
                market_id=market_id,
                token_id=no_token,
                action=SignalAction.BUY,
                price=no_price.ask,
                size=no_shares,
                reason=f"Arb NO: sum={total_cost:.3f}, profit={net_profit_pct*100:.2f}%",
                confidence=1.0,
                metadata={
                    "arb_type": "yes_no",
                    "leg": "no",
                    "total_cost": total_cost,
                    "profit_pct": net_profit_pct,
                },
            )
        )

        # =================================================================
        # Step 10: Track the arb position
        # =================================================================

        self._arb_positions[market_id] = ArbOpportunity(
            market_id=market_id,
            yes_token=yes_token,
            no_token=no_token,
            entry_cost=total_cost,
            profit_pct=net_profit_pct,
            yes_size=yes_shares,
            no_size=no_shares,
            last_signal_time=now,
        )

        self._last_signal_time[market_id] = now

        return signals

    def _resolve_token_pair(self, token_id: str) -> tuple[Optional[str], Optional[str]]:
        """Resolve YES and NO tokens from any token ID.

        Args:
            token_id: Either the YES or NO token ID

        Returns:
            Tuple of (yes_token, no_token) or (None, None) if not found
        """
        # Check if this is a YES token
        if token_id in self._token_pairs:
            return token_id, self._token_pairs[token_id]

        # Check if this is a NO token (reverse lookup)
        for yes_token, no_token in self._token_pairs.items():
            if no_token == token_id:
                return yes_token, no_token

        return None, None

    def _validate_prices(self, yes_ask: float, no_ask: float) -> bool:
        """Validate that prices are within acceptable bounds.

        Prevents:
        - Division by zero from 0 prices
        - Extreme position sizes from very low prices
        - Invalid trades at price boundaries

        Args:
            yes_ask: YES token ask price
            no_ask: NO token ask price

        Returns:
            True if prices are valid for trading
        """
        min_price = self.arb_config.min_price
        max_price = self.arb_config.max_price

        # Check YES price bounds
        if yes_ask < min_price or yes_ask > max_price:
            return False

        # Check NO price bounds
        if no_ask < min_price or no_ask > max_price:
            return False

        return True

    async def should_exit(self, position: Position, update: PriceUpdate) -> bool:
        """Determine if arb position should exit early.

        Arb positions are typically held until market resolution for
        guaranteed profit. However, we may exit early if:
        - Current bid prices sum to > $1 (can sell for profit now)
        - Market conditions have changed significantly

        Args:
            position: Current position to evaluate
            update: Latest price update

        Returns:
            True if position should be closed
        """
        market_id = position.market_id
        arb = self._arb_positions.get(market_id)

        if not arb:
            # Not tracking this as an arb, don't manage exit
            return False

        # Get current prices (bid = what we can sell for)
        yes_price = self._prices.get(arb.yes_token)
        no_price = self._prices.get(arb.no_token)

        if not yes_price or not no_price:
            return False

        # Check if we can sell both sides for > $1 (immediate profit)
        current_value = yes_price.bid + no_price.bid

        if current_value > 1.0:
            profit_if_exit = current_value - arb.entry_cost
            profit_if_hold = 1.0 - arb.entry_cost

            # Exit if we can capture more profit now than waiting
            if profit_if_exit > profit_if_hold:
                self._logger.info(
                    f"Arb early exit opportunity:\n"
                    f"  Market: {market_id[:16]}...\n"
                    f"  Exit now profit: ${profit_if_exit:.4f}\n"
                    f"  Hold to resolution: ${profit_if_hold:.4f}"
                )
                # Clean up tracking
                del self._arb_positions[market_id]
                return True

        return False

    # =========================================================================
    # Order Fill Handlers
    # =========================================================================

    def handle_fill(self, market_id: str, token_id: str, size: float, price: float) -> None:
        """Handle order fill notification.

        Updates arb tracking when one leg fills.

        Args:
            market_id: Market ID
            token_id: Token that filled
            size: Filled size
            price: Fill price
        """
        arb = self._arb_positions.get(market_id)
        if not arb:
            return

        if token_id == arb.yes_token:
            arb.yes_filled = True
            self._logger.info(f"Arb YES leg filled: {size:.4f} @ {price:.4f}")
        elif token_id == arb.no_token:
            arb.no_filled = True
            self._logger.info(f"Arb NO leg filled: {size:.4f} @ {price:.4f}")

        if arb.is_complete:
            self._logger.info(
                f"Arb complete for {market_id[:16]}...\n"
                f"  Expected profit: ${arb.expected_profit_usd:.4f}"
            )

    def handle_cancel(self, market_id: str, token_id: str) -> None:
        """Handle order cancellation.

        If an arb leg is cancelled, we should cancel the other leg too
        to avoid one-sided exposure.

        Args:
            market_id: Market ID
            token_id: Cancelled token
        """
        arb = self._arb_positions.get(market_id)
        if not arb:
            return

        self._logger.warning(
            f"Arb leg cancelled for {market_id[:16]}... - "
            f"removing arb tracking (manual intervention may be needed)"
        )

        # Remove from tracking - leaves any filled leg as regular position
        del self._arb_positions[market_id]

    # =========================================================================
    # Status Methods
    # =========================================================================

    def get_active_arbs(self) -> Dict[str, Dict]:
        """Get active arbitrage positions with current status.

        Returns:
            Dictionary of market_id -> arb details
        """
        result = {}

        for market_id, arb in self._arb_positions.items():
            yes_price = self._prices.get(arb.yes_token)
            no_price = self._prices.get(arb.no_token)
            current_sum = (yes_price.mid + no_price.mid) if yes_price and no_price else None

            result[market_id] = {
                "entry_cost": arb.entry_cost,
                "current_sum": current_sum,
                "profit_pct": arb.profit_pct,
                "expected_profit_usd": arb.expected_profit_usd,
                "yes_filled": arb.yes_filled,
                "no_filled": arb.no_filled,
                "is_complete": arb.is_complete,
                "created_at": arb.created_at.isoformat(),
            }

        return result

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        base_stats = super().get_stats()

        # Add arb-specific stats
        complete_arbs = sum(1 for a in self._arb_positions.values() if a.is_complete)
        pending_arbs = len(self._arb_positions) - complete_arbs
        total_expected_profit = sum(a.expected_profit_usd for a in self._arb_positions.values())

        base_stats.update({
            "active_arbs": len(self._arb_positions),
            "complete_arbs": complete_arbs,
            "pending_arbs": pending_arbs,
            "total_expected_profit": round(total_expected_profit, 4),
            "tracked_markets": len(self._token_pairs),
        })

        return base_stats
