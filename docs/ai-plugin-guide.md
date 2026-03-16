# AI Model Plugin Guide

This guide explains how to create custom AI/ML model plugins for PolyBot's AI Probability strategy.

## Overview

The AI Probability strategy uses a plugin system that allows you to integrate any prediction model. Plugins receive market context and return probability predictions that the strategy uses to make trading decisions.

---

## Built-in Plugins

PolyBot includes several ready-to-use plugins:

| Plugin | Description | Use Case |
|--------|-------------|----------|
| `simple_heuristic` | Rule-based mean reversion model | Default, no API required |
| `market_price` | Returns current market price | Baseline comparison |
| `random_baseline` | Random predictions | Testing only |
| `llm` | Claude/OpenAI powered analysis | Production predictions |

### Using the LLM Plugin

The `llm` plugin uses Claude (Anthropic) or OpenAI to analyze market questions:

```env
AI_MODEL_PLUGIN=llm
AI_MODEL_CONFIG={"provider": "anthropic", "api_key": "sk-ant-...", "model": "claude-sonnet-4-20250514"}
```

Configuration options:
- `provider`: `"anthropic"` or `"openai"`
- `api_key`: Your API key
- `model`: Model name (default: `claude-sonnet-4-20250514` for Anthropic, `gpt-4o` for OpenAI)
- `temperature`: Sampling temperature (default: `0.3`)
- `max_tokens`: Max response tokens (default: `1024`)

---

## CLI Commands

Manage AI plugins from the command line:

```bash
# List all available plugins
polybot ai plugins

# Show detailed plugin information
polybot ai info llm

# Test prediction on a specific market
polybot ai predict <market-id> --plugin llm --config '{"provider":"anthropic","api_key":"..."}'

# Scan markets for opportunities
polybot ai scan --plugin simple_heuristic --min-edge 0.05 --limit 50
```

---

## API Endpoints

### List Plugins
```
GET /api/strategies/ai_model/plugins
```

### Get Plugin Info
```
GET /api/strategies/ai_model/plugin/{name}
```

### Test Prediction
```
POST /api/strategies/ai_model/predict/{market_id}?plugin_name=simple_heuristic
```

### Batch Predict
```
POST /api/strategies/ai_model/batch_predict
Body: ["market-id-1", "market-id-2", ...]
```

---

## Plugin Interface

All plugins must implement the `AIModelPlugin` abstract base class:

```python
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel

class MarketContext(BaseModel):
    """Context passed to AI model for prediction."""
    market_id: str
    question: str
    description: Optional[str]
    current_yes_price: float
    current_no_price: float
    volume_24h: float
    end_date: str
    tags: list[str]
    category: Optional[str]

class Prediction(BaseModel):
    """Model prediction output."""
    yes_probability: float  # 0.0 to 1.0
    confidence: float       # 0.0 to 1.0
    reasoning: Optional[str] = None

class AIModelPlugin(ABC):
    """Base class for AI model plugins."""

    name: str = "base"
    version: str = "1.0.0"

    @abstractmethod
    async def initialize(self, config: dict) -> None:
        """Initialize the model."""
        pass

    @abstractmethod
    async def predict(self, context: MarketContext) -> Prediction:
        """Generate probability prediction for a market."""
        pass

    @abstractmethod
    async def should_update(self) -> bool:
        """Return True if model needs retraining/updating."""
        pass

    async def shutdown(self) -> None:
        """Cleanup resources."""
        pass
```

## Creating a Plugin

### Step 1: Create Plugin File

Create a new file in `src/polybot/plugins/`:

```python
# src/polybot/plugins/my_model.py

from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction

class MyModelPlugin(AIModelPlugin):
    """My custom prediction model."""

    name = "my_model"
    version = "1.0.0"

    async def initialize(self, config: dict) -> None:
        """Load model weights, connect to APIs, etc."""
        self.api_key = config.get("api_key")
        self.model_name = config.get("model", "default")
        # Initialize your model here

    async def predict(self, context: MarketContext) -> Prediction:
        """Generate prediction for market."""
        # Your prediction logic here
        probability = await self._get_prediction(context)

        return Prediction(
            yes_probability=probability,
            confidence=0.8,
            reasoning="Based on analysis..."
        )

    async def should_update(self) -> bool:
        """Check if model needs updating."""
        return False

    async def shutdown(self) -> None:
        """Cleanup."""
        pass

    async def _get_prediction(self, context: MarketContext) -> float:
        """Internal prediction logic."""
        # Implement your model here
        return 0.5
```

### Step 2: Register Plugin

Add to `src/polybot/plugins/__init__.py`:

```python
from polybot.plugins.my_model import MyModelPlugin

PLUGIN_REGISTRY = {
    "example": RandomBaselinePlugin,
    "market_price": MarketPricePlugin,
    "my_model": MyModelPlugin,  # Add your plugin
}
```

### Step 3: Configure

Update `.env`:

```env
AI_MODEL_PLUGIN=my_model
AI_MODEL_CONFIG={"api_key": "your-key", "model": "gpt-4"}
AI_MODEL_ENABLED=true
```

---

## Example Plugins

### LLM-Based Plugin

Uses an LLM API to analyze market questions:

