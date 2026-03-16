"""Central risk management orchestrator."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from polybot.config import Settings, get_settings
from polybot.risk.exposure import VenueExposure
from polybot.risk.hedge import HedgeCalculator
from polybot.risk.models import (
    AssetClass,
    HedgeRecommendation,
    RiskAlert,
    RiskCheckResult,
    RiskMetrics,
    VenuePosition,
)
from polybot.risk.portfolio import PortfolioRisk

logger = logging.getLogger(__name__)


class RiskManager:
    """Central risk management orchestrator.

    Coordinates:
    - Pre-trade risk checks
    - Real-time exposure monitoring
    - Cross-venue aggregation
    - Hedge recommendations
    - Risk alerts

    Integration:
    - Called by ExecutorService before order submission
    - Receives position updates from venue adapters
    - Publishes risk events for monitoring

    Example:
        risk_manager = get_risk_manager()

        # Pre-trade check
        result = risk_manager.check_pre_trade(
            venue="polymarket",
            symbol="market_123",
            side="buy",
            size=100.0,
            price=0.65,
        )

        if result.approved:
            # Execute trade
            pass
        else:
            print(f"Rejected: {result.reason}")
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize risk manager.

        Args:
            settings: Application settings (loaded from env if not provided)
        """
        self._settings = settings or get_settings()
        risk_config = self._settings.risk

        # Configuration from settings
        self._max_position_size_usd = risk_config.max_position_size_usd
        self._max_total_exposure_usd = risk_config.max_total_exposure_usd
        self._max_venue_exposure_usd = risk_config.max_venue_exposure_usd
        self._daily_loss_limit_usd = risk_config.daily_loss_limit_usd
        self._max_open_orders = risk_config.max_open_orders
        self._max_venue_concentration = risk_config.max_venue_concentration
        self._max_delta = risk_config.max_delta
        self._hedge_delta_threshold = risk_config.hedge_delta_threshold
        self._auto_hedge_enabled = risk_config.auto_hedge_enabled

        # Core components
        self._portfolio = PortfolioRisk()
        self._hedge_calc = HedgeCalculator(
            self._portfolio,
            delta_threshold=self._hedge_delta_threshold,
        )

        # State tracking
        self._open_orders_count = 0
        self._last_snapshot_time: Optional[datetime] = None
        self._snapshot_interval = timedelta(seconds=risk_config.snapshot_interval_sec)

        # Shadow mode flag
        self._shadow_mode = False

        # Alerts
        self._alerts: list[RiskAlert] = []
        self._max_alerts = 100

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
        exposure = self._portfolio.register_venue(venue)
        logger.info(f"Registered venue for risk tracking: {venue}")
        return exposure

    def get_venue_exposure(self, venue: str) -> Optional[VenueExposure]:
        """Get exposure tracker for a venue.

        Args:
            venue: Venue identifier

        Returns:
            VenueExposure or None
        """
        return self._portfolio.get_venue_exposure(venue)

    # =========================================================================
    # Pre-Trade Risk Checks
    # =========================================================================

    def check_pre_trade(
        self,
        venue: str,
        symbol: str,
        side: str,
        size: float,
        price: float,
        strategy: Optional[str] = None,
    ) -> RiskCheckResult:
        """Perform pre-trade risk validation.

        Called by ExecutorService before submitting orders.

        Args:
            venue: Target venue
            symbol: Market/instrument symbol
            side: "buy" or "sell"
            size: Order size
            price: Order price
            strategy: Strategy name for attribution

        Returns:
            RiskCheckResult with approval status and any adjustments
        """
        warnings: list[str] = []
        notional = size * price

        # 1. Check position size limit
        if notional > self._max_position_size_usd:
            return RiskCheckResult(
                approved=False,
                reason=f"Position size ${notional:.2f} exceeds limit ${self._max_position_size_usd:.2f}",
            )

        # 2. Check daily loss limit
        daily_pnl = self._portfolio.total_daily_pnl
        if daily_pnl < -self._daily_loss_limit_usd:
            return RiskCheckResult(
                approved=False,
                reason=f"Daily loss limit reached: ${daily_pnl:.2f}",
            )

        # 3. Check total exposure limit
        current_exposure = self._portfolio.total_exposure_usd
        new_total = current_exposure + notional

        if new_total > self._max_total_exposure_usd:
            # Calculate reduced size if possible
            available = self._max_total_exposure_usd - current_exposure
            if available <= 0:
                return RiskCheckResult(
                    approved=False,
                    reason=f"Total exposure limit ${self._max_total_exposure_usd:.2f} reached",
                )

            adjusted_size = available / price
            warnings.append(
                f"Size reduced from {size:.4f} to {adjusted_size:.4f} due to exposure limit"
            )
            size = adjusted_size
            notional = size * price

        # 4. Check venue-specific limits
        venue_exp = self._portfolio.get_venue_exposure(venue)
        if venue_exp:
            venue_new_total = venue_exp.total_exposure_usd + notional
            if venue_new_total > self._max_venue_exposure_usd:
                return RiskCheckResult(
                    approved=False,
                    reason=f"Venue {venue} exposure limit ${self._max_venue_exposure_usd:.2f} reached",
                )

        # 5. Check open orders limit
        if self._open_orders_count >= self._max_open_orders:
            return RiskCheckResult(
                approved=False,
                reason=f"Max open orders limit ({self._max_open_orders}) reached",
            )

        # 6. Check delta limits
        current_delta = self._portfolio.net_delta
        delta_impact = notional if side.lower() == "buy" else -notional
        new_delta = current_delta + delta_impact

        if abs(new_delta) > self._max_delta:
            warnings.append(
                f"Trade will breach delta limit: ${new_delta:.2f} > ${self._max_delta:.2f}"
            )

        # 7. Check concentration limits
        if venue_exp and self._portfolio.total_exposure_usd > 0:
            venue_conc = (venue_exp.total_exposure_usd + notional) / (
                self._portfolio.total_exposure_usd + notional
            )
            if venue_conc > self._max_venue_concentration:
                warnings.append(
                    f"High venue concentration: {venue_conc * 100:.1f}% > {self._max_venue_concentration * 100:.1f}%"
                )

        return RiskCheckResult(
            approved=True,
            warnings=warnings,
            adjusted_size=size if warnings else None,
            metadata={
                "notional": notional,
                "new_total_exposure": new_total,
                "delta_impact": delta_impact,
                "strategy": strategy,
            },
        )

    # =========================================================================
    # Position Management
    # =========================================================================

    def update_position(self, position: VenuePosition) -> None:
        """Update position tracking.

        Args:
            position: Position to update
        """
        venue_exp = self._portfolio.get_venue_exposure(position.venue)
        if venue_exp:
            venue_exp.update_position(position)
            self._maybe_take_snapshot()
            self._check_alerts()

    def close_position(
        self,
        venue: str,
        symbol: str,
        token_id: Optional[str] = None,
        realized_pnl: float = 0,
    ) -> None:
        """Record position close.

        Args:
            venue: Venue identifier
            symbol: Position symbol
            token_id: Token ID (for Polymarket)
            realized_pnl: Realized PnL from closing
        """
        venue_exp = self._portfolio.get_venue_exposure(venue)
        if venue_exp:
            venue_exp.remove_position(symbol, token_id)
            if realized_pnl != 0:
                venue_exp.record_realized_pnl(realized_pnl)
            self._check_alerts()

    def record_pnl(self, venue: str, pnl: float) -> None:
        """Record realized PnL.

        Args:
            venue: Venue identifier
            pnl: Realized PnL amount
        """
        venue_exp = self._portfolio.get_venue_exposure(venue)
        if venue_exp:
            venue_exp.record_realized_pnl(pnl)
            self._check_alerts()

    # =========================================================================
    # Order Tracking
    # =========================================================================

    def increment_open_orders(self) -> None:
        """Increment open orders count."""
        self._open_orders_count += 1

    def decrement_open_orders(self) -> None:
        """Decrement open orders count."""
        self._open_orders_count = max(0, self._open_orders_count - 1)

    def set_open_orders_count(self, count: int) -> None:
        """Set open orders count.

        Args:
            count: New count
        """
        self._open_orders_count = count

    # =========================================================================
    # Hedging
    # =========================================================================

    def get_hedge_recommendation(self) -> Optional[HedgeRecommendation]:
        """Get current hedge recommendation.

        Returns:
            HedgeRecommendation if hedge needed
        """
        return self._hedge_calc.calculate_delta_hedge()

    def get_hedge_status(self) -> Dict:
        """Get hedging status.

        Returns:
            Dict with hedge metrics
        """
        return self._hedge_calc.get_hedge_status()

    # =========================================================================
    # Monitoring
    # =========================================================================

    def _maybe_take_snapshot(self) -> None:
        """Take portfolio snapshot if interval elapsed."""
        now = datetime.utcnow()
        if (
            self._last_snapshot_time is None
            or (now - self._last_snapshot_time) > self._snapshot_interval
        ):
            self._portfolio.take_snapshot()
            self._last_snapshot_time = now

    def _check_alerts(self) -> None:
        """Check for risk alerts."""
        # Exposure alert
        exposure_util = (
            self._portfolio.total_exposure_usd / self._max_total_exposure_usd
            if self._max_total_exposure_usd > 0
            else 0
        )
        if exposure_util > self._settings.risk.alert_exposure_threshold:
            self._add_alert(
                RiskAlert(
                    alert_type="exposure_limit",
                    severity="warning",
                    message=f"Exposure at {exposure_util * 100:.1f}% of limit",
                    current_value=self._portfolio.total_exposure_usd,
                    threshold=self._max_total_exposure_usd,
                )
            )

        # Daily loss alert
        if self._portfolio.total_daily_pnl < -self._daily_loss_limit_usd * 0.8:
            self._add_alert(
                RiskAlert(
                    alert_type="daily_loss",
                    severity="warning",
                    message=f"Daily loss approaching limit",
                    current_value=self._portfolio.total_daily_pnl,
                    threshold=-self._daily_loss_limit_usd,
                )
            )

        # Delta alert
        if abs(self._portfolio.net_delta) > self._max_delta * 0.8:
            self._add_alert(
                RiskAlert(
                    alert_type="delta_breach",
                    severity="warning",
                    message=f"Net delta approaching limit",
                    current_value=self._portfolio.net_delta,
                    threshold=self._max_delta,
                )
            )

    def _add_alert(self, alert: RiskAlert) -> None:
        """Add alert to history.

        Args:
            alert: Risk alert
        """
        self._alerts.append(alert)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]
        logger.warning(f"Risk alert: {alert.message}")

    def get_alerts(self, limit: int = 10) -> list[RiskAlert]:
        """Get recent alerts.

        Args:
            limit: Maximum number to return

        Returns:
            List of recent alerts
        """
        return self._alerts[-limit:]

    # =========================================================================
    # Risk Status
    # =========================================================================

    def get_risk_status(self) -> Dict[str, Any]:
        """Get comprehensive risk status.

        Returns:
            Dict with all risk metrics
        """
        metrics = self._portfolio.get_risk_metrics()

        return {
            "total_exposure_usd": round(metrics.total_exposure_usd, 2),
            "net_delta": round(metrics.net_delta, 2),
            "daily_pnl": round(metrics.daily_pnl, 2),
            "unrealized_pnl": round(metrics.unrealized_pnl, 2),
            "exposure_by_venue": metrics.exposure_by_venue,
            "exposure_by_asset": metrics.exposure_by_asset_class,
            "concentration": {
                "max_venue": round(metrics.max_venue_concentration, 4),
                "max_position": round(metrics.max_position_concentration, 4),
                "herfindahl_index": round(metrics.herfindahl_index, 4),
            },
            "hedge_status": self.get_hedge_status(),
            "limits": {
                "max_total_exposure": self._max_total_exposure_usd,
                "max_venue_exposure": self._max_venue_exposure_usd,
                "max_position_size": self._max_position_size_usd,
                "daily_loss_limit": self._daily_loss_limit_usd,
                "max_delta": self._max_delta,
                "exposure_utilization": round(
                    metrics.total_exposure_usd / self._max_total_exposure_usd * 100, 1
                )
                if self._max_total_exposure_usd > 0
                else 0,
            },
            "open_orders": self._open_orders_count,
            "position_count": metrics.position_count,
            "shadow_mode": self._shadow_mode,
            "auto_hedge_enabled": self._auto_hedge_enabled,
        }

    def get_risk_metrics(self) -> RiskMetrics:
        """Get risk metrics object.

        Returns:
            RiskMetrics with all current values
        """
        return self._portfolio.get_risk_metrics()

    # =========================================================================
    # Shadow Mode
    # =========================================================================

    def set_shadow_mode(self, enabled: bool) -> None:
        """Enable or disable shadow mode.

        In shadow mode, positions are tracked but limits are not enforced.

        Args:
            enabled: Whether to enable shadow mode
        """
        self._shadow_mode = enabled
        logger.info(f"Shadow mode {'enabled' if enabled else 'disabled'}")

    @property
    def shadow_mode(self) -> bool:
        """Check if shadow mode is enabled."""
        return self._shadow_mode

    # =========================================================================
    # Daily Reset
    # =========================================================================

    def daily_reset(self) -> None:
        """Reset daily counters. Called at day boundary."""
        self._portfolio.reset_daily_stats()
        self._alerts.clear()
        logger.info("Daily risk counters reset")

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> Dict:
        """Serialize for API response.

        Returns:
            Dict representation
        """
        return self.get_risk_status()

    def __repr__(self) -> str:
        return (
            f"<RiskManager "
            f"exposure=${self._portfolio.total_exposure_usd:.2f} "
            f"delta={self._portfolio.net_delta:.2f} "
            f"shadow={self._shadow_mode}>"
        )


# =========================================================================
# Global Instance
# =========================================================================

_risk_manager: Optional[RiskManager] = None


def get_risk_manager() -> RiskManager:
    """Get or create the global risk manager.

    Returns:
        Global RiskManager instance
    """
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
        # Register default venues
        _risk_manager.register_venue("polymarket")
    return _risk_manager


def reset_risk_manager() -> None:
    """Reset the global risk manager (for testing)."""
    global _risk_manager
    _risk_manager = None
