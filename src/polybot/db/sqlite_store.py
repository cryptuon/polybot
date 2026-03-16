"""SQLite store for object data.

Handles storage of markets, orders, positions, trades, and strategy configs.

Implements the StateStore interface for database abstraction.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from polybot.config import get_settings
from polybot.db.state_store import StateStore
from polybot.models.market import Market
from polybot.models.order import Order, OrderStatus
from polybot.models.position import Position, PositionStatus
from polybot.models.trade import Trade


logger = logging.getLogger(__name__)

SCHEMA = """
-- Markets
CREATE TABLE IF NOT EXISTS markets (
    id TEXT PRIMARY KEY,
    condition_id TEXT NOT NULL,
    question TEXT,
    slug TEXT,
    description TEXT,
    outcome_yes_token TEXT,
    outcome_no_token TEXT,
    yes_price REAL,
    no_price REAL,
    volume REAL,
    volume_24h REAL,
    liquidity REAL,
    active INTEGER DEFAULT 1,
    closed INTEGER DEFAULT 0,
    resolved INTEGER DEFAULT 0,
    resolution TEXT,
    end_date TEXT,
    event_id TEXT,
    tags TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Orders
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    market_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL NOT NULL,
    size REAL NOT NULL,
    order_type TEXT DEFAULT 'GTC',
    status TEXT DEFAULT 'PENDING',
    filled_size REAL DEFAULT 0,
    average_fill_price REAL,
    strategy TEXT,
    order_hash TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    filled_at TEXT,
    cancelled_at TEXT,
    FOREIGN KEY (market_id) REFERENCES markets(id)
);

-- Positions
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    side TEXT NOT NULL,
    size REAL NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL,
    status TEXT DEFAULT 'OPEN',
    realized_pnl REAL DEFAULT 0,
    unrealized_pnl REAL,
    strategy TEXT,
    opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    exit_price REAL,
    FOREIGN KEY (market_id) REFERENCES markets(id)
);

-- Trades
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    order_id TEXT,
    market_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL NOT NULL,
    size REAL NOT NULL,
    fee REAL DEFAULT 0,
    notional REAL NOT NULL,
    strategy TEXT,
    is_maker INTEGER DEFAULT 0,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (market_id) REFERENCES markets(id)
);

