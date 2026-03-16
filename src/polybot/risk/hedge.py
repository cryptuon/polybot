"""Hedge calculator for delta neutralization."""

import logging
from typing import Dict, List, Optional

from polybot.risk.models import HedgeRecommendation, VenuePosition
from polybot.risk.portfolio import PortfolioRisk

logger = logging.getLogger(__name__)


class HedgeCalculator:
    """Calculates hedging requirements for delta neutrality.

    Supports:
    - Delta hedging with spot/perps
    - Cross-venue hedge routing
    - Urgency-based recommendations

    Example:
        calculator = HedgeCalculator(portfolio, delta_threshold=100.0)
        recommendation = calculator.calculate_delta_hedge()
        if recommendation:
            print(f"Hedge needed: {recommendation.side} {recommendation.size} {recommendation.symbol}")
    """

    # Default hedge instruments by underlying
    DEFAULT_HEDGE_INSTRUMENTS = {
        "BTC": {"venue": "binance", "symbol": "BTCUSDT", "type": "spot"},
        "ETH": {"venue": "binance", "symbol": "ETHUSDT", "type": "spot"},
        "SOL": {"venue": "binance", "symbol": "SOLUSDT", "type": "spot"},
    }

    def __init__(
        self,
        portfolio: PortfolioRisk,
        delta_threshold: float = 100.0,
        rebalance_threshold: float = 0.1,
        default_hedge_venue: str = "binance",
    ) -> None:
        """Initialize hedge calculator.

        Args:
            portfolio: Portfolio risk tracker
            delta_threshold: USD delta to trigger hedge
            rebalance_threshold: Fraction of delta to trigger rebalance (0-1)
            default_hedge_venue: Default venue for hedging
        """
        self._portfolio = portfolio
        self._delta_threshold = delta_threshold
        self._rebalance_threshold = rebalance_threshold
        self._default_hedge_venue = default_hedge_venue

        # Custom hedge mappings (can be extended)
        self._hedge_mappings: Dict[str, Dict] = dict(self.DEFAULT_HEDGE_INSTRUMENTS)

    @property
    def delta_threshold(self) -> float:
        """Get delta threshold."""
        return self._delta_threshold

    def set_delta_threshold(self, threshold: float) -> None:
        """Update delta threshold.

        Args:
            threshold: New threshold in USD
        """
        self._delta_threshold = threshold
        logger.info(f"Delta threshold updated to ${threshold}")

    def add_hedge_mapping(
        self,
        underlying: str,
        venue: str,
        symbol: str,
        instrument_type: str = "spot",
    ) -> None:
        """Add a hedge instrument mapping.

        Args:
            underlying: Underlying asset (e.g., "BTC")
            venue: Hedge venue
            symbol: Hedge instrument symbol
            instrument_type: Instrument type (spot, perp, futures)
        """
        self._hedge_mappings[underlying] = {
            "venue": venue,
            "symbol": symbol,
            "type": instrument_type,
        }

    # =========================================================================
    # Delta Hedging
    # =========================================================================

    def calculate_delta_hedge(self) -> Optional[HedgeRecommendation]:
        """Calculate hedge needed to neutralize portfolio delta.

        Returns:
            HedgeRecommendation if hedge needed, None otherwise
        """
        net_delta = self._portfolio.net_delta

        # Check if hedge is needed
        if abs(net_delta) < self._delta_threshold:
            return None

        # Determine hedge direction and size
        if net_delta > 0:
            # Long delta -> sell to hedge
            side = "sell"
            size = abs(net_delta)
        else:
            # Short delta -> buy to hedge
            side = "buy"
            size = abs(net_delta)

        # Determine urgency based on delta magnitude
        urgency = self._calculate_urgency(abs(net_delta))

        # Get hedge instrument (default to BTC for now)
        hedge_info = self._get_best_hedge_instrument()

        return HedgeRecommendation(
            venue=hedge_info["venue"],
            symbol=hedge_info["symbol"],
            side=side,
            size=size,
            reason=f"Delta neutralization: net_delta=${net_delta:.2f}",
            urgency=urgency,
            delta_impact=-net_delta,
        )

    def calculate_venue_hedge(self, venue: str) -> Optional[HedgeRecommendation]:
        """Calculate hedge for a specific venue's delta.

        Args:
            venue: Venue to hedge

        Returns:
            HedgeRecommendation if needed
        """
        venue_exp = self._portfolio.get_venue_exposure(venue)
        if not venue_exp:
            return None

        venue_delta = venue_exp.net_delta

        if abs(venue_delta) < self._delta_threshold:
            return None

        side = "sell" if venue_delta > 0 else "buy"
        size = abs(venue_delta)
        urgency = self._calculate_urgency(abs(venue_delta))
        hedge_info = self._get_best_hedge_instrument()

        return HedgeRecommendation(
            venue=hedge_info["venue"],
            symbol=hedge_info["symbol"],
            side=side,
            size=size,
            reason=f"Hedge {venue} delta: ${venue_delta:.2f}",
            urgency=urgency,
            delta_impact=-venue_delta,
        )

    def calculate_position_hedge(
        self,
        position: VenuePosition,
    ) -> Optional[HedgeRecommendation]:
        """Calculate hedge for a specific position.

        Args:
            position: Position to hedge

        Returns:
            HedgeRecommendation if available
        """
        position_delta = position.signed_delta

        if abs(position_delta) < self._delta_threshold:
            return None

        # Try to find hedge instrument for this position
        hedge_info = self._get_hedge_for_position(position)
        if not hedge_info:
            logger.warning(f"No hedge mapping for {position.symbol}")
            return None

        side = "sell" if position_delta > 0 else "buy"
        size = abs(position_delta)

        return HedgeRecommendation(
            venue=hedge_info["venue"],
            symbol=hedge_info["symbol"],
            side=side,
            size=size,
            reason=f"Position hedge: {position.symbol}",
            urgency="normal",
            delta_impact=-position_delta,
        )

    # =========================================================================
    # Hedge Analysis
    # =========================================================================

    def get_hedge_status(self) -> Dict:
        """Get current hedging status.

        Returns:
            Dict with hedge metrics
        """
        net_delta = self._portfolio.net_delta
        recommendation = self.calculate_delta_hedge()

        return {
            "net_delta": round(net_delta, 2),
            "delta_threshold": self._delta_threshold,
            "hedge_needed": abs(net_delta) > self._delta_threshold,
            "urgency": self._calculate_urgency(abs(net_delta)) if abs(net_delta) > self._delta_threshold else None,
            "recommendation": recommendation.model_dump() if recommendation else None,
            "delta_by_venue": self._portfolio.get_delta_by_venue(),
        }

    def get_hedge_opportunities(self) -> List[HedgeRecommendation]:
        """Get all hedge recommendations (portfolio + per-venue).

        Returns:
            List of hedge recommendations
        """
        recommendations = []

        # Portfolio-level hedge
        portfolio_hedge = self.calculate_delta_hedge()
        if portfolio_hedge:
            recommendations.append(portfolio_hedge)

        # Per-venue hedges (if significantly different from portfolio)
        for venue in self._portfolio.get_venues():
            venue_hedge = self.calculate_venue_hedge(venue)
            if venue_hedge and venue_hedge.size > self._delta_threshold * 0.5:
                recommendations.append(venue_hedge)

        return recommendations

    def estimate_hedge_cost(self, recommendation: HedgeRecommendation) -> float:
        """Estimate cost of executing a hedge.

        Args:
            recommendation: Hedge recommendation

        Returns:
            Estimated cost in USD (spread + fees)
        """
        # Rough estimate: 0.1% of notional for spot, 0.05% for perps
        fee_rate = 0.001  # 0.1%
        spread_cost = recommendation.size * 0.0005  # 0.05% spread estimate
        fee_cost = recommendation.size * fee_rate

        return spread_cost + fee_cost

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _calculate_urgency(self, delta_magnitude: float) -> str:
        """Calculate urgency based on delta magnitude.

        Args:
            delta_magnitude: Absolute delta value

        Returns:
            Urgency level string
        """
        if delta_magnitude > self._delta_threshold * 5:
            return "critical"
        elif delta_magnitude > self._delta_threshold * 3:
            return "high"
        elif delta_magnitude > self._delta_threshold * 1.5:
            return "normal"
        else:
            return "low"

    def _get_best_hedge_instrument(self) -> Dict:
        """Get best hedge instrument (defaults to BTC spot).

        Returns:
            Hedge instrument info dict
        """
        # For now, default to BTC
        # Future: analyze portfolio to determine best hedge
        if "BTC" in self._hedge_mappings:
            return self._hedge_mappings["BTC"]

        return {
            "venue": self._default_hedge_venue,
            "symbol": "BTCUSDT",
            "type": "spot",
        }

    def _get_hedge_for_position(self, position: VenuePosition) -> Optional[Dict]:
        """Get hedge instrument for a position.

        Args:
            position: Position to hedge

        Returns:
            Hedge instrument info or None
        """
        # Extract underlying from symbol
        symbol = position.symbol.upper()

        # Try direct mapping
        for underlying, hedge in self._hedge_mappings.items():
            if underlying in symbol:
                return hedge

        return None

    def __repr__(self) -> str:
        return (
            f"<HedgeCalculator "
            f"threshold=${self._delta_threshold} "
            f"instruments={len(self._hedge_mappings)}>"
        )
