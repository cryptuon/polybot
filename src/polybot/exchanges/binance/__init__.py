"""Binance exchange connectors.

Provides REST and WebSocket clients for:
- Spot trading
- USDM Perpetual Futures
- Options (VOPTIONS)
"""

from polybot.exchanges.binance.auth import BinanceAuth
from polybot.exchanges.binance.config import (
    BinanceFuturesConfig,
    BinanceOptionsConfig,
    BinanceSpotConfig,
)
from polybot.exchanges.binance.models.common import (
    BinanceOrder,
    BinanceOrderBook,
    BinanceTicker,
)
from polybot.exchanges.binance.rate_limiter import BinanceRateLimiter
from polybot.exchanges.binance.clients.spot import BinanceSpotRestClient
from polybot.exchanges.binance.clients.spot_ws import BinanceSpotWebSocket
from polybot.exchanges.binance.connectors.spot_connector import BinanceSpotConnector

__all__ = [
    # Config
    "BinanceSpotConfig",
    "BinanceFuturesConfig",
    "BinanceOptionsConfig",
    # Auth
    "BinanceAuth",
    # Rate Limiter
    "BinanceRateLimiter",
    # Models
    "BinanceTicker",
    "BinanceOrderBook",
    "BinanceOrder",
    # Clients
    "BinanceSpotRestClient",
    "BinanceSpotWebSocket",
    # Connectors
    "BinanceSpotConnector",
]
