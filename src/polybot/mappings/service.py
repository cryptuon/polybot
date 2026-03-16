"""Mapping service for event-to-underlying classification."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from polybot.config import Settings, get_settings
from polybot.core.nng import NNGReplier
from polybot.mappings.models import (
    ClassificationResult,
    EventCategory,
    EventMapping,
    InstrumentType,
    MappingConfidence,
    MappingQuery,
    MappingResponse,
    UnderlyingInstrument,
)
from polybot.mappings.pattern_matcher import PatternMatcher
from polybot.mappings.store import MappingStore
from polybot.services.base import BaseService

logger = logging.getLogger(__name__)


class MappingService(BaseService):
    """Service for event-to-underlying mapping.

    Provides:
    - Event classification via pattern matching
    - Mapping storage and retrieval
    - Hedge instrument suggestions
    - NNG REQ/REP interface for queries

    Example:
        service = MappingService()
        await service.start()

        # Query via NNG
        # {"type": "classify", "question": "Will BTC be above $100k?"}
    """

    name = "mapping"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize mapping service."""
        super().__init__(settings)

        self._store: Optional[MappingStore] = None
        self._matcher: Optional[PatternMatcher] = None
        self._replier: Optional[NNGReplier] = None

        # In-memory cache
        self._cache: Dict[str, EventMapping] = {}
        self._cache_ttl_sec = 300  # 5 minutes

        # Hedge instrument mappings from config
        self._hedge_instruments: Dict[str, List[Dict]] = {}

    async def _on_start(self) -> None:
        """Initialize service resources."""
        # Initialize store
        db_path = self._settings.data_dir / "mappings" / "mappings.duckdb"
        self._store = MappingStore(str(db_path))

        # Initialize pattern matcher
        config_dir = Path("config/mappings")
        patterns_file = config_dir / "event_patterns.yaml"
        assets_file = config_dir / "crypto_assets.yaml"

        self._matcher = PatternMatcher(
            patterns_file=patterns_file if patterns_file.exists() else None,
            assets_file=assets_file if assets_file.exists() else None,
        )

        # Load hedge instruments from config
        if assets_file.exists():
            self._load_hedge_instruments(assets_file)

        # Initialize NNG replier
        mapping_address = getattr(self._settings.nng, "mapping_address", None)
        if mapping_address:
            self._replier = NNGReplier(mapping_address)
            await self._replier.open()
            self._logger.info(f"Listening on {mapping_address}")

    async def _on_stop(self) -> None:
        """Cleanup resources."""
        if self._replier:
            await self._replier.close()

        if self._store:
            self._store.close()

    async def _run(self) -> None:
        """Main service loop."""
        if not self._replier:
            self._logger.warning("No NNG address configured, running in local-only mode")
            # Keep service alive
            while self._running:
                await asyncio.sleep(1)
            return

        async for msg in self._replier.requests():
            if not self._running:
                break

            try:
                response = await self._handle_request(msg)
                await self._replier.reply(response)
            except Exception as e:
                self._logger.error(f"Request handling error: {e}")
                await self._replier.reply({"success": False, "error": str(e)})

    async def _handle_request(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming request.

        Args:
            msg: Request message

        Returns:
            Response dict
        """
        query_type = msg.get("type", "")

        if query_type == "classify":
            question = msg.get("question", "")
            result = self.classify_event(question)
            return {
                "success": True,
                "classification": result.model_dump(),
            }

        elif query_type == "get_mapping":
            event_id = msg.get("event_id")
            market_id = msg.get("market_id")
            mapping = self.get_mapping(event_id=event_id, market_id=market_id)
            return {
                "success": True,
                "mapping": mapping.model_dump() if mapping else None,
            }

        elif query_type == "create_mapping":
            question = msg.get("question", "")
            market_id = msg.get("market_id", "")
            venue = msg.get("venue", "polymarket")
            mapping = self.create_mapping(question, market_id, venue)
            return {
                "success": True,
                "mapping": mapping.model_dump(),
            }

        elif query_type == "get_instruments":
            base_asset = msg.get("base_asset")
            instruments = self.get_hedge_instruments(base_asset)
            return {
                "success": True,
                "instruments": [i.model_dump() for i in instruments],
            }

        elif query_type == "list_mappings":
            category = msg.get("category")
            base_asset = msg.get("base_asset")
            limit = msg.get("limit", 100)
            mappings = self.list_mappings(
                category=EventCategory(category) if category else None,
                base_asset=base_asset,
                limit=limit,
            )
            return {
                "success": True,
                "mappings": [m.model_dump() for m in mappings],
            }

        elif query_type == "stats":
            stats = self.get_stats()
            return {"success": True, "stats": stats}

        else:
            return {"success": False, "error": f"Unknown query type: {query_type}"}

    def _load_hedge_instruments(self, path: Path) -> None:
        """Load hedge instruments from YAML config.

        Args:
            path: Path to assets YAML file
        """
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
                self._hedge_instruments = data.get("hedge_instruments", {})
                self._logger.info(
                    f"Loaded hedge instruments for {len(self._hedge_instruments)} assets"
                )
        except Exception as e:
            self._logger.error(f"Failed to load hedge instruments: {e}")

    # =========================================================================
    # Public API
    # =========================================================================

    def classify_event(self, question: str) -> ClassificationResult:
        """Classify an event question.

        Args:
            question: Event question text

        Returns:
            ClassificationResult with extracted entities
        """
        if not self._matcher:
            return ClassificationResult(
                question=question,
                category=EventCategory.UNKNOWN,
                confidence=MappingConfidence.NONE,
            )

        return self._matcher.classify(question)

    def get_mapping(
        self,
        event_id: Optional[str] = None,
        market_id: Optional[str] = None,
    ) -> Optional[EventMapping]:
        """Get an existing mapping.

        Args:
            event_id: Event identifier
            market_id: Market identifier

        Returns:
            EventMapping or None
        """
        # Check cache first
        cache_key = event_id or market_id
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]

        # Query store
        if not self._store:
            return None

        mapping = self._store.get_mapping(event_id=event_id, market_id=market_id)

        # Cache result
        if mapping and cache_key:
            self._cache[cache_key] = mapping

        return mapping

    def create_mapping(
        self,
        question: str,
        market_id: str,
        venue: str = "polymarket",
        event_id: Optional[str] = None,
    ) -> EventMapping:
        """Create a new mapping from event question.

        Args:
            question: Event question text
            market_id: Market identifier
            venue: Source venue
            event_id: Optional event ID (generated if not provided)

        Returns:
            Created EventMapping
        """
        # Classify the question
        result = self.classify_event(question)

        # Generate event ID if not provided
        if not event_id:
            event_id = f"{venue}_{uuid.uuid4().hex[:12]}"

        # Get hedge instruments for the asset
        instruments = []
        if result.base_asset:
            instruments = self.get_hedge_instruments(result.base_asset)

        # Create mapping
        mapping = EventMapping(
            event_id=event_id,
            market_id=market_id,
            venue=venue,
            question=question,
            category=result.category,
            confidence=result.confidence,
            base_asset=result.base_asset,
            threshold=result.threshold,
            threshold_direction=result.threshold_direction,
            expiry_date=result.expiry_date,
            instruments=instruments,
            classifier_version="pattern_v1",
        )

        # Save to store
        if self._store:
            self._store.save_mapping(mapping)

        # Cache it
        self._cache[event_id] = mapping
        self._cache[market_id] = mapping

        return mapping

    def get_hedge_instruments(self, base_asset: str) -> List[UnderlyingInstrument]:
        """Get hedge instruments for an asset.

        Args:
            base_asset: Asset symbol (e.g., "BTC")

        Returns:
            List of UnderlyingInstrument
        """
        asset = base_asset.upper()
        instruments_data = self._hedge_instruments.get(asset, [])

        instruments = []
        for data in instruments_data:
            inst_type = data.get("type", "spot")
            try:
                instrument_type = InstrumentType(inst_type)
            except ValueError:
                instrument_type = InstrumentType.SPOT

            instruments.append(
                UnderlyingInstrument(
                    venue=data.get("venue", "binance"),
                    symbol=data.get("symbol", f"{asset}USDT"),
                    instrument_type=instrument_type,
                    weight=data.get("weight", 1.0),
                )
            )

        # Default to spot if nothing configured
        if not instruments:
            instruments.append(
                UnderlyingInstrument(
                    venue="binance",
                    symbol=f"{asset}USDT",
                    instrument_type=InstrumentType.SPOT,
                    weight=1.0,
                )
            )

        return instruments

    def list_mappings(
        self,
        category: Optional[EventCategory] = None,
        base_asset: Optional[str] = None,
        limit: int = 100,
    ) -> List[EventMapping]:
        """List mappings with optional filters.

        Args:
            category: Filter by category
            base_asset: Filter by asset
            limit: Maximum results

        Returns:
            List of EventMapping
        """
        if not self._store:
            return []

        if category:
            return self._store.get_mappings_by_category(category, limit)
        elif base_asset:
            return self._store.get_mappings_by_asset(base_asset, limit)
        else:
            return self._store.get_active_mappings(limit=limit)

    def get_stats(self) -> Dict:
        """Get mapping statistics."""
        if not self._store:
            return {"total": 0}

        return self._store.get_stats()

    def clear_cache(self) -> None:
        """Clear the mapping cache."""
        self._cache.clear()


# =========================================================================
# Global Instance
# =========================================================================

_mapping_service: Optional[MappingService] = None


def get_mapping_service() -> MappingService:
    """Get or create global mapping service.

    Returns:
        MappingService instance
    """
    global _mapping_service
    if _mapping_service is None:
        _mapping_service = MappingService()
    return _mapping_service


def reset_mapping_service() -> None:
    """Reset global mapping service (for testing)."""
    global _mapping_service
    _mapping_service = None
