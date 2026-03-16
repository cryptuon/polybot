"""Perplexity API client for news search and analysis.

Perplexity provides real-time web search combined with LLM analysis,
perfect for checking current events that affect prediction markets.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from polybot.config import get_settings


logger = logging.getLogger(__name__)


class PerplexityClient:
    """Client for Perplexity API.

    Perplexity combines web search with LLM to provide up-to-date
    information about current events - ideal for prediction markets.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize the client.

        Args:
            api_key: Perplexity API key. If not provided, reads from env.
        """
        settings = get_settings()
        self._api_key = api_key or getattr(settings, 'perplexity_api_key', '')
        self._base_url = "https://api.perplexity.ai"
        self._client: Optional[httpx.AsyncClient] = None
        self._model = "sonar"  # Real-time web search model (or "sonar-pro" for complex queries)

    async def connect(self) -> None:
        """Initialize the HTTP client."""
        if not self._api_key:
            logger.warning("Perplexity API key not configured")
            return

        self._client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
        )
        logger.info("Perplexity client initialized")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search_news(
        self,
        query: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for recent news about a topic.

        Args:
            query: Search query (e.g., "Trump latest news today")
            context: Additional context for the search

        Returns:
            Dict with 'answer', 'sources', and 'citations'
        """
        if not self._client:
            return {"error": "Client not initialized", "answer": "", "sources": []}

        system_prompt = """You are a news analyst providing factual, up-to-date information.
Focus on recent events (last 24-48 hours) that are relevant to the query.
Be concise and factual. Include specific dates and sources when possible."""

        user_message = query
        if context:
            user_message = f"{query}\n\nContext: {context}"

        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.1,  # Low temperature for factual responses
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            data = response.json()

            answer = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])

            return {
                "answer": answer,
                "sources": citations,
                "model": self._model,
            }

        except Exception as e:
            logger.error(f"Perplexity search error: {e}")
            return {"error": str(e), "answer": "", "sources": []}

    async def check_event_status(
        self,
        market_question: str,
        market_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check if an event has already occurred or its current status.

        This is used for resolution arbitrage - finding markets where
        the outcome is already known but the market hasn't updated.

        Args:
            market_question: The prediction market question
            market_description: Optional additional context

        Returns:
            Dict with 'resolved', 'outcome', 'confidence', 'evidence'
        """
        if not self._client:
            return {"error": "Client not initialized", "resolved": False}

        prompt = f"""Analyze this prediction market question and determine if the outcome is already known:

QUESTION: {market_question}
"""
        if market_description:
            prompt += f"\nDESCRIPTION: {market_description}"

        prompt += """

Based on current news and information, answer:
1. Has this event already been resolved/decided? (yes/no/uncertain)
2. If yes, what is the outcome? (YES the event happened, NO it didn't, or UNKNOWN)
3. How confident are you? (0.0-1.0)
4. What is the evidence? (brief summary with dates)

Respond in JSON format:
{
    "resolved": true/false,
    "outcome": "YES" or "NO" or "UNKNOWN",
    "confidence": 0.0-1.0,
    "evidence": "Brief explanation with dates/sources"
}
"""

        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 512,
                },
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]

            # Parse JSON from response
            import json
            try:
                # Extract JSON from response
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    json_str = content[json_start:json_end].strip()
                elif "{" in content:
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    json_str = content[json_start:json_end]
                else:
                    json_str = content

                result = json.loads(json_str)
                result["raw_response"] = content
                return result

            except json.JSONDecodeError:
                return {
                    "resolved": False,
                    "outcome": "UNKNOWN",
                    "confidence": 0.0,
                    "evidence": content,
                    "parse_error": True,
                }

        except Exception as e:
            logger.error(f"Perplexity event check error: {e}")
            return {"error": str(e), "resolved": False}

    async def analyze_market_relationship(
        self,
        market_a_question: str,
        market_b_question: str,
    ) -> Dict[str, Any]:
        """Analyze if two markets are logically related.

        Used for calendar spreads and conditional probability arbitrage.

        Args:
            market_a_question: First market question
            market_b_question: Second market question

        Returns:
            Dict with relationship type, constraints, and confidence
        """
        if not self._client:
            return {"error": "Client not initialized", "related": False}

        prompt = f"""Analyze these two prediction market questions and determine if they are logically related:

MARKET A: {market_a_question}
MARKET B: {market_b_question}

Determine:
1. Are these markets about related topics? (yes/no)
2. Is there a logical constraint between them? Examples:
   - IMPLIES: If A is YES, then B must be YES
   - CALENDAR: Same event, different timeframes (earlier date <= later date)
   - MUTUALLY_EXCLUSIVE: Both cannot be YES
   - CONDITIONAL: One is a subset of the other
   - CORRELATED: Related but no strict logical constraint
   - UNRELATED: No meaningful relationship
3. What is the expected price relationship?
4. Confidence in this analysis (0.0-1.0)

Respond in JSON:
{{
    "related": true/false,
    "relationship_type": "IMPLIES|CALENDAR|MUTUALLY_EXCLUSIVE|CONDITIONAL|CORRELATED|UNRELATED",
    "constraint": "Description of the logical constraint if any",
    "price_relationship": "A <= B" or "A >= B" or "A + B <= 1" or "none",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation"
}}
"""

        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 512,
                },
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]

            import json
            try:
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    json_str = content[json_start:json_end].strip()
                elif "{" in content:
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    json_str = content[json_start:json_end]
                else:
                    json_str = content

                return json.loads(json_str)

            except json.JSONDecodeError:
                return {
                    "related": False,
                    "relationship_type": "UNKNOWN",
                    "confidence": 0.0,
                    "raw_response": content,
                }

        except Exception as e:
            logger.error(f"Perplexity relationship analysis error: {e}")
            return {"error": str(e), "related": False}

    async def get_poll_data(
        self,
        topic: str,
        candidates: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get current polling data for political markets.

        Args:
            topic: What to search for (e.g., "2024 presidential election polls")
            candidates: Optional list of candidates to focus on

        Returns:
            Dict with polling data and sources
        """
        if not self._client:
            return {"error": "Client not initialized", "polls": []}

        query = f"Latest polling data for {topic}"
        if candidates:
            query += f" focusing on {', '.join(candidates)}"
        query += ". Include poll numbers, dates, and polling organizations."

        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a polling analyst. Provide specific poll numbers with dates and sources. Focus on the most recent polls (last 7 days if available).",
                        },
                        {"role": "user", "content": query},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            data = response.json()

            answer = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])

            return {
                "summary": answer,
                "sources": citations,
                "query": topic,
            }

        except Exception as e:
            logger.error(f"Perplexity poll data error: {e}")
            return {"error": str(e), "polls": []}


# Module-level client instance
_client: Optional[PerplexityClient] = None


async def get_perplexity_client() -> PerplexityClient:
    """Get or create the Perplexity client singleton."""
    global _client
    if _client is None:
        _client = PerplexityClient()
        await _client.connect()
    return _client
