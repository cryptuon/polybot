"""Calendar Spread Strategy.

Exploits logical price relationships between markets with different
time horizons for the same event. Uses LLM to identify related pairs.

Example: "BTC 100k by March" <= "BTC 100k by June" (always)
If March=0.20 and June=0.15 → arbitrage opportunity (buy June, wait)

Key Features:
- LLM-based pair identification
- Caches pair relationships
- Exploits temporal arbitrage
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from polybot.config import Settings
from polybot.core.perplexity_client import PerplexityClient, get_perplexity_client
from polybot.models.messages import PriceUpdate, Signal, SignalAction
from polybot.models.position import Position
from polybot.strategies.base import BaseStrategy, StrategyConfig


@dataclass
class CalendarSpreadConfig(StrategyConfig):
    """Calendar spread configuration."""

    # Minimum mispricing to trade
    min_spread: float = 0.03  # 3% mispricing

    # Position sizing
    order_size: float = 25.0

    # LLM analysis
    relationship_cache_hours: float = 24.0  # Cache pair analysis for 24h
    max_pairs_to_analyze: int = 100

    # Rate limiting
    signal_cooldown_sec: float = 300.0
    max_analyses_per_hour: int = 20

    # Confidence
    min_relationship_confidence: float = 0.75


@dataclass
class MarketPairRelationship:
    """Cached relationship between two markets."""

    market_a_id: str
    market_b_id: str
    relationship_type: str  # CALENDAR, IMPLIES, CONDITIONAL, etc.
    price_constraint: str  # "A <= B", "A >= B", etc.
    confidence: float
    analyzed_at: datetime
    reasoning: str


class CalendarSpreadStrategy(BaseStrategy):
    """Calendar spread strategy.

    Identifies markets with temporal relationships (same event,
    different deadlines) and trades mispricings.
    """

    name = "calendar_spread"
    description = "Arbitrage on time-based market relationships"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._perplexity: Optional[PerplexityClient] = None
        self._pair_cache: Dict[str, MarketPairRelationship] = {}
        self._analyzed_pairs: Set[str] = set()
        self._analyses_this_hour: int = 0
        self._hour_start: float = time.time()
        self._signal_cooldowns: Dict[str, float] = {}

        # Track market questions for pair matching
        self._market_questions: Dict[str, str] = {}

    def _get_config(self) -> StrategyConfig:
        """Get calendar spread config."""
        return CalendarSpreadConfig()

    @property
    def cal_config(self) -> CalendarSpreadConfig:
        """Get typed config."""
        return self._config  # type: ignore

    async def _on_start(self) -> None:
        """Initialize clients."""
        self._perplexity = await get_perplexity_client()

        # Load markets to build question index
        if self._sqlite:
            markets = await self._sqlite.get_active_markets(limit=500)
            for m in markets:
                self._market_questions[m.id] = m.question

        self._logger.info(f"Calendar spread initialized with {len(self._market_questions)} markets")

    async def scan(self, update: PriceUpdate) -> List[Signal]:
        """Scan for calendar spread opportunities.

        Args:
            update: Price update

        Returns:
            List of signals
        """
        signals: List[Signal] = []

        # Rate limiting
        now = time.time()
        if now - self._hour_start > 3600:
            self._analyses_this_hour = 0
            self._hour_start = now

        # Cooldown check
        last_signal = self._signal_cooldowns.get(update.market_id, 0)
        if now - last_signal < self.cal_config.signal_cooldown_sec:
            return signals

        # Get market question
        if update.market_id not in self._market_questions:
            if self._sqlite:
                market = await self._sqlite.get_market(update.market_id)
                if market:
                    self._market_questions[update.market_id] = market.question
            if update.market_id not in self._market_questions:
                return signals

        current_question = self._market_questions[update.market_id]

        # Find related markets in cache
        for pair_key, relationship in self._pair_cache.items():
            if update.market_id not in pair_key:
                continue

            if relationship.relationship_type not in ("CALENDAR", "IMPLIES"):
                continue

            if relationship.confidence < self.cal_config.min_relationship_confidence:
                continue

            # Get the other market's price
            other_market_id = (
                relationship.market_b_id
                if relationship.market_a_id == update.market_id
                else relationship.market_a_id
            )

            other_price = self._prices.get(other_market_id)
            if not other_price:
                continue

            # Check for mispricing based on constraint
            signal = self._check_mispricing(
                update, other_price, relationship
            )
            if signal:
                signals.append(signal)
                self._signal_cooldowns[update.market_id] = now

        # Periodically analyze new potential pairs
        if self._analyses_this_hour < self.cal_config.max_analyses_per_hour:
            await self._find_new_pairs(update.market_id, current_question)

        return signals

    def _check_mispricing(
        self,
        current: PriceUpdate,
        other: PriceUpdate,
        relationship: MarketPairRelationship,
    ) -> Optional[Signal]:
        """Check if there's a mispricing between related markets.

        Args:
            current: Current market's price
            other: Related market's price
            relationship: The relationship between them

        Returns:
            Signal if mispricing found, None otherwise
        """
        # Determine which is A and which is B
        if current.market_id == relationship.market_a_id:
            price_a, price_b = current.mid, other.mid
            market_a, market_b = current, other
        else:
            price_a, price_b = other.mid, current.mid
            market_a, market_b = other, current

        constraint = relationship.price_constraint

        if constraint == "A <= B":
            # A should be <= B
            # If A > B, that's a mispricing
            if price_a > price_b + self.cal_config.min_spread:
                # Buy B (underpriced), conceptually sell A
                size = self.cal_config.order_size / market_b.ask if market_b.ask else 0

                return Signal(
                    strategy=self.name,
                    market_id=market_b.market_id,
                    token_id=market_b.token_id,
                    action=SignalAction.BUY,
                    price=market_b.ask,
                    size=size,
                    reason=f"Calendar spread: {relationship.relationship_type}, A={price_a:.3f} > B={price_b:.3f}, constraint={constraint}",
                    confidence=relationship.confidence * 0.8,
                    bid=market_b.bid,
                    ask=market_b.ask,
                )

        elif constraint == "A >= B":
            # A should be >= B
            if price_a + self.cal_config.min_spread < price_b:
                # Buy A (underpriced)
                size = self.cal_config.order_size / market_a.ask if market_a.ask else 0

                return Signal(
                    strategy=self.name,
                    market_id=market_a.market_id,
                    token_id=market_a.token_id,
                    action=SignalAction.BUY,
                    price=market_a.ask,
                    size=size,
                    reason=f"Calendar spread: {relationship.relationship_type}, A={price_a:.3f} < B={price_b:.3f}, constraint={constraint}",
                    confidence=relationship.confidence * 0.8,
                    bid=market_a.bid,
                    ask=market_a.ask,
                )

        return None

    async def _find_new_pairs(self, market_id: str, question: str) -> None:
        """Find potentially related markets and analyze relationships.

        Args:
            market_id: Current market ID
            question: Current market question
        """
        if not self._perplexity:
            return

        # Look for markets with similar questions
        similar_markets = self._find_similar_questions(question, market_id)

        for other_id, other_question in similar_markets[:3]:  # Limit checks
            pair_key = self._make_pair_key(market_id, other_id)

            if pair_key in self._analyzed_pairs:
                continue

            self._analyzed_pairs.add(pair_key)
            self._analyses_this_hour += 1

            # Analyze relationship with LLM
            try:
                result = await self._perplexity.analyze_market_relationship(
                    question, other_question
                )

                if result.get("related") and result.get("confidence", 0) >= self.cal_config.min_relationship_confidence:
                    relationship = MarketPairRelationship(
                        market_a_id=market_id,
                        market_b_id=other_id,
                        relationship_type=result.get("relationship_type", "UNKNOWN"),
                        price_constraint=result.get("price_relationship", "none"),
                        confidence=result.get("confidence", 0),
                        analyzed_at=datetime.utcnow(),
                        reasoning=result.get("reasoning", ""),
                    )

                    self._pair_cache[pair_key] = relationship
                    self._logger.info(
                        f"Found calendar pair: {relationship.relationship_type}\n"
                        f"  A: {question[:50]}...\n"
                        f"  B: {other_question[:50]}...\n"
                        f"  Constraint: {relationship.price_constraint}"
                    )

            except Exception as e:
                self._logger.error(f"Error analyzing pair relationship: {e}")

    def _find_similar_questions(
        self,
        question: str,
        exclude_id: str,
    ) -> List[Tuple[str, str]]:
        """Find markets with similar questions (potential pairs).

        Uses simple keyword matching for speed.
        """
        # Extract key terms from question
        question_lower = question.lower()
        key_terms = []

        # Look for specific patterns
        if "bitcoin" in question_lower or "btc" in question_lower:
            key_terms.append("bitcoin")
            key_terms.append("btc")
        if "trump" in question_lower:
            key_terms.append("trump")
        if "election" in question_lower:
            key_terms.append("election")

        # Look for date patterns
        import re
        dates = re.findall(r'\b(january|february|march|april|may|june|july|august|september|october|november|december|\d{4})\b', question_lower)
        key_terms.extend(dates)

        if not key_terms:
            return []

        # Find markets matching key terms
        similar = []
        for mid, q in self._market_questions.items():
            if mid == exclude_id:
                continue

            q_lower = q.lower()
            matches = sum(1 for term in key_terms if term in q_lower)

            if matches >= 2:  # At least 2 matching terms
                similar.append((mid, q))

        return similar[:10]  # Limit results

    def _make_pair_key(self, id_a: str, id_b: str) -> str:
        """Make consistent pair key regardless of order."""
        return ":".join(sorted([id_a, id_b]))

    async def should_exit(self, position: Position, update: PriceUpdate) -> bool:
        """Check if calendar spread position should exit."""
        # Exit if spread converged
        # This would need to track the paired position
        return False

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        base_stats = super().get_stats()
        base_stats.update({
            "cached_pairs": len(self._pair_cache),
            "analyzed_pairs": len(self._analyzed_pairs),
            "analyses_this_hour": self._analyses_this_hour,
            "calendar_pairs": sum(1 for p in self._pair_cache.values() if p.relationship_type == "CALENDAR"),
            "implies_pairs": sum(1 for p in self._pair_cache.values() if p.relationship_type == "IMPLIES"),
        })
        return base_stats
