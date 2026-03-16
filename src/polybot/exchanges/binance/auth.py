"""Binance API authentication.

Implements HMAC-SHA256 signing for authenticated endpoints.
"""

import hashlib
import hmac
import time
from typing import Any, Dict
from urllib.parse import urlencode


class BinanceAuth:
    """HMAC-SHA256 authentication for Binance API."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        recv_window: int = 5000,
    ) -> None:
        """Initialize Binance auth.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            recv_window: Receive window in milliseconds
        """
        self._api_key = api_key
        self._api_secret = api_secret.encode("utf-8")
        self._recv_window = recv_window

    @property
    def api_key(self) -> str:
        """Get API key."""
        return self._api_key

    @property
    def has_credentials(self) -> bool:
        """Check if credentials are configured."""
        return bool(self._api_key and self._api_secret)

    def get_headers(self) -> Dict[str, str]:
        """Get headers with API key.

        Returns:
            Headers dict with X-MBX-APIKEY
        """
        return {"X-MBX-APIKEY": self._api_key}

    def get_timestamp(self) -> int:
        """Get current timestamp in milliseconds.

        Returns:
            Current time as milliseconds since epoch
        """
        return int(time.time() * 1000)

    def sign(self, query_string: str) -> str:
        """Sign a query string with HMAC-SHA256.

        Args:
            query_string: URL-encoded query string

        Returns:
            Hex-encoded signature
        """
        return hmac.new(
            self._api_secret,
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def sign_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sign request parameters.

        Adds timestamp, recvWindow, and signature to params.

        Args:
            params: Request parameters

        Returns:
            Signed parameters dict
        """
        params = params.copy()
        params["timestamp"] = self.get_timestamp()
        params["recvWindow"] = self._recv_window

        # Create query string and sign
        query_string = urlencode(params)
        signature = self.sign(query_string)
        params["signature"] = signature

        return params

    def sign_query_string(self, query_string: str) -> str:
        """Sign a query string and return complete signed string.

        Args:
            query_string: Existing query parameters

        Returns:
            Complete query string with timestamp and signature
        """
        timestamp = self.get_timestamp()

        if query_string:
            full_query = f"{query_string}&timestamp={timestamp}&recvWindow={self._recv_window}"
        else:
            full_query = f"timestamp={timestamp}&recvWindow={self._recv_window}"

        signature = self.sign(full_query)
        return f"{full_query}&signature={signature}"
