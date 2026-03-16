"""Binance Spot REST API client."""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from polybot.exchanges.base import BaseRestClient
from polybot.exchanges.binance.auth import BinanceAuth
from polybot.exchanges.binance.config import BinanceSpotConfig
from polybot.exchanges.binance.rate_limiter import BinanceRateLimiter

logger = logging.getLogger(__name__)


class BinanceSpotRestClient(BaseRestClient):
    """Binance Spot REST API client.

    Provides async methods for interacting with Binance Spot API.
    Handles authentication, rate limiting, and error handling.
    """

    def __init__(
        self,
        config: Optional[BinanceSpotConfig] = None,
        auth: Optional[BinanceAuth] = None,
        rate_limiter: Optional[BinanceRateLimiter] = None,
    ) -> None:
        """Initialize Binance Spot REST client.

        Args:
            config: Spot API configuration
            auth: Authentication handler
            rate_limiter: Rate limiter
        """
        self._config = config or BinanceSpotConfig()
        self._auth = auth or BinanceAuth(
            self._config.api_key,
            self._config.api_secret,
            self._config.recv_window,
        )
        self._rate_limiter = rate_limiter or BinanceRateLimiter()
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def base_url(self) -> str:
        """Get base URL for REST API."""
        return self._config.rest_url

    async def open(self) -> None:
        """Open HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            logger.info(f"Binance Spot client opened (testnet={self._config.testnet})")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            logger.info("Binance Spot client closed")

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
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request body
            signed: Whether to sign the request

        Returns:
            Response data

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        if self._http_client is None:
            await self.open()

        # Rate limit
        await self._rate_limiter.acquire_for_endpoint(endpoint)

        # Build URL
        url = f"{self.base_url}{endpoint}"

        # Prepare headers
        headers = {}
        if signed or data:
            headers = self._auth.get_headers()

        # Sign if needed
        if signed:
            if params:
                params = self._auth.sign_params(params)
            elif data:
                data = self._auth.sign_params(data)
            else:
                params = self._auth.sign_params({})

        # Make request
        response = await self._http_client.request(
            method=method,
            url=url,
            params=params,
            data=urlencode(data) if data else None,
            headers=headers,
        )

        # Update rate limiter from headers
        self._rate_limiter.update_from_headers(dict(response.headers))

        # Handle errors
        response.raise_for_status()

        return response.json()

    # =========================================================================
    # Public Endpoints
    # =========================================================================

    async def ping(self) -> Dict[str, Any]:
        """Test connectivity to the API."""
        return await self.request("GET", "/api/v3/ping")

    async def get_server_time(self) -> Dict[str, Any]:
        """Get server time."""
        return await self.request("GET", "/api/v3/time")

    async def get_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get exchange information.

        Args:
            symbol: Optional symbol to filter

        Returns:
            Exchange info with rate limits and symbols
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self.request("GET", "/api/v3/exchangeInfo", params=params or None)

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get 24hr ticker for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Ticker data
        """
        return await self.request(
            "GET", "/api/v3/ticker/24hr", params={"symbol": symbol}
        )

    async def get_ticker_price(self, symbol: Optional[str] = None) -> Any:
        """Get latest price(s).

        Args:
            symbol: Optional symbol (returns all if not specified)

        Returns:
            Price data
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self.request("GET", "/api/v3/ticker/price", params=params or None)

    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get orderbook for a symbol.

        Args:
            symbol: Trading symbol
            limit: Depth limit (5, 10, 20, 50, 100, 500, 1000, 5000)

        Returns:
            Orderbook with bids and asks
        """
        return await self.request(
            "GET", "/api/v3/depth", params={"symbol": symbol, "limit": limit}
        )

    async def get_trades(self, symbol: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Get recent trades.

        Args:
            symbol: Trading symbol
            limit: Number of trades (max 1000)

        Returns:
            List of recent trades
        """
        return await self.request(
            "GET", "/api/v3/trades", params={"symbol": symbol, "limit": limit}
        )

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
    ) -> List[List[Any]]:
        """Get kline/candlestick data.

        Args:
            symbol: Trading symbol
            interval: Kline interval (1m, 5m, 1h, 1d, etc.)
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
            limit: Number of klines (max 1000)

        Returns:
            List of klines
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return await self.request("GET", "/api/v3/klines", params=params)

    # =========================================================================
    # Trading Endpoints (require authentication)
    # =========================================================================

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Optional[float] = None,
        quote_order_qty: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: str = "GTC",
        new_client_order_id: Optional[str] = None,
        stop_price: Optional[float] = None,
        iceberg_qty: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Place a new order.

        Args:
            symbol: Trading symbol
            side: BUY or SELL
            order_type: LIMIT, MARKET, STOP_LOSS, etc.
            quantity: Order quantity
            quote_order_qty: Quote asset quantity (for MARKET orders)
            price: Order price (for LIMIT orders)
            time_in_force: GTC, IOC, FOK
            new_client_order_id: Client order ID
            stop_price: Stop price (for stop orders)
            iceberg_qty: Iceberg quantity
            **kwargs: Additional parameters

        Returns:
            Order response
        """
        # Rate limit for orders
        await self._rate_limiter.acquire_order()

        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
        }

        if quantity is not None:
            params["quantity"] = quantity
        if quote_order_qty is not None:
            params["quoteOrderQty"] = quote_order_qty
        if price is not None:
            params["price"] = price
        if order_type == "LIMIT":
            params["timeInForce"] = time_in_force
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        if stop_price is not None:
            params["stopPrice"] = stop_price
        if iceberg_qty is not None:
            params["icebergQty"] = iceberg_qty

        params.update(kwargs)

        return await self.request("POST", "/api/v3/order", data=params, signed=True)

    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel an order.

        Args:
            symbol: Trading symbol
            order_id: Order ID
            orig_client_order_id: Original client order ID

        Returns:
            Cancellation response
        """
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id

        return await self.request("DELETE", "/api/v3/order", params=params, signed=True)

    async def cancel_all_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Cancel all open orders for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            List of cancelled orders
        """
        return await self.request(
            "DELETE", "/api/v3/openOrders", params={"symbol": symbol}, signed=True
        )

    async def get_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get order status.

        Args:
            symbol: Trading symbol
            order_id: Order ID
            orig_client_order_id: Original client order ID

        Returns:
            Order details
        """
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id

        return await self.request("GET", "/api/v3/order", params=params, signed=True)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open orders
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self.request(
            "GET", "/api/v3/openOrders", params=params or None, signed=True
        )

    async def get_all_orders(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Get all orders (active, canceled, filled).

        Args:
            symbol: Trading symbol
            order_id: Start from this order ID
            start_time: Start time filter
            end_time: End time filter
            limit: Number of orders (max 1000)

        Returns:
            List of orders
        """
        params: Dict[str, Any] = {"symbol": symbol, "limit": limit}
        if order_id:
            params["orderId"] = order_id
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return await self.request("GET", "/api/v3/allOrders", params=params, signed=True)

    # =========================================================================
    # Account Endpoints
    # =========================================================================

    async def get_account(self) -> Dict[str, Any]:
        """Get account information.

        Returns:
            Account data including balances
        """
        return await self.request("GET", "/api/v3/account", signed=True)

    async def get_my_trades(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        from_id: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Get account trade history.

        Args:
            symbol: Trading symbol
            order_id: Filter by order ID
            start_time: Start time filter
            end_time: End time filter
            from_id: Trade ID to fetch from
            limit: Number of trades (max 1000)

        Returns:
            List of trades
        """
        params: Dict[str, Any] = {"symbol": symbol, "limit": limit}
        if order_id:
            params["orderId"] = order_id
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        if from_id:
            params["fromId"] = from_id

        return await self.request("GET", "/api/v3/myTrades", params=params, signed=True)
