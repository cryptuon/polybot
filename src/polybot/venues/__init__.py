"""Multi-venue abstraction layer.

This module provides a unified interface for interacting with different
trading venues (Polymarket, Binance, Kalshi, Opinion).

Usage:
    from polybot.venues import get_venue, VenueType

    # Get a venue instance
    venue = get_venue(VenueType.POLYMARKET, settings)
    await venue.connect()

    # Use unified interface
    ticker = await venue.get_ticker("BTC-USDT")
    await venue.place_order(order)
"""

from typing import Any, Dict, Optional, Type

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
    OrderSide,
    OrderStatus,
    OrderType,
    VenueCapabilities,
    VenueType,
    VENUE_CAPABILITIES,
)

# Venue registry - maps VenueType to implementation class
# Implementations are registered lazily to avoid circular imports
_VENUE_REGISTRY: Dict[VenueType, Type[BaseVenue]] = {}


def register_venue(venue_type: VenueType, venue_class: Type[BaseVenue]) -> None:
    """Register a venue implementation.

    Args:
        venue_type: Type of venue
        venue_class: Implementation class
    """
    _VENUE_REGISTRY[venue_type] = venue_class


def get_venue(venue_type: VenueType, settings: Optional[Any] = None) -> BaseVenue:
    """Factory function to get a venue instance.

    Args:
        venue_type: Type of venue to create
        settings: Application settings

    Returns:
        Venue instance

    Raises:
        ValueError: If venue type is not registered
    """
    # Lazy import to avoid circular imports
    _ensure_venues_registered()

    if venue_type not in _VENUE_REGISTRY:
        raise ValueError(f"Venue type not registered: {venue_type}")

    venue_class = _VENUE_REGISTRY[venue_type]
    return venue_class(settings)


def get_registered_venues() -> Dict[VenueType, Type[BaseVenue]]:
    """Get all registered venue types and their implementations."""
    _ensure_venues_registered()
    return _VENUE_REGISTRY.copy()


def is_venue_registered(venue_type: VenueType) -> bool:
    """Check if a venue type is registered."""
    _ensure_venues_registered()
    return venue_type in _VENUE_REGISTRY


def _ensure_venues_registered() -> None:
    """Ensure all venue implementations are registered."""
    if _VENUE_REGISTRY:
        return

    # Import and register implementations
    from polybot.venues.polymarket import PolymarketVenue
    from polybot.venues.kalshi import KalshiVenue
    from polybot.venues.opinion import OpinionVenue

    register_venue(VenueType.POLYMARKET, PolymarketVenue)
    register_venue(VenueType.KALSHI, KalshiVenue)
    register_venue(VenueType.OPINION, OpinionVenue)

    # Binance is optional - only register if exchanges module exists
    try:
        from polybot.venues.binance import BinanceVenue
        register_venue(VenueType.BINANCE, BinanceVenue)
    except ImportError:
        pass  # Binance not yet implemented


__all__ = [
    # Types
    "VenueType",
    "MarketType",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "VenueCapabilities",
    "VENUE_CAPABILITIES",
    # Base classes
    "BaseVenue",
    "Ticker",
    "Market",
    "Order",
    "OrderResult",
    "Position",
    "Balance",
    # Functions
    "get_venue",
    "register_venue",
    "get_registered_venues",
    "is_venue_registered",
]
