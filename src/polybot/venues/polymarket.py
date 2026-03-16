"""Polymarket venue implementation.

Wraps the existing PolymarketClient to implement the BaseVenue interface.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from polybot.core.client import PolymarketClient
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
    VenueCapabilities,
    VenueType,
    VENUE_CAPABILITIES,
)

logger = logging.getLogger(__name__)


class PolymarketVenue(BaseVenue):
    """Polymarket venue implementation.

    Wraps the existing PolymarketClient to provide a unified venue interface.
    Supports prediction markets with binary outcomes (YES/NO tokens).
    """

    venue_type = VenueType.POLYMARKET

    def __init__(self, settings: Any = None) -> None:
        """Initialize Polymarket venue.

        Args:
            settings: Application settings
        """
        super().__init__(settings)
        self._client: Optional[PolymarketClient] = None
        self._price_callbacks: Dict[str, List[Callable[[Ticker], None]]] = {}
        self._markets_cache: Dict[str, Dict[str, Any]] = {}

    def get_capabilities(self) -> VenueCapabilities:
        """Get Polymarket capabilities."""
        return VENUE_CAPABILITIES[VenueType.POLYMARKET]

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def connect(self) -> None:
        """Connect to Polymarket APIs."""
        if self._connected:
            return

        self._client = PolymarketClient()
        self._connected = True
        logger.info("Connected to Polymarket")

    async def disconnect(self) -> None:
        """Disconnect from Polymarket."""
        if self._client:
            await self._client.close()
            self._client = None
        self._connected = False
        self._price_callbacks.clear()
        logger.info("Disconnected from Polymarket")

    # =========================================================================
    # Market Data
    # =========================================================================

    async def get_markets(self, market_type: Optional[MarketType] = None) -> List[Market]:
        """Get available prediction markets.

        Args:
            market_type: Ignored for Polymarket (only has prediction markets)

        Returns:
            List of prediction markets
        """
        if not self._client:
            raise RuntimeError("Not connected")

        raw_markets = await self._client.get_markets(limit=500)
        markets = []

        for m in raw_markets:
            market = Market(
                symbol=m.get("condition_id", ""),
                venue=VenueType.POLYMARKET,
                market_type=MarketType.PREDICTION,
                description=m.get("question", ""),
                is_active=not m.get("closed", False),
                metadata={
                    "event_id": m.get("event_id"),
                    "tokens": m.get("tokens", []),
                    "volume": m.get("volume"),
                    "liquidity": m.get("liquidity"),
                },
            )
            markets.append(market)
            self._markets_cache[market.symbol] = m

        return markets

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker for a market.

        For Polymarket, we get the orderbook and calculate bid/ask from it.

        Args:
            symbol: Market condition ID or token ID

        Returns:
            Ticker with bid/ask prices
        """
        if not self._client:
            raise RuntimeError("Not connected")

        # Try to get orderbook for the token
        try:
            book = await self._client.get_orderbook(symbol)

            # Extract best bid/ask from orderbook
            best_bid = 0.0
            best_ask = 1.0

            bids = book.get("bids", [])
            asks = book.get("asks", [])

            if bids:
                best_bid = float(bids[0].get("price", 0))
            if asks:
                best_ask = float(asks[0].get("price", 1))

            return Ticker(
                symbol=symbol,
                venue=VenueType.POLYMARKET,
                bid=best_bid,
                ask=best_ask,
                timestamp=datetime.utcnow(),
            )
        except Exception as e:
            logger.warning(f"Failed to get orderbook for {symbol}: {e}")
            # Return default ticker if orderbook fails
            return Ticker(
                symbol=symbol,
                venue=VenueType.POLYMARKET,
                bid=0.0,
                ask=1.0,
            )

    async def subscribe_prices(
        self,
        symbols: List[str],
        callback: Callable[[Ticker], None],
    ) -> None:
        """Subscribe to price updates.

        Note: Polymarket doesn't have native WebSocket price feeds in our client,
        so this stores the callback for manual polling-based updates.

        Args:
            symbols: List of token IDs to subscribe to
            callback: Function to call with price updates
        """
        for symbol in symbols:
            if symbol not in self._price_callbacks:
                self._price_callbacks[symbol] = []
            self._price_callbacks[symbol].append(callback)

    async def unsubscribe_prices(self, symbols: List[str]) -> None:
        """Unsubscribe from price updates."""
        for symbol in symbols:
            self._price_callbacks.pop(symbol, None)

    # =========================================================================
    # Trading
    # =========================================================================

    async def place_order(self, order: Order) -> OrderResult:
        """Place an order on Polymarket.

        Args:
            order: Order to place

        Returns:
            OrderResult with status
        """
        if not self._client:
            raise RuntimeError("Not connected")

        # Shadow mode - simulate without submitting
        if self._shadow_mode:
            return OrderResult(
                success=True,
                order_id=f"shadow_{order.symbol}_{datetime.utcnow().timestamp()}",
                client_order_id=order.client_order_id,
                status=OrderStatus.FILLED,
                filled_size=order.size,
                filled_price=order.price,
                venue=VenueType.POLYMARKET,
            )

        try:
            # Convert order side
            side_str = "BUY" if order.side == OrderSide.BUY else "SELL"

            result = await self._client.place_order(
                token_id=order.symbol,
                side=side_str,
                price=order.price or 0.5,
                size=order.size,
            )

            return OrderResult(
                success=True,
                order_id=result.get("orderID", result.get("id", "")),
                client_order_id=order.client_order_id,
                status=OrderStatus.OPEN,
                venue=VenueType.POLYMARKET,
                raw_response=result,
            )
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return OrderResult(
                success=False,
                error=str(e),
                venue=VenueType.POLYMARKET,
            )

    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel
            symbol: Not used for Polymarket

        Returns:
            True if cancelled successfully
        """
        if not self._client:
            raise RuntimeError("Not connected")

        if self._shadow_mode:
            return True

        try:
            await self._client.cancel_order(order_id)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_order(self, order_id: str, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get order details.

        Args:
            order_id: Order ID
            symbol: Not used for Polymarket

        Returns:
            Order details or None
        """
        if not self._client:
            raise RuntimeError("Not connected")

        orders = await self._client.get_orders()
        for order in orders:
            if order.get("id") == order_id or order.get("orderID") == order_id:
                return order
        return None

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders.

        Args:
            symbol: Optional filter by token ID

        Returns:
            List of open orders
        """
        if not self._client:
            raise RuntimeError("Not connected")

        orders = await self._client.get_orders()

        if symbol:
            orders = [o for o in orders if o.get("asset_id") == symbol]

        return orders

    # =========================================================================
    # Positions & Account
    # =========================================================================

    async def get_positions(self) -> List[Position]:
        """Get open positions.

        Returns:
            List of positions
        """
        if not self._client:
            raise RuntimeError("Not connected")

        raw_positions = await self._client.get_positions()
        positions = []

        for p in raw_positions:
            size = float(p.get("size", 0))
            if abs(size) < 0.001:
                continue  # Skip dust

            entry_price = float(p.get("avgPrice", 0) or 0)
            current_price = float(p.get("curPrice", entry_price) or entry_price)

            position = Position(
                symbol=p.get("asset", ""),
                venue=VenueType.POLYMARKET,
                side="long" if size > 0 else "short",
                size=abs(size),
                entry_price=entry_price,
                current_price=current_price,
                unrealized_pnl=float(p.get("unrealizedPnl", 0) or 0),
                realized_pnl=float(p.get("realizedPnl", 0) or 0),
            )
            positions.append(position)

        return positions

    async def get_balance(self, currency: Optional[str] = None) -> Balance:
        """Get account balance.

        For Polymarket, returns USDC balance estimated from positions.

        Args:
            currency: Ignored (Polymarket uses USDC)

        Returns:
            Balance information
        """
        if not self._client:
            raise RuntimeError("Not connected")

        # Polymarket doesn't have a direct balance endpoint
        # Estimate from positions
        positions = await self._client.get_positions()

        total_value = sum(
            float(p.get("size", 0)) * float(p.get("curPrice", 0) or 0)
            for p in positions
        )

        return Balance(
            venue=VenueType.POLYMARKET,
            currency="USDC",
            total=total_value,
            available=total_value,  # Approximation
            locked=0,
        )
