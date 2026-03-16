# Building Custom Venues

Add support for new trading venues by implementing the `BaseVenue` interface.

## The BaseVenue Interface

```python
from polybot.venues.base import (
    BaseVenue, Ticker, Market, Order, OrderResult, 
    Position, Balance
)
from polybot.venues.types import (
    VenueType, VenueCapabilities, MarketType,
    OrderSide, OrderStatus, OrderType
)

class MyVenue(BaseVenue):
    """Custom venue implementation."""
    
    venue_type = VenueType.CUSTOM  # Add to VenueType enum
    
    def __init__(self, settings=None):
        super().__init__(settings)
        self._client = None
    
    def get_capabilities(self) -> VenueCapabilities:
        """Declare what this venue supports."""
        return VenueCapabilities(
            market_types=[MarketType.BINARY, MarketType.SCALAR],
            supports_limit_orders=True,
            supports_market_orders=True,
            supports_websocket=True,
            supports_margin=False,
            max_leverage=1.0,
        )
    
    # === Lifecycle ===
    
    async def connect(self) -> None:
        """Initialize connections and authenticate."""
        self._client = MyVenueClient(
            api_key=self._settings.my_venue.api_key,
            api_secret=self._settings.my_venue.api_secret,
        )
        await self._client.authenticate()
        self._connected = True
    
    async def disconnect(self) -> None:
        """Clean up connections."""
        if self._client:
            await self._client.close()
        self._connected = False
    
    # === Market Data ===
    
    async def get_markets(
        self, 
        market_type: Optional[MarketType] = None
    ) -> List[Market]:
        """Fetch available markets."""
        raw_markets = await self._client.get_markets()
        markets = [self._parse_market(m) for m in raw_markets]
        
        if market_type:
            markets = [m for m in markets if m.market_type == market_type]
        
        return markets
    
    async def get_ticker(self, symbol: str) -> Ticker:
        """Get current prices for a symbol."""
        data = await self._client.get_ticker(symbol)
        return Ticker(
            symbol=symbol,
            venue=self.venue_type,
            bid=data["bid"],
            ask=data["ask"],
            last=data.get("last"),
            volume_24h=data.get("volume"),
        )
    
    async def subscribe_prices(
        self,
        symbols: List[str],
        callback: Callable[[Ticker], None],
    ) -> None:
        """Subscribe to real-time price updates."""
        async def on_message(data):
            ticker = self._parse_ticker(data)
            callback(ticker)
        
        await self._client.ws_subscribe(symbols, on_message)
    
    # === Trading ===
    
    async def place_order(self, order: Order) -> OrderResult:
        """Submit an order."""
        # Shadow mode simulation
        if self.shadow_mode:
            return self._simulate_order(order)
        
        try:
            result = await self._client.place_order(
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                size=order.size,
                price=order.price,
            )
            
            return OrderResult(
                success=True,
                order_id=result["order_id"],
                status=OrderStatus.PENDING,
                venue=self.venue_type,
            )
        except Exception as e:
            return OrderResult(
                success=False,
                error=str(e),
                venue=self.venue_type,
            )
    
    async def cancel_order(
        self, 
        order_id: str, 
        symbol: Optional[str] = None
    ) -> bool:
        """Cancel an open order."""
        try:
            await self._client.cancel_order(order_id)
            return True
        except Exception:
            return False
    
    async def get_order(
        self, 
        order_id: str, 
        symbol: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get order details."""
        return await self._client.get_order(order_id)
    
    async def get_open_orders(
        self, 
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all open orders."""
        return await self._client.get_open_orders(symbol)
    
    # === Positions & Account ===
    
    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        raw_positions = await self._client.get_positions()
        return [self._parse_position(p) for p in raw_positions]
    
    async def get_balance(
        self, 
        currency: Optional[str] = None
    ) -> Balance:
        """Get account balance."""
        data = await self._client.get_balance()
        return Balance(
            venue=self.venue_type,
            currency=currency or "USD",
            total=data["total"],
            available=data["available"],
            locked=data.get("locked", 0),
        )
    
    # === Helper Methods ===
    
    def _parse_market(self, raw: dict) -> Market:
        """Convert raw API response to Market."""
        return Market(
            symbol=raw["symbol"],
            venue=self.venue_type,
            market_type=MarketType.BINARY,
            description=raw.get("description"),
            is_active=raw.get("active", True),
        )
    
    def _parse_ticker(self, raw: dict) -> Ticker:
        """Convert raw WebSocket message to Ticker."""
        return Ticker(
            symbol=raw["symbol"],
            venue=self.venue_type,
            bid=raw["bid"],
            ask=raw["ask"],
        )
    
    def _parse_position(self, raw: dict) -> Position:
        """Convert raw position to Position."""
        return Position(
            symbol=raw["symbol"],
            venue=self.venue_type,
            side="long" if raw["size"] > 0 else "short",
            size=abs(raw["size"]),
            entry_price=raw["entry_price"],
        )
    
    def _simulate_order(self, order: Order) -> OrderResult:
        """Simulate order for shadow mode."""
        return OrderResult(
            success=True,
            order_id=f"shadow_{uuid.uuid4().hex[:8]}",
            status=OrderStatus.FILLED,
            filled_size=order.size,
            filled_price=order.price,
            venue=self.venue_type,
        )
```

