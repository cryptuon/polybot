"""Binance Spot WebSocket client."""

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Set

import websockets
from websockets.client import WebSocketClientProtocol

from polybot.exchanges.base import BaseWebSocketClient, ConnectionState
from polybot.exchanges.binance.config import BinanceSpotConfig

logger = logging.getLogger(__name__)


class BinanceSpotWebSocket(BaseWebSocketClient):
    """Binance Spot WebSocket client with auto-reconnection.

    Supports subscribing to multiple streams:
    - Trade streams: <symbol>@trade
    - Kline streams: <symbol>@kline_<interval>
    - Ticker streams: <symbol>@ticker
    - Book ticker: <symbol>@bookTicker
    - Depth streams: <symbol>@depth<levels>@<speed>

    Example:
        ws = BinanceSpotWebSocket(config)
        await ws.connect()
        await ws.subscribe(["btcusdt@ticker", "ethusdt@ticker"])

        async for msg in ws.messages():
            print(msg)
    """

    MAX_STREAMS_PER_CONNECTION = 1024
    PING_INTERVAL = 180  # 3 minutes

    def __init__(self, config: Optional[BinanceSpotConfig] = None) -> None:
        """Initialize WebSocket client.

        Args:
            config: Spot configuration
        """
        self._config = config or BinanceSpotConfig()
        self._ws: Optional[WebSocketClientProtocol] = None
        self._state = ConnectionState.DISCONNECTED
        self._subscriptions: Set[str] = set()
        self._message_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._running = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._tasks: List[asyncio.Task[Any]] = []
        self._request_id = 0

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._state == ConnectionState.CONNECTED

    @property
    def subscriptions(self) -> Set[str]:
        """Get current subscriptions."""
        return self._subscriptions.copy()

    def _get_next_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

    def _build_url(self) -> str:
        """Build WebSocket URL with subscribed streams."""
        base_url = self._config.websocket_url
        if self._subscriptions:
            streams = "/".join(sorted(self._subscriptions))
            return f"{base_url}/stream?streams={streams}"
        return base_url

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        if self._state == ConnectionState.CONNECTED:
            return

        self._running = True
        self._state = ConnectionState.CONNECTING

        try:
            url = self._build_url()
            self._ws = await websockets.connect(
                url,
                ping_interval=self.PING_INTERVAL,
                ping_timeout=30,
                close_timeout=10,
            )
            self._state = ConnectionState.CONNECTED
            self._reconnect_attempts = 0

            # Start message receiver
            task = asyncio.create_task(self._receive_loop())
            self._tasks.append(task)

            logger.info(f"Connected to Binance WebSocket: {url}")

        except Exception as e:
            self._state = ConnectionState.ERROR
            logger.error(f"WebSocket connection failed: {e}")
            raise

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._running = False
        self._state = ConnectionState.DISCONNECTED

        # Cancel tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

        # Close WebSocket
        if self._ws:
            await self._ws.close()
            self._ws = None

        logger.info("Disconnected from Binance WebSocket")

    async def subscribe(self, streams: List[str]) -> None:
        """Subscribe to streams.

        Args:
            streams: List of stream names (e.g., ["btcusdt@ticker"])
        """
        # Normalize stream names to lowercase
        streams = [s.lower() for s in streams]
        new_streams = set(streams) - self._subscriptions

        if not new_streams:
            return

        self._subscriptions.update(new_streams)

        if self._ws and self._state == ConnectionState.CONNECTED:
            msg = {
                "method": "SUBSCRIBE",
                "params": list(new_streams),
                "id": self._get_next_id(),
            }
            await self._ws.send(json.dumps(msg))
            logger.info(f"Subscribed to streams: {new_streams}")

    async def unsubscribe(self, streams: List[str]) -> None:
        """Unsubscribe from streams.

        Args:
            streams: List of stream names to unsubscribe from
        """
        streams = [s.lower() for s in streams]
        remove_streams = set(streams) & self._subscriptions

        if not remove_streams:
            return

        self._subscriptions -= remove_streams

        if self._ws and self._state == ConnectionState.CONNECTED:
            msg = {
                "method": "UNSUBSCRIBE",
                "params": list(remove_streams),
                "id": self._get_next_id(),
            }
            await self._ws.send(json.dumps(msg))
            logger.info(f"Unsubscribed from streams: {remove_streams}")

    async def _receive_loop(self) -> None:
        """Receive and process messages."""
        while self._running:
            try:
                if not self._ws:
                    await asyncio.sleep(1)
                    continue

                message = await self._ws.recv()
                data = json.loads(message)

                # Handle combined stream format
                if "stream" in data:
                    # Combined stream: {"stream": "btcusdt@ticker", "data": {...}}
                    payload = data["data"]
                    payload["_stream"] = data["stream"]
                elif "result" in data or "id" in data:
                    # Response to subscribe/unsubscribe
                    logger.debug(f"WebSocket response: {data}")
                    continue
                else:
                    # Single stream message
                    payload = data

                await self._message_queue.put(payload)

            except websockets.ConnectionClosed:
                if self._running:
                    logger.warning("WebSocket connection closed, reconnecting...")
                    await self._reconnect()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse WebSocket message: {e}")
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                if self._running:
                    await self._reconnect()

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        if not self._running:
            return

        self._state = ConnectionState.RECONNECTING

        while self._running and self._reconnect_attempts < self._max_reconnect_attempts:
            self._reconnect_attempts += 1
            wait_time = min(2**self._reconnect_attempts, 60)

            logger.info(
                f"Reconnecting in {wait_time}s (attempt {self._reconnect_attempts})"
            )
            await asyncio.sleep(wait_time)

            try:
                # Close existing connection
                if self._ws:
                    await self._ws.close()
                    self._ws = None

                # Reconnect
                url = self._build_url()
                self._ws = await websockets.connect(
                    url,
                    ping_interval=self.PING_INTERVAL,
                    ping_timeout=30,
                )
                self._state = ConnectionState.CONNECTED
                self._reconnect_attempts = 0

                # Re-subscribe if we connected without streams in URL
                if self._subscriptions and "/stream?" not in url:
                    await self.subscribe(list(self._subscriptions))

                logger.info(f"Reconnected to Binance WebSocket")
                return

            except Exception as e:
                logger.error(f"Reconnection failed: {e}")

        self._state = ConnectionState.ERROR
        logger.error("Max reconnection attempts reached")

    async def messages(self) -> AsyncIterator[Dict[str, Any]]:
        """Async iterator for received messages.

        Yields:
            Message data dicts
        """
        while self._running:
            try:
                msg = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                yield msg
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    # =========================================================================
    # Convenience Methods for Common Streams
    # =========================================================================

    async def subscribe_ticker(self, symbols: List[str]) -> None:
        """Subscribe to 24hr ticker streams.

        Args:
            symbols: List of symbols (e.g., ["BTCUSDT", "ETHUSDT"])
        """
        streams = [f"{s.lower()}@ticker" for s in symbols]
        await self.subscribe(streams)

    async def subscribe_book_ticker(self, symbols: List[str]) -> None:
        """Subscribe to book ticker streams (best bid/ask).

        Args:
            symbols: List of symbols
        """
        streams = [f"{s.lower()}@bookTicker" for s in symbols]
        await self.subscribe(streams)

    async def subscribe_depth(
        self, symbols: List[str], levels: int = 10, speed: str = "100ms"
    ) -> None:
        """Subscribe to depth streams.

        Args:
            symbols: List of symbols
            levels: Depth levels (5, 10, 20)
            speed: Update speed (100ms or 1000ms)
        """
        speed_suffix = "@100ms" if speed == "100ms" else ""
        streams = [f"{s.lower()}@depth{levels}{speed_suffix}" for s in symbols]
        await self.subscribe(streams)

    async def subscribe_trades(self, symbols: List[str]) -> None:
        """Subscribe to trade streams.

        Args:
            symbols: List of symbols
        """
        streams = [f"{s.lower()}@trade" for s in symbols]
        await self.subscribe(streams)

    async def subscribe_klines(self, symbols: List[str], interval: str = "1m") -> None:
        """Subscribe to kline/candlestick streams.

        Args:
            symbols: List of symbols
            interval: Kline interval (1m, 5m, 1h, 1d, etc.)
        """
        streams = [f"{s.lower()}@kline_{interval}" for s in symbols]
        await self.subscribe(streams)
