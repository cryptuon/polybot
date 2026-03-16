"""Prometheus metrics endpoint for PolyBot.

Provides application metrics for monitoring and alerting.
"""

import time
from typing import Callable

from fastapi import APIRouter, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from polybot import __version__


router = APIRouter(tags=["metrics"])

# Try to import prometheus_client, make it optional
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


if PROMETHEUS_AVAILABLE:
    # ==========================================================================
    # Application Info
    # ==========================================================================
    APP_INFO = Info("polybot", "PolyBot application information")
    APP_INFO.info({"version": __version__})

    # ==========================================================================
    # HTTP Metrics
    # ==========================================================================
    HTTP_REQUESTS_TOTAL = Counter(
        "polybot_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )

    HTTP_REQUEST_DURATION_SECONDS = Histogram(
        "polybot_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "endpoint"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )

    HTTP_REQUESTS_IN_PROGRESS = Gauge(
        "polybot_http_requests_in_progress",
        "Number of HTTP requests currently in progress",
        ["method", "endpoint"],
    )

    # ==========================================================================
    # Trading Metrics
    # ==========================================================================
    ORDERS_TOTAL = Counter(
        "polybot_orders_total",
        "Total orders placed",
        ["strategy", "side", "status"],
    )

    TRADES_TOTAL = Counter(
        "polybot_trades_total",
        "Total trades executed",
        ["strategy", "side"],
    )

    TRADE_VOLUME_USD = Counter(
        "polybot_trade_volume_usd_total",
        "Total trade volume in USD",
        ["strategy"],
    )

    PNL_REALIZED_USD = Gauge(
        "polybot_pnl_realized_usd",
        "Realized PnL in USD",
        ["strategy"],
    )

    PNL_UNREALIZED_USD = Gauge(
        "polybot_pnl_unrealized_usd",
        "Unrealized PnL in USD",
        ["strategy"],
    )

    DAILY_PNL_USD = Gauge("polybot_daily_pnl_usd", "Today's PnL in USD")

    # ==========================================================================
    # Position Metrics
    # ==========================================================================
    OPEN_POSITIONS = Gauge(
        "polybot_open_positions",
        "Number of open positions",
        ["strategy"],
    )

    POSITION_VALUE_USD = Gauge(
        "polybot_position_value_usd",
        "Total position value in USD",
        ["strategy"],
    )

    TOTAL_EXPOSURE_USD = Gauge(
        "polybot_total_exposure_usd",
        "Total exposure across all positions in USD",
    )

    # ==========================================================================
    # Market Data Metrics
    # ==========================================================================
    MARKETS_TRACKED = Gauge("polybot_markets_tracked", "Number of markets being tracked")

    PRICE_UPDATES_TOTAL = Counter(
        "polybot_price_updates_total",
        "Total price updates received",
    )

    PRICE_UPDATE_LAG_SECONDS = Histogram(
        "polybot_price_update_lag_seconds",
        "Lag between price update and processing",
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    )

    # ==========================================================================
    # Service Health Metrics
    # ==========================================================================
    SERVICE_UP = Gauge(
        "polybot_service_up",
        "Service health status (1=up, 0=down)",
        ["service"],
    )

    SERVICE_LAST_HEARTBEAT = Gauge(
        "polybot_service_last_heartbeat_timestamp",
        "Timestamp of last heartbeat",
        ["service"],
    )

    # ==========================================================================
    # Risk Metrics
    # ==========================================================================
    RISK_EXPOSURE_PCT = Gauge(
        "polybot_risk_exposure_pct",
        "Current exposure as percentage of limit",
    )

    RISK_DAILY_LOSS_PCT = Gauge(
        "polybot_risk_daily_loss_pct",
        "Today's loss as percentage of daily limit",
    )

    RISK_CHECKS_TOTAL = Counter(
        "polybot_risk_checks_total",
        "Total risk checks performed",
        ["result"],
    )


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics."""

    # Paths excluded from metrics collection
    EXCLUDED_PATHS = {"/metrics", "/health/live"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Collect metrics for each request."""
        if not PROMETHEUS_AVAILABLE:
            return await call_next(request)

        # Skip excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        method = request.method
        # Normalize endpoint (remove IDs for grouping)
        endpoint = self._normalize_path(request.url.path)

        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()

        start_time = time.time()
        status_code = 500  # Default in case of exception

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.time() - start_time
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()
            HTTP_REQUESTS_TOTAL.labels(
                method=method, endpoint=endpoint, status=status_code
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(
                duration
            )

    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing IDs with placeholders.

        This prevents high-cardinality labels in metrics.
        """
        parts = path.split("/")
        normalized = []

        for part in parts:
            # Replace UUIDs and hex strings with placeholder
            if len(part) == 36 and "-" in part:  # UUID
                normalized.append("{id}")
            elif len(part) >= 32 and all(c in "0123456789abcdef" for c in part.lower()):
                normalized.append("{id}")
            elif part.isdigit():  # Numeric IDs
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/".join(normalized)


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus text format.
    """
    if not PROMETHEUS_AVAILABLE:
        return Response(
            content="# Prometheus client not installed\n# pip install prometheus-client\n",
            media_type="text/plain",
        )

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ==========================================================================
# Helper Functions for Recording Metrics
# ==========================================================================


def record_order(strategy: str, side: str, status: str) -> None:
    """Record an order metric."""
    if PROMETHEUS_AVAILABLE:
        ORDERS_TOTAL.labels(strategy=strategy, side=side, status=status).inc()


def record_trade(strategy: str, side: str, volume: float) -> None:
    """Record a trade metric."""
    if PROMETHEUS_AVAILABLE:
        TRADES_TOTAL.labels(strategy=strategy, side=side).inc()
        TRADE_VOLUME_USD.labels(strategy=strategy).inc(volume)


def update_pnl(strategy: str, realized: float, unrealized: float) -> None:
    """Update PnL metrics."""
    if PROMETHEUS_AVAILABLE:
        PNL_REALIZED_USD.labels(strategy=strategy).set(realized)
        PNL_UNREALIZED_USD.labels(strategy=strategy).set(unrealized)


def update_positions(strategy: str, count: int, value: float) -> None:
    """Update position metrics."""
    if PROMETHEUS_AVAILABLE:
        OPEN_POSITIONS.labels(strategy=strategy).set(count)
        POSITION_VALUE_USD.labels(strategy=strategy).set(value)


def update_exposure(total_exposure: float, exposure_limit: float) -> None:
    """Update exposure metrics."""
    if PROMETHEUS_AVAILABLE:
        TOTAL_EXPOSURE_USD.set(total_exposure)
        if exposure_limit > 0:
            RISK_EXPOSURE_PCT.set(total_exposure / exposure_limit)


def update_daily_pnl(pnl: float, loss_limit: float) -> None:
    """Update daily PnL metrics."""
    if PROMETHEUS_AVAILABLE:
        DAILY_PNL_USD.set(pnl)
        if loss_limit > 0 and pnl < 0:
            RISK_DAILY_LOSS_PCT.set(abs(pnl) / loss_limit)
        else:
            RISK_DAILY_LOSS_PCT.set(0)


def update_service_health(service: str, is_up: bool) -> None:
    """Update service health metric."""
    if PROMETHEUS_AVAILABLE:
        SERVICE_UP.labels(service=service).set(1 if is_up else 0)
        if is_up:
            SERVICE_LAST_HEARTBEAT.labels(service=service).set(time.time())


def record_risk_check(passed: bool) -> None:
    """Record a risk check result."""
    if PROMETHEUS_AVAILABLE:
        RISK_CHECKS_TOTAL.labels(result="passed" if passed else "rejected").inc()


def record_price_update(lag_seconds: float = 0) -> None:
    """Record a price update."""
    if PROMETHEUS_AVAILABLE:
        PRICE_UPDATES_TOTAL.inc()
        if lag_seconds > 0:
            PRICE_UPDATE_LAG_SECONDS.observe(lag_seconds)


def update_markets_tracked(count: int) -> None:
    """Update markets tracked count."""
    if PROMETHEUS_AVAILABLE:
        MARKETS_TRACKED.set(count)
