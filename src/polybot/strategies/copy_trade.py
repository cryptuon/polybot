"""Copy trading strategy.

Mirrors trades of successful whale traders automatically.
Scans profiles, executes proportional trades.

Workflow:
1. Identify high-performing traders (whales) from leaderboard
2. Monitor their positions for changes
3. When whale trades, execute proportional trade in same direction
4. Exit when whale exits

Key Features:
- Tracks both YES and NO positions (direction-aware)
- Dynamic confidence based on whale's historical performance
- Cooldown mechanism to prevent signal spam
- Max concurrent positions limit
- Price validation to avoid extreme entries
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from polybot.config import Settings
from polybot.core.client import PolymarketClient
from polybot.models.messages import PriceUpdate, Signal, SignalAction
from polybot.models.position import Position
from polybot.strategies.base import BaseStrategy, StrategyConfig


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------


@dataclass
class WhalePosition:
    """A single position held by a whale.

    Tracks both the size and direction (YES/NO) of the position,
    allowing us to mirror the exact trade.
    """

    market_id: str
    token_id: str  # YES or NO token
    size: float
    is_yes: bool  # True if YES token, False if NO
    entry_time: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WalletInfo:
    """Information about a tracked whale wallet.

    Stores whale metadata and their current positions.
    Performance metrics (PnL, win_rate) are used to calculate
    dynamic confidence when copying trades.
    """

    address: str
    label: Optional[str] = None
    balance: float = 0.0
    pnl_30d: float = 0.0
    win_rate: float = 0.0

    # Market ID -> WhalePosition (captures direction)
    positions: Dict[str, WhalePosition] = field(default_factory=dict)
    last_updated: Optional[datetime] = None

    # Track copy performance for this specific whale
    copies_attempted: int = 0
    copies_profitable: int = 0

    def copy_success_rate(self) -> float:
        """Calculate success rate of copying this whale.

        Returns:
            Success rate between 0.0 and 1.0, or 0.5 if insufficient data.
        """
        if self.copies_attempted < 5:
            return 0.5  # Not enough data, use neutral
        return self.copies_profitable / self.copies_attempted


@dataclass
class CopyTradeConfig(StrategyConfig):
    """Copy trading configuration.

    Attributes:
        min_whale_balance: Minimum volume/balance to consider someone a whale.
        proportional_size: Fraction of whale's position to copy (0.01 = 1%).
        max_position_size: Maximum USD value per copied position.
        scan_interval_sec: How often to poll whale positions.
        max_tracked_wallets: Maximum number of whales to track.
        signal_cooldown_sec: Minimum seconds between signals for same market.
        max_concurrent_copies: Maximum number of active copied positions.
        min_price: Minimum price to enter (avoid near-zero).
        max_price: Maximum price to enter (avoid near-certain).
        min_whale_pnl: Minimum 30-day PnL to consider copying a whale.
        base_confidence: Base confidence level before adjustments.
    """

    min_whale_balance: float = 100000.0  # Min $100k volume
    proportional_size: float = 0.01  # Copy 1% of whale size
    max_position_size: float = 500.0  # Max $500 per copy
    scan_interval_sec: float = 60.0  # 1 minute scan interval
    max_tracked_wallets: int = 10

    # Production safeguards
    signal_cooldown_sec: float = 300.0  # 5 minutes between signals per market
    max_concurrent_copies: int = 5  # Max 5 active copied positions
    min_price: float = 0.05  # Avoid very low prices
    max_price: float = 0.95  # Avoid very high prices
    min_whale_pnl: float = 0.0  # Only copy profitable whales
    base_confidence: float = 0.6  # Base confidence level


@dataclass
class CopiedPosition:
    """Tracks a position we're copying from a whale.

    Allows us to properly exit when the whale exits,
    and track performance for confidence adjustments.
    """

    market_id: str
    token_id: str
    whale_address: str
    is_yes: bool
    entry_time: datetime
    entry_price: float
    our_size: float


# -----------------------------------------------------------------------------
# Strategy Implementation
# -----------------------------------------------------------------------------


class CopyTradeStrategy(BaseStrategy):
    """Copy trading strategy.

    Monitors successful traders and mirrors their positions with
    proper direction tracking, cooldowns, and dynamic confidence.

    Key Improvements:
    - Tracks both YES and NO positions (not just YES)
    - Dynamic confidence based on whale's success rate
    - Cooldown mechanism prevents signal spam
    - Max concurrent positions limit
    - Price validation for safer entries
    - Better error handling with logging
    """

    name = "copy_trade"
    description = "Mirror trades of successful traders"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize copy trade strategy.

        Args:
            settings: Application settings. If None, uses defaults.
        """
        super().__init__(settings)

        # Whale tracking
        self._whales: Dict[str, WalletInfo] = {}  # address -> WalletInfo
        self._client: Optional[PolymarketClient] = None
        self._last_scan: Optional[datetime] = None

        # Copied position tracking with full details
        self._copied_positions: Dict[str, CopiedPosition] = {}  # market_id -> CopiedPosition

        # Cooldown tracking: market_id -> last signal timestamp
        self._signal_cooldowns: Dict[str, datetime] = {}

    def _get_config(self) -> StrategyConfig:
        """Get copy trade config from settings.

        Returns:
            CopyTradeConfig with values from settings.
        """
        ct_settings = self._settings.copy_trade
        return CopyTradeConfig(
            min_whale_balance=ct_settings.min_whale_balance,
            proportional_size=ct_settings.proportional_size,
        )

    @property
    def copy_config(self) -> CopyTradeConfig:
        """Get typed config for this strategy.

        Returns:
            CopyTradeConfig instance.
        """
        return self._config  # type: ignore

    # -------------------------------------------------------------------------
    # Lifecycle Methods
    # -------------------------------------------------------------------------

    async def _on_start(self) -> None:
        """Initialize client and load whale list on strategy start."""
        self._client = PolymarketClient()

        # Load tracked wallets from database
        await self._load_tracked_wallets()

        # Initial whale scan
        await self._scan_whales()

    async def _on_stop(self) -> None:
        """Cleanup resources on strategy stop."""
        if self._client:
            await self._client.close()
            self._client = None

    # -------------------------------------------------------------------------
    # Whale Discovery and Tracking
    # -------------------------------------------------------------------------

    async def _load_tracked_wallets(self) -> None:
        """Load previously tracked wallets from database.

        In production, this would load whale addresses and their
        historical performance from the database.
        """
        if not self._sqlite:
            self._logger.warning("No database connection, cannot load tracked wallets")
            return

        # Future: Load from wallets table
        # For now, start fresh each session
        self._logger.info("Wallet tracking initialized (no persisted wallets)")

    async def _scan_whales(self) -> None:
        """Scan leaderboard for high-performing traders to track.

        Filters by minimum volume and PnL requirements.
        Respects max_tracked_wallets limit.
        """
        if not self._client:
            self._logger.error("Cannot scan whales: client not initialized")
            return

        self._logger.info("Scanning for whales...")

        try:
            # Get leaderboard
            leaderboard = await self._client.get_leaderboard(limit=50)
            whales_added = 0

            for entry in leaderboard:
                # Extract address (API returns different field names)
                address = entry.get("proxyWallet", entry.get("user", entry.get("address", "")))
                if not address:
                    continue

                # Parse performance metrics
                volume = float(entry.get("vol", 0))
                pnl = float(entry.get("pnl", entry.get("profit", 0)))

                # Filter: must meet minimum volume
                if volume < self.copy_config.min_whale_balance:
                    continue

                # Filter: must be profitable (or meet minimum PnL)
                if pnl < self.copy_config.min_whale_pnl:
                    continue

                # Respect max wallet limit
                if len(self._whales) >= self.copy_config.max_tracked_wallets:
                    break

                # Add to tracking
                self._whales[address] = WalletInfo(
                    address=address,
                    label=entry.get("userName", entry.get("username")),
                    balance=volume,
                    pnl_30d=pnl,
                )
                whales_added += 1

                # Fetch their current positions
                await self._update_whale_positions(address)

            self._logger.info(
                f"Whale scan complete: tracking {len(self._whales)} whales "
                f"({whales_added} newly added)"
            )

        except Exception as e:
            self._logger.error(f"Failed to scan whales: {e}", exc_info=True)

    async def _update_whale_positions(self, address: str) -> None:
        """Update positions for a specific whale.

        Fetches current positions and detects changes (new entries, exits).

        Args:
            address: Whale wallet address to update.
        """
        if not self._client:
            return

        whale = self._whales.get(address)
        if not whale:
            self._logger.debug(f"Unknown whale address: {address}")
            return

        try:
            positions = await self._client.get_positions(address)
            old_positions = whale.positions.copy()
            whale.positions = {}

            for pos in positions:
                # API returns conditionId as the market identifier
                market_id = pos.get("conditionId", pos.get("market", ""))
                size = float(pos.get("size", 0))
                token_id = pos.get("asset", pos.get("token_id", ""))

                # Determine if this is a YES or NO position
                # outcomeIndex: 0 = YES (first outcome), 1 = NO (second outcome)
                outcome = pos.get("outcome", pos.get("side", "")).lower()
                is_yes = outcome == "yes" or pos.get("outcomeIndex", 0) == 0

                if size > 0 and market_id:
                    whale.positions[market_id] = WhalePosition(
                        market_id=market_id,
                        token_id=token_id,
                        size=size,
                        is_yes=is_yes,
                    )

            whale.last_updated = datetime.utcnow()

            # Detect and handle position changes
            await self._detect_changes(whale, old_positions)

        except Exception as e:
            self._logger.warning(
                f"Failed to fetch positions for whale {address[:8]}...: {e}"
            )

    async def _detect_changes(
        self, whale: WalletInfo, old_positions: Dict[str, WhalePosition]
    ) -> None:
        """Detect position changes for a whale and log them.

        New positions trigger potential copy signals.
        Closed positions trigger exit signals for our copies.

        Args:
            whale: Whale info with updated positions.
            old_positions: Previous positions for comparison.
        """
        # Detect new positions
        for market_id, pos in whale.positions.items():
            if market_id not in old_positions:
                direction = "YES" if pos.is_yes else "NO"
                self._logger.info(
                    f"Whale {whale.address[:8]}... opened {direction} position "
                    f"in {market_id[:8]}...: {pos.size:.2f} shares"
                )

        # Detect closed positions
        for market_id, old_pos in old_positions.items():
            if market_id not in whale.positions:
                direction = "YES" if old_pos.is_yes else "NO"
                self._logger.info(
                    f"Whale {whale.address[:8]}... closed {direction} position "
                    f"in {market_id[:8]}..."
                )

                # Mark our copy for exit if we have one
                if market_id in self._copied_positions:
                    copied = self._copied_positions[market_id]
                    if copied.whale_address == whale.address:
                        self._logger.info(
                            f"Will exit our copy in {market_id[:8]}... "
                            f"(whale exited)"
                        )

    # -------------------------------------------------------------------------
    # Signal Generation
    # -------------------------------------------------------------------------

    def _is_on_cooldown(self, market_id: str) -> bool:
        """Check if market is on signal cooldown.

        Prevents spamming signals for the same market.

        Args:
            market_id: Market to check.

        Returns:
            True if still on cooldown, False if ready to signal.
        """
        if market_id not in self._signal_cooldowns:
            return False

        elapsed = (datetime.utcnow() - self._signal_cooldowns[market_id]).total_seconds()
        return elapsed < self.copy_config.signal_cooldown_sec

    def _record_signal(self, market_id: str) -> None:
        """Record that we sent a signal for cooldown tracking.

        Args:
            market_id: Market we signaled for.
        """
        self._signal_cooldowns[market_id] = datetime.utcnow()

    def _calculate_confidence(self, whale: WalletInfo) -> float:
        """Calculate dynamic confidence based on whale's track record.

        Factors in:
        - Base confidence level
        - Whale's 30-day PnL (positive = higher confidence)
        - Our historical success rate copying this whale

        Args:
            whale: Whale we're considering copying.

        Returns:
            Confidence score between 0.3 and 0.9.
        """
        confidence = self.copy_config.base_confidence

        # Adjust based on whale's PnL (cap influence at +/- 0.15)
        if whale.pnl_30d > 0:
            pnl_boost = min(whale.pnl_30d / 100000, 0.15)  # +0.15 max for $100k+ PnL
            confidence += pnl_boost
        else:
            pnl_penalty = max(whale.pnl_30d / 100000, -0.15)
            confidence += pnl_penalty

        # Adjust based on our copy success rate with this whale
        success_rate = whale.copy_success_rate()
        if whale.copies_attempted >= 5:
            # Adjust by deviation from 50%
            confidence += (success_rate - 0.5) * 0.2

        # Clamp to reasonable range
        return max(0.3, min(0.9, confidence))

    def _validate_price(self, price: float) -> bool:
        """Validate price is within acceptable range.

        Avoids entries at extreme prices where risk/reward is poor.

        Args:
            price: Price to validate.

        Returns:
            True if price is acceptable.
        """
        return self.copy_config.min_price <= price <= self.copy_config.max_price

    async def scan(self, update: PriceUpdate) -> List[Signal]:
        """Scan for copy trade opportunities.

        Checks if any tracked whales have positions in this market
        that we should copy.

        Args:
            update: Price update for the market.

        Returns:
            List of signals (usually 0 or 1).
        """
        signals: List[Signal] = []

        # Trigger periodic whale position scan
        now = datetime.utcnow()
        if (
            self._last_scan is None
            or (now - self._last_scan).total_seconds() > self.copy_config.scan_interval_sec
        ):
            self._last_scan = now
            # Run scan in background to not block price processing
            asyncio.create_task(self._periodic_scan())

        # Early exits
        if not self._sqlite:
            return signals

        # Check concurrent position limit
        active_copies = len(self._copied_positions)
        if active_copies >= self.copy_config.max_concurrent_copies:
            return signals

        # Check cooldown
        if self._is_on_cooldown(update.market_id):
            return signals

        # Validate price - use mid price for direction-agnostic check
        mid_price = (update.bid + update.ask) / 2 if update.bid and update.ask else None
        if not mid_price or not self._validate_price(mid_price):
            return signals

        # Get market info for token IDs
        market = await self._sqlite.get_market(update.market_id)
        if not market:
            return signals

        # Check if any whale has a position here that we should copy
        for whale in self._whales.values():
            whale_pos = whale.positions.get(update.market_id)
            if not whale_pos:
                continue

            # Already copying this market
            if self.has_position(update.market_id):
                continue

            # Already have a copy for this market
            if update.market_id in self._copied_positions:
                continue

            # Determine which token to buy and at what price
            if whale_pos.is_yes:
                token_id = market.outcome_yes_token
                action = SignalAction.BUY
                entry_price = update.ask if update.ask and update.ask > 0 else None
            else:
                token_id = market.outcome_no_token
                action = SignalAction.BUY
                # For NO token, we buy at (1 - YES bid) effectively
                entry_price = (1.0 - update.bid) if update.bid else None

            if not entry_price or not self._validate_price(entry_price):
                continue

            # Calculate our position size
            our_size = whale_pos.size * self.copy_config.proportional_size

            # Apply position limits
            max_size_by_config = self.copy_config.max_position_size / entry_price
            max_size_by_risk = self._settings.risk.max_position_size_usd / entry_price
            our_size = min(our_size, max_size_by_config, max_size_by_risk)

            if our_size <= 0:
                continue

            # Calculate confidence based on whale's track record
            confidence = self._calculate_confidence(whale)

            # Create signal
            direction = "YES" if whale_pos.is_yes else "NO"
            signal = Signal(
                strategy=self.name,
                market_id=update.market_id,
                token_id=token_id,
                action=action,
                price=entry_price,
                size=our_size,
                reason=(
                    f"Copy whale {whale.address[:8]}... ({direction}), "
                    f"whale_size={whale_pos.size:.1f}, "
                    f"whale_pnl=${whale.pnl_30d:,.0f}"
                ),
                confidence=confidence,
            )
            signals.append(signal)

            # Track this copy
            self._copied_positions[update.market_id] = CopiedPosition(
                market_id=update.market_id,
                token_id=token_id,
                whale_address=whale.address,
                is_yes=whale_pos.is_yes,
                entry_time=now,
                entry_price=entry_price,
                our_size=our_size,
            )

            # Record cooldown
            self._record_signal(update.market_id)

            # Update whale copy stats
            whale.copies_attempted += 1

            # Only one copy per market
            break

        return signals

    # -------------------------------------------------------------------------
    # Exit Logic
    # -------------------------------------------------------------------------

    async def should_exit(self, position: Position, update: PriceUpdate) -> bool:
        """Check if copied position should exit.

        Exit when the whale we're copying exits their position.

        Args:
            position: Our current position.
            update: Latest price update.

        Returns:
            True if we should exit (whale exited).
        """
        copied = self._copied_positions.get(position.market_id)
        if not copied:
            # Not tracking this copy anymore - exit
            self._logger.info(
                f"Exit copy trade {position.market_id[:8]}...: "
                f"no longer tracking (stale copy)"
            )
            return True

        whale = self._whales.get(copied.whale_address)
        if not whale:
            # Whale no longer tracked - exit
            self._logger.info(
                f"Exit copy trade {position.market_id[:8]}...: "
                f"whale {copied.whale_address[:8]}... no longer tracked"
            )
            del self._copied_positions[position.market_id]
            return True

        # Check if whale still has the position
        whale_pos = whale.positions.get(position.market_id)
        if not whale_pos:
            self._logger.info(
                f"Exit copy trade {position.market_id[:8]}...: "
                f"whale {copied.whale_address[:8]}... exited"
            )
            del self._copied_positions[position.market_id]
            return True

        return False

    # -------------------------------------------------------------------------
    # Periodic Tasks
    # -------------------------------------------------------------------------

    async def _periodic_scan(self) -> None:
        """Periodically scan all whale positions for changes.

        Runs in background with rate limiting to avoid API throttling.
        """
        for address in list(self._whales.keys()):
            try:
                await self._update_whale_positions(address)
            except Exception as e:
                self._logger.warning(f"Error updating whale {address[:8]}...: {e}")

            # Rate limiting: 1 second between API calls
            await asyncio.sleep(1)

    # -------------------------------------------------------------------------
    # Trade Result Tracking
    # -------------------------------------------------------------------------

    def record_copy_result(self, market_id: str, profitable: bool) -> None:
        """Record the result of a copy trade for performance tracking.

        Call this when a copied position is closed to update
        whale-specific success rates.

        Args:
            market_id: Market ID of the closed position.
            profitable: Whether the trade was profitable.
        """
        copied = self._copied_positions.get(market_id)
        if not copied:
            return

        whale = self._whales.get(copied.whale_address)
        if whale and profitable:
            whale.copies_profitable += 1

    # -------------------------------------------------------------------------
    # Introspection Methods
    # -------------------------------------------------------------------------

    def get_tracked_whales(self) -> List[Dict[str, Any]]:
        """Get list of tracked whales with their stats.

        Returns:
            List of whale info dictionaries.
        """
        return [
            {
                "address": w.address,
                "label": w.label,
                "balance": w.balance,
                "pnl_30d": w.pnl_30d,
                "positions_count": len(w.positions),
                "copies_attempted": w.copies_attempted,
                "copy_success_rate": w.copy_success_rate(),
                "last_updated": w.last_updated.isoformat() if w.last_updated else None,
            }
            for w in self._whales.values()
        ]

    def get_copied_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get details of positions we're currently copying.

        Returns:
            Dictionary mapping market_id to copy details.
        """
        return {
            market_id: {
                "token_id": cp.token_id,
                "whale_address": cp.whale_address,
                "is_yes": cp.is_yes,
                "entry_time": cp.entry_time.isoformat(),
                "entry_price": cp.entry_price,
                "our_size": cp.our_size,
            }
            for market_id, cp in self._copied_positions.items()
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics.

        Returns:
            Dictionary of strategy stats.
        """
        total_copies = sum(w.copies_attempted for w in self._whales.values())
        profitable_copies = sum(w.copies_profitable for w in self._whales.values())

        return {
            "tracked_whales": len(self._whales),
            "active_copies": len(self._copied_positions),
            "total_copies_attempted": total_copies,
            "total_copies_profitable": profitable_copies,
            "overall_success_rate": (
                profitable_copies / total_copies if total_copies > 0 else 0.0
            ),
            "markets_on_cooldown": len(self._signal_cooldowns),
        }
