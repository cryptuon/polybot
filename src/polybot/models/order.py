"""Order data models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    """Order side."""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    """Order status."""

    PENDING = "PENDING"  # Created but not submitted
    OPEN = "OPEN"  # Submitted to exchange
    MATCHED = "MATCHED"  # Partially or fully matched
    FILLED = "FILLED"  # Fully filled
    CANCELLED = "CANCELLED"  # Cancelled by user
    FAILED = "FAILED"  # Failed to submit
    EXPIRED = "EXPIRED"  # Order expired


class OrderType(str, Enum):
    """Order type."""

    GTC = "GTC"  # Good til cancelled
    GTD = "GTD"  # Good til date
    FOK = "FOK"  # Fill or kill
    IOC = "IOC"  # Immediate or cancel


class Order(BaseModel):
    """Trading order."""

    id: Optional[str] = None
    market_id: str = Field(description="Market condition ID")
    token_id: str = Field(description="Outcome token ID")

    # Order parameters
    side: OrderSide
    price: float = Field(ge=0, le=1, description="Order price (0-1)")
    size: float = Field(gt=0, description="Order size in shares")
    order_type: OrderType = OrderType.GTC

    # Status
    status: OrderStatus = OrderStatus.PENDING
    filled_size: float = Field(default=0, description="Amount filled")
    average_fill_price: Optional[float] = None

    # Metadata
    strategy: Optional[str] = None
    order_hash: Optional[str] = None
    error_message: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @property
    def remaining_size(self) -> float:
        """Get remaining unfilled size."""
        return self.size - self.filled_size

    @property
    def is_active(self) -> bool:
        """Check if order is still active."""
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.MATCHED)

    @property
    def notional_value(self) -> float:
        """Calculate notional value of the order."""
        return self.price * self.size


class OrderFill(BaseModel):
    """Record of an order fill."""

    order_id: str
    fill_price: float
    fill_size: float
    fee: float = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class OrderBook(BaseModel):
    """Orderbook snapshot."""

    market_id: str
    token_id: str
    timestamp: datetime

    bids: list[tuple[float, float]] = Field(
        default_factory=list, description="List of (price, size) tuples"
    )
    asks: list[tuple[float, float]] = Field(
        default_factory=list, description="List of (price, size) tuples"
    )

    @property
    def best_bid(self) -> Optional[float]:
        """Get best bid price (highest bid)."""
        # Note: CLOB API does not guarantee sorted order
        return max((b[0] for b in self.bids), default=None) if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        """Get best ask price (lowest ask)."""
        # Note: CLOB API does not guarantee sorted order
        return min((a[0] for a in self.asks), default=None) if self.asks else None

    @property
    def spread(self) -> Optional[float]:
        """Get bid-ask spread."""
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None

    @property
    def mid_price(self) -> Optional[float]:
        """Get mid price."""
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return None
