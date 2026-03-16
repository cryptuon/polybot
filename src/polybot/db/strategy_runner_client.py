"""Strategy runner client for controlling strategies via NNG.

Provides an interface for the API to start/stop/restart strategies
by sending commands to the StrategyRunnerService.
"""

import logging
from typing import Any, Dict, Optional

from polybot.config import get_settings
from polybot.core.nng import NNGRequester


logger = logging.getLogger(__name__)


class StrategyRunnerClient:
    """Client for the strategy runner service.

    Uses NNG REQ/REP pattern to send commands to the strategy runner
    and receive responses.
    """

    def __init__(self) -> None:
        """Initialize the client."""
        self._settings = get_settings()
        self._requester: Optional[NNGRequester] = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to the strategy runner service."""
        if self._connected:
            return

        self._requester = NNGRequester(self._settings.nng.strategy_runner_address)
        await self._requester.open()
        self._connected = True
        logger.info("Strategy runner client connected")

    async def close(self) -> None:
        """Close the connection."""
        if self._requester:
            await self._requester.close()
            self._requester = None
            self._connected = False

    async def _command(self, command: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a command to the strategy runner.

        Args:
            command: Command name
            params: Optional command parameters

        Returns:
            Command result

        Raises:
            RuntimeError: If command fails
        """
        if not self._connected or not self._requester:
            await self.connect()

        request = {
            "command": command,
            "params": params or {},
        }

        try:
            response = await self._requester.request(request)

            if not response.get("success"):
                error = response.get("error", "Unknown error")
                raise RuntimeError(f"Strategy runner command failed: {error}")

            return response.get("data")

        except Exception as e:
            logger.error(f"Strategy runner command error: {e}")
            raise

    async def get_status(self) -> Dict[str, Any]:
        """Get status of all strategies.

        Returns:
            Dict with strategy names as keys and status info as values
        """
        return await self._command("status")

    async def start_strategy(self, strategy: str) -> bool:
        """Start a strategy.

        Args:
            strategy: Strategy name

        Returns:
            True if started successfully
        """
        await self._command("start", {"strategy": strategy})
        return True

    async def stop_strategy(self, strategy: str) -> bool:
        """Stop a strategy.

        Args:
            strategy: Strategy name

        Returns:
            True if stopped successfully
        """
        await self._command("stop", {"strategy": strategy})
        return True

    async def restart_strategy(self, strategy: str) -> bool:
        """Restart a strategy.

        Args:
            strategy: Strategy name

        Returns:
            True if restarted successfully
        """
        await self._command("restart", {"strategy": strategy})
        return True

    async def start_all(self) -> bool:
        """Start all enabled strategies.

        Returns:
            True if command succeeded
        """
        await self._command("start_all")
        return True

    async def stop_all(self) -> bool:
        """Stop all running strategies.

        Returns:
            True if command succeeded
        """
        await self._command("stop_all")
        return True


# Module-level client instance
_client: Optional[StrategyRunnerClient] = None


async def get_strategy_runner_client() -> StrategyRunnerClient:
    """Get or create the strategy runner client singleton.

    Returns:
        Connected strategy runner client
    """
    global _client
    if _client is None:
        _client = StrategyRunnerClient()
        await _client.connect()
    return _client
