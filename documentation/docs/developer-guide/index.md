# Developer Guide

Build and extend PolyBot with custom strategies, venues, and AI models.

## Architecture

PolyBot uses a multi-service architecture with NNG messaging:

```
Dashboard (Vue.js)
       |
   FastAPI Gateway
       |
+------+------+
|      |      |
Scanner Executor Analytics
       |
   Strategies
```

[Full architecture documentation](architecture.md)

## Extending PolyBot

### Custom Strategies

Build your own trading strategies:

```python
class MyStrategy(BaseStrategy):
    async def scan(self, update: PriceUpdate) -> list[Signal]:
        # Your alpha here
        ...
```

[Custom strategy guide](extending/custom-strategy.md)

### Custom Venues

Add new trading venues:

```python
class MyVenue(BaseVenue):
    async def place_order(self, order: Order) -> OrderResult:
        # Venue integration
        ...
```

[Custom venue guide](extending/custom-venue.md)

### AI Plugins

Integrate AI models for prediction:

```python
class MyPlugin(AIModelPlugin):
    async def predict(self, context: MarketContext) -> Prediction:
        # Your model
        ...
```

[AI plugin guide](extending/ai-plugins.md)

## API Reference

REST API documentation:

- Markets, strategies, orders, positions
- WebSocket for real-time updates
- Authentication

[API reference](api-reference/index.md)

## Contributing

We welcome contributions!

- [Contributing guide](contributing.md)
- [GitHub Issues](https://github.com/cryptuon/polybot/issues)
- [Discord](https://discord.gg/cryptuon)
