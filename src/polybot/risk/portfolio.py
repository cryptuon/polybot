"""Cross-venue portfolio risk aggregation."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from polybot.risk.exposure import VenueExposure
from polybot.risk.models import (
    AssetClass,
    PortfolioSnapshot,
    RiskMetrics,
    VenuePosition,
)

logger = logging.getLogger(__name__)


class PortfolioRisk:
    """Aggregates risk across all venues.

    Provides portfolio-level view of:
    - Total exposure across venues
    - Net delta and Greeks
    - Concentration metrics
    - Historical snapshots

    Example:
        portfolio = PortfolioRisk()
        portfolio.register_venue("polymarket")
        portfolio.register_venue("binance")

        # Get cross-venue metrics
        print(f"Total exposure: ${portfolio.total_exposure_usd}")
        print(f"Net delta: {portfolio.net_delta}")
    """

    def __init__(self, max_snapshots: int = 1000) -> None:
        """Initialize portfolio risk tracker.

        Args:
            max_snapshots: Maximum snapshots to keep in history
        """
        self._exposures: Dict[str, VenueExposure] = {}
        self._snapshots: List[PortfolioSnapshot] = []
        self._max_snapshots = max_snapshots

    # =========================================================================
    # Venue Registration
    # =========================================================================

    def register_venue(self, venue: str) -> VenueExposure:
        """Register a venue for tracking.

        Args:
            venue: Venue identifier

        Returns:
            VenueExposure for the venue
        """
        if venue not in self._exposures:
            self._exposures[venue] = VenueExposure(venue)
            logger.info(f"Registered venue for risk tracking: {venue}")
        return self._exposures[venue]

    def get_venue_exposure(self, venue: str) -> Optional[VenueExposure]:
        """Get exposure tracker for a venue.

        Args:
            venue: Venue identifier

        Returns:
            VenueExposure or None
        """
        return self._exposures.get(venue)

    def get_venues(self) -> List[str]:
        """Get list of registered venues.

        Returns:
            List of venue identifiers
        """
        return list(self._exposures.keys())

    # =========================================================================
    # Aggregated Exposure
    # =========================================================================

    @property
    def total_exposure_usd(self) -> float:
        """Total exposure across all venues."""
        return sum(exp.total_exposure_usd for exp in self._exposures.values())

    @property
    def long_exposure_usd(self) -> float:
        """Total long exposure across all venues."""
        return sum(exp.long_exposure_usd for exp in self._exposures.values())

    @property
    def short_exposure_usd(self) -> float:
        """Total short exposure across all venues."""
        return sum(exp.short_exposure_usd for exp in self._exposures.values())

    @property
    def net_exposure_usd(self) -> float:
        """Net exposure across all venues."""
        return sum(exp.net_exposure_usd for exp in self._exposures.values())

    @property
    def net_delta(self) -> float:
        """Net delta across all venues."""
        return sum(exp.net_delta for exp in self._exposures.values())

    @property
    def net_gamma(self) -> float:
        """Net gamma across all venues."""
        return sum(exp.net_gamma for exp in self._exposures.values())

    @property
    def net_vega(self) -> float:
        """Net vega across all venues."""
        return sum(exp.net_vega for exp in self._exposures.values())

    @property
    def net_theta(self) -> float:
        """Net theta across all venues."""
        return sum(exp.net_theta for exp in self._exposures.values())

    @property
    def total_daily_pnl(self) -> float:
        """Total daily PnL across venues."""
        return sum(exp.daily_pnl for exp in self._exposures.values())

    @property
    def total_unrealized_pnl(self) -> float:
        """Total unrealized PnL across venues."""
        return sum(exp.unrealized_pnl for exp in self._exposures.values())

    @property
    def total_position_count(self) -> int:
        """Total position count across venues."""
        return sum(exp.position_count for exp in self._exposures.values())

    # =========================================================================
    # Exposure Breakdown
    # =========================================================================

    def get_exposure_by_venue(self) -> Dict[str, float]:
        """Get exposure breakdown by venue.

        Returns:
            Dict of venue -> exposure
        """
        return {
            venue: exp.total_exposure_usd for venue, exp in self._exposures.items()
        }

    def get_exposure_by_asset_class(self) -> Dict[str, float]:
        """Get exposure breakdown by asset class.

        Returns:
            Dict of asset_class -> exposure
        """
        by_asset: Dict[str, float] = {}
        for exp in self._exposures.values():
            for position in exp.get_positions():
                key = position.asset_class.value
                by_asset[key] = by_asset.get(key, 0) + abs(position.notional_usd)
        return by_asset

    def get_delta_by_venue(self) -> Dict[str, float]:
        """Get delta breakdown by venue.

        Returns:
            Dict of venue -> delta
        """
        return {venue: exp.net_delta for venue, exp in self._exposures.items()}

    # =========================================================================
    # Position Access
    # =========================================================================

    def get_all_positions(self) -> List[VenuePosition]:
        """Get all positions across venues.

        Returns:
            List of all positions
        """
        positions = []
        for exp in self._exposures.values():
            positions.extend(exp.get_positions())
        return positions

    def get_positions_by_venue(self, venue: str) -> List[VenuePosition]:
        """Get positions for a specific venue.

        Args:
            venue: Venue identifier

        Returns:
            List of positions
        """
        exp = self._exposures.get(venue)
        return exp.get_positions() if exp else []

    def get_positions_for_symbol(self, symbol: str) -> List[VenuePosition]:
        """Get positions for a specific symbol across venues.

        Args:
            symbol: Symbol to search for

        Returns:
            List of matching positions
        """
        positions = []
        for exp in self._exposures.values():
            for pos in exp.get_positions():
                if pos.symbol == symbol:
                    positions.append(pos)
        return positions

    def get_positions_by_asset_class(
        self, asset_class: AssetClass
    ) -> List[VenuePosition]:
        """Get positions filtered by asset class.

        Args:
            asset_class: Asset class to filter by

        Returns:
            List of matching positions
        """
        positions = []
        for exp in self._exposures.values():
            positions.extend(exp.get_positions(asset_class))
        return positions

    # =========================================================================
    # Concentration Metrics
    # =========================================================================

    def get_concentration_metrics(self) -> Dict[str, float]:
        """Calculate concentration risk metrics.

        Returns:
            Dict with concentration metrics
        """
        total = self.total_exposure_usd
        if total == 0:
            return {
                "max_venue_concentration": 0,
                "max_position_concentration": 0,
                "herfindahl_index": 0,
                "top_3_concentration": 0,
            }

        # Venue concentration
        venue_exposures = self.get_exposure_by_venue()
        max_venue_conc = max(venue_exposures.values()) / total if venue_exposures else 0

        # Position concentration
        positions = self.get_all_positions()
        position_exposures = [abs(p.notional_usd) for p in positions]
        max_position_conc = max(position_exposures) / total if position_exposures else 0

        # Top 3 concentration
        sorted_exposures = sorted(position_exposures, reverse=True)
        top_3 = sum(sorted_exposures[:3])
        top_3_conc = top_3 / total

        # Herfindahl-Hirschman Index
        hhi = sum((e / total) ** 2 for e in position_exposures) if position_exposures else 0

        return {
            "max_venue_concentration": max_venue_conc,
            "max_position_concentration": max_position_conc,
            "herfindahl_index": hhi,
            "top_3_concentration": top_3_conc,
        }

    def get_venue_concentration(self, venue: str) -> float:
        """Get concentration for a specific venue.

        Args:
            venue: Venue identifier

        Returns:
            Concentration as fraction (0-1)
        """
        total = self.total_exposure_usd
        if total == 0:
            return 0

        exp = self._exposures.get(venue)
        if not exp:
            return 0

        return exp.total_exposure_usd / total

    # =========================================================================
    # Snapshots
    # =========================================================================

    def take_snapshot(self) -> PortfolioSnapshot:
        """Capture current portfolio state.

        Returns:
            PortfolioSnapshot with current metrics
        """
        snapshot = PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            total_exposure_usd=self.total_exposure_usd,
            net_delta=self.net_delta,
            positions_by_venue=self.get_exposure_by_venue(),
            positions_by_asset=self.get_exposure_by_asset_class(),
            daily_pnl=self.total_daily_pnl,
        )

        self._snapshots.append(snapshot)

        # Trim if needed
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots :]

        return snapshot

    def get_snapshots(self, limit: int = 100) -> List[PortfolioSnapshot]:
        """Get recent snapshots.

        Args:
            limit: Maximum number to return

        Returns:
            List of recent snapshots
        """
        return self._snapshots[-limit:]

    def get_latest_snapshot(self) -> Optional[PortfolioSnapshot]:
        """Get most recent snapshot.

        Returns:
            Latest snapshot or None
        """
        return self._snapshots[-1] if self._snapshots else None

    # =========================================================================
    # Risk Metrics
    # =========================================================================

    def get_risk_metrics(self) -> RiskMetrics:
        """Calculate comprehensive risk metrics.

        Returns:
            RiskMetrics with all current metrics
        """
        concentration = self.get_concentration_metrics()

        return RiskMetrics(
            total_exposure_usd=self.total_exposure_usd,
            long_exposure_usd=self.long_exposure_usd,
            short_exposure_usd=self.short_exposure_usd,
            net_exposure_usd=self.net_exposure_usd,
            exposure_by_venue=self.get_exposure_by_venue(),
            exposure_by_asset_class=self.get_exposure_by_asset_class(),
            net_delta=self.net_delta,
            net_gamma=self.net_gamma,
            net_vega=self.net_vega,
            net_theta=self.net_theta,
            daily_pnl=self.total_daily_pnl,
            unrealized_pnl=self.total_unrealized_pnl,
            max_venue_concentration=concentration["max_venue_concentration"],
            max_position_concentration=concentration["max_position_concentration"],
            herfindahl_index=concentration["herfindahl_index"],
            position_count=self.total_position_count,
            timestamp=datetime.utcnow(),
        )

    # =========================================================================
    # Daily Reset
    # =========================================================================

    def reset_daily_stats(self) -> None:
        """Reset daily counters for all venues."""
        for exp in self._exposures.values():
            exp.reset_daily_stats()
        logger.info("Reset daily stats for all venues")

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> Dict:
        """Serialize for reporting.

        Returns:
            Dict representation
        """
        return {
            "total_exposure_usd": round(self.total_exposure_usd, 2),
            "net_delta": round(self.net_delta, 4),
            "daily_pnl": round(self.total_daily_pnl, 2),
            "position_count": self.total_position_count,
            "venues": {
                venue: exp.to_dict() for venue, exp in self._exposures.items()
            },
            "concentration": self.get_concentration_metrics(),
        }

    def __repr__(self) -> str:
        return (
            f"<PortfolioRisk "
            f"venues={len(self._exposures)} "
            f"exposure=${self.total_exposure_usd:.2f} "
            f"delta={self.net_delta:.2f}>"
        )
