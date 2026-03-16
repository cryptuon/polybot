"""Executor client for querying shadow data via NNG.

This client allows the API to query the executor service for shadow trading data.
"""

import logging
from typing import Any, Dict, List, Optional

from polybot.config import get_settings
from polybot.core.nng import NNGRequester


logger = logging.getLogger(__name__)


class ExecutorClient:
    """Client for the executor service.

    Uses NNG REQ/REP pattern to query shadow data from the executor.
    """

    def __init__(self) -> None:
        """Initialize the client."""
        self._settings = get_settings()
        self._requester: Optional[NNGRequester] = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to the executor service."""
        if self._connected:
            return

        self._requester = NNGRequester(self._settings.nng.executor_address)
        await self._requester.open()
        self._connected = True
        logger.info("Executor client connected")

    async def close(self) -> None:
        """Close the connection."""
        if self._requester:
            await self._requester.close()
            self._requester = None
            self._connected = False

    async def _query(self, request: Dict[str, Any]) -> Any:
        """Execute a query against the executor service."""
        if not self._connected or not self._requester:
            await self.connect()

        try:
            response = await self._requester.request(request)

            if not response.get("success"):
                error = response.get("error", "Unknown error")
                raise RuntimeError(f"Executor query failed: {error}")

            return response.get("data")

        except Exception as e:
            logger.error(f"Executor query error: {e}")
            raise

    async def get_shadow_summary(self) -> Dict[str, Any]:
        """Get shadow trading summary."""
        return await self._query({"type": "shadow_summary"})

    async def get_shadow_stats(self, strategy: Optional[str] = None) -> Dict[str, Any]:
        """Get shadow trading statistics."""
        return await self._query({"type": "shadow_stats", "strategy": strategy})

    async def get_shadow_positions(self, strategy: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get shadow positions."""
        return await self._query({"type": "shadow_positions", "strategy": strategy})

    async def get_shadow_trades(self, strategy: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get shadow trade history."""
        return await self._query({"type": "shadow_trades", "strategy": strategy, "limit": limit})

    async def reset_shadow(self, strategy: Optional[str] = None) -> None:
        """Reset shadow tracking data."""
        await self._query({"type": "shadow_reset", "strategy": strategy})


# Module-level client instance for dependency injection
_client: Optional[ExecutorClient] = None


async def get_executor_client() -> ExecutorClient:
    """Get or create the executor client singleton."""
    global _client
    if _client is None:
        _client = ExecutorClient()
        await _client.connect()
    return _client
