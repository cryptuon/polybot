"""Authentication for Polymarket API.

Implements L1 (wallet-based) and L2 (API key-based) authentication
following Polymarket's authentication specification.
"""

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any, Dict

from eth_account import Account
from eth_account.messages import encode_typed_data


@dataclass
class ApiCredentials:
    """L2 API credentials."""

    api_key: str
    secret: str
    passphrase: str


# EIP-712 domain for Polymarket CLOB
CLOB_DOMAIN = {
    "name": "ClobAuthDomain",
    "version": "1",
    "chainId": 137,
}

# EIP-712 types for authentication
AUTH_TYPES = {
    "ClobAuth": [
        {"name": "address", "type": "address"},
        {"name": "timestamp", "type": "string"},
        {"name": "nonce", "type": "uint256"},
        {"name": "message", "type": "string"},
    ],
}

AUTH_MESSAGE = "This message attests that I control the given wallet"


class L1Auth:
    """L1 authentication using wallet private key.

    Used for:
    - Creating/deriving API keys
    - Signing orders locally
    """

    def __init__(self, private_key: str) -> None:
        """Initialize with wallet private key.

        Args:
            private_key: Hex private key (with or without 0x prefix)
        """
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
        self._private_key = private_key
        self._account = Account.from_key(private_key)

    @property
    def address(self) -> str:
        """Get the wallet address."""
        return self._account.address

    def sign_auth_message(self, timestamp: str, nonce: int = 0) -> str:
        """Sign an authentication message using EIP-712.

        Args:
            timestamp: Unix timestamp as string
            nonce: Nonce value (default 0)

        Returns:
            Hex-encoded signature
        """
        typed_data = {
            "types": AUTH_TYPES,
            "primaryType": "ClobAuth",
            "domain": CLOB_DOMAIN,
            "message": {
                "address": self.address,
                "timestamp": timestamp,
                "nonce": nonce,
                "message": AUTH_MESSAGE,
            },
        }

        signable = encode_typed_data(full_message=typed_data)
        signed = self._account.sign_message(signable)
        # Polymarket requires 0x prefix on signature
        return "0x" + signed.signature.hex()

    def get_auth_headers(self, nonce: int = 0) -> Dict[str, str]:
        """Get L1 authentication headers for API requests.

        Args:
            nonce: Nonce value (default 0)

        Returns:
            Dictionary of headers to include in request
        """
        timestamp = str(int(time.time()))
        signature = self.sign_auth_message(timestamp, nonce)

        return {
            "POLY_ADDRESS": self.address,
            "POLY_SIGNATURE": signature,
            "POLY_TIMESTAMP": timestamp,
            "POLY_NONCE": str(nonce),
        }

    def sign_order(self, order_data: Dict[str, Any]) -> str:
        """Sign an order using EIP-712.

        Args:
            order_data: Order data to sign

        Returns:
            Hex-encoded signature
        """
        # Order signing types for Polymarket
        order_types = {
            "Order": [
                {"name": "salt", "type": "uint256"},
                {"name": "maker", "type": "address"},
                {"name": "signer", "type": "address"},
                {"name": "taker", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
                {"name": "makerAmount", "type": "uint256"},
                {"name": "takerAmount", "type": "uint256"},
                {"name": "expiration", "type": "uint256"},
                {"name": "nonce", "type": "uint256"},
                {"name": "feeRateBps", "type": "uint256"},
                {"name": "side", "type": "uint8"},
                {"name": "signatureType", "type": "uint8"},
            ],
        }

        order_domain = {
            "name": "Polymarket CTF Exchange",
            "version": "1",
            "chainId": 137,
        }

        typed_data = {
            "types": order_types,
            "primaryType": "Order",
            "domain": order_domain,
            "message": order_data,
        }

        signable = encode_typed_data(full_message=typed_data)
        signed = self._account.sign_message(signable)
        # Polymarket requires 0x prefix on signature
        return "0x" + signed.signature.hex()


class L2Auth:
    """L2 authentication using API credentials.

    Used for:
    - All trading operations
    - Order placement, cancellation
    - Position queries
    """

    def __init__(
        self,
        credentials: ApiCredentials,
        address: str,
    ) -> None:
        """Initialize with API credentials.

        Args:
            credentials: API credentials (api_key, secret, passphrase)
            address: Wallet address associated with these credentials
        """
        self._credentials = credentials
        self._address = address
        # Add padding if needed (base64 strings must be multiple of 4)
        secret = credentials.secret
        padding_needed = 4 - (len(secret) % 4)
        if padding_needed != 4:
            secret += "=" * padding_needed
        self._secret_bytes = base64.b64decode(secret)

    @property
    def address(self) -> str:
        """Get the wallet address."""
        return self._address

    def _sign_request(
        self,
        timestamp: str,
        method: str,
        path: str,
        body: str = "",
    ) -> str:
        """Create HMAC-SHA256 signature for request.

        Args:
            timestamp: Unix timestamp as string
            method: HTTP method (GET, POST, DELETE)
            path: Request path
            body: Request body (empty string for GET)

        Returns:
            Base64-encoded signature
        """
        message = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            self._secret_bytes,
            message.encode("utf-8"),
            hashlib.sha256,
        )
        return base64.b64encode(signature.digest()).decode("utf-8")

    def get_auth_headers(
        self,
        method: str,
        path: str,
        body: str = "",
    ) -> Dict[str, str]:
        """Get L2 authentication headers for API requests.

        Args:
            method: HTTP method
            path: Request path (e.g., "/order")
            body: Request body JSON string

        Returns:
            Dictionary of headers to include in request
        """
        timestamp = str(int(time.time()))
        signature = self._sign_request(timestamp, method, path, body)

        return {
            "POLY_ADDRESS": self._address,
            "POLY_SIGNATURE": signature,
            "POLY_TIMESTAMP": timestamp,
            "POLY_API_KEY": self._credentials.api_key,
            "POLY_PASSPHRASE": self._credentials.passphrase,
        }


def create_l1_auth(private_key: str) -> L1Auth:
    """Create L1 auth from private key."""
    return L1Auth(private_key)


def create_l2_auth(
    api_key: str,
    api_secret: str,
    api_passphrase: str,
    address: str,
) -> L2Auth:
    """Create L2 auth from API credentials."""
    credentials = ApiCredentials(
        api_key=api_key,
        secret=api_secret,
        passphrase=api_passphrase,
    )
    return L2Auth(credentials, address)
