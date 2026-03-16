"""DuckDB store for strategy execution logs.

Separate from the main analytics database to keep strategy logs
isolated and optimized for log queries.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import duckdb

from polybot.config import get_settings


logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Log levels for strategy logs."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SIGNAL = "SIGNAL"  # Special level for trading signals


class LogType(str, Enum):
    """Types of strategy log entries."""
    SCAN = "scan"           # Regular scan activity
    SIGNAL = "signal"       # Trading signal generated
    ENTRY = "entry"         # Position entry
    EXIT = "exit"           # Position exit
    ERROR = "error"         # Error occurred
    START = "start"         # Strategy started
    STOP = "stop"           # Strategy stopped
    CONFIG = "config"       # Configuration change


@dataclass
class StrategyLogEntry:
    """A single strategy log entry."""
    id: Optional[int]
    strategy: str
    timestamp: datetime
    log_type: LogType
    level: LogLevel
    message: str
    market_id: Optional[str] = None
    token_id: Optional[str] = None
    price: Optional[float] = None
    size: Optional[float] = None
    action: Optional[str] = None
    reason: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "strategy": self.strategy,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "log_type": self.log_type.value if self.log_type else None,
            "level": self.level.value if self.level else None,
            "message": self.message,
            "market_id": self.market_id,
            "token_id": self.token_id,
            "price": self.price,
            "size": self.size,
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class StrategyRunSummary:
    """Summary of a strategy run session."""
    id: Optional[int]
    strategy: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[float]
    scans_performed: int
    signals_generated: int
    entries: int
    exits: int
    errors: int
    status: str  # "running", "stopped", "error"


SCHEMA = """
-- Strategy log entries
CREATE TABLE IF NOT EXISTS strategy_logs (
    id INTEGER PRIMARY KEY,
    strategy VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    log_type VARCHAR NOT NULL,
    level VARCHAR NOT NULL,
    message TEXT NOT NULL,
    market_id VARCHAR,
    token_id VARCHAR,
    price DOUBLE,
    size DOUBLE,
    action VARCHAR,
    reason VARCHAR,
    confidence DOUBLE,
    metadata JSON
);

-- Strategy run sessions
CREATE TABLE IF NOT EXISTS strategy_runs (
    id INTEGER PRIMARY KEY,
    strategy VARCHAR NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    scans_performed INTEGER DEFAULT 0,
    signals_generated INTEGER DEFAULT 0,
    entries INTEGER DEFAULT 0,
    exits INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    status VARCHAR DEFAULT 'running',
    config JSON
);

