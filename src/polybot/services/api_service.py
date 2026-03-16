"""API server service.

Runs the FastAPI server as part of the service manager.
"""

import asyncio
import logging
from typing import Optional

import uvicorn

from polybot.config import Settings
from polybot.services.base import BaseService


logger = logging.getLogger(__name__)


class APIService(BaseService):
    """API server service.

    Runs the FastAPI application with uvicorn.
    """

    name = "api"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)
        self._server: Optional[uvicorn.Server] = None

    async def _on_start(self) -> None:
        """Initialize API server."""
        pass  # Server is created in _run

    async def _on_stop(self) -> None:
        """Shutdown API server."""
        if self._server:
            self._server.should_exit = True

    async def _run(self) -> None:
        """Run the API server."""
        config = uvicorn.Config(
            "polybot.api.app:app",
            host=self._settings.api.host,
            port=self._settings.api.port,
            log_level="info",
            loop="asyncio",
        )
        self._server = uvicorn.Server(config)

        self._logger.info(
            f"Starting API server on http://{self._settings.api.host}:{self._settings.api.port}"
        )

        await self._server.serve()
