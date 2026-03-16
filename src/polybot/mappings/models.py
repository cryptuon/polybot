"""Event mapping models for cross-venue arbitrage."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class EventCategory(str, Enum):
    """Category of prediction market event."""

    CRYPTO_PRICE = "crypto_price"  # "Will BTC be above $50k?"
    CRYPTO_VOLATILITY = "crypto_volatility"  # "Will BTC move 10% in 24h?"
    TIME_BASED = "time_based"  # Events with specific dates
    BINARY_OUTCOME = "binary_outcome"  # Yes/No events
    MULTI_OUTCOME = "multi_outcome"  # Multiple choice events
    SPORTS = "sports"  # Sports betting
    POLITICS = "politics"  # Political events
    WEATHER = "weather"  # Weather predictions
    UNKNOWN = "unknown"


class MappingConfidence(str, Enum):
    """Confidence level of event-to-underlying mapping."""

    EXACT = "exact"  # Direct 1:1 mapping (e.g., BTC price threshold)
    PROXY = "proxy"  # Correlated but not exact (e.g., crypto market sentiment)
    WEAK = "weak"  # Loosely related
    NONE = "none"  # No meaningful mapping


class InstrumentType(str, Enum):
    """Type of underlying instrument."""

    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURES = "futures"
    OPTIONS = "options"


class UnderlyingInstrument(BaseModel):
    """An instrument that can be used to hedge or price an event.

    Example:
        For event "Will BTC be above $100k by Dec 2024?":
        - venue: "binance"
        - symbol: "BTCUSDT"
        - instrument_type: "spot"
        - weight: 1.0
    """

    venue: str = Field(..., description="Venue where instrument trades")
    symbol: str = Field(..., description="Instrument symbol")
    instrument_type: InstrumentType = Field(
        default=InstrumentType.SPOT, description="Type of instrument"
    )
    weight: float = Field(
        default=1.0, description="Weight for hedge ratio calculation"
    )
    expiry: Optional[datetime] = Field(
        default=None, description="Expiry for futures/options"
    )
    strike: Optional[float] = Field(
        default=None, description="Strike for options"
    )

    def model_dump(self, **kwargs):
        """Serialize to dict."""
        d = super().model_dump(**kwargs)
        if d.get("expiry"):
            d["expiry"] = d["expiry"].isoformat()
        return d


class EventMapping(BaseModel):
    """Maps a prediction market event to underlying instruments.

    Links Polymarket/Kalshi events to hedgeable instruments on Binance.

    Example:
        event_id: "polymarket_123"
        market_id: "Will BTC be above $100k by Dec 2024?"
        category: CRYPTO_PRICE
        confidence: EXACT
        base_asset: "BTC"
        threshold: 100000.0
        expiry_date: 2024-12-31
        instruments: [BinanceSpot(BTCUSDT), BinanceFutures(BTCUSDT-DEC24)]
    """

    event_id: str = Field(..., description="Unique event identifier")
    market_id: str = Field(..., description="Market ID on prediction venue")
    venue: str = Field(default="polymarket", description="Source venue")
    question: str = Field(..., description="Event question text")
    category: EventCategory = Field(
        default=EventCategory.UNKNOWN, description="Event category"
    )
    confidence: MappingConfidence = Field(
        default=MappingConfidence.NONE, description="Mapping confidence"
    )

    # Asset information
    base_asset: Optional[str] = Field(
        default=None, description="Base asset (e.g., BTC, ETH)"
    )
    quote_asset: str = Field(default="USD", description="Quote asset")
    threshold: Optional[float] = Field(
        default=None, description="Price threshold for crypto events"
    )
    threshold_direction: Optional[str] = Field(
        default=None, description="above/below/equal"
    )

    # Timing
    expiry_date: Optional[datetime] = Field(
        default=None, description="Event expiry date"
    )

    # Underlying instruments for hedging
    instruments: List[UnderlyingInstrument] = Field(
        default_factory=list, description="Hedging instruments"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    classifier_version: Optional[str] = Field(
        default=None, description="Version of classifier that created mapping"
    )
    manual_override: bool = Field(
        default=False, description="Was this manually set?"
    )

    def model_dump(self, **kwargs):
        """Serialize to dict."""
        d = super().model_dump(**kwargs)
        if d.get("expiry_date"):
            d["expiry_date"] = d["expiry_date"].isoformat()
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        if d.get("updated_at"):
            d["updated_at"] = d["updated_at"].isoformat()
        return d


class PriceComparison(BaseModel):
    """Compares prediction market implied price vs underlying price.

    Used to identify arbitrage opportunities.
    """

    event_id: str
    market_id: str
    question: str

    # Prediction market data
    prediction_price: float = Field(..., description="YES token price (0-1)")
    implied_probability: float = Field(..., description="Implied probability")

    # Underlying data
    underlying_price: float = Field(..., description="Current underlying price")
    threshold: Optional[float] = Field(
        default=None, description="Event threshold"
    )
    threshold_direction: Optional[str] = Field(default=None)

    # Derived metrics
    model_probability: Optional[float] = Field(
        default=None, description="Model-implied probability"
    )
    divergence: Optional[float] = Field(
        default=None, description="Price vs model divergence"
    )
    divergence_pct: Optional[float] = Field(
        default=None, description="Divergence as percentage"
    )

    # Trading info
    instruments: List[UnderlyingInstrument] = Field(default_factory=list)
    hedge_ratio: float = Field(default=1.0, description="Hedge ratio")

    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ClassificationResult(BaseModel):
    """Result of classifying an event question."""

    question: str
    category: EventCategory
    confidence: MappingConfidence

    # Extracted entities
    base_asset: Optional[str] = None
    threshold: Optional[float] = None
    threshold_direction: Optional[str] = None
    expiry_date: Optional[datetime] = None

    # Pattern match info
    pattern_id: Optional[str] = Field(
        default=None, description="ID of matched pattern"
    )
    pattern_regex: Optional[str] = Field(
        default=None, description="Matched regex pattern"
    )
    match_groups: Dict[str, str] = Field(
        default_factory=dict, description="Captured groups"
    )

    # Score
    score: float = Field(default=0.0, description="Classification confidence score")


class MappingQuery(BaseModel):
    """Query for mapping service."""

    query_type: str = Field(..., description="get_mapping, classify, get_instruments")

    # For get_mapping
    market_id: Optional[str] = None
    event_id: Optional[str] = None

    # For classify
    question: Optional[str] = None

    # For get_instruments
    category: Optional[EventCategory] = None
    base_asset: Optional[str] = None


class MappingResponse(BaseModel):
    """Response from mapping service."""

    success: bool
    error: Optional[str] = None

    # Response data
    mapping: Optional[EventMapping] = None
    mappings: List[EventMapping] = Field(default_factory=list)
    classification: Optional[ClassificationResult] = None
    instruments: List[UnderlyingInstrument] = Field(default_factory=list)