```python
import httpx
from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction

class LLMPlugin(AIModelPlugin):
    name = "llm"
    version = "1.0.0"

    async def initialize(self, config: dict) -> None:
        self.api_key = config["api_key"]
        self.model = config.get("model", "gpt-4")
        self.client = httpx.AsyncClient()

    async def predict(self, context: MarketContext) -> Prediction:
        prompt = f"""Analyze this prediction market and estimate the probability.

Question: {context.question}
Description: {context.description}
Current YES price: ${context.current_yes_price:.3f}
End date: {context.end_date}
Tags: {', '.join(context.tags)}

Respond with a JSON object containing:
- probability: float between 0 and 1
- confidence: float between 0 and 1
- reasoning: brief explanation
"""

        response = await self.client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}
            }
        )

        result = response.json()["choices"][0]["message"]["content"]
        data = json.loads(result)

        return Prediction(
            yes_probability=data["probability"],
            confidence=data["confidence"],
            reasoning=data["reasoning"]
        )

    async def should_update(self) -> bool:
        return False

    async def shutdown(self) -> None:
        await self.client.aclose()
```

### News Sentiment Plugin

Analyzes news sentiment to make predictions:

```python
import httpx
from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction

class NewsSentimentPlugin(AIModelPlugin):
    name = "news_sentiment"
    version = "1.0.0"

    async def initialize(self, config: dict) -> None:
        self.news_api_key = config["news_api_key"]
        self.sentiment_model = await self._load_sentiment_model()

    async def predict(self, context: MarketContext) -> Prediction:
        # Extract keywords from question
        keywords = self._extract_keywords(context.question)

        # Fetch recent news
        news = await self._fetch_news(keywords)

        # Analyze sentiment
        sentiment_scores = [
            self.sentiment_model.analyze(article)
            for article in news
        ]

        # Convert sentiment to probability
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        probability = (avg_sentiment + 1) / 2  # -1 to 1 -> 0 to 1

        return Prediction(
            yes_probability=probability,
            confidence=min(len(news) / 10, 1.0),  # More news = higher confidence
            reasoning=f"Based on {len(news)} news articles"
        )

    async def should_update(self) -> bool:
        return False
```

### Ensemble Plugin

Combines multiple models:

```python
from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction

class EnsemblePlugin(AIModelPlugin):
    name = "ensemble"
    version = "1.0.0"

    async def initialize(self, config: dict) -> None:
        self.models = []
        self.weights = config.get("weights", [])

        # Load sub-models
        for model_config in config.get("models", []):
            model_class = PLUGIN_REGISTRY[model_config["name"]]
            model = model_class()
            await model.initialize(model_config.get("config", {}))
            self.models.append(model)

        # Default equal weights
        if not self.weights:
            self.weights = [1.0 / len(self.models)] * len(self.models)

    async def predict(self, context: MarketContext) -> Prediction:
        predictions = []

        for model in self.models:
            pred = await model.predict(context)
            predictions.append(pred)

        # Weighted average
        weighted_prob = sum(
            p.yes_probability * w
            for p, w in zip(predictions, self.weights)
        )

        # Confidence is minimum of all models
        min_confidence = min(p.confidence for p in predictions)

        return Prediction(
            yes_probability=weighted_prob,
            confidence=min_confidence,
            reasoning=f"Ensemble of {len(self.models)} models"
        )

    async def should_update(self) -> bool:
        return any(await m.should_update() for m in self.models)

    async def shutdown(self) -> None:
        for model in self.models:
            await model.shutdown()
```

---

## External Plugins

Plugins can be loaded from external packages:

### Package Structure

```
my-polybot-plugin/
├── pyproject.toml
└── src/
    └── my_plugin/
        ├── __init__.py
        └── model.py
```

### pyproject.toml

```toml
[project]
name = "my-polybot-plugin"
version = "0.1.0"
dependencies = ["polybot"]

[project.entry-points."polybot.plugins"]
my_plugin = "my_plugin.model:MyPlugin"
```

### Install and Use

```bash
pip install my-polybot-plugin

# Then configure
AI_MODEL_PLUGIN=my_plugin
```

---

## Best Practices

### Prediction Quality

1. **Calibration**: Ensure probabilities are well-calibrated
2. **Confidence**: Be conservative with confidence scores
3. **Edge Cases**: Handle missing data gracefully

### Performance

1. **Async**: Use async/await for I/O operations
2. **Caching**: Cache expensive computations
3. **Batching**: Process multiple markets efficiently

### Error Handling

```python
async def predict(self, context: MarketContext) -> Prediction:
    try:
        result = await self._make_prediction(context)
        return result
    except Exception as e:
        # Return neutral prediction on error
        return Prediction(
            yes_probability=0.5,
            confidence=0.0,
            reasoning=f"Error: {str(e)}"
        )
```

### Testing

```python
import pytest
from polybot.plugins.my_model import MyModelPlugin
from polybot.plugins.base import MarketContext

@pytest.fixture
async def plugin():
    p = MyModelPlugin()
    await p.initialize({"api_key": "test"})
    yield p
    await p.shutdown()

@pytest.mark.asyncio
async def test_prediction(plugin):
    context = MarketContext(
        market_id="test",
        question="Will it rain tomorrow?",
        current_yes_price=0.5,
        current_no_price=0.5,
        volume_24h=1000,
        end_date="2024-01-20",
        tags=["weather"]
    )

    prediction = await plugin.predict(context)

    assert 0 <= prediction.yes_probability <= 1
    assert 0 <= prediction.confidence <= 1
```

---

## Configuration Options

The strategy uses these settings:

```env
# Plugin selection
AI_MODEL_PLUGIN=my_model

# JSON config passed to initialize()
AI_MODEL_CONFIG={"key": "value"}

# Minimum confidence to act on prediction
AI_MIN_CONFIDENCE=0.7

# Minimum edge (predicted - market) to trade
AI_MIN_EDGE=0.05

# Maximum position size
AI_MAX_POSITION_USD=200
```

The strategy only trades when:
1. `confidence >= AI_MIN_CONFIDENCE`
2. `|predicted_prob - market_price| >= AI_MIN_EDGE`