-- Scan summaries (aggregated per minute to reduce log volume)
CREATE TABLE IF NOT EXISTS scan_summaries (
    strategy VARCHAR NOT NULL,
    minute TIMESTAMP NOT NULL,
    scan_count INTEGER DEFAULT 0,
    opportunities_found INTEGER DEFAULT 0,
    signals_generated INTEGER DEFAULT 0,
    avg_scan_duration_ms DOUBLE,
    PRIMARY KEY (strategy, minute)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_logs_strategy_time
    ON strategy_logs(strategy, timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_type
    ON strategy_logs(log_type);
CREATE INDEX IF NOT EXISTS idx_logs_level
    ON strategy_logs(level);
CREATE INDEX IF NOT EXISTS idx_runs_strategy
    ON strategy_runs(strategy, start_time);

-- Auto-increment sequence for logs
CREATE SEQUENCE IF NOT EXISTS strategy_logs_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS strategy_runs_id_seq START 1;
"""


class StrategyLogsStore:
    """DuckDB store for strategy execution logs."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize the store.

        Args:
            db_path: Path to DuckDB database file
        """
        settings = get_settings()
        self._db_path = db_path or settings.database.strategy_logs_path
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self, read_only: bool = False) -> None:
        """Connect to database and initialize schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self._db_path), read_only=read_only)

        if not read_only:
            self._conn.execute(SCHEMA)

        logger.info(f"Connected to strategy logs DB: {self._db_path}")

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def checkpoint(self) -> None:
        """Force a checkpoint to flush WAL."""
        if self._conn:
            self._conn.execute("CHECKPOINT")

    def __enter__(self) -> "StrategyLogsStore":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # =========================================================================
    # Log Entry Operations
    # =========================================================================

    def insert_log(self, entry: StrategyLogEntry) -> int:
        """Insert a log entry.

        Returns:
            The ID of the inserted log entry
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        result = self._conn.execute(
            """
            INSERT INTO strategy_logs (
                id, strategy, timestamp, log_type, level, message,
                market_id, token_id, price, size, action, reason, confidence, metadata
            ) VALUES (
                nextval('strategy_logs_id_seq'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            ) RETURNING id
            """,
            [
                entry.strategy,
                entry.timestamp,
                entry.log_type.value,
                entry.level.value,
                entry.message,
                entry.market_id,
                entry.token_id,
                entry.price,
                entry.size,
                entry.action,
                entry.reason,
                entry.confidence,
                entry.metadata,
            ],
        ).fetchone()

        return result[0] if result else 0

    def get_logs(
        self,
        strategy: Optional[str] = None,
        log_type: Optional[LogType] = None,
        level: Optional[LogLevel] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        market_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[StrategyLogEntry]:
        """Query strategy logs.

        Args:
            strategy: Filter by strategy name
            log_type: Filter by log type
            level: Filter by log level
            start_time: Start of time range
            end_time: End of time range
            market_id: Filter by market ID
            limit: Maximum entries to return
            offset: Number of entries to skip

        Returns:
            List of log entries
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = "SELECT * FROM strategy_logs WHERE 1=1"
        params: List[Any] = []

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        if log_type:
            query += " AND log_type = ?"
            params.append(log_type.value)
        if level:
            query += " AND level = ?"
            params.append(level.value)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        if market_id:
            query += " AND market_id = ?"
            params.append(market_id)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        result = self._conn.execute(query, params).fetchall()
        columns = [
            "id", "strategy", "timestamp", "log_type", "level", "message",
            "market_id", "token_id", "price", "size", "action", "reason",
            "confidence", "metadata"
        ]

        entries = []
        for row in result:
            data = dict(zip(columns, row))
            entries.append(StrategyLogEntry(
                id=data["id"],
                strategy=data["strategy"],
                timestamp=data["timestamp"],
                log_type=LogType(data["log_type"]) if data["log_type"] else LogType.SCAN,
                level=LogLevel(data["level"]) if data["level"] else LogLevel.INFO,
                message=data["message"],
                market_id=data["market_id"],
                token_id=data["token_id"],
                price=data["price"],
                size=data["size"],
                action=data["action"],
                reason=data["reason"],
                confidence=data["confidence"],
                metadata=data["metadata"],
            ))

        return entries

    def get_log_count(
        self,
        strategy: Optional[str] = None,
        log_type: Optional[LogType] = None,
        level: Optional[LogLevel] = None,
        start_time: Optional[datetime] = None,
    ) -> int:
        """Get count of log entries matching criteria."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = "SELECT COUNT(*) FROM strategy_logs WHERE 1=1"
        params: List[Any] = []

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        if log_type:
            query += " AND log_type = ?"
            params.append(log_type.value)
        if level:
            query += " AND level = ?"
            params.append(level.value)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        result = self._conn.execute(query, params).fetchone()
        return result[0] if result else 0

    # =========================================================================
    # Run Session Operations
    # =========================================================================

    def start_run(self, strategy: str, config: Optional[Dict] = None) -> int:
        """Record a strategy run starting.

        Returns:
            The run ID
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        result = self._conn.execute(
            """
            INSERT INTO strategy_runs (id, strategy, start_time, status, config)
            VALUES (nextval('strategy_runs_id_seq'), ?, ?, 'running', ?)
            RETURNING id
            """,
            [strategy, datetime.utcnow(), config],
        ).fetchone()

        return result[0] if result else 0

    def end_run(
        self,
        run_id: int,
        scans: int = 0,
        signals: int = 0,
        entries: int = 0,
        exits: int = 0,
        errors: int = 0,
        status: str = "stopped",
    ) -> None:
        """Record a strategy run ending."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        self._conn.execute(
            """
            UPDATE strategy_runs SET
                end_time = ?,
                scans_performed = ?,
                signals_generated = ?,
                entries = ?,
                exits = ?,
                errors = ?,
                status = ?
            WHERE id = ?
            """,
            [datetime.utcnow(), scans, signals, entries, exits, errors, status, run_id],
        )

    def get_runs(
        self,
        strategy: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[StrategyRunSummary]:
        """Get strategy run history."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = """
        SELECT id, strategy, start_time, end_time, scans_performed,
               signals_generated, entries, exits, errors, status
        FROM strategy_runs WHERE 1=1
        """
        params: List[Any] = []

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)

        result = self._conn.execute(query, params).fetchall()

        runs = []
        for row in result:
            # row: id, strategy, start_time, end_time, scans, signals, entries, exits, errors, status
            start_time = row[2]
            end_time = row[3]
            duration = None
            if start_time and end_time:
                duration = (end_time - start_time).total_seconds()

            runs.append(StrategyRunSummary(
                id=row[0],
                strategy=row[1],
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                scans_performed=row[4] or 0,
                signals_generated=row[5] or 0,
                entries=row[6] or 0,
                exits=row[7] or 0,
                errors=row[8] or 0,
                status=row[9] or "unknown",
            ))

        return runs

    def get_current_run(self, strategy: str) -> Optional[int]:
        """Get the current running session ID for a strategy."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        result = self._conn.execute(
            """
            SELECT id FROM strategy_runs
            WHERE strategy = ? AND status = 'running'
            ORDER BY start_time DESC LIMIT 1
            """,
            [strategy],
        ).fetchone()

        return result[0] if result else None

    # =========================================================================
    # Scan Summary Operations
    # =========================================================================

    def update_scan_summary(
        self,
        strategy: str,
        scan_count: int = 1,
        opportunities: int = 0,
        signals: int = 0,
        scan_duration_ms: Optional[float] = None,
    ) -> None:
        """Update aggregated scan summary for current minute."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        minute = datetime.utcnow().replace(second=0, microsecond=0)

        # Try to update existing
        result = self._conn.execute(
            """
            UPDATE scan_summaries SET
                scan_count = scan_count + ?,
                opportunities_found = opportunities_found + ?,
                signals_generated = signals_generated + ?,
                avg_scan_duration_ms = CASE
                    WHEN avg_scan_duration_ms IS NULL THEN ?
                    ELSE (avg_scan_duration_ms + ?) / 2
                END
            WHERE strategy = ? AND minute = ?
            RETURNING scan_count
            """,
            [scan_count, opportunities, signals, scan_duration_ms, scan_duration_ms, strategy, minute],
        ).fetchone()

        if not result:
            # Insert new
            self._conn.execute(
                """
                INSERT INTO scan_summaries (strategy, minute, scan_count, opportunities_found, signals_generated, avg_scan_duration_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [strategy, minute, scan_count, opportunities, signals, scan_duration_ms],
            )

    def get_scan_summaries(
        self,
        strategy: str,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get scan summaries for the past N hours."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        result = self._conn.execute(
            """
            SELECT minute, scan_count, opportunities_found, signals_generated, avg_scan_duration_ms
            FROM scan_summaries
            WHERE strategy = ? AND minute >= ?
            ORDER BY minute DESC
            """,
            [strategy, datetime.utcnow() - timedelta(hours=hours)],
        ).fetchall()

        return [
            {
                "minute": row[0],
                "scan_count": row[1],
                "opportunities_found": row[2],
                "signals_generated": row[3],
                "avg_scan_duration_ms": row[4],
            }
            for row in result
        ]

    # =========================================================================
    # Cleanup Operations
    # =========================================================================

    def cleanup_old_logs(self, days: int = 30) -> int:
        """Delete logs older than specified days.

        Returns:
            Number of deleted rows
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        cutoff = datetime.utcnow() - timedelta(days=days)

        result = self._conn.execute(
            "DELETE FROM strategy_logs WHERE timestamp < ? RETURNING id",
            [cutoff],
        ).fetchall()

        return len(result)

    def cleanup_old_summaries(self, days: int = 7) -> int:
        """Delete scan summaries older than specified days."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        cutoff = datetime.utcnow() - timedelta(days=days)

        result = self._conn.execute(
            "DELETE FROM scan_summaries WHERE minute < ? RETURNING minute",
            [cutoff],
        ).fetchall()

        return len(result)


# Global store instance
_store: Optional[StrategyLogsStore] = None


def get_strategy_logs_store() -> StrategyLogsStore:
    """Get the global strategy logs store instance."""
    global _store
    if _store is None:
        _store = StrategyLogsStore()
        _store.connect()
    return _store
