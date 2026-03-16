"""Per-venue exposure tracking."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from polybot.risk.models import AssetClass, VenuePosition

logger = logging.getLogger(__name__)


class VenueExposure:
    """Tracks exposure for a single venue.

    Aggregates all positions, orders, and exposure metrics for one venue.
    Updated by venue adapters and queried by PortfolioRisk.

    Example:
        exposure = VenueExposure("polymarket")
        exposure.update_position(position)
        print(f"Total exposure: ${exposure.total_exposure_usd}")
    """

    def __init__(self, venue: str) -> None:
        """Initialize venue exposure tracker.

        Args:
            venue: Venue identifier (e.g., "polymarket", "binance")
        """
        self.venue = venue
        self._positions: Dict[str, VenuePosition] = {}  # key -> position
        self._pending_orders_value: float = 0
        self._daily_pnl: float = 0
        self._daily_volume: float = 0
        self._last_update: Optional[datetime] = None

    def _position_key(self, symbol: str, token_id: Optional[str] = None) -> str:
        """Generate unique key for a position."""
        return f"{symbol}:{token_id or ''}"

    # =========================================================================
    # Exposure Properties
    # =========================================================================

    @property
    def total_exposure_usd(self) -> float:
        """Total notional exposure on this venue."""
        return sum(abs(p.notional_usd) for p in self._positions.values())

    @property
    def long_exposure_usd(self) -> float:
        """Total long exposure."""
        return sum(
            p.notional_usd for p in self._positions.values() if p.side == "long"
        )

    @property
    def short_exposure_usd(self) -> float:
        """Total short exposure (as positive value)."""
        return sum(
            abs(p.notional_usd) for p in self._positions.values() if p.side == "short"
        )

    @property
    def net_exposure_usd(self) -> float:
        """Net directional exposure (long - short)."""
        return self.long_exposure_usd - self.short_exposure_usd

    @property
    def net_delta(self) -> float:
        """Net delta exposure across all positions."""
        return sum(p.signed_delta for p in self._positions.values())

    @property
    def net_gamma(self) -> float:
        """Net gamma exposure."""
        return sum(p.gamma * p.size for p in self._positions.values())

    @property
    def net_vega(self) -> float:
        """Net vega exposure."""
        return sum(p.vega * p.size for p in self._positions.values())

    @property
    def net_theta(self) -> float:
        """Net theta exposure."""
        return sum(p.theta * p.size for p in self._positions.values())

    @property
    def unrealized_pnl(self) -> float:
        """Total unrealized PnL."""
        return sum(p.unrealized_pnl for p in self._positions.values())

    @property
    def realized_pnl(self) -> float:
        """Total realized PnL."""
        return sum(p.realized_pnl for p in self._positions.values())

    @property
    def daily_pnl(self) -> float:
        """Daily PnL (realized + unrealized)."""
        return self._daily_pnl + self.unrealized_pnl

    @property
    def position_count(self) -> int:
        """Number of open positions."""
        return len(self._positions)

    # =========================================================================
    # Position Management
    # =========================================================================

    def update_position(self, position: VenuePosition) -> None:
        """Update or add a position.

        Args:
            position: Position to update
        """
        key = self._position_key(position.symbol, position.token_id)
        self._positions[key] = position
        self._last_update = datetime.utcnow()
        logger.debug(f"Updated position {key}: {position.size} @ {position.entry_price}")

    def remove_position(self, symbol: str, token_id: Optional[str] = None) -> Optional[VenuePosition]:
        """Remove a closed position.

        Args:
            symbol: Position symbol
            token_id: Token ID (for Polymarket)

        Returns:
            Removed position or None
        """
        key = self._position_key(symbol, token_id)
        position = self._positions.pop(key, None)
        if position:
            self._last_update = datetime.utcnow()
            logger.debug(f"Removed position {key}")
        return position

    def get_position(self, symbol: str, token_id: Optional[str] = None) -> Optional[VenuePosition]:
        """Get a specific position.

        Args:
            symbol: Position symbol
            token_id: Token ID (for Polymarket)

        Returns:
            Position or None
        """
        key = self._position_key(symbol, token_id)
        return self._positions.get(key)

    def get_positions(self, asset_class: Optional[AssetClass] = None) -> List[VenuePosition]:
        """Get all positions, optionally filtered by asset class.

        Args:
            asset_class: Optional filter

        Returns:
            List of positions
        """
        positions = list(self._positions.values())
        if asset_class:
            positions = [p for p in positions if p.asset_class == asset_class]
        return positions

    def has_position(self, symbol: str, token_id: Optional[str] = None) -> bool:
        """Check if position exists.

        Args:
            symbol: Position symbol
            token_id: Token ID

        Returns:
            True if position exists
        """
        key = self._position_key(symbol, token_id)
        return key in self._positions

    # =========================================================================
    # Price Updates
    # =========================================================================

    def update_prices(self, prices: Dict[str, float]) -> None:
        """Batch update current prices for positions.

        Args:
            prices: Dict of symbol -> price
        """
        for position in self._positions.values():
            if position.symbol in prices:
                new_price = prices[position.symbol]
                position.current_price = new_price

                # Recalculate unrealized PnL
                if position.entry_price > 0:
                    price_change = new_price - position.entry_price
                    if position.side == "long":
                        position.unrealized_pnl = position.size * price_change
                    else:
                        position.unrealized_pnl = -position.size * price_change

                    # Update notional
                    position.notional_usd = position.size * new_price

        self._last_update = datetime.utcnow()

    def update_position_price(
        self,
        symbol: str,
        price: float,
        token_id: Optional[str] = None,
    ) -> None:
        """Update price for a single position.

        Args:
            symbol: Position symbol
            price: New price
            token_id: Token ID
        """
        position = self.get_position(symbol, token_id)
        if position:
            position.current_price = price
            if position.entry_price > 0:
                price_change = price - position.entry_price
                if position.side == "long":
                    position.unrealized_pnl = position.size * price_change
                else:
                    position.unrealized_pnl = -position.size * price_change
                position.notional_usd = position.size * price
            position.updated_at = datetime.utcnow()

    # =========================================================================
    # PnL Tracking
    # =========================================================================

    def record_realized_pnl(self, pnl: float) -> None:
        """Record realized PnL.

        Args:
            pnl: Realized PnL amount
        """
        self._daily_pnl += pnl
        logger.debug(f"Recorded PnL ${pnl:.2f}, daily total: ${self._daily_pnl:.2f}")

    def record_volume(self, volume: float) -> None:
        """Record trading volume.

        Args:
            volume: Volume in USD
        """
        self._daily_volume += volume

    def reset_daily_stats(self) -> None:
        """Reset daily counters (call at day boundary)."""
        self._daily_pnl = 0
        self._daily_volume = 0
        logger.info(f"Reset daily stats for {self.venue}")

    # =========================================================================
    # Pending Orders
    # =========================================================================

    def set_pending_orders_value(self, value: float) -> None:
        """Set total value of pending orders.

        Args:
            value: Total pending order value in USD
        """
        self._pending_orders_value = value

    @property
    def pending_orders_value(self) -> float:
        """Get pending orders value."""
        return self._pending_orders_value

    # =========================================================================
    # Exposure by Category
    # =========================================================================

    def get_exposure_by_asset_class(self) -> Dict[str, float]:
        """Get exposure breakdown by asset class.

        Returns:
            Dict of asset_class -> exposure
        """
        by_asset: Dict[str, float] = {}
        for position in self._positions.values():
            key = position.asset_class.value
            by_asset[key] = by_asset.get(key, 0) + abs(position.notional_usd)
        return by_asset

    def get_exposure_by_symbol(self) -> Dict[str, float]:
        """Get exposure breakdown by symbol.

        Returns:
            Dict of symbol -> exposure
        """
        by_symbol: Dict[str, float] = {}
        for position in self._positions.values():
            by_symbol[position.symbol] = by_symbol.get(position.symbol, 0) + abs(
                position.notional_usd
            )
        return by_symbol

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> Dict:
        """Serialize for reporting.

        Returns:
            Dict representation
        """
        return {
            "venue": self.venue,
            "total_exposure_usd": round(self.total_exposure_usd, 2),
            "long_exposure_usd": round(self.long_exposure_usd, 2),
            "short_exposure_usd": round(self.short_exposure_usd, 2),
            "net_exposure_usd": round(self.net_exposure_usd, 2),
            "net_delta": round(self.net_delta, 4),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_volume": round(self._daily_volume, 2),
            "position_count": self.position_count,
            "pending_orders_value": round(self._pending_orders_value, 2),
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }

    def __repr__(self) -> str:
        return (
            f"<VenueExposure {self.venue} "
            f"exposure=${self.total_exposure_usd:.2f} "
            f"positions={self.position_count}>"
        )
