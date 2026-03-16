"""Base classes for exchange connectors."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional


class ExchangeType(str, Enum):
    """Supported exchange types."""

    BINANCE = "binance"
    # Future exchanges can be added here


class MarketType(str, Enum):
    """Market types within an exchange."""

    SPOT = "spot"
    FUTURES_PERPETUAL = "futures_perpetual"
    FUTURES_DELIVERY = "futures_delivery"
    OPTIONS = "options"


class ConnectionState(str, Enum):
    """WebSocket connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class BaseRestClient(ABC):
    """Abstract base for REST API clients."""

    @abstractmethod
    async def open(self) -> None:
        """Open the HTTP client."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the HTTP client."""
        ...

    @abstractmethod
    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """Make an API request.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            signed: Whether to sign the request

        Returns:
            Response data as dict
        """
        ...


class BaseWebSocketClient(ABC):
    """Abstract base for WebSocket clients."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish WebSocket connection."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        ...

    @abstractmethod
    async def subscribe(self, streams: List[str]) -> None:
        """Subscribe to streams.

        Args:
            streams: List of stream names to subscribe to
        """
        ...

    @abstractmethod
    async def unsubscribe(self, streams: List[str]) -> None:
        """Unsubscribe from streams.

        Args:
            streams: List of stream names to unsubscribe from
        """
        ...

    @abstractmethod
    async def messages(self) -> AsyncIterator[Dict[str, Any]]:
        """Async iterator for received messages.

        Yields:
            Message data as dict
        """
        ...


class BaseExchangeConnector(ABC):
    """Abstract base for exchange connectors.

    Provides a unified interface for interacting with an exchange,
    combining REST and WebSocket functionality.
    """

    exchange_type: ExchangeType
    market_type: MarketType

    @abstractmethod
    async def start(self) -> None:
        """Start the connector (initialize clients, connect)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the connector (cleanup, disconnect)."""
        ...

    # =========================================================================
    # Pricing
    # =========================================================================

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get ticker for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Ticker data
        """
        ...

    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get orderbook for a symbol.

        Args:
            symbol: Trading symbol
            limit: Depth limit

        Returns:
            Orderbook data with bids and asks
        """
        ...

    @abstractmethod
    async def subscribe_ticker(
        self,
        symbols: List[str],
        callback: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """Subscribe to ticker updates.

        Args:
            symbols: List of symbols to subscribe to
            callback: Function to call with updates
        """
        ...

    @abstractmethod
    async def subscribe_orderbook(
        self,
        symbols: List[str],
        callback: Callable[[Dict[str, Any]], Any],
        depth: int = 10,
    ) -> None:
        """Subscribe to orderbook updates.

        Args:
            symbols: List of symbols to subscribe to
            callback: Function to call with updates
            depth: Orderbook depth
        """
        ...

    # =========================================================================
    # Orders
    # =========================================================================

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Place an order.

        Args:
            symbol: Trading symbol
            side: BUY or SELL
            order_type: LIMIT, MARKET, etc.
            quantity: Order quantity
            price: Order price (for limit orders)
            **kwargs: Additional order parameters

        Returns:
            Order response
        """
        ...

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Cancel an order.

        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        ...

    @abstractmethod
    async def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Get order status.

        Args:
            symbol: Trading symbol
            order_id: Order ID

        Returns:
            Order details
        """
        ...

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open orders
        """
        ...

    # =========================================================================
    # Account
    # =========================================================================

    @abstractmethod
    async def get_account(self) -> Dict[str, Any]:
        """Get account information.

        Returns:
            Account data including balances
        """
        ...

    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get positions (for futures/options).

        Returns:
            List of positions
        """
        ...
