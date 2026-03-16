"""State service.

Responsible for:
- Managing internal state (markets, orders, positions, trades)
- Providing centralized access to SQLite database
- Answering state queries from other services and API
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from polybot.config import Settings
from polybot.core.nng import NNGReplier
from polybot.db.sqlite_store import SQLiteStore
from polybot.models.market import Market
from polybot.models.order import Order, OrderSide, OrderStatus, OrderType
from polybot.models.position import Position, PositionStatus
from polybot.models.trade import Trade
from polybot.services.base import BaseService


logger = logging.getLogger(__name__)


class StateService(BaseService):
    """State management service."""

    name = "state"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._replier: Optional[NNGReplier] = None
        self._sqlite: Optional[SQLiteStore] = None

    async def _on_start(self) -> None:
        """Initialize state service resources."""
        # Initialize database
        self._sqlite = SQLiteStore()
        await self._sqlite.connect()

        # Initialize NNG replier for handling queries
        self._replier = NNGReplier(self._settings.nng.state_address)
        await self._replier.open()

    async def _on_stop(self) -> None:
        """Cleanup state service resources."""
        if self._replier:
            await self._replier.close()

        if self._sqlite:
            await self._sqlite.close()

    async def _run(self) -> None:
        """Main state service loop."""
        # Start request handler
        await self._handle_requests()

    async def _handle_requests(self) -> None:
        """Handle state queries via REQ/REP."""
        if not self._replier:
            return

        async for msg in self._replier.requests():
            if not self._running:
                break

            try:
                query_type = msg.get("query_type", "")
                params = msg.get("params", {})

                result = await self._execute_query(query_type, params)
                await self._replier.reply({"success": True, "data": result})

            except Exception as e:
                self._logger.error(f"Query error: {e}")
                await self._replier.reply({"success": False, "error": str(e)})

    async def _execute_query(
        self,
        query_type: str,
        params: Dict[str, Any],
    ) -> Any:
        """Execute a state query.

        Args:
            query_type: Type of query
            params: Query parameters

        Returns:
            Query result
        """
        if not self._sqlite:
            raise RuntimeError("Database not connected")

        # Market queries
        if query_type == "get_market":
            market = await self._sqlite.get_market(params.get("market_id", ""))
            return self._market_to_dict(market) if market else None

        elif query_type == "get_active_markets":
            markets = await self._sqlite.get_active_markets(
                limit=params.get("limit", 100)
            )
            return [self._market_to_dict(m) for m in markets]

        elif query_type == "save_market":
            market = self._dict_to_market(params.get("market", {}))
            await self._sqlite.save_market(market)
            return True

        # Order queries
        elif query_type == "get_order":
            order = await self._sqlite.get_order(params.get("order_id", ""))
            return self._order_to_dict(order) if order else None

        elif query_type == "get_orders":
            orders = await self._sqlite.get_orders(
                strategy=params.get("strategy"),
                status=params.get("status"),
                limit=params.get("limit", 100),
            )
            return [self._order_to_dict(o) for o in orders]

        elif query_type == "get_open_orders":
            orders = await self._sqlite.get_open_orders(
                strategy=params.get("strategy")
            )
            return [self._order_to_dict(o) for o in orders]

        elif query_type == "save_order":
            order = self._dict_to_order(params.get("order", {}))
            await self._sqlite.save_order(order)
            return True

        # Position queries
        elif query_type == "get_position":
            position = await self._sqlite.get_position(params.get("position_id", 0))
            return self._position_to_dict(position) if position else None

        elif query_type == "get_positions":
            positions = await self._sqlite.get_positions(
                strategy=params.get("strategy"),
                status=params.get("status"),
                limit=params.get("limit", 100),
            )
            return [self._position_to_dict(p) for p in positions]

        elif query_type == "get_open_positions":
            positions = await self._sqlite.get_open_positions(
                strategy=params.get("strategy")
            )
            return [self._position_to_dict(p) for p in positions]

        elif query_type == "save_position":
            position = self._dict_to_position(params.get("position", {}))
            position_id = await self._sqlite.save_position(position)
            return position_id

        elif query_type == "close_position":
            position = await self._sqlite.close_position(
                position_id=params.get("position_id", 0),
                exit_price=params.get("exit_price", 0),
            )
            return self._position_to_dict(position) if position else None

        # Trade queries
        elif query_type == "get_trades":
            trades = await self._sqlite.get_trades(
                strategy=params.get("strategy"),
                market_id=params.get("market_id"),
                limit=params.get("limit", 100),
            )
            return [self._trade_to_dict(t) for t in trades]

        elif query_type == "save_trade":
            trade = self._dict_to_trade(params.get("trade", {}))
            await self._sqlite.save_trade(trade)
            return True

        # Strategy config queries
        elif query_type == "get_strategy_config":
            return await self._sqlite.get_strategy_config(params.get("name", ""))

        elif query_type == "save_strategy_config":
            await self._sqlite.save_strategy_config(
                name=params.get("name", ""),
                enabled=params.get("enabled", False),
                config=params.get("config", {}),
                shadow=params.get("shadow", False),
            )
            return True

        else:
            raise ValueError(f"Unknown query type: {query_type}")

    # =========================================================================
    # Serialization helpers
    # =========================================================================

    def _market_to_dict(self, market: Market) -> Dict[str, Any]:
        """Convert Market to dict for serialization."""
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
        """Convert Order to dict for serialization."""
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
        """Convert Position to dict for serialization."""
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
        """Convert Trade to dict for serialization."""
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
