# AI Model Strategy

The AI Model strategy uses machine learning or LLM-based predictions to identify mispriced markets.

## How It Works

1. **Analyze market** - AI plugin evaluates market question and context
2. **Predict probability** - Model outputs estimated true probability
3. **Calculate edge** - Compare prediction to current market price
4. **Trade edge** - If edge exceeds threshold, generate signal

## Example

```
Market: "Will SpaceX launch Starship by June 2026?"
Current YES price: $0.35

AI Model prediction:
- Probability: 55%
- Confidence: 75%
- Edge: 55% - 35% = +20%

Since edge (20%) > minimum (5%), BUY YES
```

## Configuration

```bash
# Which AI plugin to use
AI_MODEL_PLUGIN=claude

# Plugin-specific configuration (JSON)
AI_MODEL_CONFIG={"api_key": "sk-...", "model": "claude-sonnet-4-20250514"}

# Minimum model confidence to trade
AI_MIN_CONFIDENCE=0.7

# Minimum edge vs market price
AI_MIN_EDGE=0.05
```

## Available Plugins

| Plugin | Description | Requires |
|--------|-------------|----------|
| `simple_heuristic` | Rule-based baseline | Nothing |
| `perplexity` | Web search + reasoning | Perplexity API key |
| `llm` | Generic LLM wrapper | OpenAI/Anthropic key |

## Risk Level

**Medium** - Depends heavily on model quality and calibration.

Risks:
- Model miscalibration
- Overconfidence on uncertain events
- API costs
- Latency in prediction

## CLI Commands

```bash
# List available plugins
polybot ai plugins

# Test prediction on a specific market
polybot ai predict <market_id> --plugin claude

# Scan all markets for opportunities
polybot ai scan --plugin claude --min-edge 0.05

# Show plugin info
polybot ai info claude
```

## Building Custom Plugins

Create your own AI plugin:

```python
from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction

class MyPlugin(AIModelPlugin):
    name = "my_plugin"
    
    async def predict(self, context: MarketContext) -> Prediction:
        # Your model logic
        return Prediction(
            yes_probability=0.65,
            confidence=0.8,
            reasoning="Based on..."
        )
```

See [AI Plugin Guide](../../developer-guide/extending/ai-plugins.md) for details.

## Best Practices

1. **Calibrate your model** - Test predictions against outcomes
2. **Track performance** - Monitor win rate and edge capture
3. **Use confidence scores** - Don't trade low-confidence predictions
4. **Consider ensemble** - Combine multiple models
5. **Watch for drift** - Retrain periodically
