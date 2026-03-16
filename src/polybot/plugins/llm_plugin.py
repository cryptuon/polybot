"""LLM-based prediction plugin.

Uses Claude or OpenAI API to analyze prediction market questions
and generate probability estimates based on current knowledge.

Optionally uses Perplexity for real-time news grounding before prediction.
"""

import json
import logging
from typing import Any, Dict, Optional

import httpx

from polybot.config import get_settings
from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction


logger = logging.getLogger(__name__)


class LLMPlugin(AIModelPlugin):
    """LLM-powered prediction plugin.

    Uses Claude (Anthropic) or OpenAI API to analyze market questions
    and generate probability predictions.

    Configuration:
        provider: "anthropic" or "openai"
        api_key: API key for the provider
        model: Model name (e.g., "claude-sonnet-4-20250514", "gpt-4o")
        temperature: Sampling temperature (default: 0.3)
        max_tokens: Max response tokens (default: 1024)
        use_perplexity_grounding: If True, fetch real-time news via Perplexity first
        perplexity_api_key: Perplexity API key (or uses PERPLEXITY_API_KEY env var)
    """

    name = "llm"
    version = "1.1.0"
    description = "LLM-powered market prediction using Claude or OpenAI (with optional Perplexity grounding)"
    supports_batch = False

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._provider: str = "anthropic"
        self._api_key: str = ""
        self._model: str = "claude-sonnet-4-20250514"
        self._temperature: float = 0.3
        self._max_tokens: int = 1024
        self._predictions_made: int = 0
        self._total_tokens_used: int = 0

        # Perplexity grounding
        self._use_perplexity_grounding: bool = False
        self._perplexity_api_key: str = ""
        self._perplexity_client: Optional[httpx.AsyncClient] = None

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the LLM client.

        Args:
            config: Configuration with provider, api_key, model, etc.
        """
        settings = get_settings()

        self._provider = config.get("provider", "anthropic")
        self._api_key = config.get("api_key", "")
        self._model = config.get("model", self._default_model())
        self._temperature = config.get("temperature", 0.3)
        self._max_tokens = config.get("max_tokens", 1024)

        # Perplexity grounding configuration
        self._use_perplexity_grounding = config.get("use_perplexity_grounding", False)
        self._perplexity_api_key = config.get("perplexity_api_key") or getattr(
            settings, "perplexity_api_key", ""
        )

        if not self._api_key:
            raise ValueError("API key is required for LLM plugin")

        self._client = httpx.AsyncClient(timeout=60.0)

        # Initialize Perplexity client if grounding is enabled
        if self._use_perplexity_grounding and self._perplexity_api_key:
            self._perplexity_client = httpx.AsyncClient(
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {self._perplexity_api_key}",
                    "Content-Type": "application/json",
                }
            )
            logger.info(f"LLM plugin initialized with Perplexity grounding: provider={self._provider}, model={self._model}")
        else:
            logger.info(f"LLM plugin initialized: provider={self._provider}, model={self._model}")

    def _default_model(self) -> str:
        """Get default model for provider."""
        if self._provider == "anthropic":
            return "claude-sonnet-4-20250514"
        elif self._provider == "openai":
            return "gpt-4o"
        return "claude-sonnet-4-20250514"

    async def predict(self, context: MarketContext) -> Prediction:
        """Generate prediction using LLM.

        Args:
            context: Market context with question, prices, etc.

        Returns:
            Prediction with probability and reasoning
        """
        if not self._client:
            raise RuntimeError("LLM client not initialized")

        # Optionally fetch real-time news grounding from Perplexity
        news_context = ""
        if self._use_perplexity_grounding and self._perplexity_client:
            news_context = await self._fetch_perplexity_grounding(context.question)

        prompt = self._build_prompt(context, news_context=news_context)

        try:
            if self._provider == "anthropic":
                result = await self._call_anthropic(prompt)
            elif self._provider == "openai":
                result = await self._call_openai(prompt)
            else:
                raise ValueError(f"Unknown provider: {self._provider}")

            self._predictions_made += 1
            return result

        except Exception as e:
            logger.error(f"LLM prediction error: {e}")
            # Return neutral prediction on error
            return Prediction(
                yes_probability=0.5,
                confidence=0.0,
                reasoning=f"Error generating prediction: {str(e)}",
                model_version=self.version,
            )

    async def _fetch_perplexity_grounding(self, question: str) -> str:
        """Fetch real-time news context from Perplexity.

        Args:
            question: Market question to search for

        Returns:
            News summary to include in LLM prompt
        """
        if not self._perplexity_client:
            return ""

        try:
            response = await self._perplexity_client.post(
                "https://api.perplexity.ai/chat/completions",
                json={
                    "model": "sonar",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a news researcher. Provide a brief, factual summary of recent news relevant to the question. Focus on the last 7 days. Be concise.",
                        },
                        {
                            "role": "user",
                            "content": f"What are the latest news and developments related to: {question}",
                        },
                    ],
                    "temperature": 0.1,
                    "max_tokens": 512,
                },
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])

            if citations:
                sources = ", ".join(citations[:3])
                return f"{content}\n\n[Sources: {sources}]"
            return content

        except Exception as e:
            logger.warning(f"Failed to fetch Perplexity grounding: {e}")
            return ""

    def _build_prompt(self, context: MarketContext, news_context: str = "") -> str:
        """Build the analysis prompt for the LLM.

        Args:
            context: Market context
            news_context: Optional real-time news from Perplexity

        Returns:
            Formatted prompt string
        """
        prompt = f"""You are an expert prediction market analyst. Analyze the following market and estimate the probability of the YES outcome.

