"""Strategy logs service.

Provides a NNG REQ/REP interface for strategy logging operations.
Keeps strategy logs in a separate DuckDB database from analytics.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from polybot.config import Settings
from polybot.core.nng import NNGReplier
from polybot.db.strategy_logs_store import (
    StrategyLogsStore,
    StrategyLogEntry,
    LogType,
    LogLevel,
)
from polybot.services.base import BaseService


logger = logging.getLogger(__name__)


class StrategyLogsService(BaseService):
    """Strategy logs service.

    Handles storage and retrieval of strategy execution logs.
    """

    name = "strategy_logs"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._store: Optional[StrategyLogsStore] = None
        self._replier: Optional[NNGReplier] = None

    async def _on_start(self) -> None:
        """Initialize service resources."""
        # Initialize DuckDB store
        self._store = StrategyLogsStore()
        self._store.connect()

        # Initialize NNG replier for queries
        self._replier = NNGReplier(self._settings.nng.strategy_logs_address)
        await self._replier.open()

        self._logger.info("Strategy logs service initialized")

    async def _on_stop(self) -> None:
        """Cleanup service resources."""
        if self._replier:
            await self._replier.close()

        if self._store:
            self._store.close()

    async def _run(self) -> None:
        """Main service loop."""
        # Start query handler
        query_task = self.create_task(self._handle_queries())

        # Start periodic checkpoint
        checkpoint_task = self.create_task(self._checkpoint_loop())

        # Start cleanup task
        cleanup_task = self.create_task(self._cleanup_loop())

        await asyncio.gather(
            query_task, checkpoint_task, cleanup_task,
            return_exceptions=True
        )

    async def _handle_queries(self) -> None:
        """Handle incoming queries via NNG REQ/REP."""
        if not self._replier:
            return

        async for request in self._replier.requests():
            if not self._running:
                break

            try:
                response = await self._process_query(request)
                await self._replier.reply(response)
            except Exception as e:
                self._logger.error(f"Query handling error: {e}")
                await self._replier.reply({
                    "success": False,
                    "error": str(e),
                })

    async def _process_query(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a query request.

        Args:
            request: Query request with query_type and params

        Returns:
            Response dict with success, data, or error
        """
        query_type = request.get("query_type", "")
        params = request.get("params", {})

        try:
            # Log operations
            if query_type == "insert_log":
                result = await self._insert_log(params)
                return {"success": True, "data": result}

            elif query_type == "get_logs":
                result = await self._get_logs(params)
                return {"success": True, "data": result}

            elif query_type == "get_log_count":
                result = await self._get_log_count(params)
                return {"success": True, "data": result}

            # Run operations
            elif query_type == "start_run":
                result = await self._start_run(params)
                return {"success": True, "data": result}

            elif query_type == "end_run":
                await self._end_run(params)
                return {"success": True, "data": None}

            elif query_type == "get_runs":
                result = await self._get_runs(params)
                return {"success": True, "data": result}

            elif query_type == "get_current_run":
                result = await self._get_current_run(params)
                return {"success": True, "data": result}

            # Scan summary operations
            elif query_type == "update_scan_summary":
                await self._update_scan_summary(params)
                return {"success": True, "data": None}

            elif query_type == "get_scan_summaries":
                result = await self._get_scan_summaries(params)
                return {"success": True, "data": result}

            else:
                return {"success": False, "error": f"Unknown query type: {query_type}"}

        except Exception as e:
            self._logger.error(f"Query processing error: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Log Operations
    # =========================================================================

    async def _insert_log(self, params: Dict[str, Any]) -> int:
        """Insert a log entry."""
        if not self._store:
            raise RuntimeError("Store not initialized")

        entry = StrategyLogEntry(
            id=None,
            strategy=params.get("strategy", ""),
            timestamp=datetime.fromisoformat(params["timestamp"]) if params.get("timestamp") else datetime.utcnow(),
            log_type=LogType(params.get("log_type", "scan")),
            level=LogLevel(params.get("level", "INFO")),
            message=params.get("message", ""),
            market_id=params.get("market_id"),
            token_id=params.get("token_id"),
            price=params.get("price"),
            size=params.get("size"),
            action=params.get("action"),
            reason=params.get("reason"),
            confidence=params.get("confidence"),
            metadata=params.get("metadata"),
        )

        return self._store.insert_log(entry)

    async def _get_logs(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get log entries."""
        if not self._store:
            return []

        log_type = LogType(params["log_type"]) if params.get("log_type") else None
        level = LogLevel(params["level"]) if params.get("level") else None
        start_time = datetime.fromisoformat(params["start_time"]) if params.get("start_time") else None
        end_time = datetime.fromisoformat(params["end_time"]) if params.get("end_time") else None

        entries = self._store.get_logs(
            strategy=params.get("strategy"),
            log_type=log_type,
            level=level,
            start_time=start_time,
            end_time=end_time,
            market_id=params.get("market_id"),
            limit=params.get("limit", 100),
            offset=params.get("offset", 0),
        )

        return [e.to_dict() for e in entries]

    async def _get_log_count(self, params: Dict[str, Any]) -> int:
        """Get log count."""
        if not self._store:
            return 0

        log_type = LogType(params["log_type"]) if params.get("log_type") else None
        level = LogLevel(params["level"]) if params.get("level") else None
        start_time = datetime.fromisoformat(params["start_time"]) if params.get("start_time") else None

        return self._store.get_log_count(
            strategy=params.get("strategy"),
            log_type=log_type,
            level=level,
            start_time=start_time,
        )

    # =========================================================================
    # Run Operations
    # =========================================================================

    async def _start_run(self, params: Dict[str, Any]) -> int:
        """Start a run session."""
        if not self._store:
            raise RuntimeError("Store not initialized")

        return self._store.start_run(
            strategy=params.get("strategy", ""),
            config=params.get("config"),
        )

    async def _end_run(self, params: Dict[str, Any]) -> None:
        """End a run session."""
        if not self._store:
            return

        self._store.end_run(
            run_id=params.get("run_id", 0),
            scans=params.get("scans", 0),
            signals=params.get("signals", 0),
            entries=params.get("entries", 0),
            exits=params.get("exits", 0),
            errors=params.get("errors", 0),
            status=params.get("status", "stopped"),
        )

    async def _get_runs(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get run history."""
        if not self._store:
            return []

        runs = self._store.get_runs(
            strategy=params.get("strategy"),
            status=params.get("status"),
            limit=params.get("limit", 50),
        )

        return [
            {
                "id": r.id,
                "strategy": r.strategy,
                "start_time": r.start_time.isoformat() if r.start_time else None,
                "end_time": r.end_time.isoformat() if r.end_time else None,
                "duration_seconds": r.duration_seconds,
                "scans_performed": r.scans_performed,
                "signals_generated": r.signals_generated,
                "entries": r.entries,
                "exits": r.exits,
                "errors": r.errors,
                "status": r.status,
            }
            for r in runs
        ]

    async def _get_current_run(self, params: Dict[str, Any]) -> Optional[int]:
        """Get current run ID."""
        if not self._store:
            return None

        return self._store.get_current_run(params.get("strategy", ""))

    # =========================================================================
    # Scan Summary Operations
    # =========================================================================

    async def _update_scan_summary(self, params: Dict[str, Any]) -> None:
        """Update scan summary."""
        if not self._store:
            return

        self._store.update_scan_summary(
            strategy=params.get("strategy", ""),
            scan_count=params.get("scan_count", 1),
            opportunities=params.get("opportunities", 0),
            signals=params.get("signals", 0),
            scan_duration_ms=params.get("scan_duration_ms"),
        )

    async def _get_scan_summaries(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get scan summaries."""
        if not self._store:
            return []

        summaries = self._store.get_scan_summaries(
            strategy=params.get("strategy", ""),
            hours=params.get("hours", 24),
        )

        # Convert datetime to ISO string for msgpack
        for s in summaries:
            if s.get("minute"):
                s["minute"] = s["minute"].isoformat()

        return summaries

    # =========================================================================
    # Background Tasks
    # =========================================================================

    async def _checkpoint_loop(self) -> None:
        """Periodically checkpoint the database."""
        interval = 60  # seconds

        while self._running:
            try:
                await asyncio.sleep(interval)
                if self._store:
                    self._store.checkpoint()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Checkpoint error: {e}")

    async def _cleanup_loop(self) -> None:
        """Periodically cleanup old logs."""
        interval = 3600  # 1 hour

        while self._running:
            try:
                await asyncio.sleep(interval)
                if self._store:
                    deleted_logs = self._store.cleanup_old_logs(days=30)
                    deleted_summaries = self._store.cleanup_old_summaries(days=7)
                    if deleted_logs > 0 or deleted_summaries > 0:
                        self._logger.info(
                            f"Cleaned up {deleted_logs} old logs, "
                            f"{deleted_summaries} old summaries"
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Cleanup error: {e}")
