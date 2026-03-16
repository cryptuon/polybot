"""NNG messaging utilities for inter-service communication.

Provides high-level wrappers around pynng for PUB/SUB, REQ/REP,
and PUSH/PULL patterns used for service communication.
"""

import asyncio
import logging
import os
import stat
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

import msgpack
import pynng

from polybot.config import get_settings


logger = logging.getLogger(__name__)

T = TypeVar("T")


def ensure_ipc_directory() -> None:
    """Ensure the IPC directory exists with secure permissions.

    Creates the IPC directory with 0700 permissions (owner only) to prevent
    unauthorized access to IPC sockets on multi-user systems.
    """
    settings = get_settings()
    ipc_path = settings.nng.ipc_path

    # Create directory if it doesn't exist
    if not os.path.exists(ipc_path):
        os.makedirs(ipc_path, mode=stat.S_IRWXU, exist_ok=True)  # 0700 - owner only
        logger.info(f"Created IPC directory with secure permissions: {ipc_path}")
    else:
        # Verify existing directory has secure permissions
        current_mode = os.stat(ipc_path).st_mode
        if current_mode & (stat.S_IRWXG | stat.S_IRWXO):
            # Fix permissions if group/other have access
            os.chmod(ipc_path, stat.S_IRWXU)
            logger.warning(f"Fixed insecure IPC directory permissions: {ipc_path}")


@dataclass
class Message:
    """Base message structure for NNG communication."""

    type: str
    data: Dict[str, Any]
    timestamp: int


def _default_encoder(obj: Any) -> Any:
    """Custom encoder for msgpack to handle datetime and other types."""
    if isinstance(obj, datetime):
        return {"__datetime__": True, "value": obj.isoformat()}
    raise TypeError(f"Cannot serialize {type(obj)}")


def _default_decoder(obj: Dict[str, Any]) -> Any:
    """Custom decoder for msgpack to reconstruct datetime objects."""
    if isinstance(obj, dict) and obj.get("__datetime__"):
        return datetime.fromisoformat(obj["value"])
    return obj


def serialize(msg: Dict[str, Any]) -> bytes:
    """Serialize a message to bytes using msgpack."""
    return msgpack.packb(msg, use_bin_type=True, default=_default_encoder)


def deserialize(data: bytes) -> Dict[str, Any]:
    """Deserialize bytes to a message using msgpack."""
    return msgpack.unpackb(data, raw=False, object_hook=_default_decoder)


class NNGSocket(ABC):
    """Abstract base class for NNG sockets."""

    def __init__(self, address: str) -> None:
        self._address = address
        self._socket: Optional[pynng.Socket] = None

    @abstractmethod
    def _create_socket(self) -> pynng.Socket:
        """Create the underlying NNG socket."""
        pass

    async def open(self) -> None:
        """Open the socket connection."""
        ensure_ipc_directory()
        self._socket = self._create_socket()
        self._socket.recv_timeout = get_settings().nng.recv_timeout_ms

    async def close(self) -> None:
        """Close the socket connection."""
        if self._socket:
            self._socket.close()
            self._socket = None

    async def __aenter__(self) -> "NNGSocket":
        await self.open()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


class NNGPublisher(NNGSocket):
    """NNG PUB socket for publishing messages.

    Usage:
        async with NNGPublisher(settings.nng.prices_address) as pub:
            await pub.publish({"type": "price", "data": {...}})
    """

    def _create_socket(self) -> pynng.Socket:
        sock = pynng.Pub0()
        sock.listen(self._address)
        logger.info(f"Publisher listening on {self._address}")
        return sock

    async def publish(self, message: Dict[str, Any]) -> None:
        """Publish a message to all subscribers.

        Args:
            message: Message dictionary to publish
        """
        if not self._socket:
            raise RuntimeError("Socket not open")

        data = serialize(message)
        # pynng send is synchronous, run in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._socket.send, data)