## Market Information

**Question:** {context.question}
"""
        if context.description:
            prompt += f"\n**Description:** {context.description}\n"

        prompt += f"""
**Current Prices:**
- YES: ${context.current_yes_price:.3f} ({context.current_yes_price*100:.1f}%)
- NO: ${context.current_no_price:.3f} ({context.current_no_price*100:.1f}%)
- Spread: {context.spread*100:.2f}%
"""

        if context.volume_24h:
            prompt += f"\n**24h Volume:** ${context.volume_24h:,.0f}"

        if context.hours_remaining is not None:
            if context.hours_remaining < 24:
                prompt += f"\n**Time Remaining:** {context.hours_remaining:.1f} hours"
            else:
                days = context.hours_remaining / 24
                prompt += f"\n**Time Remaining:** {days:.1f} days"

        if context.tags:
            prompt += f"\n**Tags:** {', '.join(context.tags)}"

        # Include real-time news if available (from Perplexity grounding)
        if news_context:
            prompt += f"""

## Recent News & Developments (Real-time)

{news_context}
"""

        prompt += """

## Your Task

Analyze this prediction market and provide:
1. Your estimated probability that YES is the correct outcome (0.0 to 1.0)
2. Your confidence in this estimate (0.0 to 1.0)
3. Brief reasoning for your prediction

Consider:
- Base rates and historical patterns for similar events
- Current news and information that might affect the outcome
- Whether the current market price seems accurate
- Time remaining until resolution
- Any potential biases in market pricing

Respond with a JSON object in this exact format:
```json
{
    "yes_probability": 0.XX,
    "confidence": 0.XX,
    "reasoning": "Your brief explanation here"
}
```

Be calibrated in your predictions - don't be overconfident. If you're uncertain, reflect that in both your probability estimate and confidence score.
"""
        return prompt

    async def _call_anthropic(self, prompt: str) -> Prediction:
        """Call Anthropic Claude API."""
        response = await self._client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self._model,
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()

        # Track token usage
        if "usage" in data:
            self._total_tokens_used += data["usage"].get("input_tokens", 0)
            self._total_tokens_used += data["usage"].get("output_tokens", 0)

        # Extract text from response
        content = data["content"][0]["text"]
        return self._parse_response(content)

    async def _call_openai(self, prompt: str) -> Prediction:
        """Call OpenAI API."""
        response = await self._client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self._temperature,
                "max_tokens": self._max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()

        # Track token usage
        if "usage" in data:
            self._total_tokens_used += data["usage"].get("total_tokens", 0)

        # Extract text from response
        content = data["choices"][0]["message"]["content"]
        return self._parse_response(content)

    def _parse_response(self, content: str) -> Prediction:
        """Parse LLM response into Prediction."""
        # Try to extract JSON from response
        try:
            # Look for JSON in code block
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                # Try to find JSON object directly
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]

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
                model_version=f"{self._model}",
                features_used=["llm_analysis", "market_context"],
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # Return neutral prediction if parsing fails
            return Prediction(
                yes_probability=0.5,
                confidence=0.1,
                reasoning=f"Failed to parse response: {content[:200]}...",
                model_version=self.version,
            )

    async def should_update(self) -> bool:
        """LLM models don't need updating in the traditional sense."""
        return False

    async def shutdown(self) -> None:
        """Close the HTTP clients."""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._perplexity_client:
            await self._perplexity_client.aclose()
            self._perplexity_client = None

    def get_info(self) -> Dict[str, Any]:
        """Get plugin information including usage stats."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "provider": self._provider,
            "model": self._model,
            "predictions_made": self._predictions_made,
            "total_tokens_used": self._total_tokens_used,
            "perplexity_grounding_enabled": self._use_perplexity_grounding,
        }


# Register plugin
Plugin = LLMPlugin
