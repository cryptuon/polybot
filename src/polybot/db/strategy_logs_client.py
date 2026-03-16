"""Strategy logs client for querying the strategy logs service via NNG.

This client provides a simple interface for API routes and strategies
to log and query strategy execution data without direct database access.
All queries are routed through the strategy logs service via IPC.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from polybot.config import get_settings
from polybot.core.nng import NNGRequester


logger = logging.getLogger(__name__)


class StrategyLogsClient:
    """Client for the strategy logs service.

    Uses NNG REQ/REP pattern to send queries to the strategy logs service
    and receive responses.
    """

    def __init__(self) -> None:
        """Initialize the client."""
        self._settings = get_settings()
        self._requester: Optional[NNGRequester] = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to the strategy logs service."""
        if self._connected:
            return

        self._requester = NNGRequester(self._settings.nng.strategy_logs_address)
        await self._requester.open()
        self._connected = True
        logger.info("Strategy logs client connected")

    async def close(self) -> None:
        """Close the connection."""
        if self._requester:
            await self._requester.close()
            self._requester = None
            self._connected = False

    async def _query(self, query_type: str, params: Dict[str, Any]) -> Any:
        """Execute a query against the strategy logs service.

        Args:
            query_type: Type of query to execute
            params: Query parameters

        Returns:
            Query result

        Raises:
            RuntimeError: If not connected or query fails
        """
        if not self._connected or not self._requester:
            await self.connect()

        request = {
            "query_type": query_type,
            "params": params,
        }

        try:
            response = await self._requester.request(request)

            if not response.get("success"):
                error = response.get("error", "Unknown error")
                raise RuntimeError(f"Strategy logs query failed: {error}")

            return response.get("data")

        except Exception as e:
            logger.error(f"Strategy logs query error: {e}")
            raise

    # =========================================================================
    # Log Entry Operations
    # =========================================================================

    async def log(
        self,
        strategy: str,
        log_type: str,
        level: str,
        message: str,
        market_id: Optional[str] = None,
        token_id: Optional[str] = None,
        price: Optional[float] = None,
        size: Optional[float] = None,
        action: Optional[str] = None,
        reason: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert a log entry.

        Args:
            strategy: Strategy name
            log_type: Type of log (scan, signal, entry, exit, error, start, stop)
            level: Log level (DEBUG, INFO, WARNING, ERROR, SIGNAL)
            message: Log message
            market_id: Optional market ID
            token_id: Optional token ID
            price: Optional price
            size: Optional size
            action: Optional action (BUY, SELL, CLOSE)
            reason: Optional reason
            confidence: Optional confidence score
            metadata: Optional additional metadata

        Returns:
            Log entry ID
        """
        return await self._query("insert_log", {
            "strategy": strategy,
            "timestamp": datetime.utcnow().isoformat(),
            "log_type": log_type,
            "level": level,
            "message": message,
            "market_id": market_id,
            "token_id": token_id,
            "price": price,
            "size": size,
            "action": action,
            "reason": reason,
            "confidence": confidence,
            "metadata": metadata,
        })

    async def get_logs(
        self,
        strategy: Optional[str] = None,
        log_type: Optional[str] = None,
        level: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        market_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query strategy logs.

        Args:
            strategy: Filter by strategy name
            log_type: Filter by log type
            level: Filter by log level
            start_time: Start of time range
            end_time: End of time range
            market_id: Filter by market ID
            limit: Maximum entries to return
            offset: Number of entries to skip

        Returns:
            List of log entries
        """
        return await self._query("get_logs", {
            "strategy": strategy,
            "log_type": log_type,
            "level": level,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "market_id": market_id,
            "limit": limit,
            "offset": offset,
        })

    async def get_log_count(
        self,
        strategy: Optional[str] = None,
        log_type: Optional[str] = None,
        level: Optional[str] = None,
        start_time: Optional[datetime] = None,
    ) -> int:
        """Get count of log entries matching criteria."""
        return await self._query("get_log_count", {
            "strategy": strategy,
            "log_type": log_type,
            "level": level,
            "start_time": start_time.isoformat() if start_time else None,
        })

    # =========================================================================
    # Run Session Operations
    # =========================================================================

    async def start_run(
        self,
        strategy: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Record a strategy run starting.

        Args:
            strategy: Strategy name
            config: Strategy configuration

        Returns:
            Run session ID
        """
        return await self._query("start_run", {
            "strategy": strategy,
            "config": config,
        })

    async def end_run(
        self,
        run_id: int,
        scans: int = 0,
        signals: int = 0,
        entries: int = 0,
        exits: int = 0,
        errors: int = 0,
        status: str = "stopped",
    ) -> None:
        """Record a strategy run ending.

        Args:
            run_id: Run session ID
            scans: Number of scans performed
            signals: Number of signals generated
            entries: Number of position entries
            exits: Number of position exits
            errors: Number of errors
            status: Final status (stopped, error)
        """
        await self._query("end_run", {
            "run_id": run_id,
            "scans": scans,
            "signals": signals,
            "entries": entries,
            "exits": exits,
            "errors": errors,
            "status": status,
        })

    async def get_runs(
        self,
        strategy: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get strategy run history.

        Args:
            strategy: Filter by strategy name
            status: Filter by status
            limit: Maximum runs to return

        Returns:
            List of run summaries
        """
        return await self._query("get_runs", {
            "strategy": strategy,
            "status": status,
            "limit": limit,
        })

    async def get_current_run(self, strategy: str) -> Optional[int]:
        """Get the current running session ID for a strategy.

        Args:
            strategy: Strategy name

        Returns:
            Run ID or None if not running
        """
        return await self._query("get_current_run", {"strategy": strategy})

    # =========================================================================
    # Scan Summary Operations
    # =========================================================================

    async def update_scan_summary(
        self,
        strategy: str,
        scan_count: int = 1,
        opportunities: int = 0,
        signals: int = 0,
        scan_duration_ms: Optional[float] = None,
    ) -> None:
        """Update aggregated scan summary for current minute.

        Args:
            strategy: Strategy name
            scan_count: Number of scans to add
            opportunities: Opportunities found
            signals: Signals generated
            scan_duration_ms: Scan duration in milliseconds
        """
        await self._query("update_scan_summary", {
            "strategy": strategy,
            "scan_count": scan_count,
            "opportunities": opportunities,
            "signals": signals,
            "scan_duration_ms": scan_duration_ms,
        })

    async def get_scan_summaries(
        self,
        strategy: str,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get scan summaries for the past N hours.

        Args:
            strategy: Strategy name
            hours: Hours of history

        Returns:
            List of scan summaries per minute
        """
        return await self._query("get_scan_summaries", {
            "strategy": strategy,
            "hours": hours,
        })


# Module-level client instance for dependency injection
_client: Optional[StrategyLogsClient] = None


async def get_strategy_logs_client() -> StrategyLogsClient:
    """Get or create the strategy logs client singleton.

    Returns:
        Connected strategy logs client
    """
    global _client
    if _client is None:
        _client = StrategyLogsClient()
        await _client.connect()
    return _client
