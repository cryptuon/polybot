"""Binance Spot unified connector.

Combines REST and WebSocket clients into a single interface.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from polybot.exchanges.base import BaseExchangeConnector, ExchangeType, MarketType
from polybot.exchanges.binance.auth import BinanceAuth
from polybot.exchanges.binance.clients.spot import BinanceSpotRestClient
from polybot.exchanges.binance.clients.spot_ws import BinanceSpotWebSocket
from polybot.exchanges.binance.config import BinanceSpotConfig
from polybot.exchanges.binance.rate_limiter import BinanceRateLimiter

logger = logging.getLogger(__name__)


class BinanceSpotConnector(BaseExchangeConnector):
    """Unified Binance Spot connector with REST + WebSocket.

    Provides a unified interface for:
    - REST API calls for trading and account data
    - WebSocket streams for real-time market data
    - Automatic reconnection and error handling

    Example:
        connector = BinanceSpotConnector()
        await connector.start()

        # Subscribe to real-time prices
        async def on_ticker(data):
            print(f"Price update: {data}")

        await connector.subscribe_ticker(["BTCUSDT"], on_ticker)

        # Place an order
        result = await connector.place_order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            quantity=0.001,
            price=50000.0,
        )

        await connector.stop()
    """

    exchange_type = ExchangeType.BINANCE
    market_type = MarketType.SPOT

    def __init__(self, config: Optional[BinanceSpotConfig] = None) -> None:
        """Initialize Binance Spot connector.

        Args:
            config: Spot configuration (loaded from env if not provided)
        """
        self._config = config or BinanceSpotConfig()
        self._auth = BinanceAuth(
            self._config.api_key,
            self._config.api_secret,
            self._config.recv_window,
        )
        self._rate_limiter = BinanceRateLimiter()

        self._rest_client: Optional[BinanceSpotRestClient] = None
        self._ws_client: Optional[BinanceSpotWebSocket] = None
        self._running = False

        # Callbacks for subscriptions
        self._ticker_callbacks: Dict[str, List[Callable[[Dict[str, Any]], Any]]] = {}
        self._orderbook_callbacks: Dict[str, List[Callable[[Dict[str, Any]], Any]]] = {}
        self._trade_callbacks: Dict[str, List[Callable[[Dict[str, Any]], Any]]] = {}

        # Message processing task
        self._process_task: Optional[asyncio.Task[Any]] = None

    @property
    def is_authenticated(self) -> bool:
        """Check if API credentials are configured."""
        return self._auth.has_credentials

    async def start(self) -> None:
        """Start the connector."""
        if self._running:
            return

        self._running = True

        # Initialize REST client
        self._rest_client = BinanceSpotRestClient(
            self._config, self._auth, self._rate_limiter
        )
        await self._rest_client.open()

        # Initialize WebSocket client
        self._ws_client = BinanceSpotWebSocket(self._config)
        await self._ws_client.connect()

        # Start message processor
        self._process_task = asyncio.create_task(self._process_ws_messages())

        logger.info(
            f"Binance Spot connector started (testnet={self._config.testnet})"
        )

    async def stop(self) -> None:
        """Stop the connector."""
        self._running = False

        # Stop message processor
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
            self._process_task = None

        # Close WebSocket
        if self._ws_client:
            await self._ws_client.disconnect()
            self._ws_client = None

        # Close REST client
        if self._rest_client:
            await self._rest_client.close()
            self._rest_client = None

        # Clear callbacks
        self._ticker_callbacks.clear()
        self._orderbook_callbacks.clear()
        self._trade_callbacks.clear()

        logger.info("Binance Spot connector stopped")

    # =========================================================================
    # REST Methods - Pricing
    # =========================================================================

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get 24hr ticker for symbol.

        Args:
            symbol: Trading symbol (e.g., BTCUSDT)

        Returns:
            Ticker data
        """
        if not self._rest_client:
            raise RuntimeError("Connector not started")
        return await self._rest_client.get_ticker(symbol)

    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get orderbook for symbol.

        Args:
            symbol: Trading symbol
            limit: Depth limit

        Returns:
            Orderbook with bids and asks
        """
        if not self._rest_client:
            raise RuntimeError("Connector not started")
        result = await self._rest_client.get_orderbook(symbol, limit)
        result["symbol"] = symbol
        return result

    async def get_price(self, symbol: str) -> float:
        """Get current price for symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Current price
        """
        if not self._rest_client:
            raise RuntimeError("Connector not started")
        result = await self._rest_client.get_ticker_price(symbol)
        return float(result.get("price", 0))

    # =========================================================================
    # REST Methods - Orders
    # =========================================================================

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
            price: Order price (required for LIMIT)
            **kwargs: Additional parameters

        Returns:
            Order response
        """
        if not self._rest_client:
            raise RuntimeError("Connector not started")

        return await self._rest_client.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            **kwargs,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Cancel an order.

        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        if not self._rest_client:
            raise RuntimeError("Connector not started")
        return await self._rest_client.cancel_order(symbol, int(order_id))

    async def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Get order status.

        Args:
            symbol: Trading symbol
            order_id: Order ID

        Returns:
            Order details
        """
        if not self._rest_client:
            raise RuntimeError("Connector not started")
        return await self._rest_client.get_order(symbol, int(order_id))

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open orders
        """
        if not self._rest_client:
            raise RuntimeError("Connector not started")
        return await self._rest_client.get_open_orders(symbol)

    # =========================================================================
    # REST Methods - Account
    # =========================================================================

    async def get_account(self) -> Dict[str, Any]:
        """Get account information.

        Returns:
            Account data including balances
        """
        if not self._rest_client:
            raise RuntimeError("Connector not started")
        return await self._rest_client.get_account()

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get positions (non-zero balances for spot).

        Returns:
            List of non-zero balances as "positions"
        """
        account = await self.get_account()
        balances = account.get("balances", [])
        return [
            b for b in balances
            if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0
        ]

    async def get_balance(self, asset: str) -> Dict[str, Any]:
        """Get balance for a specific asset.

        Args:
            asset: Asset symbol (e.g., BTC, USDT)

        Returns:
            Balance info with free and locked amounts
        """
        account = await self.get_account()
        balances = account.get("balances", [])
        for b in balances:
            if b.get("asset") == asset:
                return b
        return {"asset": asset, "free": "0", "locked": "0"}

    # =========================================================================
    # WebSocket Methods - Subscriptions
    # =========================================================================

    async def subscribe_ticker(
        self,
        symbols: List[str],
        callback: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """Subscribe to ticker updates.

        Args:
            symbols: List of symbols
            callback: Function to call with updates
        """
        if not self._ws_client:
            raise RuntimeError("Connector not started")

        await self._ws_client.subscribe_ticker(symbols)

        for symbol in symbols:
            symbol_upper = symbol.upper()
            if symbol_upper not in self._ticker_callbacks:
                self._ticker_callbacks[symbol_upper] = []
            self._ticker_callbacks[symbol_upper].append(callback)

    async def subscribe_orderbook(
        self,
        symbols: List[str],
        callback: Callable[[Dict[str, Any]], Any],
        depth: int = 10,
    ) -> None:
        """Subscribe to orderbook updates.

        Args:
            symbols: List of symbols
            callback: Function to call with updates
            depth: Orderbook depth (5, 10, 20)
        """
        if not self._ws_client:
            raise RuntimeError("Connector not started")

        await self._ws_client.subscribe_depth(symbols, depth)

        for symbol in symbols:
            symbol_upper = symbol.upper()
            if symbol_upper not in self._orderbook_callbacks:
                self._orderbook_callbacks[symbol_upper] = []
            self._orderbook_callbacks[symbol_upper].append(callback)

    async def subscribe_trades(
        self,
        symbols: List[str],
        callback: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """Subscribe to trade updates.

        Args:
            symbols: List of symbols
            callback: Function to call with updates
        """
        if not self._ws_client:
            raise RuntimeError("Connector not started")

        await self._ws_client.subscribe_trades(symbols)

        for symbol in symbols:
            symbol_upper = symbol.upper()
            if symbol_upper not in self._trade_callbacks:
                self._trade_callbacks[symbol_upper] = []
            self._trade_callbacks[symbol_upper].append(callback)

    async def _process_ws_messages(self) -> None:
        """Process WebSocket messages and dispatch to callbacks."""
        if not self._ws_client:
            return

        async for msg in self._ws_client.messages():
            if not self._running:
                break

            try:
                event_type = msg.get("e", "")
                symbol = msg.get("s", "").upper()

                if event_type == "24hrTicker":
                    callbacks = self._ticker_callbacks.get(symbol, [])
                    for callback in callbacks:
                        await self._safe_callback(callback, msg)

                elif event_type == "depthUpdate":
                    callbacks = self._orderbook_callbacks.get(symbol, [])
                    for callback in callbacks:
                        await self._safe_callback(callback, msg)

                elif event_type == "trade":
                    callbacks = self._trade_callbacks.get(symbol, [])
                    for callback in callbacks:
                        await self._safe_callback(callback, msg)

            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")

    async def _safe_callback(
        self,
        callback: Callable[[Dict[str, Any]], Any],
        data: Dict[str, Any],
    ) -> None:
        """Safely execute callback."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as e:
            logger.error(f"Callback error: {e}")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def ping(self) -> bool:
        """Test connectivity.

        Returns:
            True if connected
        """
        if not self._rest_client:
            return False
        try:
            await self._rest_client.ping()
            return True
        except Exception:
            return False

    def get_rate_limit_status(self) -> Dict[str, Dict[str, float]]:
        """Get rate limit status.

        Returns:
            Rate limit utilization by type
        """
        return self._rate_limiter.get_status()
