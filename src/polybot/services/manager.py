"""Service manager for coordinating all PolyBot services.

Handles:
- Starting/stopping services
- Process management
- Health monitoring
- Graceful shutdown
"""

import asyncio
import logging
import multiprocessing
import os
import signal
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from polybot.config import get_settings
from polybot.services.base import BaseService
from polybot.services.state import StateService
from polybot.services.scanner import ScannerService
from polybot.services.executor import ExecutorService
from polybot.services.analytics import AnalyticsService
from polybot.services.strategy_logs import StrategyLogsService
from polybot.services.strategy_runner import StrategyRunnerService
from polybot.services.api_service import APIService


logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """Service status."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass
class ServiceInfo:
    """Information about a managed service."""

    name: str
    service_class: Type[BaseService]
    status: ServiceStatus = ServiceStatus.STOPPED
    process: Optional[multiprocessing.Process] = None
    error: Optional[str] = None


# Registry of available services
SERVICE_REGISTRY: Dict[str, Type[BaseService]] = {
    "state": StateService,
    "scanner": ScannerService,
    "executor": ExecutorService,
    "analytics": AnalyticsService,
    "strategy_logs": StrategyLogsService,
    "strategy_runner": StrategyRunnerService,
    "api": APIService,
}


def _run_service_process(service_class: Type[BaseService], name: str) -> None:
    """Run a service in a subprocess.

    Args:
        service_class: Service class to instantiate
        name: Service name
    """
    # Configure logging for subprocess
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{name}] %(levelname)s: %(message)s",
    )

    # Create and run service
    service = service_class()

    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Service {name} failed: {e}")
        sys.exit(1)


class ServiceManager:
    """Manager for all PolyBot services.

    Provides process-based service management with health monitoring.
    """

    def __init__(self) -> None:
        self._services: Dict[str, ServiceInfo] = {}
        self._running = False

        # Initialize service info for all registered services
        for name, service_class in SERVICE_REGISTRY.items():
            self._services[name] = ServiceInfo(
                name=name,
                service_class=service_class,
            )

    def start_service(self, name: str) -> bool:
        """Start a single service.

        Args:
            name: Service name

        Returns:
            True if started successfully
        """
        if name not in self._services:
            logger.error(f"Unknown service: {name}")
            return False

        info = self._services[name]

        if info.status == ServiceStatus.RUNNING:
            logger.warning(f"Service {name} is already running")
            return True

        logger.info(f"Starting service: {name}")
        info.status = ServiceStatus.STARTING

        try:
            # Create subprocess
            process = multiprocessing.Process(
                target=_run_service_process,
                args=(info.service_class, name),
                name=f"polybot-{name}",
            )
            process.start()

            info.process = process
            info.status = ServiceStatus.RUNNING
            info.error = None

            logger.info(f"Service {name} started (PID: {process.pid})")
            return True

        except Exception as e:
            info.status = ServiceStatus.FAILED
            info.error = str(e)
            logger.error(f"Failed to start {name}: {e}")
            return False

    def stop_service(self, name: str, timeout: float = 10.0) -> bool:
        """Stop a single service.

        Args:
            name: Service name
            timeout: Shutdown timeout in seconds

        Returns:
            True if stopped successfully
        """
        if name not in self._services:
            logger.error(f"Unknown service: {name}")
            return False

        info = self._services[name]

        if info.status != ServiceStatus.RUNNING or not info.process:
            logger.warning(f"Service {name} is not running")
            return True

        logger.info(f"Stopping service: {name}")
        info.status = ServiceStatus.STOPPING

        try:
            # Send SIGTERM
            info.process.terminate()

            # Wait for graceful shutdown
            info.process.join(timeout=timeout)

            if info.process.is_alive():
                # Force kill if still running
                logger.warning(f"Force killing {name}")
                info.process.kill()
                info.process.join(timeout=5)

            info.status = ServiceStatus.STOPPED
            info.process = None
            logger.info(f"Service {name} stopped")
            return True

        except Exception as e:
            info.status = ServiceStatus.FAILED
            info.error = str(e)
            logger.error(f"Failed to stop {name}: {e}")
            return False

    def start_all(self, services: Optional[List[str]] = None) -> bool:
        """Start all services (or a subset).

        Args:
            services: List of service names to start (all if None)

        Returns:
            True if all started successfully
        """
        self._running = True

        service_names = services or list(self._services.keys())
        success = True

        # Start in order: state first (others depend on it), then scanner, executor, analytics, strategy_logs, strategy_runner, api
        order = ["state", "scanner", "executor", "analytics", "strategy_logs", "strategy_runner", "api"]
        ordered_names = [n for n in order if n in service_names]
        ordered_names.extend([n for n in service_names if n not in order])

        for name in ordered_names:
            if not self.start_service(name):
                success = False

        return success

    def stop_all(self) -> bool:
        """Stop all running services.

        Returns:
            True if all stopped successfully
        """
        self._running = False
        success = True

        # Stop in reverse order
        for name in reversed(list(self._services.keys())):
            if self._services[name].status == ServiceStatus.RUNNING:
                if not self.stop_service(name):
                    success = False

        return success

    def restart_service(self, name: str) -> bool:
        """Restart a service.

        Args:
            name: Service name

        Returns:
            True if restarted successfully
        """
        self.stop_service(name)
        return self.start_service(name)

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all services.

        Returns:
            Dict of service status information
        """
        status = {}

        for name, info in self._services.items():
            status[name] = {
                "status": info.status.value,
                "pid": info.process.pid if info.process else None,
                "error": info.error,
            }

        return status

    def is_healthy(self) -> bool:
        """Check if all services are healthy.

        Returns:
            True if all expected services are running
        """
        for info in self._services.values():
            if info.status == ServiceStatus.RUNNING:
                if info.process and not info.process.is_alive():
                    return False
        return True

    def check_and_restart_failed(self) -> None:
        """Check for failed services and restart them."""
        for name, info in self._services.items():
            if info.status == ServiceStatus.RUNNING:
                if info.process and not info.process.is_alive():
                    logger.warning(f"Service {name} died, restarting...")
                    info.status = ServiceStatus.FAILED
                    self.start_service(name)

    async def run(self, services: Optional[List[str]] = None) -> None:
        """Run the service manager with health monitoring.

        Args:
            services: List of services to run (all if None)
        """
        # Setup signal handlers
        def signal_handler(signum: int, frame: Any) -> None:
            logger.info("Received shutdown signal")
            self.stop_all()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start services
        self.start_all(services)

        # Monitor loop
        while self._running:
            await asyncio.sleep(10)
            self.check_and_restart_failed()

        # Cleanup
        self.stop_all()


# Convenience functions for CLI
async def start_all_services() -> None:
    """Start all PolyBot services."""
    manager = ServiceManager()
    await manager.run()


async def start_service(name: str) -> None:
    """Start a single service.

    Args:
        name: Service name
    """
    if name not in SERVICE_REGISTRY:
        logger.error(f"Unknown service: {name}")
        return

    service_class = SERVICE_REGISTRY[name]
    service = service_class()
    await service.run()