class NNGSubscriber(NNGSocket):
    """NNG SUB socket for receiving messages.

    Usage:
        async with NNGSubscriber(settings.nng.prices_address) as sub:
            async for message in sub.messages():
                handle(message)
    """

    def __init__(self, address: str, topic: str = "") -> None:
        """Initialize subscriber.

        Args:
            address: NNG address to connect to
            topic: Topic filter (empty string for all messages)
        """
        super().__init__(address)
        self._topic = topic.encode() if topic else b""

    def _create_socket(self) -> pynng.Socket:
        sock = pynng.Sub0()
        sock.subscribe(self._topic)
        sock.dial(self._address)
        logger.info(f"Subscriber connected to {self._address}")
        return sock

    async def receive(self) -> Optional[Dict[str, Any]]:
        """Receive a single message.

        Returns:
            Message dictionary or None on timeout
        """
        if not self._socket:
            raise RuntimeError("Socket not open")

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._socket.recv)
            return deserialize(data)
        except pynng.Timeout:
            return None
        except Exception as e:
            logger.error(f"Receive error: {e}")
            return None

    async def messages(self):
        """Async generator for receiving messages.

        Yields:
            Message dictionaries
        """
        while True:
            msg = await self.receive()
            if msg is not None:
                yield msg


class NNGRequester(NNGSocket):
    """NNG REQ socket for request-reply pattern.

    Usage:
        async with NNGRequester(settings.nng.executor_address) as req:
            response = await req.request({"type": "order", ...})

    Note: Uses a lock to serialize access since REQ/REP requires
    strict send-then-receive ordering. Concurrent requests are queued.
    """

    def __init__(self, address: str) -> None:
        super().__init__(address)
        self._lock = asyncio.Lock()

    def _create_socket(self) -> pynng.Socket:
        sock = pynng.Req0()
        sock.dial(self._address)
        logger.info(f"Requester connected to {self._address}")
        return sock

    async def request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request and wait for reply.

        Args:
            message: Request message

        Returns:
            Reply message
        """
        if not self._socket:
            raise RuntimeError("Socket not open")

        # Lock ensures only one request at a time (REQ/REP is sequential)
        async with self._lock:
            data = serialize(message)
            loop = asyncio.get_event_loop()

            # Send request
            await loop.run_in_executor(None, self._socket.send, data)

            # Receive reply
            reply_data = await loop.run_in_executor(None, self._socket.recv)
            return deserialize(reply_data)


class NNGReplier(NNGSocket):
    """NNG REP socket for handling requests.

    Usage:
        async with NNGReplier(settings.nng.executor_address) as rep:
            async for request in rep.requests():
                response = handle(request)
                await rep.reply(response)
    """

    def _create_socket(self) -> pynng.Socket:
        sock = pynng.Rep0()
        sock.listen(self._address)
        logger.info(f"Replier listening on {self._address}")
        return sock

    async def receive_request(self) -> Optional[Dict[str, Any]]:
        """Receive a request.

        Returns:
            Request message or None on timeout
        """
        if not self._socket:
            raise RuntimeError("Socket not open")

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._socket.recv)
            return deserialize(data)
        except pynng.Timeout:
            return None

    async def reply(self, message: Dict[str, Any]) -> None:
        """Send a reply to the last request.

        Args:
            message: Reply message
        """
        if not self._socket:
            raise RuntimeError("Socket not open")

        data = serialize(message)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._socket.send, data)

    async def requests(self):
        """Async generator for receiving requests.

        Yields:
            Request dictionaries
        """
        while True:
            req = await self.receive_request()
            if req is not None:
                yield req


class NNGPusher(NNGSocket):
    """NNG PUSH socket for push/pull pattern.

    Usage:
        async with NNGPusher(settings.nng.signals_address) as push:
            await push.push({"type": "signal", ...})
    """

    def _create_socket(self) -> pynng.Socket:
        sock = pynng.Push0()
        sock.dial(self._address)
        logger.info(f"Pusher connected to {self._address}")
        return sock

    async def push(self, message: Dict[str, Any]) -> None:
        """Push a message to a puller.

        Args:
            message: Message to push
        """
        if not self._socket:
            raise RuntimeError("Socket not open")

        data = serialize(message)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._socket.send, data)


class NNGPuller(NNGSocket):
    """NNG PULL socket for receiving pushed messages.

    Usage:
        async with NNGPuller(settings.nng.signals_address) as pull:
            async for message in pull.messages():
                handle(message)
    """

    def _create_socket(self) -> pynng.Socket:
        sock = pynng.Pull0()
        sock.listen(self._address)
        logger.info(f"Puller listening on {self._address}")
        return sock

    async def receive(self) -> Optional[Dict[str, Any]]:
        """Receive a single message.

        Returns:
            Message dictionary or None on timeout
        """
        if not self._socket:
            raise RuntimeError("Socket not open")

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._socket.recv)
            return deserialize(data)
        except pynng.Timeout:
            return None

    async def messages(self):
        """Async generator for receiving messages.

        Yields:
            Message dictionaries
        """
        while True:
            msg = await self.receive()
            if msg is not None:
                yield msg