## Required Methods

| Method | Description |
|--------|-------------|
| `get_capabilities()` | Return venue capabilities |
| `connect()` | Initialize connections |
| `disconnect()` | Clean up |
| `get_markets()` | List available markets |
| `get_ticker()` | Get current prices |
| `subscribe_prices()` | Real-time price stream |
| `place_order()` | Submit order |
| `cancel_order()` | Cancel order |
| `get_order()` | Get order details |
| `get_open_orders()` | List open orders |
| `get_positions()` | List positions |
| `get_balance()` | Get account balance |

## Configuration

Add venue configuration:

```python
# config.py
class MyVenueConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MY_VENUE_", 
        env_file=".env"
    )
    
    api_key: str = Field(default="")
    api_secret: str = Field(default="")
    base_url: str = Field(default="https://api.myvenue.com")
    environment: str = Field(default="sandbox")
```

Add to Settings:
```python
class Settings(BaseSettings):
    # ...
    my_venue: MyVenueConfig = Field(default_factory=MyVenueConfig)
```

## Registration

Add to venue types:

```python
# venues/types.py
class VenueType(Enum):
    POLYMARKET = "polymarket"
    KALSHI = "kalshi"
    BINANCE = "binance"
    MY_VENUE = "my_venue"  # Add your venue
```

Register in venues module:

```python
# venues/__init__.py
from polybot.venues.my_venue import MyVenue

VENUE_REGISTRY = {
    VenueType.MY_VENUE: MyVenue,
    # ...
}
```

## Testing

```python
import pytest
from polybot.venues.my_venue import MyVenue

@pytest.fixture
async def venue():
    v = MyVenue()
    await v.connect()
    yield v
    await v.disconnect()

async def test_get_markets(venue):
    markets = await venue.get_markets()
    assert len(markets) > 0
    assert all(m.venue == VenueType.MY_VENUE for m in markets)

async def test_get_ticker(venue):
    ticker = await venue.get_ticker("BTC-USD")
    assert ticker.bid > 0
    assert ticker.ask >= ticker.bid

async def test_shadow_order(venue):
    venue.set_shadow_mode(True)
    
    order = Order(
        symbol="BTC-USD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        size=1.0,
        price=50000.0,
    )
    
    result = await venue.place_order(order)
    assert result.success
    assert "shadow" in result.order_id
```

## Best Practices

1. **Handle rate limits** - Implement backoff
2. **Support shadow mode** - For testing
3. **Parse errors carefully** - Map to standard types
4. **Log extensively** - Debug integration issues
5. **Test with sandbox** - Before production
