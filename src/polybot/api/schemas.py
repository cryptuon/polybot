"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Market Schemas
# =============================================================================


class MarketResponse(BaseModel):
    """Market data response."""

    id: str
    question: str
    slug: Optional[str] = None
    description: Optional[str] = None
    outcome_yes_token: str
    outcome_no_token: str
    yes_price: Optional[float] = None
    no_price: Optional[float] = None
    spread: Optional[float] = None
    volume_24h: Optional[float] = None
    liquidity: Optional[float] = None
    active: bool = True
    closed: bool = False
    end_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)


class MarketListResponse(BaseModel):
    """List of markets response."""

    markets: List[MarketResponse]
    total: int
    offset: int
    limit: int


class OrderBookLevel(BaseModel):
    """Single level in orderbook."""

    price: float
    size: float


class OrderBookResponse(BaseModel):
    """Orderbook response."""

    market_id: str
    token_id: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    timestamp: datetime


# =============================================================================
# Strategy Schemas
# =============================================================================


class StrategyConfig(BaseModel):
    """Strategy configuration."""

    enabled: bool
    shadow: bool = False  # Shadow mode: generate signals but don't execute
    config: Dict[str, Any] = Field(default_factory=dict)


class StrategyResponse(BaseModel):
    """Strategy status response."""

    name: str
    description: str
    enabled: bool
    shadow: bool = False
    running: bool
    positions: int
    signals_sent: int
    config: Dict[str, Any] = Field(default_factory=dict)


class StrategyListResponse(BaseModel):
    """List of strategies response."""

    strategies: List[StrategyResponse]


class StrategyToggleRequest(BaseModel):
    """Request to toggle strategy."""

    enabled: bool


class ShadowToggleRequest(BaseModel):
    """Request to toggle shadow mode for a strategy."""

    shadow: bool


class StrategyUpdateRequest(BaseModel):
    """Request to update strategy config."""

    config: Dict[str, Any]


# =============================================================================
# Order Schemas
# =============================================================================


class OrderCreate(BaseModel):
    """Request to create an order."""

    market_id: str
    token_id: str
    side: str = Field(pattern="^(BUY|SELL)$")
    price: float = Field(ge=0, le=1)
    size: float = Field(gt=0)
    order_type: str = Field(default="GTC", pattern="^(GTC|GTD|FOK|IOC)$")


class OrderResponse(BaseModel):
    """Order response."""

    id: str
    market_id: str
    token_id: str
    side: str
    price: float
    size: float
    order_type: str
    status: str
    filled_size: float
    average_fill_price: Optional[float] = None
    strategy: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class OrderListResponse(BaseModel):
    """List of orders response."""

    orders: List[OrderResponse]
    total: int


# =============================================================================
# Position Schemas
# =============================================================================


class PositionResponse(BaseModel):
    """Position response."""

    id: int
    market_id: str
    token_id: str
    side: str
    size: float
    entry_price: float
    current_price: Optional[float] = None
    status: str
    realized_pnl: float
    unrealized_pnl: Optional[float] = None
    strategy: Optional[str] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None


class PositionListResponse(BaseModel):
    """List of positions response."""

    positions: List[PositionResponse]
    total: int
    total_value: float
    total_pnl: float


class PositionCloseRequest(BaseModel):
    """Request to close a position."""

    price: Optional[float] = None  # Optional limit price


# =============================================================================
# Analytics Schemas
# =============================================================================


class PerformanceSummary(BaseModel):
    """Performance summary response."""

    total_trades: int
    total_wins: int
    total_losses: int
    win_rate: float
    total_pnl: float
    total_volume: float
    total_fees: float
    avg_daily_pnl: float
    best_day: float
    worst_day: float


class DailyStatsResponse(BaseModel):
    """Daily statistics response."""

    date: datetime
    strategy: Optional[str] = None
    trades: int
    wins: int
    losses: int
    pnl: float
    volume: float
    fees: float


class AnalyticsHistoryResponse(BaseModel):
    """Analytics history response."""

    days: List[DailyStatsResponse]
    summary: PerformanceSummary


class PriceCandle(BaseModel):
    """OHLCV price candle."""

    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class PriceHistoryResponse(BaseModel):
    """Price history response."""

    market_id: str
    interval: str
    candles: List[PriceCandle]


# =============================================================================
# Settings Schemas
# =============================================================================


class RiskSettings(BaseModel):
    """Risk management settings."""

    max_position_size_usd: float
    max_total_exposure_usd: float
    daily_loss_limit_usd: float
    max_open_orders: int


class SettingsResponse(BaseModel):
    """Settings response."""

    risk: RiskSettings
    strategies: Dict[str, StrategyConfig]


class SettingsUpdateRequest(BaseModel):
    """Request to update settings."""

    risk: Optional[RiskSettings] = None
    strategies: Optional[Dict[str, StrategyConfig]] = None


# =============================================================================
# System Schemas
# =============================================================================


class ServiceStatus(BaseModel):
    """Service status."""

    name: str
    status: str
    pid: Optional[int] = None
    error: Optional[str] = None


class SystemStatusResponse(BaseModel):
    """System status response."""

    services: List[ServiceStatus]
    healthy: bool
    uptime_seconds: float


class RiskStatusResponse(BaseModel):
    """Risk status response."""

    daily_pnl: float
    total_exposure: float
    open_orders: int
    open_positions: int
    risk_limits: Dict[str, float]


# =============================================================================
# WebSocket Schemas
# =============================================================================


class WSMessage(BaseModel):
    """WebSocket message."""

    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WSSubscribeRequest(BaseModel):
    """WebSocket subscription request."""

    channels: List[str]  # "prices", "orders", "positions", "events"
    market_ids: Optional[List[str]] = None


# =============================================================================
# Strategy Logs Schemas
# =============================================================================


class StrategyLogEntry(BaseModel):
    """Strategy log entry response."""

    id: int
    strategy: str
    timestamp: datetime
    log_type: str
    level: str
    message: str
    market_id: Optional[str] = None
    token_id: Optional[str] = None
    price: Optional[float] = None
    size: Optional[float] = None
    action: Optional[str] = None
    reason: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class StrategyLogsResponse(BaseModel):
    """Strategy logs list response."""

    logs: List[StrategyLogEntry]
    total: int
    limit: int
    offset: int


class StrategyRunSummary(BaseModel):
    """Strategy run session summary."""

    id: Optional[int] = None
    strategy: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    scans_performed: int = 0
    signals_generated: int = 0
    entries: int = 0
    exits: int = 0
    errors: int = 0
    status: str = "running"
    config: Optional[Dict[str, Any]] = None


class StrategyRunsResponse(BaseModel):
    """Strategy runs list response."""

    runs: List[StrategyRunSummary]
    total: int


class ScanSummary(BaseModel):
    """Scan summary for a time period."""

    minute: datetime
    scan_count: int
    opportunities: int
    signals: int
    avg_scan_duration_ms: Optional[float] = None


class ScanSummariesResponse(BaseModel):
    """Scan summaries response."""

    strategy: str
    hours: int
    summaries: List[ScanSummary]
