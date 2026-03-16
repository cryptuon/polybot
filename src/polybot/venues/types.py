"""Venue type definitions and capabilities."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class VenueType(str, Enum):
    """Supported trading venues."""

    POLYMARKET = "polymarket"  # Crypto prediction market (Polygon/USDC)
    BINANCE = "binance"  # CEX spot/futures/options
    KALSHI = "kalshi"  # CFTC-regulated prediction market
    OPINION = "opinion"  # DEX prediction protocol


class MarketType(str, Enum):
    """Types of markets within a venue."""

    PREDICTION = "prediction"  # Binary outcome markets
    SPOT = "spot"  # Spot trading
    PERPETUAL = "perpetual"  # Perpetual futures
    FUTURES = "futures"  # Dated futures
    OPTIONS = "options"  # Options


class OrderSide(str, Enum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type."""

    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(str, Enum):
    """Order status."""

    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class VenueCapabilities:
    """Capabilities of a trading venue."""

    supports_spot: bool = False
    supports_futures: bool = False
    supports_options: bool = False
    supports_prediction_markets: bool = False
    supports_websocket: bool = False
    supports_shadow_mode: bool = True
    requires_compliance_review: bool = False
    is_dex: bool = False
    settlement_currency: str = "USD"
    supported_market_types: List[MarketType] = field(default_factory=list)


# Pre-defined capabilities for each venue
VENUE_CAPABILITIES = {
    VenueType.POLYMARKET: VenueCapabilities(
        supports_prediction_markets=True,
        supports_websocket=True,
        supports_shadow_mode=True,
        settlement_currency="USDC",
        supported_market_types=[MarketType.PREDICTION],
    ),
    VenueType.BINANCE: VenueCapabilities(
        supports_spot=True,
        supports_futures=True,
        supports_options=True,
        supports_websocket=True,
        supports_shadow_mode=True,
        settlement_currency="USDT",
        supported_market_types=[
            MarketType.SPOT,
            MarketType.PERPETUAL,
            MarketType.FUTURES,
            MarketType.OPTIONS,
        ],
    ),
    VenueType.KALSHI: VenueCapabilities(
        supports_prediction_markets=True,
        supports_websocket=True,
        supports_shadow_mode=True,
        requires_compliance_review=True,
        settlement_currency="USD",
        supported_market_types=[MarketType.PREDICTION],
    ),
    VenueType.OPINION: VenueCapabilities(
        supports_prediction_markets=True,
        supports_websocket=False,
        supports_shadow_mode=True,
        is_dex=True,
        settlement_currency="ETH",
        supported_market_types=[MarketType.PREDICTION],
    ),
}
