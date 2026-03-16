"""Perplexity-based prediction plugin.

Uses Perplexity API for real-time web search combined with LLM analysis
to generate probability predictions with current information.

This is the recommended plugin for news-sensitive markets where
real-time information is crucial (politics, sports, crypto events).
"""

import json
import logging
from typing import Any, Dict, Optional

import httpx

from polybot.config import get_settings
from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction


logger = logging.getLogger(__name__)


class PerplexityPlugin(AIModelPlugin):
    """Perplexity-powered prediction plugin.

    Uses Perplexity's Sonar model which combines real-time web search
    with LLM analysis. Ideal for markets where current events matter.

    Configuration:
        api_key: Perplexity API key (or uses PERPLEXITY_API_KEY env var)
        model: Model name (default: "sonar", or "sonar-pro" for complex queries)
        temperature: Sampling temperature (default: 0.2)
        search_recency: How recent news to focus on ("day", "week", "month")
    """

    name = "perplexity"
    version = "1.0.0"
    description = "Real-time web search + LLM prediction using Perplexity"
    supports_batch = False

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._api_key: str = ""
        self._model: str = "sonar"
        self._temperature: float = 0.2
        self._search_recency: str = "week"
        self._predictions_made: int = 0
        self._base_url = "https://api.perplexity.ai"

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the Perplexity client.

        Args:
            config: Configuration dict
        """
        settings = get_settings()

        self._api_key = config.get("api_key") or getattr(settings, "perplexity_api_key", "")
        self._model = config.get("model", "sonar")
        self._temperature = config.get("temperature", 0.2)
        self._search_recency = config.get("search_recency", "week")

        if not self._api_key:
            raise ValueError(
                "Perplexity API key required. Set PERPLEXITY_API_KEY env var "
                "or pass api_key in plugin config."
            )

        self._client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
        )
        logger.info(f"Perplexity plugin initialized: model={self._model}")

    async def predict(self, context: MarketContext) -> Prediction:
        """Generate prediction using Perplexity real-time search.

        Args:
            context: Market context with question, prices, etc.

        Returns:
            Prediction with probability and reasoning
        """
        if not self._client:
            raise RuntimeError("Perplexity client not initialized")

        prompt = self._build_prompt(context)

        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": self._system_prompt(),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": self._temperature,
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])

            self._predictions_made += 1

            prediction = self._parse_response(content)

            # Add citations to reasoning if available
            if citations and prediction.reasoning:
                sources_str = ", ".join(citations[:3])
                prediction = Prediction(
                    yes_probability=prediction.yes_probability,
                    confidence=prediction.confidence,
                    reasoning=f"{prediction.reasoning} [Sources: {sources_str}]",
                    model_version=self._model,
                    features_used=["perplexity_search", "real_time_news", "market_context"],
                )

            return prediction

        except Exception as e:
            logger.error(f"Perplexity prediction error: {e}")
            return Prediction(
                yes_probability=0.5,
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                model_version=self.version,
            )

    def _system_prompt(self) -> str:
        """Get system prompt for analysis."""
        return """You are an expert prediction market analyst with access to real-time information.
Your job is to analyze prediction market questions and estimate probabilities based on current news and data.

Key principles:
1. Use the most recent information available
2. Be calibrated - don't be overconfident
3. Consider base rates and historical patterns
4. Account for uncertainty in your confidence score
5. Focus on facts, not speculation"""

    def _build_prompt(self, context: MarketContext) -> str:
        """Build the analysis prompt."""
        prompt = f"""Analyze this prediction market and estimate the probability of YES outcome.

## Market Question
{context.question}
"""
        if context.description:
            prompt += f"\n## Description\n{context.description}\n"

        prompt += f"""
## Current Market
- YES price: {context.current_yes_price:.1%}
- Spread: {context.spread:.2%}
"""
        if context.hours_remaining is not None:
            if context.hours_remaining < 24:
                prompt += f"- Time remaining: {context.hours_remaining:.1f} hours\n"
            else:
                prompt += f"- Time remaining: {context.hours_remaining/24:.1f} days\n"

        if context.volume_24h:
            prompt += f"- 24h volume: ${context.volume_24h:,.0f}\n"

        prompt += f"""
## Your Task
Search for the latest news and information about this topic.
Based on current events and data, provide:

1. **yes_probability**: Your estimate (0.0 to 1.0)
2. **confidence**: Your confidence in this estimate (0.0 to 1.0)
3. **reasoning**: Brief explanation with specific recent events/data

Focus on news from the last {self._search_recency}.

Respond with JSON:
```json
{{
    "yes_probability": 0.XX,
    "confidence": 0.XX,
    "reasoning": "Brief explanation citing specific recent events"
}}
```
"""
        return prompt

    def _parse_response(self, content: str) -> Prediction:
        """Parse Perplexity response into Prediction."""
        try:
            # Extract JSON from response
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "{" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            else:
                json_str = content

            data = json.loads(json_str)

            yes_prob = float(data.get("yes_probability", 0.5))
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "No reasoning provided")

            # Validate ranges
            yes_prob = max(0.01, min(0.99, yes_prob))
            confidence = max(0.0, min(1.0, confidence))

            return Prediction(
                yes_probability=yes_prob,
                confidence=confidence,
                reasoning=reasoning,
                model_version=self._model,
                features_used=["perplexity_search", "real_time_news"],
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse Perplexity response: {e}")
            return Prediction(
                yes_probability=0.5,
                confidence=0.1,
                reasoning=f"Parse error: {content[:200]}...",
                model_version=self.version,
            )

    async def should_update(self) -> bool:
        """Perplexity uses real-time search, no model updates needed."""
        return False

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "model": self._model,
            "predictions_made": self._predictions_made,
            "features": ["real_time_search", "news_analysis", "citations"],
        }


# Register plugin
Plugin = PerplexityPlugin
