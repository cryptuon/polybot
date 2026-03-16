"""Poll Divergence Strategy.

Trades political markets when polling data diverges from market prices.
Uses Perplexity to get real-time polling data.

Example: Polls show 55% Trump, market shows 48% → buy Trump

Key Features:
- Real-time poll data via Perplexity
- Compares polls to market prices
- Trades toward poll consensus
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from polybot.config import Settings
from polybot.core.perplexity_client import PerplexityClient, get_perplexity_client
from polybot.models.messages import PriceUpdate, Signal, SignalAction
from polybot.models.position import Position
from polybot.strategies.base import BaseStrategy, StrategyConfig


@dataclass
class PollDivergenceConfig(StrategyConfig):
    """Poll divergence configuration."""

    # Minimum divergence to trade
    min_divergence_pct: float = 0.05  # 5% gap between polls and market

    # Position sizing
    order_size: float = 30.0

    # Poll data refresh
    poll_refresh_interval_sec: float = 3600.0  # Refresh every hour
    max_poll_age_hours: float = 48.0  # Use polls from last 48 hours

    # Rate limiting
    signal_cooldown_sec: float = 600.0
    max_polls_per_hour: int = 10

    # Confidence
    min_confidence: float = 0.60


@dataclass
class PollData:
    """Cached polling data for a market."""

    market_id: str
    topic: str
    poll_probability: float  # Aggregated poll estimate
    poll_sources: List[str]
    fetched_at: datetime
    raw_summary: str


class PollDivergenceStrategy(BaseStrategy):
    """Poll divergence strategy.

    Compares polling data to market prices for political events.
    """

    name = "poll_divergence"
    description = "Trade on poll vs market price divergence"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._perplexity: Optional[PerplexityClient] = None
        self._poll_cache: Dict[str, PollData] = {}
        self._signal_cooldowns: Dict[str, float] = {}
        self._polls_this_hour: int = 0
        self._hour_start: float = time.time()

        # Political keywords to identify relevant markets
        self._political_keywords = [
            "election", "president", "senate", "house", "congress",
            "governor", "trump", "biden", "republican", "democrat",
            "gop", "vote", "primary", "candidate", "poll"
        ]

    def _get_config(self) -> StrategyConfig:
        """Get poll divergence config."""
        return PollDivergenceConfig()

    @property
    def poll_config(self) -> PollDivergenceConfig:
        """Get typed config."""
        return self._config  # type: ignore

    async def _on_start(self) -> None:
        """Initialize Perplexity client."""
        self._perplexity = await get_perplexity_client()
        self._logger.info("Poll divergence strategy initialized")

    def _is_political_market(self, question: str) -> bool:
        """Check if market is political/poll-relevant.

        Args:
            question: Market question

        Returns:
            True if this is a political market
        """
        question_lower = question.lower()
        return any(kw in question_lower for kw in self._political_keywords)

    async def scan(self, update: PriceUpdate) -> List[Signal]:
        """Scan for poll divergence opportunities.

        Args:
            update: Price update

        Returns:
            List of signals
        """
        signals: List[Signal] = []
        now = time.time()

        # Rate limiting
        if now - self._hour_start > 3600:
            self._polls_this_hour = 0
            self._hour_start = now

        # Check cooldown
        if now - self._signal_cooldowns.get(update.market_id, 0) < self.poll_config.signal_cooldown_sec:
            return signals

        # Get market info
        if not self._sqlite:
            return signals

        market = await self._sqlite.get_market(update.market_id)
        if not market:
            return signals

        # Only process political markets
        if not self._is_political_market(market.question):
            return signals

        # Check if we have recent poll data
        poll_data = self._poll_cache.get(update.market_id)

        if poll_data:
            # Check if poll data is fresh
            age_hours = (datetime.utcnow() - poll_data.fetched_at).total_seconds() / 3600
            if age_hours > self.poll_config.max_poll_age_hours:
                poll_data = None

        # Fetch new poll data if needed
        if not poll_data and self._polls_this_hour < self.poll_config.max_polls_per_hour:
            poll_data = await self._fetch_poll_data(update.market_id, market.question)

        if not poll_data:
            return signals

        # Compare polls to market price
        market_price = update.mid
        poll_price = poll_data.poll_probability

        divergence = poll_price - market_price

        if abs(divergence) >= self.poll_config.min_divergence_pct:
            if divergence > 0:
                # Polls higher than market → buy
                if update.ask and update.ask > 0:
                    size = self.poll_config.order_size / update.ask
                    confidence = min(0.85, self.poll_config.min_confidence + abs(divergence))

                    signals.append(Signal(
                        strategy=self.name,
                        market_id=update.market_id,
                        token_id=update.token_id,
                        action=SignalAction.BUY,
                        price=update.ask,
                        size=size,
                        reason=f"Poll divergence: polls={poll_price*100:.1f}% > market={market_price*100:.1f}% (gap={divergence*100:.1f}%)",
                        confidence=confidence,
                        bid=update.bid,
                        ask=update.ask,
                    ))
            else:
                # Polls lower than market → sell
                if update.bid and update.bid > 0:
                    size = self.poll_config.order_size / update.bid
                    confidence = min(0.85, self.poll_config.min_confidence + abs(divergence))

                    signals.append(Signal(
                        strategy=self.name,
                        market_id=update.market_id,
                        token_id=update.token_id,
                        action=SignalAction.SELL,
                        price=update.bid,
                        size=size,
                        reason=f"Poll divergence: polls={poll_price*100:.1f}% < market={market_price*100:.1f}% (gap={abs(divergence)*100:.1f}%)",
                        confidence=confidence,
                        bid=update.bid,
                        ask=update.ask,
                    ))

            self._signal_cooldowns[update.market_id] = now

        return signals

    async def _fetch_poll_data(
        self,
        market_id: str,
        question: str,
    ) -> Optional[PollData]:
        """Fetch polling data for a political market.

        Args:
            market_id: Market ID
            question: Market question

        Returns:
            Poll data if available
        """
        if not self._perplexity:
            return None

        try:
            self._polls_this_hour += 1

            # Extract topic from question
            topic = self._extract_poll_topic(question)

            result = await self._perplexity.get_poll_data(topic)

            if "error" in result:
                return None

            # Parse poll probability from summary
            poll_prob = self._extract_probability(result.get("summary", ""), question)

            if poll_prob is None:
                return None

            poll_data = PollData(
                market_id=market_id,
                topic=topic,
                poll_probability=poll_prob,
                poll_sources=result.get("sources", []),
                fetched_at=datetime.utcnow(),
                raw_summary=result.get("summary", ""),
            )

            self._poll_cache[market_id] = poll_data

            self._logger.info(
                f"Poll data for {market_id[:8]}...: {poll_prob*100:.1f}%\n"
                f"  Topic: {topic}\n"
                f"  Sources: {len(poll_data.poll_sources)}"
            )

            return poll_data

        except Exception as e:
            self._logger.error(f"Error fetching poll data: {e}")
            return None

    def _extract_poll_topic(self, question: str) -> str:
        """Extract search topic from market question.

        Args:
            question: Market question

        Returns:
            Search topic for polling
        """
        # Try to extract key entities
        question_lower = question.lower()

        if "trump" in question_lower:
            if "election" in question_lower or "president" in question_lower:
                return "Trump presidential election polls"
            return "Trump polls"

        if "biden" in question_lower:
            return "Biden approval polls"

        if "senate" in question_lower:
            return "Senate election polls"

        if "house" in question_lower:
            return "House election polls"

        # Generic fallback
        return question

    def _extract_probability(self, summary: str, question: str) -> Optional[float]:
        """Extract probability from poll summary.

        Args:
            summary: Poll summary text
            question: Original question for context

        Returns:
            Probability estimate or None
        """
        # Look for percentage patterns
        percentages = re.findall(r'(\d+(?:\.\d+)?)\s*%', summary)

        if not percentages:
            return None

        # Try to find the most relevant percentage
        # This is a simple heuristic - could be improved with LLM
        values = [float(p) / 100 for p in percentages if 0 < float(p) < 100]

        if not values:
            return None

        # If question mentions a specific candidate, try to match
        question_lower = question.lower()

        # For "Will X win?" questions, look for X's percentage
        # This is simplified - real implementation would need more context

        # Default to first reasonable percentage
        return values[0]

    async def should_exit(self, position: Position, update: PriceUpdate) -> bool:
        """Check if poll divergence position should exit.

        Exit when divergence closes or reverses.
        """
        poll_data = self._poll_cache.get(position.market_id)

        if not poll_data:
            # No poll data - exit after some time
            age = (datetime.utcnow() - position.entry_time).total_seconds() / 3600
            if age > 24:  # Exit after 24 hours if no data
                return True
            return False

        # Check if divergence closed
        market_price = update.mid
        poll_price = poll_data.poll_probability
        divergence = poll_price - market_price

        if position.side == "BUY":
            # We bought because polls > market
            # Exit if divergence closed or reversed
            if divergence < self.poll_config.min_divergence_pct / 2:
                self._logger.info(f"Poll divergence closed: {divergence*100:.1f}%")
                return True

        else:  # SELL
            # We sold because polls < market
            if divergence > -self.poll_config.min_divergence_pct / 2:
                self._logger.info(f"Poll divergence closed: {divergence*100:.1f}%")
                return True

        return False

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        base_stats = super().get_stats()
        base_stats.update({
            "cached_polls": len(self._poll_cache),
            "polls_this_hour": self._polls_this_hour,
            "political_markets": len([p for p in self._poll_cache.values()]),
        })
        return base_stats
