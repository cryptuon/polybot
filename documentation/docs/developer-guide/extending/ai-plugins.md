# Building AI Model Plugins

PolyBot's AI Model strategy uses a plugin system for probability prediction. Integrate any ML model, LLM, or external API.

## The AIModelPlugin Interface

```python
from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction
from typing import Any, Dict

class MyAIPlugin(AIModelPlugin):
    """Custom AI prediction plugin."""
    
    name = "my_ai_model"
    version = "1.0.0"
    description = "My custom AI probability model"
    
    # Capabilities
    supports_batch = True
    supports_streaming = False
    max_context_length = 8000
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Load model weights or initialize API clients.
        
        Called once when the plugin is loaded.
        
        Args:
            config: Configuration from AI_MODEL_CONFIG env var
        """
        self.model = await load_my_model(config.get("model_path"))
        # Or for API-based:
        # self.client = AnthropicClient(api_key=config["api_key"])
    
    async def predict(self, context: MarketContext) -> Prediction:
        """Generate probability prediction for a market.
        
        Args:
            context: Market information
        
        Returns:
            Prediction with yes_probability and confidence
        """
        prob = self.model.predict(context.question)
        return Prediction(
            yes_probability=prob,
            confidence=0.7,
            reasoning="Model analysis",
            model_version=self.version,
        )
    
    async def should_update(self) -> bool:
        """Return True if model needs retraining."""
        return False
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        await self.model.close()
```

## Required Methods

### `initialize(config: dict)`

Called once when the plugin loads. Use for:

- Loading model weights
- Connecting to APIs
- Initializing resources

The `config` dict comes from the `AI_MODEL_CONFIG` environment variable (JSON).

### `predict(context: MarketContext) -> Prediction`

The core prediction method. Given market context, return your probability estimate.

### `should_update() -> bool`

Called periodically. Return `True` to trigger `update()`.

## MarketContext Fields

| Field | Type | Description |
|-------|------|-------------|
| `market_id` | str | Unique market identifier |
| `question` | str | Market question text |
| `description` | Optional[str] | Detailed description |
| `current_yes_price` | float | Current YES price (0-1) |
| `current_no_price` | float | Current NO price (0-1) |
| `spread` | float | Bid-ask spread |
| `volume_24h` | Optional[float] | 24-hour volume in USD |
| `liquidity` | Optional[float] | Current liquidity |
| `end_date` | Optional[str] | ISO format end date |
| `hours_remaining` | Optional[float] | Hours until resolution |
| `tags` | List[str] | Market categories |
| `price_history` | Optional[List[Dict]] | Recent price data |

## Prediction Fields

| Field | Type | Description |
|-------|------|-------------|
| `yes_probability` | float | Predicted probability (0-1) |
| `confidence` | float | Model confidence (0-1) |
| `reasoning` | Optional[str] | Explanation |
| `model_version` | Optional[str] | Model version used |
| `features_used` | Optional[List[str]] | Key features |

## Example: LLM Plugin

```python
import anthropic
from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction

class ClaudePlugin(AIModelPlugin):
    """Use Claude for market prediction."""
    
    name = "claude"
    version = "1.0.0"
    description = "Claude-powered probability prediction"
    
    async def initialize(self, config: dict) -> None:
        self.client = anthropic.AsyncAnthropic(
            api_key=config.get("api_key")
        )
        self.model = config.get("model", "claude-sonnet-4-20250514")
    
    async def predict(self, context: MarketContext) -> Prediction:
        prompt = f"""Analyze this prediction market and estimate the true probability.

Market Question: {context.question}

Description: {context.description or 'N/A'}

Current YES price: {context.current_yes_price:.1%}
Hours remaining: {context.hours_remaining:.0f}h
24h volume: ${context.volume_24h:,.0f}

Consider:
1. Base rates for similar events
2. Recent news and developments
3. Time until resolution
4. Market efficiency

Respond with ONLY a JSON object:
{{"probability": 0.XX, "confidence": 0.XX, "reasoning": "brief explanation"}}"""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response
        import json
        result = json.loads(response.content[0].text)
        
        return Prediction(
            yes_probability=result["probability"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            model_version=self.model,
        )
    
    async def should_update(self) -> bool:
        return False
    
    async def shutdown(self) -> None:
        pass
```

