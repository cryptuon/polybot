"""Common Binance data models."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class BinanceOrderSide(str, Enum):
    """Order side."""

    BUY = "BUY"
    SELL = "SELL"


class BinanceOrderType(str, Enum):
    """Order type."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"


class BinanceTimeInForce(str, Enum):
    """Time in force."""

    GTC = "GTC"  # Good Til Cancelled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    GTX = "GTX"  # Good Til Crossing (Post Only)


class BinanceOrderStatus(str, Enum):
    """Order status."""

    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PENDING_CANCEL = "PENDING_CANCEL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class BinanceTicker(BaseModel):
    """24hr ticker statistics."""

    symbol: str
    price_change: float = Field(alias="priceChange", default=0)
    price_change_percent: float = Field(alias="priceChangePercent", default=0)
    weighted_avg_price: float = Field(alias="weightedAvgPrice", default=0)
    prev_close_price: float = Field(alias="prevClosePrice", default=0)
    last_price: float = Field(alias="lastPrice", default=0)
    last_qty: float = Field(alias="lastQty", default=0)
    bid_price: float = Field(alias="bidPrice", default=0)
    bid_qty: float = Field(alias="bidQty", default=0)
    ask_price: float = Field(alias="askPrice", default=0)
    ask_qty: float = Field(alias="askQty", default=0)
    open_price: float = Field(alias="openPrice", default=0)
    high_price: float = Field(alias="highPrice", default=0)
    low_price: float = Field(alias="lowPrice", default=0)
    volume: float = Field(default=0)
    quote_volume: float = Field(alias="quoteVolume", default=0)
    open_time: int = Field(alias="openTime", default=0)
    close_time: int = Field(alias="closeTime", default=0)
    first_id: int = Field(alias="firstId", default=0)
    last_id: int = Field(alias="lastId", default=0)
    count: int = Field(default=0)

    class Config:
        populate_by_name = True

    @property
    def mid_price(self) -> float:
        """Calculate mid price from bid/ask."""
        if self.bid_price and self.ask_price:
            return (self.bid_price + self.ask_price) / 2
        return self.last_price

    @property
    def spread(self) -> float:
        """Calculate spread."""
        return self.ask_price - self.bid_price

    @property
    def spread_pct(self) -> float:
        """Calculate spread as percentage of mid."""
        mid = self.mid_price
        if mid > 0:
            return self.spread / mid * 100
        return 0


class BinanceOrderBookLevel(BaseModel):
    """Single orderbook level."""

    price: float
    quantity: float


class BinanceOrderBook(BaseModel):
    """Orderbook snapshot."""

    symbol: str = ""
    last_update_id: int = Field(alias="lastUpdateId", default=0)
    bids: List[List[str]] = Field(default_factory=list)
    asks: List[List[str]] = Field(default_factory=list)

    class Config:
        populate_by_name = True

    @property
    def best_bid(self) -> Optional[float]:
        """Get best bid price."""
        return float(self.bids[0][0]) if self.bids else None

    @property
    def best_bid_qty(self) -> Optional[float]:
        """Get best bid quantity."""
        return float(self.bids[0][1]) if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        """Get best ask price."""
        return float(self.asks[0][0]) if self.asks else None

    @property
    def best_ask_qty(self) -> Optional[float]:
        """Get best ask quantity."""
        return float(self.asks[0][1]) if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        """Calculate mid price."""
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread(self) -> Optional[float]:
        """Calculate spread."""
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None

    def get_bids(self, depth: int = 10) -> List[BinanceOrderBookLevel]:
        """Get bid levels as typed objects."""
        return [
            BinanceOrderBookLevel(price=float(b[0]), quantity=float(b[1]))
            for b in self.bids[:depth]
        ]

    def get_asks(self, depth: int = 10) -> List[BinanceOrderBookLevel]:
        """Get ask levels as typed objects."""
        return [
            BinanceOrderBookLevel(price=float(a[0]), quantity=float(a[1]))
            for a in self.asks[:depth]
        ]


class BinanceOrder(BaseModel):
    """Order response model."""

    symbol: str
    order_id: int = Field(alias="orderId")
    order_list_id: int = Field(alias="orderListId", default=-1)
    client_order_id: str = Field(alias="clientOrderId", default="")
    price: str = "0"
    orig_qty: str = Field(alias="origQty", default="0")
    executed_qty: str = Field(alias="executedQty", default="0")
    cummulative_quote_qty: str = Field(alias="cummulativeQuoteQty", default="0")
    status: BinanceOrderStatus = BinanceOrderStatus.NEW
    time_in_force: BinanceTimeInForce = Field(
        alias="timeInForce", default=BinanceTimeInForce.GTC
    )
    order_type: BinanceOrderType = Field(alias="type", default=BinanceOrderType.LIMIT)
    side: BinanceOrderSide = BinanceOrderSide.BUY
    stop_price: str = Field(alias="stopPrice", default="0")
    iceberg_qty: str = Field(alias="icebergQty", default="0")
    time: int = 0
    update_time: int = Field(alias="updateTime", default=0)
    is_working: bool = Field(alias="isWorking", default=True)
    orig_quote_order_qty: str = Field(alias="origQuoteOrderQty", default="0")

    class Config:
        populate_by_name = True

    @property
    def filled_pct(self) -> float:
        """Calculate fill percentage."""
        orig = float(self.orig_qty)
        executed = float(self.executed_qty)
        if orig > 0:
            return executed / orig * 100
        return 0

    @property
    def is_active(self) -> bool:
        """Check if order is still active."""
        return self.status in (
            BinanceOrderStatus.NEW,
            BinanceOrderStatus.PARTIALLY_FILLED,
        )
