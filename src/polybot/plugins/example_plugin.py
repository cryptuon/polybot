"""Example AI model plugin implementations.

Provides example plugins for testing and as templates
for custom implementations.
"""

import random
from typing import Any, Dict

from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction


class RandomBaselinePlugin(AIModelPlugin):
    """Random baseline plugin for testing.

    Returns random predictions - useful for benchmarking
    and testing the plugin system.
    """

    name = "random_baseline"
    version = "1.0.0"
    description = "Random baseline predictor for testing"

    def __init__(self) -> None:
        self._rng: random.Random = random.Random()
        self._predictions_made = 0

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize with optional seed."""
        seed = config.get("seed", 42)
        self._rng = random.Random(seed)

    async def predict(self, context: MarketContext) -> Prediction:
        """Return random prediction."""
        self._predictions_made += 1

        yes_prob = self._rng.random()
        confidence = self._rng.uniform(0.3, 0.7)  # Low confidence

        return Prediction(
            yes_probability=yes_prob,
            confidence=confidence,
            reasoning="Random baseline prediction (for testing only)",
            model_version=self.version,
        )

    async def should_update(self) -> bool:
        """Never needs update."""
        return False


class MarketPricePlugin(AIModelPlugin):
    """Plugin that returns current market price as prediction.

    Useful as a baseline - just trusts the market's assessment.
    """

    name = "market_price"
    version = "1.0.0"
    description = "Returns market price as prediction"

    async def initialize(self, config: Dict[str, Any]) -> None:
        """No initialization needed."""
        pass

    async def predict(self, context: MarketContext) -> Prediction:
        """Return market price as prediction."""
        return Prediction(
            yes_probability=context.current_yes_price,
            confidence=0.5,  # Neutral confidence
            reasoning="Using market price as baseline prediction",
            model_version=self.version,
        )

    async def should_update(self) -> bool:
        """Never needs update."""
        return False


class SimpleHeuristicPlugin(AIModelPlugin):
    """Simple heuristic-based plugin.

    Applies basic rules based on market characteristics:
    - High volume = more confidence in market price
    - Near expiration = higher confidence
    - Extreme prices = potential for reversion
    """

    name = "simple_heuristic"
    version = "1.0.0"
    description = "Simple rule-based prediction model"

    async def initialize(self, config: Dict[str, Any]) -> None:
        """No initialization needed."""
        self._reversion_threshold = config.get("reversion_threshold", 0.95)

    async def predict(self, context: MarketContext) -> Prediction:
        """Apply simple heuristics."""
        market_price = context.current_yes_price
        confidence = 0.5

        # Start with market price
        prediction = market_price

        # Rule 1: Mean reversion for extreme prices
        if market_price > self._reversion_threshold:
            # Slightly bearish on very high prices
            prediction = market_price - 0.02
            confidence = 0.6
            reasoning = "Slight mean reversion expectation at extreme high"
        elif market_price < (1 - self._reversion_threshold):
            # Slightly bullish on very low prices
            prediction = market_price + 0.02
            confidence = 0.6
            reasoning = "Slight mean reversion expectation at extreme low"
        else:
            reasoning = "Following market price"

        # Rule 2: Adjust confidence based on time to expiration
        if context.hours_remaining is not None:
            if context.hours_remaining < 24:
                confidence *= 1.2  # More confident near expiration
            elif context.hours_remaining > 720:  # 30 days
                confidence *= 0.8  # Less confident far from expiration

        # Rule 3: Adjust confidence based on volume
        if context.volume_24h is not None:
            if context.volume_24h > 100000:
                confidence *= 1.1  # Higher volume = more efficient market
            elif context.volume_24h < 1000:
                confidence *= 0.9  # Lower volume = less reliable

        # Clamp values
        prediction = max(0.01, min(0.99, prediction))
        confidence = max(0.1, min(0.9, confidence))

        return Prediction(
            yes_probability=prediction,
            confidence=confidence,
            reasoning=reasoning,
            model_version=self.version,
            features_used=["market_price", "time_to_expiry", "volume"],
        )

    async def should_update(self) -> bool:
        """No updates needed for rule-based model."""
        return False


# Registry of example plugins
EXAMPLE_PLUGINS = {
    "random_baseline": RandomBaselinePlugin,
    "market_price": MarketPricePlugin,
    "simple_heuristic": SimpleHeuristicPlugin,
}


# Import LLM and Perplexity plugins for registry
def get_all_plugins() -> dict:
    """Get all available plugins including LLM and Perplexity."""
    from polybot.plugins.llm_plugin import LLMPlugin
    from polybot.plugins.perplexity_plugin import PerplexityPlugin

    return {
        **EXAMPLE_PLUGINS,
        "llm": LLMPlugin,
        "perplexity": PerplexityPlugin,
    }
