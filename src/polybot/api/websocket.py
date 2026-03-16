"""WebSocket handler for real-time frontend updates."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Set

from fastapi import WebSocket, WebSocketDisconnect

from polybot.core.nng import NNGSubscriber
from polybot.config import get_settings


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._subscriptions: Dict[WebSocket, Set[str]] = {}
        self._running = False
        self._tasks: List[asyncio.Task[Any]] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self._connections.add(websocket)
        self._subscriptions[websocket] = set()
        logger.info(f"WebSocket connected: {len(self._connections)} total")

    def disconnect(self, websocket: WebSocket) -> None:
        """Handle WebSocket disconnection."""
        self._connections.discard(websocket)
        self._subscriptions.pop(websocket, None)
        logger.info(f"WebSocket disconnected: {len(self._connections)} total")

    async def subscribe(self, websocket: WebSocket, channels: List[str]) -> None:
        """Subscribe a connection to channels."""
        if websocket in self._subscriptions:
            self._subscriptions[websocket].update(channels)

    async def unsubscribe(self, websocket: WebSocket, channels: List[str]) -> None:
        """Unsubscribe a connection from channels."""
        if websocket in self._subscriptions:
            self._subscriptions[websocket] -= set(channels)

    async def broadcast(self, channel: str, message: Dict[str, Any]) -> None:
        """Broadcast message to all subscribed connections."""
        payload = json.dumps({
            "channel": channel,
            "data": message,
            "timestamp": datetime.utcnow().isoformat(),
        })

        disconnected = []

        for websocket in self._connections:
            # Check if subscribed to this channel
            if channel in self._subscriptions.get(websocket, set()):
                try:
                    await websocket.send_text(payload)
                except Exception:
                    disconnected.append(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)

    async def send_personal(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """Send message to a specific connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception:
            self.disconnect(websocket)

    async def start_nng_bridge(self) -> None:
        """Start bridge from NNG to WebSocket."""
        self._running = True
        settings = get_settings()

        # Subscribe to price updates
        price_task = asyncio.create_task(
            self._bridge_channel(settings.nng.prices_address, "prices")
        )
        self._tasks.append(price_task)

        # Subscribe to events from all services
        # Each service publishes to its own event address
        for service in ["scanner", "executor", "analytics"]:
            event_task = asyncio.create_task(
                self._bridge_channel(
                    settings.nng.service_events_address(service),
                    "events"
                )
            )
            self._tasks.append(event_task)

    async def stop_nng_bridge(self) -> None:
        """Stop NNG bridge."""
        self._running = False

        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()

    async def _bridge_channel(self, nng_address: str, channel: str) -> None:
        """Bridge NNG messages to WebSocket channel."""
        try:
            async with NNGSubscriber(nng_address) as subscriber:
                async for msg in subscriber.messages():
                    if not self._running:
                        break
                    await self.broadcast(channel, msg)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"NNG bridge error for {channel}: {e}")


# Global connection manager
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint handler."""
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type", "")

                if msg_type == "subscribe":
                    channels = message.get("channels", [])
                    await manager.subscribe(websocket, channels)
                    await manager.send_personal(websocket, {
                        "type": "subscribed",
                        "channels": channels,
                    })

                elif msg_type == "unsubscribe":
                    channels = message.get("channels", [])
                    await manager.unsubscribe(websocket, channels)
                    await manager.send_personal(websocket, {
                        "type": "unsubscribed",
                        "channels": channels,
                    })

                elif msg_type == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})

                else:
                    await manager.send_personal(websocket, {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    })

            except json.JSONDecodeError:
                await manager.send_personal(websocket, {
                    "type": "error",
                    "message": "Invalid JSON",
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
