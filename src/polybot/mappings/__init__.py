"""Event-to-underlying mapping for cross-venue arbitrage.

This module provides:
- Event classification from prediction market questions
- Mapping to hedgeable underlying instruments
- Persistent storage in DuckDB
- NNG-based service interface

Usage:
    from polybot.mappings import get_mapping_service, EventCategory

    # Get service
    service = get_mapping_service()

    # Classify an event
    result = service.classify_event("Will BTC be above $100,000 by December 2024?")
    print(result.category)  # EventCategory.CRYPTO_PRICE
    print(result.base_asset)  # "BTC"
    print(result.threshold)  # 100000.0

    # Create mapping with hedge instruments
    mapping = service.create_mapping(
        question="Will BTC be above $100,000 by December 2024?",
        market_id="polymarket_123",
    )
    print(mapping.instruments)  # [BinanceSpot(BTCUSDT)]
"""

from polybot.mappings.models import (
    ClassificationResult,
    EventCategory,
    EventMapping,
    InstrumentType,
    MappingConfidence,
    MappingQuery,
    MappingResponse,
    PriceComparison,
    UnderlyingInstrument,
)
from polybot.mappings.pattern_matcher import PatternMatcher
from polybot.mappings.service import (
    MappingService,
    get_mapping_service,
    reset_mapping_service,
)
from polybot.mappings.store import MappingStore

__all__ = [
    # Models
    "EventCategory",
    "MappingConfidence",
    "InstrumentType",
    "UnderlyingInstrument",
    "EventMapping",
    "PriceComparison",
    "ClassificationResult",
    "MappingQuery",
    "MappingResponse",
    # Core classes
    "PatternMatcher",
    "MappingStore",
    "MappingService",
    # Functions
    "get_mapping_service",
    "reset_mapping_service",
]
