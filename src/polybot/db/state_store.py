"""Abstract state store interface.

This module defines the interface for internal state storage,
allowing different backends (SQLite, PostgreSQL, etc.) to be
used interchangeably.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from polybot.models.market import Market
from polybot.models.order import Order
from polybot.models.position import Position
from polybot.models.trade import Trade


class StateStore(ABC):
    """Abstract base class for internal state storage.

    Implementations can use SQLite, PostgreSQL, or other databases.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the database."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the database connection."""
        pass

    # =========================================================================
    # Markets
    # =========================================================================

    @abstractmethod
    async def save_market(self, market: Market) -> None:
        """Save or update a market.

        Args:
            market: Market to save
        """
        pass

    @abstractmethod
    async def get_market(self, market_id: str) -> Optional[Market]:
        """Get a market by ID.

        Args:
            market_id: Market ID

        Returns:
            Market or None if not found
        """
        pass

    @abstractmethod
    async def get_active_markets(self, limit: int = 100) -> List[Market]:
        """Get active markets.

        Args:
            limit: Maximum markets to return

        Returns:
            List of active markets
        """
        pass

    # =========================================================================
    # Orders
    # =========================================================================

    @abstractmethod
    async def save_order(self, order: Order) -> None:
        """Save or update an order.

        Args:
            order: Order to save
        """
        pass

    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID.

        Args:
            order_id: Order ID

        Returns:
            Order or None if not found
        """
        pass

    @abstractmethod
    async def get_open_orders(self, strategy: Optional[str] = None) -> List[Order]:
        """Get open orders.

        Args:
            strategy: Filter by strategy

        Returns:
            List of open orders
        """
        pass

    @abstractmethod
    async def get_orders(
        self,
        strategy: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Order]:
        """Get orders with optional filters.

        Args:
            strategy: Filter by strategy
            status: Filter by status
            limit: Maximum orders to return

        Returns:
            List of orders
        """
        pass

    # =========================================================================
    # Positions
    # =========================================================================

    @abstractmethod
    async def save_position(self, position: Position) -> int:
        """Save or update a position.

        Args:
            position: Position to save

        Returns:
            Position ID
        """
        pass

    @abstractmethod
    async def get_position(self, position_id: int) -> Optional[Position]:
        """Get a position by ID.

        Args:
            position_id: Position ID

        Returns:
            Position or None if not found
        """
        pass

    @abstractmethod
    async def get_open_positions(self, strategy: Optional[str] = None) -> List[Position]:
        """Get open positions.

        Args:
            strategy: Filter by strategy

        Returns:
            List of open positions
        """
        pass

    @abstractmethod
    async def get_positions(
        self,
        strategy: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Position]:
        """Get positions with optional filters.

        Args:
            strategy: Filter by strategy
            status: Filter by status
            limit: Maximum positions to return

        Returns:
            List of positions
        """
        pass

    @abstractmethod
    async def close_position(self, position_id: int, exit_price: float) -> Optional[Position]:
        """Close a position.

        Args:
            position_id: Position ID
            exit_price: Exit price

        Returns:
            Updated position or None if not found
        """
        pass

    # =========================================================================
    # Trades
    # =========================================================================

    @abstractmethod
    async def save_trade(self, trade: Trade) -> None:
        """Save a trade record.

        Args:
            trade: Trade to save
        """
        pass

    @abstractmethod
    async def get_trades(
        self,
        strategy: Optional[str] = None,
        market_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Trade]:
        """Get trades with optional filters.

        Args:
            strategy: Filter by strategy
            market_id: Filter by market
            limit: Maximum trades to return

        Returns:
            List of trades
        """
        pass

    # =========================================================================
    # Strategy Config
    # =========================================================================

    @abstractmethod
    async def get_strategy_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get strategy configuration.

        Args:
            name: Strategy name

        Returns:
            Config dict or None if not found
        """
        pass

    @abstractmethod
    async def save_strategy_config(
        self, name: str, enabled: bool, config: Dict[str, Any], shadow: bool = False
    ) -> None:
        """Save strategy configuration.

        Args:
            name: Strategy name
            enabled: Whether strategy is enabled
            config: Strategy config dict
            shadow: Whether to run in shadow mode (paper trading)
        """
        pass
