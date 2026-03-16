"""Unified risk management layer.

This module provides multi-venue risk management for PolyBot:
- Pre-trade risk checks
- Cross-venue exposure aggregation
- Delta hedging recommendations
- Position and PnL tracking

Usage:
    from polybot.risk import get_risk_manager, RiskCheckResult

    # Get global risk manager
    risk = get_risk_manager()

    # Register venues
    risk.register_venue("polymarket")
    risk.register_venue("binance")

    # Pre-trade check
    result = risk.check_pre_trade(
        venue="polymarket",
        symbol="market_123",
        side="buy",
        size=100.0,
        price=0.65,
    )

    if result.approved:
        # Execute trade
        pass
"""

from polybot.risk.exposure import VenueExposure
from polybot.risk.hedge import HedgeCalculator
from polybot.risk.manager import RiskManager, get_risk_manager, reset_risk_manager
from polybot.risk.models import (
    AssetClass,
    HedgeRecommendation,
    PortfolioSnapshot,
    RiskAlert,
    RiskCheckResult,
    RiskMetrics,
    VenuePosition,
)
from polybot.risk.portfolio import PortfolioRisk

__all__ = [
    # Models
    "AssetClass",
    "VenuePosition",
    "RiskCheckResult",
    "HedgeRecommendation",
    "PortfolioSnapshot",
    "RiskAlert",
    "RiskMetrics",
    # Core classes
    "VenueExposure",
    "PortfolioRisk",
    "HedgeCalculator",
    "RiskManager",
    # Functions
    "get_risk_manager",
    "reset_risk_manager",
]
