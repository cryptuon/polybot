"""State client for querying the state service via NNG.

This client provides a simple interface for API routes and services
to query state data without directly connecting to the database.
All queries are routed through the state service via IPC.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from polybot.config import get_settings
from polybot.core.nng import NNGRequester
from polybot.models.market import Market
from polybot.models.order import Order, OrderSide, OrderStatus, OrderType
from polybot.models.position import Position, PositionStatus
from polybot.models.trade import Trade


logger = logging.getLogger(__name__)


class StateClient:
    """Client for querying the state service.

    Uses NNG REQ/REP pattern to send queries to the state service
    and receive responses. This avoids direct database access.
    """

    def __init__(self) -> None:
        """Initialize the client."""
        self._settings = get_settings()
        self._requester: Optional[NNGRequester] = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to the state service."""
        if self._connected:
            return

        self._requester = NNGRequester(self._settings.nng.state_address)
        await self._requester.open()
        self._connected = True
        logger.info("State client connected")

    async def close(self) -> None:
        """Close the connection."""
        if self._requester:
            await self._requester.close()
            self._requester = None
            self._connected = False

    async def _query(self, query_type: str, params: Dict[str, Any]) -> Any:
        """Execute a query against the state service.

        Args:
            query_type: Type of query to execute
            params: Query parameters

        Returns:
            Query result

        Raises:
            RuntimeError: If not connected or query fails
        """
        if not self._connected or not self._requester:
            await self.connect()

        request = {
            "query_type": query_type,
            "params": params,
        }

        try:
            response = await self._requester.request(request)

            if not response.get("success"):
                error = response.get("error", "Unknown error")
                raise RuntimeError(f"State query failed: {error}")

            return response.get("data")

        except Exception as e:
            logger.error(f"State query error: {e}")
            raise

    # =========================================================================
    # Markets
    # =========================================================================

    async def get_market(self, market_id: str) -> Optional[Market]:
        """Get a market by ID."""
        data = await self._query("get_market", {"market_id": market_id})
        return self._dict_to_market(data) if data else None

    async def get_active_markets(self, limit: int = 100) -> List[Market]:
        """Get active markets."""
        data = await self._query("get_active_markets", {"limit": limit})
        return [self._dict_to_market(m) for m in data] if data else []

    async def save_market(self, market: Market) -> None:
        """Save or update a market."""
        await self._query("save_market", {"market": self._market_to_dict(market)})

    # =========================================================================
    # Orders
    # =========================================================================

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        data = await self._query("get_order", {"order_id": order_id})
        return self._dict_to_order(data) if data else None

    async def get_orders(
        self,
        strategy: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Order]:
        """Get orders with optional filters."""
        data = await self._query("get_orders", {
            "strategy": strategy,
            "status": status,
            "limit": limit,
        })
        return [self._dict_to_order(o) for o in data] if data else []

    async def get_open_orders(self, strategy: Optional[str] = None) -> List[Order]:
        """Get open orders."""
        data = await self._query("get_open_orders", {"strategy": strategy})
        return [self._dict_to_order(o) for o in data] if data else []

    async def save_order(self, order: Order) -> None:
        """Save or update an order."""
        if not isinstance(order, Order):
            raise TypeError(f"Expected Order object, got {type(order).__name__}: {order}")
        await self._query("save_order", {"order": self._order_to_dict(order)})

    # =========================================================================
    # Positions
    # =========================================================================

    async def get_position(self, position_id: int) -> Optional[Position]:
        """Get a position by ID."""
        data = await self._query("get_position", {"position_id": position_id})
        return self._dict_to_position(data) if data else None

    async def get_positions(
        self,
        strategy: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Position]:
        """Get positions with optional filters."""
        data = await self._query("get_positions", {
            "strategy": strategy,
            "status": status,
            "limit": limit,
        })
        return [self._dict_to_position(p) for p in data] if data else []

    async def get_open_positions(self, strategy: Optional[str] = None) -> List[Position]:
        """Get open positions."""
        data = await self._query("get_open_positions", {"strategy": strategy})
        return [self._dict_to_position(p) for p in data] if data else []

    async def save_position(self, position: Position) -> int:
        """Save or update a position. Returns position ID."""
        return await self._query("save_position", {"position": self._position_to_dict(position)})

    async def close_position(self, position_id: int, exit_price: float) -> Optional[Position]:
        """Close a position."""
        data = await self._query("close_position", {
            "position_id": position_id,
            "exit_price": exit_price,
        })
        return self._dict_to_position(data) if data else None

    # =========================================================================
    # Trades
    # =========================================================================

    async def get_trades(
        self,
        strategy: Optional[str] = None,
        market_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Trade]:
        """Get trades with optional filters."""
        data = await self._query("get_trades", {
            "strategy": strategy,
            "market_id": market_id,
            "limit": limit,
        })
        return [self._dict_to_trade(t) for t in data] if data else []

    async def save_trade(self, trade: Trade) -> None:
        """Save a trade record."""
        await self._query("save_trade", {"trade": self._trade_to_dict(trade)})

    # =========================================================================
    # Strategy Config
    # =========================================================================

    async def get_strategy_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get strategy configuration."""
        return await self._query("get_strategy_config", {"name": name})

    async def save_strategy_config(
        self, name: str, enabled: bool, config: Dict[str, Any], shadow: bool = False
    ) -> None:
        """Save strategy configuration.

        Args:
            name: Strategy name
            enabled: Whether strategy is enabled
            config: Strategy-specific configuration
            shadow: Whether to run in shadow mode (generate signals but don't execute)
        """
        await self._query("save_strategy_config", {
            "name": name,
            "enabled": enabled,
            "shadow": shadow,
            "config": config,
        })

    # =========================================================================
    # Serialization helpers
    # =========================================================================

    def _market_to_dict(self, market: Market) -> Dict[str, Any]:
        """Convert Market to dict."""
        return {
            "id": market.id,
            "question": market.question,
            "slug": market.slug,
            "description": market.description,
            "outcome_yes_token": market.outcome_yes_token,
            "outcome_no_token": market.outcome_no_token,
            "yes_price": market.yes_price,
            "no_price": market.no_price,
            "volume": market.volume,
            "volume_24h": market.volume_24h,
            "liquidity": market.liquidity,
            "active": market.active,
            "closed": market.closed,
            "resolved": market.resolved,
            "resolution": market.resolution,
            "end_date": market.end_date.isoformat() if market.end_date else None,
            "event_id": market.event_id,
            "tags": market.tags,
        }

    def _dict_to_market(self, data: Dict[str, Any]) -> Market:
        """Convert dict to Market."""
        return Market(
            id=data.get("id", ""),
            question=data.get("question"),
            slug=data.get("slug"),
            description=data.get("description"),
            outcome_yes_token=data.get("outcome_yes_token"),
            outcome_no_token=data.get("outcome_no_token"),
            yes_price=data.get("yes_price"),
            no_price=data.get("no_price"),
            volume=data.get("volume"),
            volume_24h=data.get("volume_24h"),
            liquidity=data.get("liquidity"),
            active=data.get("active", True),
            closed=data.get("closed", False),
            resolved=data.get("resolved", False),
            resolution=data.get("resolution"),
            end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            event_id=data.get("event_id"),
            tags=data.get("tags", []),
        )

    def _order_to_dict(self, order: Order) -> Dict[str, Any]:
        """Convert Order to dict."""
        return {
            "id": order.id,
            "market_id": order.market_id,
            "token_id": order.token_id,
            "side": order.side.value,
            "price": order.price,
            "size": order.size,
            "order_type": order.order_type.value,
            "status": order.status.value,
            "filled_size": order.filled_size,
            "average_fill_price": order.average_fill_price,
            "strategy": order.strategy,
            "order_hash": order.order_hash,
            "error_message": order.error_message,
            "created_at": order.created_at.isoformat(),
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
        }

    def _dict_to_order(self, data: Dict[str, Any]) -> Order:
        """Convert dict to Order."""
        return Order(
            id=data.get("id", ""),
            market_id=data.get("market_id", ""),
            token_id=data.get("token_id", ""),
            side=OrderSide(data.get("side", "BUY")),
            price=data.get("price", 0),
            size=data.get("size", 0),
            order_type=OrderType(data.get("order_type", "GTC")),
            status=OrderStatus(data.get("status", "PENDING")),
            filled_size=data.get("filled_size", 0),
            average_fill_price=data.get("average_fill_price"),
            strategy=data.get("strategy"),
            order_hash=data.get("order_hash"),
            error_message=data.get("error_message"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            filled_at=datetime.fromisoformat(data["filled_at"]) if data.get("filled_at") else None,
            cancelled_at=datetime.fromisoformat(data["cancelled_at"]) if data.get("cancelled_at") else None,
        )

    def _position_to_dict(self, position: Position) -> Dict[str, Any]:
        """Convert Position to dict."""
        return {
            "id": position.id,
            "market_id": position.market_id,
            "token_id": position.token_id,
            "side": position.side,
            "size": position.size,
            "entry_price": position.entry_price,
            "current_price": position.current_price,
            "status": position.status.value,
            "realized_pnl": position.realized_pnl,
            "unrealized_pnl": position.unrealized_pnl,
            "strategy": position.strategy,
            "opened_at": position.opened_at.isoformat(),
            "closed_at": position.closed_at.isoformat() if position.closed_at else None,
            "exit_price": position.exit_price,
        }

    def _dict_to_position(self, data: Dict[str, Any]) -> Position:
        """Convert dict to Position."""
        return Position(
            id=data.get("id"),
            market_id=data.get("market_id", ""),
            token_id=data.get("token_id", ""),
            side=data.get("side", "BUY"),
            size=data.get("size", 0),
            entry_price=data.get("entry_price", 0),
            current_price=data.get("current_price"),
            status=PositionStatus(data.get("status", "OPEN")),
            realized_pnl=data.get("realized_pnl", 0),
            unrealized_pnl=data.get("unrealized_pnl"),
            strategy=data.get("strategy"),
            opened_at=datetime.fromisoformat(data["opened_at"]) if data.get("opened_at") else datetime.utcnow(),
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            exit_price=data.get("exit_price"),
        )

    def _trade_to_dict(self, trade: Trade) -> Dict[str, Any]:
        """Convert Trade to dict."""
        return {
            "id": trade.id,
            "order_id": trade.order_id,
            "market_id": trade.market_id,
            "token_id": trade.token_id,
            "side": trade.side.value,
            "price": trade.price,
            "size": trade.size,
            "fee": trade.fee,
            "notional": trade.notional,
            "strategy": trade.strategy,
            "is_maker": trade.is_maker,
            "timestamp": trade.timestamp.isoformat(),
        }

    def _dict_to_trade(self, data: Dict[str, Any]) -> Trade:
        """Convert dict to Trade."""
        return Trade(
            id=data.get("id", ""),
            order_id=data.get("order_id"),
            market_id=data.get("market_id", ""),
            token_id=data.get("token_id", ""),
            side=OrderSide(data.get("side", "BUY")),
            price=data.get("price", 0),
            size=data.get("size", 0),
            fee=data.get("fee", 0),
            notional=data.get("notional", 0),
            strategy=data.get("strategy"),
            is_maker=data.get("is_maker", False),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.utcnow(),
        )


# Module-level client instance for dependency injection
_client: Optional[StateClient] = None


async def get_state_client() -> StateClient:
    """Get or create the state client singleton.

    Returns:
        Connected state client
    """
    global _client
    if _client is None:
        _client = StateClient()
        await _client.connect()
    return _client
