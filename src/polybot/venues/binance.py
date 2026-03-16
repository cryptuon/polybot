"""Binance venue implementation.

Wraps the Binance exchange connectors to implement the BaseVenue interface.
Supports spot, perpetual futures, and options markets.
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


class BinanceVenue(BaseVenue):
    """Binance venue implementation.

    Wraps the Binance exchange connectors (spot, futures, options) to provide
    a unified venue interface. This class delegates to the appropriate
    connector based on the market type.

    Configuration:
    - BINANCE_API_KEY: API key
    - BINANCE_API_SECRET: API secret
    - BINANCE_TESTNET: Use testnet (default: true for safety)
    - BINANCE_SPOT_ENABLED: Enable spot trading
    - BINANCE_FUTURES_ENABLED: Enable futures trading
    - BINANCE_OPTIONS_ENABLED: Enable options trading
    """

    venue_type = VenueType.BINANCE

    def __init__(self, settings: Any = None) -> None:
        """Initialize Binance venue.

        Args:
            settings: Application settings
        """
        super().__init__(settings)

        # Connector instances (lazy initialized)
        self._spot_connector = None
        self._futures_connector = None
        self._options_connector = None

        # Configuration
        self._testnet = True
        self._spot_enabled = True
        self._futures_enabled = False
        self._options_enabled = False

        # Load config from settings
        if settings:
            binance_config = getattr(settings, "binance", None)
            if binance_config:
                self._testnet = getattr(binance_config, "testnet", True)
                self._spot_enabled = getattr(binance_config, "spot_enabled", True)
                self._futures_enabled = getattr(binance_config, "futures_enabled", False)
                self._options_enabled = getattr(binance_config, "options_enabled", False)

    def get_capabilities(self) -> VenueCapabilities:
        """Get Binance capabilities."""
        caps = VENUE_CAPABILITIES[VenueType.BINANCE]
        # Adjust based on what's enabled
        return VenueCapabilities(
            supports_spot=self._spot_enabled,
            supports_futures=self._futures_enabled,
            supports_options=self._options_enabled,
            supports_prediction_markets=False,
            supports_websocket=True,
            supports_shadow_mode=True,
            settlement_currency="USDT",
            supported_market_types=[
                mt for mt in caps.supported_market_types
                if (mt == MarketType.SPOT and self._spot_enabled)
                or (mt == MarketType.PERPETUAL and self._futures_enabled)
                or (mt == MarketType.FUTURES and self._futures_enabled)
                or (mt == MarketType.OPTIONS and self._options_enabled)
            ],
        )

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def connect(self) -> None:
        """Connect to Binance APIs.

        Initializes the appropriate connectors based on configuration.
        """
        if self._connected:
            return

        try:
            # Import connectors here to avoid circular imports
            # and allow graceful failure if not implemented yet
            if self._spot_enabled:
                try:
                    from polybot.exchanges.binance.connectors.spot_connector import (
                        BinanceSpotConnector,
                    )
                    self._spot_connector = BinanceSpotConnector()
                    await self._spot_connector.start()
                    logger.info("Binance spot connector started")
                except ImportError:
                    logger.warning(
                        "Binance spot connector not yet implemented. "
                        "Run in shadow mode only."
                    )

            if self._futures_enabled:
                try:
                    from polybot.exchanges.binance.connectors.futures_connector import (
                        BinanceFuturesConnector,
                    )
                    self._futures_connector = BinanceFuturesConnector()
                    await self._futures_connector.start()
                    logger.info("Binance futures connector started")
                except ImportError:
                    logger.warning("Binance futures connector not yet implemented")

            if self._options_enabled:
                try:
                    from polybot.exchanges.binance.connectors.options_connector import (
                        BinanceOptionsConnector,
                    )
                    self._options_connector = BinanceOptionsConnector()
                    await self._options_connector.start()
                    logger.info("Binance options connector started")
                except ImportError:
                    logger.warning("Binance options connector not yet implemented")

            self._connected = True
            logger.info(
                f"Connected to Binance (testnet={self._testnet}, "
                f"spot={self._spot_enabled}, futures={self._futures_enabled}, "
                f"options={self._options_enabled})"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Binance: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Binance."""
        if self._spot_connector:
            await self._spot_connector.stop()
            self._spot_connector = None

        if self._futures_connector:
            await self._futures_connector.stop()
            self._futures_connector = None

        if self._options_connector:
            await self._options_connector.stop()
            self._options_connector = None

        self._connected = False
        logger.info("Disconnected from Binance")

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_markets(self, market_type: Optional[MarketType] = None) -> List[Market]:
        """Get available Binance markets.

        Args:
            market_type: Filter by market type (SPOT, PERPETUAL, OPTIONS)

        Returns:
            List of available markets
        """
        markets = []

        if (market_type is None or market_type == MarketType.SPOT) and self._spot_connector:
            # TODO: Implement when connector is ready
            pass

        if (market_type is None or market_type == MarketType.PERPETUAL) and self._futures_connector:
            # TODO: Implement when connector is ready
            pass

        if (market_type is None or market_type == MarketType.OPTIONS) and self._options_connector:
            # TODO: Implement when connector is ready
            pass

        return markets

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker for a Binance symbol.

        Args:
            symbol: Trading symbol (e.g., BTCUSDT)

        Returns:
            Ticker with bid/ask prices
        """
        if self._spot_connector:
            ticker_data = await self._spot_connector.get_ticker(symbol)
            return Ticker(
                symbol=symbol,
                venue=VenueType.BINANCE,
                bid=float(ticker_data.get("bidPrice", 0)),
                ask=float(ticker_data.get("askPrice", 0)),
                last=float(ticker_data.get("lastPrice", 0)),
                volume_24h=float(ticker_data.get("volume", 0)),
            )

        raise RuntimeError("No connector available for ticker")

    async def subscribe_prices(
        self,
        symbols: List[str],
        callback: Callable[[Ticker], None],
    ) -> None:
        """Subscribe to real-time price updates.

        Args:
            symbols: List of symbols to subscribe to
            callback: Function to call with price updates
        """
        if self._spot_connector:
            # Convert callback to connector format
            async def ticker_callback(data: Dict[str, Any]) -> None:
                ticker = Ticker(
                    symbol=data.get("s", ""),
                    venue=VenueType.BINANCE,
                    bid=float(data.get("b", 0)),
                    ask=float(data.get("a", 0)),
                    last=float(data.get("c", 0)),
                )
                callback(ticker)

            await self._spot_connector.subscribe_ticker(symbols, ticker_callback)

    # =========================================================================
    # Trading
    # =========================================================================

    async def place_order(self, order: Order) -> OrderResult:
        """Place an order on Binance.

        Args:
            order: Order to place

        Returns:
            OrderResult with status
        """
        if self._shadow_mode:
            return OrderResult(
                success=True,
                order_id=f"binance_shadow_{order.symbol}",
                client_order_id=order.client_order_id,
                status=OrderStatus.FILLED,
                filled_size=order.size,
                filled_price=order.price,
                venue=VenueType.BINANCE,
            )

        if self._spot_connector:
            result = await self._spot_connector.place_order(
                symbol=order.symbol,
                side=order.side.value.upper(),
                order_type=order.order_type.value.upper(),
                quantity=order.size,
                price=order.price,
            )

            return OrderResult(
                success=True,
                order_id=str(result.get("orderId", "")),
                client_order_id=result.get("clientOrderId"),
                status=OrderStatus.OPEN,
                venue=VenueType.BINANCE,
                raw_response=result,
            )

        raise RuntimeError("No connector available for order placement")

    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Cancel a Binance order.

        Args:
            order_id: Order ID to cancel
            symbol: Symbol (required for Binance)

        Returns:
            True if cancelled successfully
        """
        if not symbol:
            raise ValueError("Symbol required for Binance order cancellation")

        if self._spot_connector:
            try:
                await self._spot_connector.cancel_order(symbol, order_id)
                return True
            except Exception as e:
                logger.error(f"Failed to cancel order {order_id}: {e}")
                return False

        raise RuntimeError("No connector available for order cancellation")

    async def get_order(self, order_id: str, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get order details.

        Args:
            order_id: Order ID
            symbol: Symbol (required for Binance)

        Returns:
            Order details or None
        """
        if not symbol:
            raise ValueError("Symbol required for Binance order query")

        if self._spot_connector:
            return await self._spot_connector.get_order(symbol, order_id)

        return None

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open orders
        """
        if self._spot_connector:
            return await self._spot_connector.get_open_orders(symbol)

        return []

    # =========================================================================
    # Positions & Account
    # =========================================================================

    async def get_positions(self) -> List[Position]:
        """Get open positions.

        For spot, returns non-zero balances as "positions".
        For futures, returns actual positions.
        """
        positions = []

        if self._futures_connector:
            # TODO: Implement futures positions
            pass

        return positions

    async def get_balance(self, currency: Optional[str] = None) -> Balance:
        """Get account balance.

        Args:
            currency: Specific currency (default: USDT)

        Returns:
            Balance information
        """
        currency = currency or "USDT"

        if self._spot_connector:
            account = await self._spot_connector.get_account()
            balances = account.get("balances", [])

            for b in balances:
                if b.get("asset") == currency:
                    return Balance(
                        venue=VenueType.BINANCE,
                        currency=currency,
                        total=float(b.get("free", 0)) + float(b.get("locked", 0)),
                        available=float(b.get("free", 0)),
                        locked=float(b.get("locked", 0)),
                    )

        # Return empty balance if not found
        return Balance(
            venue=VenueType.BINANCE,
            currency=currency,
            total=0,
            available=0,
            locked=0,
        )
