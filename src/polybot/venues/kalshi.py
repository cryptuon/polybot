"""Kalshi venue implementation (stub).

Kalshi is a CFTC-regulated prediction market. This is a stub implementation
that will be completed when compliance review is approved.

Note: Kalshi requires additional compliance review before live trading.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from polybot.venues.base import (
    Balance,
    BaseVenue,
    Market,
    Order,
    OrderResult,
    Position,
    Ticker,
)
from polybot.venues.types import (
    MarketType,
    OrderStatus,
    VenueCapabilities,
    VenueType,
    VENUE_CAPABILITIES,
)

logger = logging.getLogger(__name__)


class KalshiVenue(BaseVenue):
    """Kalshi venue implementation (stub).

    This is a placeholder implementation for the CFTC-regulated Kalshi
    prediction market. Full implementation requires:

    1. Compliance review and approval
    2. Kalshi API credentials (api_key, api_secret)
    3. Testing on Kalshi demo environment

    Kalshi-specific considerations:
    - CFTC-regulated, requires KYC verification
    - USD settlement (not crypto)
    - Different market structure than Polymarket
    - Rate limits and API restrictions apply
    """

    venue_type = VenueType.KALSHI

    def __init__(self, settings: Any = None) -> None:
        """Initialize Kalshi venue.

        Args:
            settings: Application settings
        """
        super().__init__(settings)
        self._compliance_approved = False

        # Check if compliance is approved in settings
        if settings:
            kalshi_config = getattr(settings, "kalshi", None)
            if kalshi_config:
                self._compliance_approved = getattr(
                    kalshi_config, "compliance_approved", False
                )

    def get_capabilities(self) -> VenueCapabilities:
        """Get Kalshi capabilities."""
        return VENUE_CAPABILITIES[VenueType.KALSHI]

    def _check_compliance(self) -> None:
        """Check if compliance review is approved."""
        if not self._compliance_approved:
            raise RuntimeError(
                "Kalshi requires compliance review before trading. "
                "Set KALSHI_COMPLIANCE_APPROVED=true after review."
            )

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def connect(self) -> None:
        """Connect to Kalshi API.

        Raises:
            RuntimeError: If compliance not approved
            NotImplementedError: Stub not yet implemented
        """
        self._check_compliance()

        # TODO: Implement Kalshi API connection
        # - Initialize REST client with api_key/api_secret
        # - Authenticate and get session token
        # - Initialize WebSocket for real-time data
        raise NotImplementedError(
            "Kalshi venue not yet implemented. "
            "See https://kalshi.com/docs/api for API documentation."
        )

    async def disconnect(self) -> None:
        """Disconnect from Kalshi."""
        self._connected = False
        logger.info("Disconnected from Kalshi")

    # =========================================================================
    # Market Data (stubs)
    # =========================================================================

    async def get_markets(self, market_type: Optional[MarketType] = None) -> List[Market]:
        """Get available Kalshi markets."""
        raise NotImplementedError("Kalshi get_markets not implemented")

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker for a Kalshi market."""
        raise NotImplementedError("Kalshi get_ticker not implemented")

    async def subscribe_prices(
        self,
        symbols: List[str],
        callback: Callable[[Ticker], None],
    ) -> None:
        """Subscribe to Kalshi price updates."""
        raise NotImplementedError("Kalshi subscribe_prices not implemented")

    # =========================================================================
    # Trading (stubs)
    # =========================================================================

    async def place_order(self, order: Order) -> OrderResult:
        """Place an order on Kalshi."""
        self._check_compliance()

        if self._shadow_mode:
            return OrderResult(
                success=True,
                order_id=f"kalshi_shadow_{order.symbol}",
                status=OrderStatus.FILLED,
                filled_size=order.size,
                filled_price=order.price,
                venue=VenueType.KALSHI,
            )

        raise NotImplementedError("Kalshi place_order not implemented")

    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Cancel a Kalshi order."""
        raise NotImplementedError("Kalshi cancel_order not implemented")

    async def get_order(self, order_id: str, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get Kalshi order details."""
        raise NotImplementedError("Kalshi get_order not implemented")

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open Kalshi orders."""
        raise NotImplementedError("Kalshi get_open_orders not implemented")

    # =========================================================================
    # Positions & Account (stubs)
    # =========================================================================

    async def get_positions(self) -> List[Position]:
        """Get Kalshi positions."""
        raise NotImplementedError("Kalshi get_positions not implemented")

    async def get_balance(self, currency: Optional[str] = None) -> Balance:
        """Get Kalshi account balance."""
        raise NotImplementedError("Kalshi get_balance not implemented")
