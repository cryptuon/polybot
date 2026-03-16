"""WebSocket manager for Polymarket real-time data.

Handles connections to market and user channels for real-time
price updates, order status, and trade confirmations.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import websockets
from websockets.client import WebSocketClientProtocol

from polybot.config import get_settings
from polybot.core.auth import L2Auth


logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    """WebSocket channel types."""

    MARKET = "market"
    USER = "user"


class EventType(str, Enum):
    """WebSocket event types."""

    # Market channel events
    BOOK = "book"
    PRICE_CHANGE = "price_change"
    TICK_SIZE_CHANGE = "tick_size_change"
    LAST_TRADE_PRICE = "last_trade_price"

    # User channel events
    TRADE = "trade"
    ORDER = "order"


@dataclass
class Subscription:
    """Subscription to a WebSocket channel."""

    channel: ChannelType
    asset_ids: Set[str] = field(default_factory=set)
    callback: Optional[Callable[[Dict[str, Any]], None]] = None


MessageHandler = Callable[[Dict[str, Any]], None]


class WebSocketManager:
    """Manager for Polymarket WebSocket connections.

    Handles:
    - Market channel for price/orderbook updates
    - User channel for order/trade updates
    - Automatic reconnection
    - Subscription management
    """

    def __init__(self, l2_auth: Optional[L2Auth] = None) -> None:
        """Initialize the WebSocket manager.

        Args:
            l2_auth: L2 authentication for user channel (optional)
        """
        settings = get_settings()
        self._ws_url = settings.ws_base_url
        self._l2_auth = l2_auth

        self._connections: Dict[ChannelType, WebSocketClientProtocol] = {}
        self._subscriptions: Dict[ChannelType, Subscription] = {}
        self._handlers: Dict[EventType, List[MessageHandler]] = {
            event_type: [] for event_type in EventType
        }
        self._running = False
        self._tasks: List[asyncio.Task[Any]] = []

    def on_event(self, event_type: EventType, handler: MessageHandler) -> None:
        """Register a handler for an event type.

        Args:
            event_type: Type of event to handle
            handler: Callback function
        """
        self._handlers[event_type].append(handler)

    def off_event(self, event_type: EventType, handler: MessageHandler) -> None:
        """Unregister a handler for an event type.

        Args:
            event_type: Type of event
            handler: Callback function to remove
        """
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def subscribe_market(self, asset_ids: List[str]) -> None:
        """Subscribe to market channel for asset updates.

        Args:
            asset_ids: List of token IDs to subscribe to
        """
        if ChannelType.MARKET not in self._subscriptions:
            self._subscriptions[ChannelType.MARKET] = Subscription(
                channel=ChannelType.MARKET
            )

        sub = self._subscriptions[ChannelType.MARKET]
        new_ids = set(asset_ids) - sub.asset_ids
        sub.asset_ids.update(asset_ids)

        # If connected, send subscription message
        conn = self._connections.get(ChannelType.MARKET)
        if conn and new_ids:
            await conn.send(
                json.dumps({
                    "assets_ids": list(new_ids),
                    "operation": "subscribe",
                })
            )

    async def unsubscribe_market(self, asset_ids: List[str]) -> None:
        """Unsubscribe from market channel for assets.

        Args:
            asset_ids: List of token IDs to unsubscribe from
        """
        sub = self._subscriptions.get(ChannelType.MARKET)
        if not sub:
            return

        sub.asset_ids -= set(asset_ids)

        conn = self._connections.get(ChannelType.MARKET)
        if conn:
            await conn.send(
                json.dumps({
                    "assets_ids": asset_ids,
                    "operation": "unsubscribe",
                })
            )

    async def subscribe_user(self, market_ids: List[str]) -> None:
        """Subscribe to user channel for order/trade updates.

        Args:
            market_ids: List of market condition IDs
        """
        if not self._l2_auth:
            raise ValueError("L2 auth required for user channel")

        if ChannelType.USER not in self._subscriptions:
            self._subscriptions[ChannelType.USER] = Subscription(
                channel=ChannelType.USER
            )

        self._subscriptions[ChannelType.USER].asset_ids.update(market_ids)

    async def _connect(self, channel: ChannelType) -> WebSocketClientProtocol:
        """Establish WebSocket connection.

        Args:
            channel: Channel type to connect to

        Returns:
            WebSocket connection
        """
        url = f"{self._ws_url}/{channel.value}"

        # Build connection message
        conn_msg: Dict[str, Any] = {
            "type": channel.value.upper(),
        }

        sub = self._subscriptions.get(channel)
        if sub:
            if channel == ChannelType.MARKET:
                conn_msg["assets_ids"] = list(sub.asset_ids)
            elif channel == ChannelType.USER:
                conn_msg["markets"] = list(sub.asset_ids)
                # Add auth for user channel
                if self._l2_auth:
                    headers = self._l2_auth.get_auth_headers("GET", "/ws/user")
                    conn_msg["auth"] = {
                        "apiKey": headers["POLY_API_KEY"],
                        "secret": headers["POLY_SIGNATURE"],
                        "passphrase": headers["POLY_PASSPHRASE"],
                    }

        conn = await websockets.connect(url)
        await conn.send(json.dumps(conn_msg))

        self._connections[channel] = conn
        logger.info(f"Connected to {channel.value} channel")

        return conn

    async def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message.

        Args:
            message: Raw message string
        """
        try:
            data = json.loads(message)
            event_type_str = data.get("event_type", "")

            # Map to EventType
            try:
                event_type = EventType(event_type_str)
            except ValueError:
                logger.debug(f"Unknown event type: {event_type_str}")
                return

            # Call handlers
            for handler in self._handlers[event_type]:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Handler error: {e}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")

    async def _listen(self, channel: ChannelType) -> None:
        """Listen for messages on a channel.

        Args:
            channel: Channel to listen on
        """
        while self._running:
            try:
                conn = self._connections.get(channel)
                if not conn:
                    conn = await self._connect(channel)

                async for message in conn:
                    if isinstance(message, bytes):
                        message = message.decode("utf-8")
                    await self._handle_message(message)

            except websockets.ConnectionClosed:
                logger.warning(f"{channel.value} connection closed, reconnecting...")
                self._connections.pop(channel, None)
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"{channel.value} error: {e}")
                self._connections.pop(channel, None)
                await asyncio.sleep(5)

    async def start(self) -> None:
        """Start WebSocket connections."""
        self._running = True

        for channel in self._subscriptions:
            task = asyncio.create_task(self._listen(channel))
            self._tasks.append(task)

        logger.info("WebSocket manager started")

    async def stop(self) -> None:
        """Stop WebSocket connections."""
        self._running = False

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        # Close connections
        for conn in self._connections.values():
            await conn.close()

        self._connections.clear()
        self._tasks.clear()

        logger.info("WebSocket manager stopped")

    async def __aenter__(self) -> "WebSocketManager":
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()
