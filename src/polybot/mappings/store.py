"""DuckDB-based storage for event mappings."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import duckdb

from polybot.mappings.models import (
    EventCategory,
    EventMapping,
    InstrumentType,
    MappingConfidence,
    UnderlyingInstrument,
)

logger = logging.getLogger(__name__)


class MappingStore:
    """Persistent storage for event-to-underlying mappings.

    Uses DuckDB for efficient querying and persistence.

    Example:
        store = MappingStore("data/mappings.duckdb")
        store.save_mapping(mapping)
        mapping = store.get_mapping(market_id="polymarket_123")
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize mapping store.

        Args:
            db_path: Path to DuckDB file. Uses in-memory if None.
        """
        self._db_path = db_path
        if db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = duckdb.connect(db_path)
        else:
            self._conn = duckdb.connect(":memory:")

        self._create_tables()

    def _create_tables(self) -> None:
        """Create database tables."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS mappings (
                event_id VARCHAR PRIMARY KEY,
                market_id VARCHAR NOT NULL,
                venue VARCHAR DEFAULT 'polymarket',
                question VARCHAR NOT NULL,
                category VARCHAR DEFAULT 'unknown',
                confidence VARCHAR DEFAULT 'none',
                base_asset VARCHAR,
                quote_asset VARCHAR DEFAULT 'USD',
                threshold DOUBLE,
                threshold_direction VARCHAR,
                expiry_date TIMESTAMP,
                instruments JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                classifier_version VARCHAR,
                manual_override BOOLEAN DEFAULT FALSE
            )
        """)

        # Index for common queries
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mappings_market_id ON mappings(market_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mappings_category ON mappings(category)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mappings_base_asset ON mappings(base_asset)
        """)

        logger.info("Mapping store tables initialized")

    def save_mapping(self, mapping: EventMapping) -> None:
        """Save or update a mapping.

        Args:
            mapping: EventMapping to save
        """
        instruments_json = json.dumps(
            [i.model_dump() for i in mapping.instruments]
        )

        self._conn.execute(
            """
            INSERT OR REPLACE INTO mappings (
                event_id, market_id, venue, question, category, confidence,
                base_asset, quote_asset, threshold, threshold_direction,
                expiry_date, instruments, created_at, updated_at,
                classifier_version, manual_override
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                mapping.event_id,
                mapping.market_id,
                mapping.venue,
                mapping.question,
                mapping.category.value,
                mapping.confidence.value,
                mapping.base_asset,
                mapping.quote_asset,
                mapping.threshold,
                mapping.threshold_direction,
                mapping.expiry_date,
                instruments_json,
                mapping.created_at,
                datetime.utcnow(),
                mapping.classifier_version,
                mapping.manual_override,
            ],
        )

        logger.debug(f"Saved mapping: {mapping.event_id}")

    def get_mapping(
        self,
        event_id: Optional[str] = None,
        market_id: Optional[str] = None,
    ) -> Optional[EventMapping]:
        """Get a mapping by event_id or market_id.

        Args:
            event_id: Event identifier
            market_id: Market identifier

        Returns:
            EventMapping or None
        """
        if event_id:
            result = self._conn.execute(
                "SELECT * FROM mappings WHERE event_id = ?", [event_id]
            ).fetchone()
        elif market_id:
            result = self._conn.execute(
                "SELECT * FROM mappings WHERE market_id = ?", [market_id]
            ).fetchone()
        else:
            return None

        if result:
            return self._row_to_mapping(result)
        return None

    def get_mappings_by_category(
        self,
        category: EventCategory,
        limit: int = 100,
    ) -> List[EventMapping]:
        """Get mappings by category.

        Args:
            category: Event category
            limit: Maximum results

        Returns:
            List of EventMapping
        """
        results = self._conn.execute(
            """
            SELECT * FROM mappings
            WHERE category = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            [category.value, limit],
        ).fetchall()

        return [self._row_to_mapping(r) for r in results]

    def get_mappings_by_asset(
        self,
        base_asset: str,
        limit: int = 100,
    ) -> List[EventMapping]:
        """Get mappings by base asset.

        Args:
            base_asset: Asset symbol (e.g., "BTC")
            limit: Maximum results

        Returns:
            List of EventMapping
        """
        results = self._conn.execute(
            """
            SELECT * FROM mappings
            WHERE base_asset = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            [base_asset.upper(), limit],
        ).fetchall()

        return [self._row_to_mapping(r) for r in results]

    def get_mappings_by_venue(
        self,
        venue: str,
        limit: int = 100,
    ) -> List[EventMapping]:
        """Get mappings by source venue.

        Args:
            venue: Venue identifier
            limit: Maximum results

        Returns:
            List of EventMapping
        """
        results = self._conn.execute(
            """
            SELECT * FROM mappings
            WHERE venue = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            [venue, limit],
        ).fetchall()

        return [self._row_to_mapping(r) for r in results]

    def get_active_mappings(
        self,
        min_confidence: MappingConfidence = MappingConfidence.PROXY,
        limit: int = 100,
    ) -> List[EventMapping]:
        """Get active mappings with minimum confidence.

        Args:
            min_confidence: Minimum confidence level
            limit: Maximum results

        Returns:
            List of EventMapping
        """
        # Confidence ordering: exact > proxy > weak > none
        confidence_order = {
            MappingConfidence.EXACT: 4,
            MappingConfidence.PROXY: 3,
            MappingConfidence.WEAK: 2,
            MappingConfidence.NONE: 1,
        }

        min_order = confidence_order[min_confidence]
        valid_confidences = [
            c.value for c, order in confidence_order.items() if order >= min_order
        ]

        results = self._conn.execute(
            f"""
            SELECT * FROM mappings
            WHERE confidence IN ({','.join('?' * len(valid_confidences))})
            AND (expiry_date IS NULL OR expiry_date > CURRENT_TIMESTAMP)
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            valid_confidences + [limit],
        ).fetchall()

        return [self._row_to_mapping(r) for r in results]

    def search_mappings(
        self,
        query: str,
        limit: int = 50,
    ) -> List[EventMapping]:
        """Search mappings by question text.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching EventMapping
        """
        results = self._conn.execute(
            """
            SELECT * FROM mappings
            WHERE question ILIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            [f"%{query}%", limit],
        ).fetchall()

        return [self._row_to_mapping(r) for r in results]

    def delete_mapping(self, event_id: str) -> bool:
        """Delete a mapping.

        Args:
            event_id: Event identifier

        Returns:
            True if deleted
        """
        result = self._conn.execute(
            "DELETE FROM mappings WHERE event_id = ? RETURNING event_id",
            [event_id],
        ).fetchone()

        return result is not None

    def count_mappings(self) -> int:
        """Get total mapping count."""
        result = self._conn.execute("SELECT COUNT(*) FROM mappings").fetchone()
        return result[0] if result else 0

    def get_stats(self) -> Dict:
        """Get mapping statistics."""
        total = self.count_mappings()

        by_category = self._conn.execute("""
            SELECT category, COUNT(*) as count
            FROM mappings
            GROUP BY category
        """).fetchall()

        by_confidence = self._conn.execute("""
            SELECT confidence, COUNT(*) as count
            FROM mappings
            GROUP BY confidence
        """).fetchall()

        by_asset = self._conn.execute("""
            SELECT base_asset, COUNT(*) as count
            FROM mappings
            WHERE base_asset IS NOT NULL
            GROUP BY base_asset
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()

        return {
            "total": total,
            "by_category": {row[0]: row[1] for row in by_category},
            "by_confidence": {row[0]: row[1] for row in by_confidence},
            "top_assets": {row[0]: row[1] for row in by_asset if row[0]},
        }

    def _row_to_mapping(self, row: tuple) -> EventMapping:
        """Convert database row to EventMapping.

        Args:
            row: Database row tuple

        Returns:
            EventMapping instance
        """
        # Parse instruments JSON
        instruments_data = json.loads(row[11]) if row[11] else []
        instruments = []
        for inst in instruments_data:
            instruments.append(
                UnderlyingInstrument(
                    venue=inst["venue"],
                    symbol=inst["symbol"],
                    instrument_type=InstrumentType(inst.get("instrument_type", "spot")),
                    weight=inst.get("weight", 1.0),
                )
            )

        return EventMapping(
            event_id=row[0],
            market_id=row[1],
            venue=row[2],
            question=row[3],
            category=EventCategory(row[4]) if row[4] else EventCategory.UNKNOWN,
            confidence=MappingConfidence(row[5]) if row[5] else MappingConfidence.NONE,
            base_asset=row[6],
            quote_asset=row[7] or "USD",
            threshold=row[8],
            threshold_direction=row[9],
            expiry_date=row[10],
            instruments=instruments,
            created_at=row[12] or datetime.utcnow(),
            updated_at=row[13] or datetime.utcnow(),
            classifier_version=row[14],
            manual_override=row[15] or False,
        )

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()

    def __repr__(self) -> str:
        return f"<MappingStore path={self._db_path} count={self.count_mappings()}>"
