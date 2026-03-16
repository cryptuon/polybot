# Extending PolyBot

PolyBot is designed for extensibility. Add your own strategies, venues, or AI models.

## Extension Points

### Custom Strategies

Build trading strategies by inheriting from `BaseStrategy`:

```python
class MyStrategy(BaseStrategy):
    async def scan(self, update) -> list[Signal]:
        ...
    
    async def should_exit(self, position, update) -> bool:
        ...
```

[Custom Strategy Guide](custom-strategy.md)

### Custom Venues

Add new trading venues by inheriting from `BaseVenue`:

```python
class MyVenue(BaseVenue):
    async def place_order(self, order) -> OrderResult:
        ...
```

[Custom Venue Guide](custom-venue.md)

### AI Plugins

Integrate AI models by inheriting from `AIModelPlugin`:

```python
class MyPlugin(AIModelPlugin):
    async def predict(self, context) -> Prediction:
        ...
```

[AI Plugin Guide](ai-plugins.md)

## Architecture

```
┌─────────────────┐
│   BaseStrategy  │◄── Your custom strategies
├─────────────────┤
│    BaseVenue    │◄── Your custom venues
├─────────────────┤
│  AIModelPlugin  │◄── Your AI models
└─────────────────┘
```

## Quick Start

1. Choose what to extend
2. Create a new file in the appropriate directory
3. Inherit from the base class
4. Implement required methods
5. Register your extension
6. Test in shadow mode

## Best Practices

- Start with shadow mode
- Write comprehensive tests
- Handle errors gracefully
- Log important events
- Document your code
