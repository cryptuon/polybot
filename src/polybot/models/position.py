"""Position data models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PositionStatus(str, Enum):
    """Position status."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"


class Position(BaseModel):
    """Trading position."""

    id: Optional[int] = None
    market_id: str = Field(description="Market condition ID")
    token_id: str = Field(description="Outcome token ID")

    # Position details
    side: str = Field(description="YES or NO")
    size: float = Field(description="Position size in shares")
    entry_price: float = Field(description="Average entry price")

    # Current state
    current_price: Optional[float] = None
    status: PositionStatus = PositionStatus.OPEN

    # P&L
    realized_pnl: float = Field(default=0, description="Realized P&L")
    unrealized_pnl: Optional[float] = None

    # Metadata
    strategy: Optional[str] = None

    # Timestamps
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None

    class Config:
        from_attributes = True

    @property
    def cost_basis(self) -> float:
        """Calculate cost basis of position."""
        return self.entry_price * self.size

    @property
    def current_value(self) -> Optional[float]:
        """Calculate current value of position."""
        if self.current_price is not None:
            return self.current_price * self.size
        return None

    @property
    def total_pnl(self) -> Optional[float]:
        """Calculate total P&L (realized + unrealized)."""
        if self.unrealized_pnl is not None:
            return self.realized_pnl + self.unrealized_pnl
        return self.realized_pnl

    @property
    def return_pct(self) -> Optional[float]:
        """Calculate return percentage."""
        if self.current_price is not None and self.entry_price > 0:
            return (self.current_price - self.entry_price) / self.entry_price
        return None

    def update_unrealized_pnl(self, current_price: float) -> None:
        """Update unrealized P&L based on current price.

        Args:
            current_price: Current market price
        """
        self.current_price = current_price
        self.unrealized_pnl = (current_price - self.entry_price) * self.size

    def close(self, exit_price: float) -> float:
        """Close the position.

        Args:
            exit_price: Price at which position is closed

        Returns:
            Realized P&L from closing
        """
        pnl = (exit_price - self.entry_price) * self.size
        self.realized_pnl += pnl
        self.unrealized_pnl = 0
        self.exit_price = exit_price
        self.status = PositionStatus.CLOSED
        self.closed_at = datetime.utcnow()
        return pnl


class PositionSummary(BaseModel):
    """Summary of all positions."""

    total_positions: int = 0
    open_positions: int = 0
    closed_positions: int = 0

    total_value: float = 0
    total_cost_basis: float = 0
    total_realized_pnl: float = 0
    total_unrealized_pnl: float = 0

    @property
    def total_pnl(self) -> float:
        """Total P&L across all positions."""
        return self.total_realized_pnl + self.total_unrealized_pnl

    @property
    def total_return_pct(self) -> Optional[float]:
        """Total return percentage."""
        if self.total_cost_basis > 0:
            return self.total_pnl / self.total_cost_basis
        return None
