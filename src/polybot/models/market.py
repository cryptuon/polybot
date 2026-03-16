"""Market and Event data models."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """Tag/category for markets."""

    id: str
    label: str
    slug: Optional[str] = None


class Market(BaseModel):
    """Polymarket market (binary outcome)."""

    id: str = Field(description="Market condition ID")
    question: str = Field(description="Market question")
    slug: Optional[str] = None
    description: Optional[str] = None

    # Outcome tokens
    outcome_yes_token: str = Field(description="YES outcome token ID")
    outcome_no_token: str = Field(description="NO outcome token ID")

    # Prices (0-1)
    yes_price: Optional[float] = None
    no_price: Optional[float] = None

    # Volume and liquidity
    volume: Optional[float] = None
    volume_24h: Optional[float] = None
    liquidity: Optional[float] = None

    # Status
    active: bool = True
    closed: bool = False
    resolved: bool = False
    resolution: Optional[str] = None  # "YES", "NO", or None

    # Timestamps
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Relationships
    event_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True

    @property
    def spread(self) -> Optional[float]:
        """Calculate bid-ask spread."""
        if self.yes_price is not None and self.no_price is not None:
            return abs(1 - self.yes_price - self.no_price)
        return None

    @property
    def implied_probability(self) -> Optional[float]:
        """Get implied probability from YES price."""
        return self.yes_price


class Event(BaseModel):
    """Polymarket event (collection of markets)."""

    id: str = Field(description="Event ID")
    title: str = Field(description="Event title")
    slug: Optional[str] = None
    description: Optional[str] = None

    # Status
    active: bool = True
    closed: bool = False

    # Timestamps
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    # Related markets
    markets: List[Market] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    # Volume
    volume: Optional[float] = None
    liquidity: Optional[float] = None

    class Config:
        from_attributes = True


class MarketSnapshot(BaseModel):
    """Point-in-time snapshot of market prices."""

    market_id: str
    token_id: str
    timestamp: datetime
    bid: float
    ask: float
    mid: float
    spread: float
    volume: Optional[float] = None

    class Config:
        from_attributes = True
