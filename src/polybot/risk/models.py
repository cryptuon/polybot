"""Risk management data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AssetClass(str, Enum):
    """Asset class for risk categorization."""

    PREDICTION = "prediction"  # Binary outcome markets
    SPOT = "spot"  # Spot crypto
    PERPETUAL = "perpetual"  # Perpetual futures
    FUTURES = "futures"  # Dated futures
    OPTION = "option"  # Options


class RiskCheckResult(BaseModel):
    """Result of a pre-trade risk check."""

    approved: bool
    reason: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    adjusted_size: Optional[float] = None  # If size was reduced
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.approved


class VenuePosition(BaseModel):
    """Position on a specific venue."""

    venue: str  # VenueType value
    asset_class: AssetClass
    symbol: str  # Market ID or instrument symbol
    token_id: Optional[str] = None  # For Polymarket tokens
    side: str  # "long" or "short"
    size: float  # Position size
    entry_price: float
    current_price: Optional[float] = None
    notional_usd: float  # USD value
    unrealized_pnl: float = 0
    realized_pnl: float = 0

    # Greeks (for options and prediction markets)
    delta: float = 1.0  # Delta exposure (1.0 for spot)
    gamma: float = 0.0  # Gamma (options only)
    vega: float = 0.0  # Vega (options only)
    theta: float = 0.0  # Theta (options only)

    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True

    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.side == "long"

    @property
    def signed_size(self) -> float:
        """Get signed size (positive for long, negative for short)."""
        return self.size if self.is_long else -self.size

    @property
    def signed_delta(self) -> float:
        """Get signed delta exposure."""
        return self.delta * self.signed_size


@dataclass
class PortfolioSnapshot:
    """Point-in-time portfolio state."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_exposure_usd: float = 0
    net_delta: float = 0
    positions_by_venue: Dict[str, float] = field(default_factory=dict)
    positions_by_asset: Dict[str, float] = field(default_factory=dict)
    daily_pnl: float = 0
    open_orders_value: float = 0


class HedgeRecommendation(BaseModel):
    """Recommended hedge trade."""

    venue: str  # Target venue for hedge
    symbol: str  # Instrument to trade
    side: str  # "buy" or "sell"
    size: float  # Size to trade
    reason: str  # Why this hedge is recommended
    urgency: str = "normal"  # "low", "normal", "high", "critical"
    delta_impact: float = 0  # Expected delta change
    estimated_cost: float = 0  # Estimated transaction cost

    class Config:
        from_attributes = True


class RiskAlert(BaseModel):
    """Risk alert/warning."""

    alert_type: str  # "exposure_limit", "daily_loss", "delta_breach", etc.
    severity: str  # "info", "warning", "critical"
    message: str
    current_value: float
    threshold: float
    venue: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RiskMetrics(BaseModel):
    """Comprehensive risk metrics snapshot."""

    # Exposure
    total_exposure_usd: float = 0
    long_exposure_usd: float = 0
    short_exposure_usd: float = 0
    net_exposure_usd: float = 0

    # By venue
    exposure_by_venue: Dict[str, float] = Field(default_factory=dict)
    exposure_by_asset_class: Dict[str, float] = Field(default_factory=dict)

    # Greeks
    net_delta: float = 0
    net_gamma: float = 0
    net_vega: float = 0
    net_theta: float = 0

    # PnL
    daily_pnl: float = 0
    unrealized_pnl: float = 0
    realized_pnl: float = 0

    # Concentration
    max_venue_concentration: float = 0
    max_position_concentration: float = 0
    herfindahl_index: float = 0

    # Limits utilization
    exposure_utilization: float = 0  # % of max exposure used
    daily_loss_utilization: float = 0  # % of daily loss limit used

    # Counts
    position_count: int = 0
    open_orders_count: int = 0

    timestamp: datetime = Field(default_factory=datetime.utcnow)