## Example: Heuristic Plugin

```python
class SimpleHeuristicPlugin(AIModelPlugin):
    """Rule-based prediction for testing."""
    
    name = "simple_heuristic"
    version = "1.0.0"
    description = "Simple heuristic baseline"
    
    async def initialize(self, config: dict) -> None:
        pass
    
    async def predict(self, context: MarketContext) -> Prediction:
        # Simple heuristics
        prob = context.current_yes_price  # Start with market price
        confidence = 0.5
        reasons = []
        
        # Adjust for time remaining
        if context.hours_remaining and context.hours_remaining < 24:
            # Near expiry, trust market more
            confidence = 0.3
            reasons.append("near expiry")
        
        # Adjust for volume
        if context.volume_24h and context.volume_24h > 100000:
            confidence += 0.1
            reasons.append("high volume")
        
        # Adjust for extreme prices
        if context.current_yes_price < 0.1:
            prob = context.current_yes_price * 1.5  # Slightly higher
            reasons.append("longshot adjustment")
        elif context.current_yes_price > 0.9:
            prob = context.current_yes_price * 0.95  # Slightly lower
            reasons.append("favorite adjustment")
        
        return Prediction(
            yes_probability=max(0, min(1, prob)),
            confidence=confidence,
            reasoning=", ".join(reasons) or "market price baseline",
        )
    
    async def should_update(self) -> bool:
        return False
```

## Plugin Registration

### Option 1: Built-in Plugins

Place in `src/polybot/plugins/`:

```python
# src/polybot/plugins/my_plugin.py
class MyPlugin(AIModelPlugin):
    ...
```

Register in `example_plugin.py`:
```python
def get_all_plugins():
    return {
        "my_plugin": MyPlugin,
        # ...
    }
```

### Option 2: Entry Points

For installable plugins, use entry points in `pyproject.toml`:

```toml
[project.entry-points."polybot.plugins"]
my_plugin = "my_package.plugin:MyPlugin"
```

### Option 3: Custom Path

Set `POLYBOT_AI_PLUGIN_PATH` environment variable.

## Configuration

Set in `.env`:

```bash
# Plugin to use
AI_MODEL_PLUGIN=claude

# Plugin configuration (JSON)
AI_MODEL_CONFIG={"api_key": "sk-...", "model": "claude-sonnet-4-20250514"}

# Strategy settings
AI_MIN_CONFIDENCE=0.7
AI_MIN_EDGE=0.05
```

## Testing Plugins

### CLI Testing

```bash
# List available plugins
polybot ai plugins

# Test prediction on a market
polybot ai predict <market_id> --plugin claude

# Scan all markets
polybot ai scan --plugin claude --min-edge 0.05
```

### Unit Tests

```python
import pytest
from my_plugin import MyPlugin
from polybot.plugins.base import MarketContext

@pytest.fixture
def plugin():
    p = MyPlugin()
    await p.initialize({})
    return p

@pytest.fixture
def context():
    return MarketContext(
        market_id="0x123",
        question="Will X happen by Y?",
        current_yes_price=0.5,
        current_no_price=0.5,
        spread=0.02,
    )

async def test_predict(plugin, context):
    prediction = await plugin.predict(context)
    
    assert 0 <= prediction.yes_probability <= 1
    assert 0 <= prediction.confidence <= 1
    assert prediction.reasoning is not None
```

## Best Practices

1. **Calibration**: Ensure your probabilities are well-calibrated
2. **Confidence scores**: Use lower confidence when uncertain
3. **Rate limiting**: Respect API limits for external services
4. **Caching**: Cache predictions for identical contexts
5. **Logging**: Log predictions for analysis
6. **Fallbacks**: Handle API failures gracefully

## Batch Predictions

For efficiency, implement `predict_batch`:

```python
async def predict_batch(self, contexts: list[MarketContext]) -> list[Prediction]:
    """Batch prediction for multiple markets."""
    # Default: sequential
    return [await self.predict(ctx) for ctx in contexts]
    
    # Optimized: parallel API calls
    tasks = [self.predict(ctx) for ctx in contexts]
    return await asyncio.gather(*tasks)
```

Enable with:
```python
supports_batch = True
```
