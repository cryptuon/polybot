"""Base service class for all PolyBot services.

Provides common functionality for NNG messaging, lifecycle management,
and logging.
"""

import asyncio
import logging
import signal
from abc import ABC, abstractmethod
from typing import Any, Optional

from polybot.config import Settings, get_settings
from polybot.core.nng import NNGPublisher, NNGSubscriber, ensure_ipc_directory
from polybot.models.messages import Heartbeat, SystemEvent, EventType


class BaseService(ABC):
    """Abstract base class for PolyBot services.

    Provides:
    - Configuration management
    - NNG messaging setup
    - Lifecycle hooks (start, stop)
    - Event publishing
    - Heartbeat publishing
    - Signal handling
    """

    name: str = "base"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize the service.

        Args:
            settings: Configuration settings (uses global if not provided)
        """
        self._settings = settings or get_settings()
        self._running = False
        self._tasks: list[asyncio.Task[Any]] = []

        # NNG sockets (initialized in start)
        self._event_publisher: Optional[NNGPublisher] = None

        # Setup logging
        self._logger = logging.getLogger(f"polybot.services.{self.name}")

    @property
    def settings(self) -> Settings:
        """Get service settings."""
        return self._settings

    @property
    def is_running(self) -> bool:
        """Check if service is running."""
        return self._running

    async def start(self) -> None:
        """Start the service."""
        self._logger.info(f"Starting {self.name} service...")

        # Ensure IPC directory exists
        ensure_ipc_directory()

        # Initialize event publisher with service-specific address
        # Each service needs its own publisher to avoid IPC address conflicts
        self._event_publisher = NNGPublisher(
            self._settings.nng.service_events_address(self.name)
        )
        await self._event_publisher.open()

        # Call subclass initialization
        await self._on_start()

        self._running = True

        # Publish started event
        await self._publish_event(EventType.SERVICE_STARTED, {"service": self.name})

        self._logger.info(f"{self.name} service started")

    async def stop(self) -> None:
        """Stop the service."""
        self._logger.info(f"Stopping {self.name} service...")

        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()

        # Call subclass cleanup
        await self._on_stop()

        # Publish stopped event
        if self._event_publisher:
            await self._publish_event(EventType.SERVICE_STOPPED, {"service": self.name})
            await self._event_publisher.close()

        self._logger.info(f"{self.name} service stopped")

    async def run(self) -> None:
        """Run the service until stopped."""
        await self.start()

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Start heartbeat
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._tasks.append(heartbeat_task)

        # Run main loop
        try:
            await self._run()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    @abstractmethod
    async def _on_start(self) -> None:
        """Called when service starts. Override in subclass."""
        pass

    @abstractmethod
    async def _on_stop(self) -> None:
        """Called when service stops. Override in subclass."""
        pass

    @abstractmethod
    async def _run(self) -> None:
        """Main service loop. Override in subclass."""
        pass

    async def _publish_event(
        self,
        event_type: EventType,
        data: dict[str, Any],
    ) -> None:
        """Publish a system event.

        Args:
            event_type: Type of event
            data: Event data
        """
        if self._event_publisher:
            event = SystemEvent(
                source=self.name,
                event_type=event_type,
                data=data,
            )
            await self._event_publisher.publish(event.to_dict())

    async def _heartbeat_loop(self) -> None:
        """Publish periodic heartbeats."""
        while self._running:
            try:
                if self._event_publisher:
                    heartbeat = Heartbeat(service=self.name)
                    await self._event_publisher.publish(heartbeat.to_dict())
                await asyncio.sleep(10)  # Heartbeat every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5)

    def create_task(self, coro: Any) -> asyncio.Task[Any]:
        """Create and track an async task.

        Args:
            coro: Coroutine to run

        Returns:
            Created task
        """
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task
