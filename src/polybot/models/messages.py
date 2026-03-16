"""NNG message schemas for inter-service communication."""

import time
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Types of NNG messages."""

    # Price updates
    PRICE = "price"
    BOOK = "book"

    # Signals
    SIGNAL = "signal"

    # Orders
    ORDER_REQUEST = "order_req"
    ORDER_RESPONSE = "order_resp"

    # Events
    EVENT = "event"

    # Control
    HEARTBEAT = "heartbeat"
    SHUTDOWN = "shutdown"


class PriceUpdate(BaseModel):
    """Price update message from scanner to strategies."""

    type: str = MessageType.PRICE.value
    market_id: str
    token_id: str
    bid: float
    ask: float
    mid: float
    spread: float
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PriceUpdate":
        return cls(**data)


class BookUpdate(BaseModel):
    """Orderbook update message."""

    type: str = MessageType.BOOK.value
    market_id: str
    token_id: str
    bids: list[tuple[float, float]]  # (price, size)
    asks: list[tuple[float, float]]  # (price, size)
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class SignalAction(str, Enum):
    """Signal action types."""

    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"


class Signal(BaseModel):
    """Trading signal from strategy to executor."""

    type: str = MessageType.SIGNAL.value
    strategy: str
    market_id: str
    token_id: str
    action: SignalAction
    price: float
    size: float
    reason: str = ""
    confidence: float = Field(default=1.0, ge=0, le=1)
    bid: Optional[float] = None  # Current bid price for PnL tracking
    ask: Optional[float] = None  # Current ask price for PnL tracking
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        data = self.model_dump()
        data["action"] = self.action.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signal":
        if isinstance(data.get("action"), str):
            data["action"] = SignalAction(data["action"])
        return cls(**data)


class OrderRequest(BaseModel):
    """Order request from strategy to executor."""

    type: str = MessageType.ORDER_REQUEST.value
    request_id: str
    signal: Dict[str, Any]
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class OrderResponse(BaseModel):
    """Order response from executor to strategy."""

    type: str = MessageType.ORDER_RESPONSE.value
    request_id: str
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class EventType(str, Enum):
    """System event types."""

    # Order events
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_FAILED = "order_failed"

    # Position events
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"

    # Strategy events
    STRATEGY_STARTED = "strategy_started"
    STRATEGY_STOPPED = "strategy_stopped"
    STRATEGY_ERROR = "strategy_error"

    # System events
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    ALERT = "alert"


class SystemEvent(BaseModel):
    """System event message."""

    type: str = MessageType.EVENT.value
    source: str  # Service name
    event_type: EventType
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        data = self.model_dump()
        data["event_type"] = self.event_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemEvent":
        if isinstance(data.get("event_type"), str):
            data["event_type"] = EventType(data["event_type"])
        return cls(**data)


class Heartbeat(BaseModel):
    """Heartbeat message for service health monitoring."""

    type: str = MessageType.HEARTBEAT.value
    service: str
    status: str = "healthy"
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
