"""Strategy logs endpoints.

Provides access to strategy execution logs, run history, and scan summaries.
All queries are routed through the strategy logs service via IPC.
"""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException

from polybot.api.schemas import (
    StrategyLogEntry,
    StrategyLogsResponse,
    StrategyRunSummary,
    StrategyRunsResponse,
    ScanSummary,
    ScanSummariesResponse,
)
from polybot.db.strategy_logs_client import StrategyLogsClient, get_strategy_logs_client


router = APIRouter(prefix="/strategy-logs", tags=["strategy-logs"])


def _parse_metadata(metadata):
    """Parse metadata field - handles both dict and JSON string."""
    if metadata is None:
        return None
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        try:
            return json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


# =============================================================================
# IMPORTANT: These /all/* routes MUST come BEFORE /{strategy}/* routes
# Otherwise FastAPI will match "all" as a strategy name parameter
# =============================================================================

@router.get("/all/logs", response_model=StrategyLogsResponse)
async def get_all_logs(
    log_type: Optional[str] = Query(None, description="Filter by log type"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    start_time: Optional[datetime] = Query(None, description="Start of time range"),
    end_time: Optional[datetime] = Query(None, description="End of time range"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    client: StrategyLogsClient = Depends(get_strategy_logs_client),
) -> StrategyLogsResponse:
    """Get logs for all strategies.

    Args:
        log_type: Filter by type (scan, signal, entry, exit, error, start, stop)
        level: Filter by level (DEBUG, INFO, WARNING, ERROR, SIGNAL)
        start_time: Start of time range
        end_time: End of time range
        limit: Maximum entries to return
        offset: Number of entries to skip
    """
    try:
        logs = await client.get_logs(
            strategy=None,
            log_type=log_type,
            level=level,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )

        total = await client.get_log_count(
            strategy=None,
            log_type=log_type,
            level=level,
            start_time=start_time,
        )

        return StrategyLogsResponse(
            logs=[
                StrategyLogEntry(
                    id=log.get("id", 0),
                    strategy=log.get("strategy", ""),
                    timestamp=datetime.fromisoformat(log["timestamp"]) if isinstance(log.get("timestamp"), str) else log.get("timestamp", datetime.utcnow()),
                    log_type=log.get("log_type", ""),
                    level=log.get("level", ""),
                    message=log.get("message", ""),
                    market_id=log.get("market_id"),
                    token_id=log.get("token_id"),
                    price=log.get("price"),
                    size=log.get("size"),
                    action=log.get("action"),
                    reason=log.get("reason"),
                    confidence=log.get("confidence"),
                    metadata=_parse_metadata(log.get("metadata")),
                )
                for log in logs
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        # Return empty result if strategy logs service is unavailable
        import logging
        logging.getLogger(__name__).warning(f"Strategy logs service unavailable: {e}")
        return StrategyLogsResponse(logs=[], total=0, limit=limit, offset=offset)


@router.get("/all/runs", response_model=StrategyRunsResponse)
async def get_all_runs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    client: StrategyLogsClient = Depends(get_strategy_logs_client),
) -> StrategyRunsResponse:
    """Get run history for all strategies.

    Args:
        status: Filter by status
        limit: Maximum runs to return
    """
    try:
        runs = await client.get_runs(
            strategy=None,
            status=status,
            limit=limit,
        )

        return StrategyRunsResponse(
            runs=[
                StrategyRunSummary(
                    id=run.get("id"),
                    strategy=run.get("strategy", ""),
                    start_time=datetime.fromisoformat(run["start_time"]) if isinstance(run.get("start_time"), str) else run.get("start_time", datetime.utcnow()),
                    end_time=datetime.fromisoformat(run["end_time"]) if isinstance(run.get("end_time"), str) and run.get("end_time") else run.get("end_time"),
                    duration_seconds=run.get("duration_seconds"),
                    scans_performed=run.get("scans_performed", 0),
                    signals_generated=run.get("signals_generated", 0),
                    entries=run.get("entries", 0),
                    exits=run.get("exits", 0),
                    errors=run.get("errors", 0),
                    status=run.get("status", "unknown"),
                    config=run.get("config"),
                )
                for run in runs
            ],
            total=len(runs),
        )

    except Exception as e:
        # Return empty result if strategy logs service is unavailable
        import logging
        logging.getLogger(__name__).warning(f"Strategy logs service unavailable: {e}")
        return StrategyRunsResponse(runs=[], total=0)


@router.post("/cleanup-stale-runs")
async def cleanup_stale_runs(
    client: StrategyLogsClient = Depends(get_strategy_logs_client),
) -> dict:
    """Mark all stale 'running' runs as 'stopped'.

    This is useful for cleaning up runs that weren't properly ended
    due to service shutdown or crashes.

    Returns:
        Number of runs cleaned up
    """
    try:
        # Get all running runs and mark them as stopped
        runs = await client.get_runs(status="running", limit=200)
        cleaned = 0

        for run in runs:
            run_id = run.get("id")
            if run_id:
                await client.end_run(
                    run_id=run_id,
                    scans=run.get("scans_performed", 0),
                    signals=run.get("signals_generated", 0),
                    entries=run.get("entries", 0),
                    exits=run.get("exits", 0),
                    errors=run.get("errors", 0),
                    status="stopped",
                )
                cleaned += 1

        return {"success": True, "cleaned": cleaned}

    except Exception as e:
        # Return success with 0 cleaned if strategy logs service is unavailable
        import logging
        logging.getLogger(__name__).warning(f"Strategy logs service unavailable: {e}")
        return {"success": False, "cleaned": 0, "error": "Strategy logs service unavailable"}


# =============================================================================
# Strategy-specific routes (parameterized)
# =============================================================================

@router.get("/{strategy}/logs", response_model=StrategyLogsResponse)
async def get_strategy_logs(
    strategy: str,
    log_type: Optional[str] = Query(None, description="Filter by log type"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    start_time: Optional[datetime] = Query(None, description="Start of time range"),
    end_time: Optional[datetime] = Query(None, description="End of time range"),
    market_id: Optional[str] = Query(None, description="Filter by market ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    client: StrategyLogsClient = Depends(get_strategy_logs_client),
) -> StrategyLogsResponse:
    """Get logs for a strategy.

    Args:
        strategy: Strategy name
        log_type: Filter by type (scan, signal, entry, exit, error, start, stop)
        level: Filter by level (DEBUG, INFO, WARNING, ERROR, SIGNAL)
        start_time: Start of time range
        end_time: End of time range
        market_id: Filter by market ID
        limit: Maximum entries to return
        offset: Number of entries to skip
    """
    try:
        logs = await client.get_logs(
            strategy=strategy,
            log_type=log_type,
            level=level,
            start_time=start_time,
            end_time=end_time,
            market_id=market_id,
            limit=limit,
            offset=offset,
        )

        total = await client.get_log_count(
            strategy=strategy,
            log_type=log_type,
            level=level,
            start_time=start_time,
        )

        return StrategyLogsResponse(
            logs=[
                StrategyLogEntry(
                    id=log.get("id", 0),
                    strategy=log.get("strategy", ""),
                    timestamp=datetime.fromisoformat(log["timestamp"]) if isinstance(log.get("timestamp"), str) else log.get("timestamp", datetime.utcnow()),
                    log_type=log.get("log_type", ""),
                    level=log.get("level", ""),
                    message=log.get("message", ""),
                    market_id=log.get("market_id"),
                    token_id=log.get("token_id"),
                    price=log.get("price"),
                    size=log.get("size"),
                    action=log.get("action"),
                    reason=log.get("reason"),
                    confidence=log.get("confidence"),
                    metadata=_parse_metadata(log.get("metadata")),
                )
                for log in logs
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        # Return empty result if strategy logs service is unavailable
        import logging
        logging.getLogger(__name__).warning(f"Strategy logs service unavailable: {e}")
        return StrategyLogsResponse(logs=[], total=0, limit=limit, offset=offset)


@router.get("/{strategy}/runs", response_model=StrategyRunsResponse)
async def get_strategy_runs(
    strategy: str,
    status: Optional[str] = Query(None, description="Filter by status (running, stopped, error)"),
    limit: int = Query(50, ge=1, le=200),
    client: StrategyLogsClient = Depends(get_strategy_logs_client),
) -> StrategyRunsResponse:
    """Get run history for a strategy.

    Args:
        strategy: Strategy name
        status: Filter by status
        limit: Maximum runs to return
    """
    try:
        runs = await client.get_runs(
            strategy=strategy,
            status=status,
            limit=limit,
        )

        return StrategyRunsResponse(
            runs=[
                StrategyRunSummary(
                    id=run.get("id"),
                    strategy=run.get("strategy", ""),
                    start_time=datetime.fromisoformat(run["start_time"]) if isinstance(run.get("start_time"), str) else run.get("start_time", datetime.utcnow()),
                    end_time=datetime.fromisoformat(run["end_time"]) if isinstance(run.get("end_time"), str) and run.get("end_time") else run.get("end_time"),
                    duration_seconds=run.get("duration_seconds"),
                    scans_performed=run.get("scans_performed", 0),
                    signals_generated=run.get("signals_generated", 0),
                    entries=run.get("entries", 0),
                    exits=run.get("exits", 0),
                    errors=run.get("errors", 0),
                    status=run.get("status", "unknown"),
                    config=run.get("config"),
                )
                for run in runs
            ],
            total=len(runs),
        )

    except Exception as e:
        # Return empty result if strategy logs service is unavailable
        import logging
        logging.getLogger(__name__).warning(f"Strategy logs service unavailable: {e}")
        return StrategyRunsResponse(runs=[], total=0)


@router.get("/{strategy}/runs/current")
async def get_current_run(
    strategy: str,
    client: StrategyLogsClient = Depends(get_strategy_logs_client),
) -> dict:
    """Get the current active run for a strategy.

    Args:
        strategy: Strategy name

    Returns:
        Current run ID or null if not running
    """
    try:
        run_id = await client.get_current_run(strategy)
        return {"strategy": strategy, "run_id": run_id, "running": run_id is not None}

    except Exception as e:
        # Return not running if strategy logs service is unavailable
        import logging
        logging.getLogger(__name__).warning(f"Strategy logs service unavailable: {e}")
        return {"strategy": strategy, "run_id": None, "running": False}


@router.get("/{strategy}/scans", response_model=ScanSummariesResponse)
async def get_scan_summaries(
    strategy: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history (max 7 days)"),
    client: StrategyLogsClient = Depends(get_strategy_logs_client),
) -> ScanSummariesResponse:
    """Get scan summaries for a strategy.

    Returns aggregated scan statistics per minute for the past N hours.

    Args:
        strategy: Strategy name
        hours: Hours of history to retrieve
    """
    try:
        summaries = await client.get_scan_summaries(
            strategy=strategy,
            hours=hours,
        )

        return ScanSummariesResponse(
            strategy=strategy,
            hours=hours,
            summaries=[
                ScanSummary(
                    minute=datetime.fromisoformat(s["minute"]) if isinstance(s.get("minute"), str) else s.get("minute", datetime.utcnow()),
                    scan_count=s.get("scan_count", 0),
                    opportunities=s.get("opportunities", 0),
                    signals=s.get("signals", 0),
                    avg_scan_duration_ms=s.get("avg_scan_duration_ms"),
                )
                for s in summaries
            ],
        )

    except Exception as e:
        # Return empty result if strategy logs service is unavailable
        import logging
        logging.getLogger(__name__).warning(f"Strategy logs service unavailable: {e}")
        return ScanSummariesResponse(strategy=strategy, hours=hours, summaries=[])