-- Strategy configurations
CREATE TABLE IF NOT EXISTS strategy_configs (
    name TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    shadow INTEGER DEFAULT 0,
    config TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tracked wallets (for copy trading)
CREATE TABLE IF NOT EXISTS wallets (
    address TEXT PRIMARY KEY,
    label TEXT,
    is_whale INTEGER DEFAULT 0,
    tracked INTEGER DEFAULT 0,
    balance REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_orders_market ON orders(market_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_strategy ON orders(strategy);
CREATE INDEX IF NOT EXISTS idx_positions_market ON positions(market_id);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_trades_market ON trades(market_id);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_markets_active ON markets(active);
"""


class SQLiteStore(StateStore):
    """SQLite implementation of the state store."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize the store.

        Args:
            db_path: Path to SQLite database file
        """
        settings = get_settings()
        self._db_path = db_path or settings.database.sqlite_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Connect to database and initialize schema."""
        # Ensure directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row

        # Initialize schema
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

        # Run migrations for existing databases
        await self._run_migrations()

        logger.info(f"Connected to SQLite database: {self._db_path}")

    async def _run_migrations(self) -> None:
        """Run database migrations for schema updates.

        This handles adding new columns to existing tables that were created
        before the column was added to the schema.
        """
        if not self._conn:
            return

        # Get existing columns in strategy_configs
        async with self._conn.execute("PRAGMA table_info(strategy_configs)") as cursor:
            columns = await cursor.fetchall()
            column_names = {col["name"] for col in columns}

        # Add shadow column if missing
        if "shadow" not in column_names:
            logger.info("Migrating strategy_configs: adding shadow column")
            await self._conn.execute(
                "ALTER TABLE strategy_configs ADD COLUMN shadow INTEGER DEFAULT 0"
            )
            await self._conn.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def __aenter__(self) -> "SQLiteStore":
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # =========================================================================
    # Markets
    # =========================================================================

    async def save_market(self, market: Market) -> None:
        """Save or update a market."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO markets (
                id, condition_id, question, slug, description,
                outcome_yes_token, outcome_no_token,
                yes_price, no_price, volume, volume_24h, liquidity,
                active, closed, resolved, resolution,
                end_date, event_id, tags, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                market.id,
                market.id,  # condition_id same as id
                market.question,
                market.slug,
                market.description,
                market.outcome_yes_token,
                market.outcome_no_token,
                market.yes_price,
                market.no_price,
                market.volume,
                market.volume_24h,
                market.liquidity,
                market.active,
                market.closed,
                market.resolved,
                market.resolution,
                market.end_date.isoformat() if market.end_date else None,
                market.event_id,
                json.dumps(market.tags),
                datetime.utcnow().isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_market(self, market_id: str) -> Optional[Market]:
        """Get a market by ID."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            "SELECT * FROM markets WHERE id = ?", (market_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_market(row)
            return None

    async def get_active_markets(self, limit: int = 100) -> List[Market]:
        """Get active markets."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            "SELECT * FROM markets WHERE active = 1 AND closed = 0 ORDER BY volume_24h DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_market(row) for row in rows]

    def _row_to_market(self, row: aiosqlite.Row) -> Market:
        """Convert database row to Market model."""
        return Market(
            id=row["id"],
            question=row["question"],
            slug=row["slug"],
            description=row["description"],
            outcome_yes_token=row["outcome_yes_token"],
            outcome_no_token=row["outcome_no_token"],
            yes_price=row["yes_price"],
            no_price=row["no_price"],
            volume=row["volume"],
            volume_24h=row["volume_24h"],
            liquidity=row["liquidity"],
            active=bool(row["active"]),
            closed=bool(row["closed"]),
            resolved=bool(row["resolved"]),
            resolution=row["resolution"],
            end_date=datetime.fromisoformat(row["end_date"]) if row["end_date"] else None,
            event_id=row["event_id"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
        )

    # =========================================================================
    # Orders
    # =========================================================================

    async def save_order(self, order: Order) -> None:
        """Save or update an order."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO orders (
                id, market_id, token_id, side, price, size, order_type,
                status, filled_size, average_fill_price, strategy,
                order_hash, error_message, created_at, updated_at,
                filled_at, cancelled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.id,
                order.market_id,
                order.token_id,
                order.side.value,
                order.price,
                order.size,
                order.order_type.value,
                order.status.value,
                order.filled_size,
                order.average_fill_price,
                order.strategy,
                order.order_hash,
                order.error_message,
                order.created_at.isoformat(),
                datetime.utcnow().isoformat(),
                order.filled_at.isoformat() if order.filled_at else None,
                order.cancelled_at.isoformat() if order.cancelled_at else None,
            ),
        )
        await self._conn.commit()

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_order(row)
            return None

    async def get_open_orders(
        self, strategy: Optional[str] = None
    ) -> List[Order]:
        """Get open orders, optionally filtered by strategy."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = "SELECT * FROM orders WHERE status IN ('PENDING', 'OPEN', 'MATCHED')"
        params: tuple[Any, ...] = ()

        if strategy:
            query += " AND strategy = ?"
            params = (strategy,)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_order(row) for row in rows]

    def _row_to_order(self, row: aiosqlite.Row) -> Order:
        """Convert database row to Order model."""
        from polybot.models.order import OrderSide, OrderStatus, OrderType

        return Order(
            id=row["id"],
            market_id=row["market_id"],
            token_id=row["token_id"],
            side=OrderSide(row["side"]),
            price=row["price"],
            size=row["size"],
            order_type=OrderType(row["order_type"]),
            status=OrderStatus(row["status"]),
            filled_size=row["filled_size"],
            average_fill_price=row["average_fill_price"],
            strategy=row["strategy"],
            order_hash=row["order_hash"],
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            filled_at=datetime.fromisoformat(row["filled_at"]) if row["filled_at"] else None,
            cancelled_at=datetime.fromisoformat(row["cancelled_at"]) if row["cancelled_at"] else None,
        )

    # =========================================================================
    # Positions
    # =========================================================================

    async def save_position(self, position: Position) -> int:
        """Save or update a position. Returns the position ID."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        if position.id:
            await self._conn.execute(
                """
                UPDATE positions SET
                    size = ?, current_price = ?, status = ?,
                    realized_pnl = ?, unrealized_pnl = ?,
                    closed_at = ?, exit_price = ?
                WHERE id = ?
                """,
                (
                    position.size,
                    position.current_price,
                    position.status.value,
                    position.realized_pnl,
                    position.unrealized_pnl,
                    position.closed_at.isoformat() if position.closed_at else None,
                    position.exit_price,
                    position.id,
                ),
            )
        else:
            cursor = await self._conn.execute(
                """
                INSERT INTO positions (
                    market_id, token_id, side, size, entry_price,
                    current_price, status, realized_pnl, unrealized_pnl,
                    strategy, opened_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    position.market_id,
                    position.token_id,
                    position.side,
                    position.size,
                    position.entry_price,
                    position.current_price,
                    position.status.value,
                    position.realized_pnl,
                    position.unrealized_pnl,
                    position.strategy,
                    position.opened_at.isoformat(),
                ),
            )
            position.id = cursor.lastrowid

        await self._conn.commit()
        return position.id or 0

    async def get_open_positions(
        self, strategy: Optional[str] = None
    ) -> List[Position]:
        """Get open positions."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = "SELECT * FROM positions WHERE status = 'OPEN'"
        params: tuple[Any, ...] = ()

        if strategy:
            query += " AND strategy = ?"
            params = (strategy,)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_position(row) for row in rows]

    def _row_to_position(self, row: aiosqlite.Row) -> Position:
        """Convert database row to Position model."""
        return Position(
            id=row["id"],
            market_id=row["market_id"],
            token_id=row["token_id"],
            side=row["side"],
            size=row["size"],
            entry_price=row["entry_price"],
            current_price=row["current_price"],
            status=PositionStatus(row["status"]),
            realized_pnl=row["realized_pnl"],
            unrealized_pnl=row["unrealized_pnl"],
            strategy=row["strategy"],
            opened_at=datetime.fromisoformat(row["opened_at"]),
            closed_at=datetime.fromisoformat(row["closed_at"]) if row["closed_at"] else None,
            exit_price=row["exit_price"],
        )

    # =========================================================================
    # Trades
    # =========================================================================

    async def save_trade(self, trade: Trade) -> None:
        """Save a trade record."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            INSERT INTO trades (
                id, order_id, market_id, token_id, side,
                price, size, fee, notional, strategy, is_maker, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.id,
                trade.order_id,
                trade.market_id,
                trade.token_id,
                trade.side.value,
                trade.price,
                trade.size,
                trade.fee,
                trade.notional,
                trade.strategy,
                trade.is_maker,
                trade.timestamp.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_trades(
        self,
        strategy: Optional[str] = None,
        market_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Trade]:
        """Get trades with optional filters."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = "SELECT * FROM trades WHERE 1=1"
        params: List[Any] = []

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        if market_id:
            query += " AND market_id = ?"
            params.append(market_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_trade(row) for row in rows]

    def _row_to_trade(self, row: aiosqlite.Row) -> Trade:
        """Convert database row to Trade model."""
        from polybot.models.order import OrderSide

        return Trade(
            id=row["id"],
            order_id=row["order_id"],
            market_id=row["market_id"],
            token_id=row["token_id"],
            side=OrderSide(row["side"]),
            price=row["price"],
            size=row["size"],
            fee=row["fee"],
            notional=row["notional"],
            strategy=row["strategy"],
            is_maker=bool(row["is_maker"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )

    # =========================================================================
    # Strategy Config
    # =========================================================================

    async def get_strategy_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get strategy configuration."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            "SELECT * FROM strategy_configs WHERE name = ?", (name,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "name": row["name"],
                    "enabled": bool(row["enabled"]),
                    "shadow": bool(row["shadow"]) if "shadow" in row.keys() else False,
                    "config": json.loads(row["config"]) if row["config"] else {},
                }
            return None

    async def save_strategy_config(
        self, name: str, enabled: bool, config: Dict[str, Any], shadow: bool = False
    ) -> None:
        """Save strategy configuration."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO strategy_configs (name, enabled, shadow, config, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, enabled, shadow, json.dumps(config), datetime.utcnow().isoformat()),
        )
        await self._conn.commit()

    # =========================================================================
    # Additional methods for StateStore interface
    # =========================================================================

    async def get_orders(
        self,
        strategy: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Order]:
        """Get orders with optional filters."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = "SELECT * FROM orders WHERE 1=1"
        params: List[Any] = []

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_order(row) for row in rows]

    async def get_position(self, position_id: int) -> Optional[Position]:
        """Get a position by ID."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            "SELECT * FROM positions WHERE id = ?", (position_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_position(row)
            return None

    async def get_positions(
        self,
        strategy: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Position]:
        """Get positions with optional filters."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = "SELECT * FROM positions WHERE 1=1"
        params: List[Any] = []

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY opened_at DESC LIMIT ?"
        params.append(limit)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_position(row) for row in rows]

    async def close_position(self, position_id: int, exit_price: float) -> Optional[Position]:
        """Close a position."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        # Get current position
        position = await self.get_position(position_id)
        if not position or position.status != PositionStatus.OPEN:
            return None

        # Calculate realized PnL
        if position.side == "BUY":
            realized_pnl = (exit_price - position.entry_price) * position.size
        else:
            realized_pnl = (position.entry_price - exit_price) * position.size

        # Update position
        now = datetime.utcnow()
        await self._conn.execute(
            """
            UPDATE positions SET
                status = ?, exit_price = ?, realized_pnl = ?,
                closed_at = ?
            WHERE id = ?
            """,
            (
                PositionStatus.CLOSED.value,
                exit_price,
                realized_pnl,
                now.isoformat(),
                position_id,
            ),
        )
        await self._conn.commit()

        # Return updated position
        return await self.get_position(position_id)


# Global store instance
_store: Optional[SQLiteStore] = None


async def get_sqlite_store() -> SQLiteStore:
    """Get the global SQLite store instance."""
    global _store
    if _store is None:
        _store = SQLiteStore()
        await _store.connect()
    return _store
