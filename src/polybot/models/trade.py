"""Trade data models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from polybot.models.order import OrderSide


class Trade(BaseModel):
    """Executed trade record."""

    id: Optional[str] = None
    order_id: Optional[str] = None
    market_id: str = Field(description="Market condition ID")
    token_id: str = Field(description="Outcome token ID")

    # Trade details
    side: OrderSide
    price: float = Field(description="Execution price")
    size: float = Field(description="Trade size in shares")
    fee: float = Field(default=0, description="Trading fee")

    # Value
    notional: float = Field(description="Trade notional value")

    # Metadata
    strategy: Optional[str] = None
    is_maker: bool = False

    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True

    @property
    def net_value(self) -> float:
        """Calculate net value after fees."""
        if self.side == OrderSide.BUY:
            return -(self.notional + self.fee)
        else:
            return self.notional - self.fee


class TradeStats(BaseModel):
    """Trading statistics for a strategy or time period."""

    strategy: Optional[str] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    # Counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # Volume
    total_volume: float = 0
    buy_volume: float = 0
    sell_volume: float = 0

    # P&L
    total_pnl: float = 0
    total_fees: float = 0
    gross_profit: float = 0
    gross_loss: float = 0

    @property
    def win_rate(self) -> Optional[float]:
        """Calculate win rate."""
        if self.total_trades > 0:
            return self.winning_trades / self.total_trades
        return None

    @property
    def profit_factor(self) -> Optional[float]:
        """Calculate profit factor (gross profit / gross loss)."""
        if self.gross_loss > 0:
            return self.gross_profit / abs(self.gross_loss)
        return None

    @property
    def net_pnl(self) -> float:
        """Calculate net P&L after fees."""
        return self.total_pnl - self.total_fees

    @property
    def average_trade_pnl(self) -> Optional[float]:
        """Calculate average P&L per trade."""
        if self.total_trades > 0:
            return self.total_pnl / self.total_trades
        return None


class DailyStats(BaseModel):
    """Daily trading statistics."""

    date: datetime
    strategy: Optional[str] = None

    trades: int = 0
    wins: int = 0
    losses: int = 0
    volume: float = 0
    pnl: float = 0
    fees: float = 0

    class Config:
        from_attributes = True
