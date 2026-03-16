"""Real health check implementation with dependency checks.

Provides comprehensive health endpoints for production monitoring.
"""

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Response
from pydantic import BaseModel

from polybot import __version__
from polybot.config import get_settings


logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health status for a single component."""

    status: HealthStatus
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    last_check: datetime


class HealthResponse(BaseModel):
    """Complete health check response."""

    status: HealthStatus
    version: str
    timestamp: datetime
    uptime_seconds: float
    components: Dict[str, ComponentHealth]


# Track service start time
_start_time = datetime.now(timezone.utc)


async def check_sqlite_health() -> ComponentHealth:
    """Check SQLite database connectivity."""
    start = datetime.now(timezone.utc)
    settings = get_settings()

    try:
        import aiosqlite

        db_path = settings.database.sqlite_path

        # Check if database file exists
        if not Path(db_path).exists():
            return ComponentHealth(
                status=HealthStatus.DEGRADED,
                message=f"Database file not found: {db_path}",
                last_check=datetime.now(timezone.utc),
            )

        # Test connection and query
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.execute("SELECT 1")
            await cursor.fetchone()

        latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"SQLite health check failed: {e}")
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=str(e)[:100],  # Truncate error message
            last_check=datetime.now(timezone.utc),
        )


async def check_duckdb_health() -> ComponentHealth:
    """Check DuckDB database connectivity."""
    start = datetime.now(timezone.utc)
    settings = get_settings()

    try:
        import duckdb

        db_path = settings.database.duckdb_path

        # Check if database file exists (it might not exist on first run)
        if not Path(db_path).exists():
            return ComponentHealth(
                status=HealthStatus.DEGRADED,
                message=f"Analytics database not initialized: {db_path}",
                last_check=datetime.now(timezone.utc),
            )

        # Test connection (read-only mode for health check)
        conn = duckdb.connect(str(db_path), read_only=True)
        conn.execute("SELECT 1").fetchone()
        conn.close()

        latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"DuckDB health check failed: {e}")
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=str(e)[:100],
            last_check=datetime.now(timezone.utc),
        )


async def check_nng_health() -> ComponentHealth:
    """Check NNG IPC directory status."""
    settings = get_settings()

    try:
        ipc_path = Path(settings.nng.ipc_path)

        if ipc_path.exists():
            # Check if any sockets exist (indicates services are running)
            socket_files = list(ipc_path.glob("*.pub")) + list(ipc_path.glob("*.req"))
            socket_count = len(socket_files)

            return ComponentHealth(
                status=HealthStatus.HEALTHY,
                message=f"IPC path exists, {socket_count} socket(s) found",
                last_check=datetime.now(timezone.utc),
            )
        else:
            return ComponentHealth(
                status=HealthStatus.DEGRADED,
                message=f"IPC path not created: {ipc_path}",
                last_check=datetime.now(timezone.utc),
            )

    except Exception as e:
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=str(e)[:100],
            last_check=datetime.now(timezone.utc),
        )


async def check_config_health() -> ComponentHealth:
    """Check configuration validity."""
    try:
        settings = get_settings()

        issues = []

        # Check for missing critical credentials
        if not settings.polymarket.private_key:
            issues.append("Missing Polymarket private key")

        # Check database paths are writable
        data_dir = Path(settings.database.sqlite_path).parent
        if not data_dir.exists():
            issues.append(f"Data directory missing: {data_dir}")

        if issues:
            return ComponentHealth(
                status=HealthStatus.DEGRADED,
                message="; ".join(issues),
                last_check=datetime.now(timezone.utc),
            )

        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Configuration valid",
            last_check=datetime.now(timezone.utc),
        )

    except Exception as e:
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=str(e)[:100],
            last_check=datetime.now(timezone.utc),
        )


@router.get("/health", response_model=HealthResponse)
async def health_check(response: Response) -> HealthResponse:
    """Comprehensive health check endpoint.

    Checks all system components and returns aggregate status.

    Returns:
        - 200: All systems healthy or degraded
        - 503: One or more critical systems unhealthy
    """
    # Run health checks in parallel
    sqlite_health, duckdb_health, nng_health, config_health = await asyncio.gather(
        check_sqlite_health(),
        check_duckdb_health(),
        check_nng_health(),
        check_config_health(),
    )

    components = {
        "sqlite": sqlite_health,
        "duckdb": duckdb_health,
        "nng": nng_health,
        "config": config_health,
    }

    # Determine overall status
    statuses = [c.status for c in components.values()]

    if HealthStatus.UNHEALTHY in statuses:
        # SQLite unhealthy is critical
        if components["sqlite"].status == HealthStatus.UNHEALTHY:
            overall_status = HealthStatus.UNHEALTHY
            response.status_code = 503
        else:
            overall_status = HealthStatus.DEGRADED
            response.status_code = 200
    elif HealthStatus.DEGRADED in statuses:
        overall_status = HealthStatus.DEGRADED
        response.status_code = 200
    else:
        overall_status = HealthStatus.HEALTHY
        response.status_code = 200

    uptime = (datetime.now(timezone.utc) - _start_time).total_seconds()

    return HealthResponse(
        status=overall_status,
        version=__version__,
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=uptime,
        components=components,
    )


@router.get("/health/live")
async def liveness_probe() -> Dict[str, str]:
    """Kubernetes liveness probe.

    Always returns 200 if the process is running.
    Used to detect if the application has crashed or is stuck.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_probe(response: Response) -> Dict[str, Any]:
    """Kubernetes readiness probe.

    Checks if the service can handle requests.
    Used to determine if traffic should be routed to this instance.
    """
    sqlite_health = await check_sqlite_health()

    if sqlite_health.status == HealthStatus.UNHEALTHY:
        response.status_code = 503
        return {"status": "not_ready", "reason": sqlite_health.message}

    return {"status": "ready", "version": __version__}
