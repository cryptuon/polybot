"""Strategy runner service.

Automatically runs enabled strategies as background tasks.
Monitors strategy health and supports dynamic start/stop.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Type

from polybot.config import Settings
from polybot.core.nng import NNGReplier
from polybot.db.state_client import StateClient
from polybot.services.base import BaseService
from polybot.strategies.base import BaseStrategy
from polybot.strategies import STRATEGY_REGISTRY


logger = logging.getLogger(__name__)


class StrategyStatus(str, Enum):
    """Strategy runtime status."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass
class StrategyInfo:
    """Information about a managed strategy."""

    name: str
    strategy_class: Type[BaseStrategy]
    instance: Optional[BaseStrategy] = None
    task: Optional[asyncio.Task] = None
    status: StrategyStatus = StrategyStatus.STOPPED
    error: Optional[str] = None
    restart_count: int = 0


class StrategyRunnerService(BaseService):
    """Service that runs enabled strategies.

    Manages the lifecycle of trading strategies:
    - Starts enabled strategies on service start
    - Monitors strategy health
    - Supports dynamic start/stop via NNG commands
    - Auto-restarts failed strategies (with backoff)
    """

    name = "strategy_runner"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._strategies: Dict[str, StrategyInfo] = {}
        self._replier: Optional[NNGReplier] = None
        self._state_client: Optional[StateClient] = None

        # Max restart attempts before giving up
        self._max_restarts = 3
        self._restart_delay = 5.0  # seconds

        # Initialize strategy info for all registered strategies
        for name, strategy_class in STRATEGY_REGISTRY.items():
            self._strategies[name] = StrategyInfo(
                name=name,
                strategy_class=strategy_class,
            )

    async def _on_start(self) -> None:
        """Initialize service resources."""
        # Initialize NNG replier for commands
        self._replier = NNGReplier(self._settings.nng.strategy_runner_address)
        await self._replier.open()

        # Initialize state client for checking enabled status
        self._state_client = StateClient()
        await self._state_client.connect()

        # Start all enabled strategies
        await self._start_enabled_strategies()

        self._logger.info("Strategy runner service initialized")

    async def _on_stop(self) -> None:
        """Cleanup service resources."""
        # Stop all running strategies
        await self._stop_all_strategies()

        if self._state_client:
            await self._state_client.close()

        if self._replier:
            await self._replier.close()

    async def _run(self) -> None:
        """Main service loop."""
        # Start command handler
        command_task = self.create_task(self._handle_commands())

        # Start health monitor
        monitor_task = self.create_task(self._health_monitor())

        await asyncio.gather(
            command_task, monitor_task,
            return_exceptions=True
        )

    async def _start_enabled_strategies(self) -> None:
        """Start all strategies that are enabled in database."""
        for name, info in self._strategies.items():
            if await self._is_strategy_enabled(name):
                await self._start_strategy(name)

    async def _stop_all_strategies(self) -> None:
        """Stop all running strategies."""
        for name in list(self._strategies.keys()):
            if self._strategies[name].status == StrategyStatus.RUNNING:
                await self._stop_strategy(name)

    async def _is_strategy_enabled(self, name: str) -> bool:
        """Check if a strategy is enabled in database.

        Args:
            name: Strategy name

        Returns:
            True if strategy is enabled in database
        """
        if not self._state_client:
            return False

        try:
            config = await self._state_client.get_strategy_config(name)
            if config:
                return config.get("enabled", False)
            return False
        except Exception as e:
            self._logger.warning(f"Failed to get strategy config for {name}: {e}")
            return False

    async def _start_strategy(self, name: str) -> bool:
        """Start a single strategy.

        Args:
            name: Strategy name

        Returns:
            True if started successfully
        """
        if name not in self._strategies:
            self._logger.error(f"Unknown strategy: {name}")
            return False

        info = self._strategies[name]

        if info.status == StrategyStatus.RUNNING:
            self._logger.warning(f"Strategy {name} is already running")
            return True

        self._logger.info(f"Starting strategy: {name}")
        info.status = StrategyStatus.STARTING
        info.error = None

        try:
            # Create strategy instance
            info.instance = info.strategy_class(self._settings)

            # Create task to run the strategy
            info.task = asyncio.create_task(
                self._run_strategy(name),
                name=f"strategy_{name}"
            )

            info.status = StrategyStatus.RUNNING
            self._logger.info(f"Strategy {name} started")
            return True

        except Exception as e:
            info.status = StrategyStatus.FAILED
            info.error = str(e)
            self._logger.error(f"Failed to start strategy {name}: {e}")
            return False

    async def _run_strategy(self, name: str) -> None:
        """Run a strategy and handle its lifecycle.

        Args:
            name: Strategy name
        """
        info = self._strategies[name]

        if not info.instance:
            return

        try:
            # Run the strategy (this blocks until strategy stops)
            await info.instance.run()

            # Strategy completed normally
            info.status = StrategyStatus.STOPPED
            self._logger.info(f"Strategy {name} stopped normally")

        except asyncio.CancelledError:
            # Strategy was cancelled (stop requested)
            info.status = StrategyStatus.STOPPED
            self._logger.info(f"Strategy {name} was cancelled")

        except Exception as e:
            # Strategy failed
            info.status = StrategyStatus.FAILED
            info.error = str(e)
            self._logger.error(f"Strategy {name} failed: {e}")

        finally:
            info.instance = None
            info.task = None

    async def _stop_strategy(self, name: str) -> bool:
        """Stop a running strategy.

        Args:
            name: Strategy name

        Returns:
            True if stopped successfully
        """
        if name not in self._strategies:
            self._logger.error(f"Unknown strategy: {name}")
            return False

        info = self._strategies[name]

        if info.status != StrategyStatus.RUNNING:
            self._logger.warning(f"Strategy {name} is not running")
            return True

        self._logger.info(f"Stopping strategy: {name}")
        info.status = StrategyStatus.STOPPING

        try:
            # Cancel the task
            if info.task:
                info.task.cancel()
                try:
                    await asyncio.wait_for(info.task, timeout=10.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

            info.status = StrategyStatus.STOPPED
            info.instance = None
            info.task = None

            self._logger.info(f"Strategy {name} stopped")
            return True

        except Exception as e:
            info.status = StrategyStatus.FAILED
            info.error = str(e)
            self._logger.error(f"Failed to stop strategy {name}: {e}")
            return False

    async def _restart_strategy(self, name: str) -> bool:
        """Restart a strategy.

        Args:
            name: Strategy name

        Returns:
            True if restarted successfully
        """
        await self._stop_strategy(name)
        await asyncio.sleep(1)  # Brief pause before restart
        return await self._start_strategy(name)

    async def _health_monitor(self) -> None:
        """Monitor strategy health and restart failed strategies."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                for name, info in self._strategies.items():
                    # Check if strategy task died unexpectedly
                    if info.status == StrategyStatus.RUNNING and info.task:
                        if info.task.done():
                            # Task completed/failed
                            try:
                                info.task.result()
                            except Exception as e:
                                info.status = StrategyStatus.FAILED
                                info.error = str(e)

                    # Auto-restart failed strategies if enabled
                    if info.status == StrategyStatus.FAILED:
                        if await self._is_strategy_enabled(name):
                            if info.restart_count < self._max_restarts:
                                self._logger.warning(
                                    f"Strategy {name} failed, attempting restart "
                                    f"({info.restart_count + 1}/{self._max_restarts})"
                                )
                                info.restart_count += 1
                                await asyncio.sleep(self._restart_delay * info.restart_count)
                                await self._start_strategy(name)
                            else:
                                self._logger.error(
                                    f"Strategy {name} exceeded max restarts, giving up"
                                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Health monitor error: {e}")

    async def _handle_commands(self) -> None:
        """Handle incoming commands via NNG REQ/REP."""
        if not self._replier:
            return

        async for request in self._replier.requests():
            if not self._running:
                break

            try:
                response = await self._process_command(request)
                await self._replier.reply(response)
            except Exception as e:
                self._logger.error(f"Command handling error: {e}")
                await self._replier.reply({
                    "success": False,
                    "error": str(e),
                })

    async def _process_command(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a command request.

        Args:
            request: Command request with 'command' and optional params

        Returns:
            Response dict
        """
        command = request.get("command", "")
        params = request.get("params", {})

        try:
            if command == "status":
                return {"success": True, "data": await self._get_status()}

            elif command == "start":
                name = params.get("strategy")
                if not name:
                    return {"success": False, "error": "Strategy name required"}
                success = await self._start_strategy(name)
                return {"success": success}

            elif command == "stop":
                name = params.get("strategy")
                if not name:
                    return {"success": False, "error": "Strategy name required"}
                success = await self._stop_strategy(name)
                return {"success": success}

            elif command == "restart":
                name = params.get("strategy")
                if not name:
                    return {"success": False, "error": "Strategy name required"}
                success = await self._restart_strategy(name)
                return {"success": success}

            elif command == "start_all":
                await self._start_enabled_strategies()
                return {"success": True}

            elif command == "stop_all":
                await self._stop_all_strategies()
                return {"success": True}

            else:
                return {"success": False, "error": f"Unknown command: {command}"}

        except Exception as e:
            self._logger.error(f"Command processing error: {e}")
            return {"success": False, "error": str(e)}

    async def _get_status(self) -> Dict[str, Any]:
        """Get status of all strategies.

        Returns:
            Dict of strategy status information
        """
        status = {}

        for name, info in self._strategies.items():
            status[name] = {
                "status": info.status.value,
                "enabled": await self._is_strategy_enabled(name),
                "error": info.error,
                "restart_count": info.restart_count,
            }

            # Add stats if running
            if info.instance and info.status == StrategyStatus.RUNNING:
                status[name]["stats"] = info.instance.get_stats()

        return status
