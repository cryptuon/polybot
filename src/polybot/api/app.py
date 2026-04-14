"""FastAPI application for PolyBot."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from polybot import __version__
from polybot.config import get_settings
from polybot.ui import DIST_DIR, has_bundled_ui
from polybot.api.routes import (
    markets_router,
    strategies_router,
    orders_router,
    positions_router,
    analytics_router,
    settings_router,
    strategy_logs_router,
    shadow_router,
    mcp_router,
)
from polybot.api.websocket import websocket_endpoint, manager
from polybot.api.health import router as health_router
from polybot.api.metrics import router as metrics_router, MetricsMiddleware
from polybot.api.middleware import (
    CorrelationIdMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting PolyBot API...")

    # Start WebSocket NNG bridge
    await manager.start_nng_bridge()

    yield

    # Cleanup
    logger.info("Shutting down PolyBot API...")
    await manager.stop_nng_bridge()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="PolyBot API",
        description="Trading bot API for Polymarket",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS middleware - configured via environment variables
    cors_config = settings.cors
    allowed_origins = [
        origin.strip()
        for origin in cors_config.allowed_origins.split(",")
        if origin.strip()
    ]
    allowed_methods = [
        method.strip()
        for method in cors_config.allow_methods.split(",")
        if method.strip()
    ]
    allowed_headers = [
        header.strip()
        for header in cors_config.allow_headers.split(",")
        if header.strip()
    ]

    # Add middleware (order matters - first added is outermost)
    # Security headers should be outermost
    app.add_middleware(SecurityHeadersMiddleware)

    # Metrics collection
    app.add_middleware(MetricsMiddleware)

    # Correlation ID for request tracing
    app.add_middleware(CorrelationIdMiddleware)

    # Rate limiting
    app.add_middleware(RateLimitMiddleware, requests_per_minute=120, burst_size=20)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=cors_config.allow_credentials,
        allow_methods=allowed_methods,
        allow_headers=allowed_headers,
    )

    # Include health and metrics routers (no auth required)
    app.include_router(health_router)
    app.include_router(metrics_router)

    # Include API routers
    app.include_router(markets_router, prefix="/api")
    app.include_router(strategies_router, prefix="/api")
    app.include_router(orders_router, prefix="/api")
    app.include_router(positions_router, prefix="/api")
    app.include_router(analytics_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(strategy_logs_router, prefix="/api")
    app.include_router(shadow_router, prefix="/api")
    app.include_router(mcp_router, prefix="/api")

    # WebSocket endpoint
    app.websocket("/ws")(websocket_endpoint)

    # Serve bundled Vue.js dashboard
    if has_bundled_ui():
        app.mount("/ui", StaticFiles(directory=DIST_DIR, html=True), name="ui")
        logger.info(f"Serving bundled UI from {DIST_DIR}")

    # Root endpoint
    @app.get("/")
    async def root() -> dict:
        """Root endpoint."""
        return {
            "name": "PolyBot API",
            "version": __version__,
            "docs": "/docs",
            "ui": "/ui" if has_bundled_ui() else None,
        }

    return app


# Create default app instance
app = create_app()
