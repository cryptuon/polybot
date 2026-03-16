"""Polymarket API client.

Wraps the official py-clob-client for CLOB operations and provides
additional methods for Gamma and Data APIs.
"""

import asyncio
from typing import Any, Dict, List, Optional

import httpx
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs
from py_clob_client.http_helpers import helpers as clob_helpers

from polybot.config import get_settings
from polybot.core.rate_limiter import EndpointType, get_rate_limiter

# Monkey-patch py_clob_client to use a more realistic User-Agent
# This helps avoid Cloudflare bot detection
_original_overload_headers = clob_helpers.overloadHeaders


def _patched_overload_headers(method: str, headers: dict) -> dict:
    """Patched version with realistic User-Agent."""
    headers = _original_overload_headers(method, headers)
    # Use a realistic browser-like User-Agent
    headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    return headers


clob_helpers.overloadHeaders = _patched_overload_headers


class PolymarketClient:
    """Unified client for Polymarket APIs.

    Uses the official py-clob-client for CLOB operations (auth, orders)
    and httpx for Gamma/Data API calls.
    """

    def __init__(self) -> None:
        """Initialize the client from settings."""
        settings = get_settings()

        self._gamma_url = settings.gamma_base_url
        self._data_url = settings.data_base_url
        self._rate_limiter = get_rate_limiter()
        self._http_client = httpx.AsyncClient(timeout=30.0)

        # Initialize CLOB client if we have credentials
        self._clob: Optional[ClobClient] = None
        self._address: Optional[str] = None

        pk = settings.polymarket.private_key
        if pk:
            # Determine signature type and funder
            sig_type = settings.polymarket.signature_type
            funder = settings.polymarket.proxy_address or None

            # Check if we have existing API creds
            creds = None
            if settings.polymarket.api_key:
                creds = ApiCreds(
                    api_key=settings.polymarket.api_key,
                    api_secret=settings.polymarket.api_secret,
                    api_passphrase=settings.polymarket.api_passphrase,
                )

            # Initialize with appropriate parameters based on signature type
            if sig_type == 0:
                # EOA direct trading - no funder needed
                self._clob = ClobClient(
                    host=settings.clob_base_url,
                    chain_id=settings.chain_id,
                    key=pk,
                    creds=creds,
                )
            else:
                # Browser wallet or Magic (sig_type 1 or 2) - needs funder
                self._clob = ClobClient(
                    host=settings.clob_base_url,
                    chain_id=settings.chain_id,
                    key=pk,
                    creds=creds,
                    signature_type=sig_type,
                    funder=funder,
                )

            self._address = self._clob.get_address()

    @property
    def address(self) -> Optional[str]:
        """Get the wallet address."""
        return self._address

    @property
    def has_credentials(self) -> bool:
        """Check if API credentials are set."""
        return self._clob is not None and self._clob.creds is not None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http_client.aclose()

    async def __aenter__(self) -> "PolymarketClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # =========================================================================
    # API Key Management
    # =========================================================================

    async def create_or_derive_api_key(self) -> ApiCreds:
        """Create or derive API credentials.

        Returns:
            API credentials
        """
        if not self._clob:
            raise ValueError("Private key required")

        await self._rate_limiter.acquire(EndpointType.CLOB_GENERAL)

        # Run sync method in executor
        loop = asyncio.get_event_loop()
        creds = await loop.run_in_executor(
            None, self._clob.create_or_derive_api_creds
        )
        self._clob.set_api_creds(creds)
        return creds

    # =========================================================================
    # CLOB Methods (orderbook, prices)
    # =========================================================================

    async def get_orderbook(self, token_id: str) -> Dict[str, Any]:
        """Get orderbook for a token."""
        if not self._clob:
            raise ValueError("Client not initialized")

        await self._rate_limiter.acquire(EndpointType.CLOB_BOOK)

        loop = asyncio.get_event_loop()

        def fetch_book():
            book = self._clob.get_order_book(token_id)
            # Convert OrderBookSummary to dict for compatibility
            return {
                "asset_id": book.asset_id,
                "bids": [{"price": b.price, "size": b.size} for b in (book.bids or [])],
                "asks": [{"price": a.price, "size": a.size} for a in (book.asks or [])],
            }

        return await loop.run_in_executor(None, fetch_book)

    async def get_orderbooks(self, token_ids: List[str]) -> List[Dict[str, Any]]:
        """Get orderbooks for multiple tokens."""
        if not self._clob:
            raise ValueError("Client not initialized")

        await self._rate_limiter.acquire(EndpointType.CLOB_BOOKS)

        loop = asyncio.get_event_loop()

        def fetch_books():
            from py_clob_client.clob_types import BookParams
            params = [BookParams(token_id=tid) for tid in token_ids]
            books = self._clob.get_order_books(params)
            # Convert OrderBookSummary objects to dicts for compatibility
            return [
                {
                    "asset_id": book.asset_id,
                    "bids": [{"price": b.price, "size": b.size} for b in (book.bids or [])],
                    "asks": [{"price": a.price, "size": a.size} for a in (book.asks or [])],
                }
                for book in books
            ]

        return await loop.run_in_executor(None, fetch_books)

    async def get_midpoint(self, token_id: str) -> float:
        """Get midpoint price for a token."""
        if not self._clob:
            raise ValueError("Client not initialized")

        await self._rate_limiter.acquire(EndpointType.CLOB_PRICE)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._clob.get_midpoint, token_id
        )
        return float(result.get("mid", 0))

    async def get_spread(self, token_id: str) -> Dict[str, Any]:
        """Get spread for a token."""
        if not self._clob:
            raise ValueError("Client not initialized")

        await self._rate_limiter.acquire(EndpointType.CLOB_PRICE)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._clob.get_spread, token_id
        )

    # =========================================================================
    # Order Methods (require API credentials)
    # =========================================================================

    async def place_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
    ) -> Dict[str, Any]:
        """Place a limit order.

        Args:
            token_id: Outcome token ID
            side: "BUY" or "SELL"
            price: Order price (0-1)
            size: Order size in shares

        Returns:
            Order response
        """
        if not self._clob or not self.has_credentials:
            raise ValueError("API credentials required")

        await self._rate_limiter.acquire(EndpointType.CLOB_ORDER_POST)

        # Build order using official client
        loop = asyncio.get_event_loop()

        # Create order args
        from py_clob_client.order_builder.constants import BUY, SELL

        order_side = BUY if side.upper() == "BUY" else SELL

        # Build and sign order using OrderArgs dataclass
        def build_and_post():
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=order_side,
            )
            signed_order = self._clob.create_order(order_args)
            return self._clob.post_order(signed_order)

        return await loop.run_in_executor(None, build_and_post)

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order."""
        if not self._clob or not self.has_credentials:
            raise ValueError("API credentials required")

        await self._rate_limiter.acquire(EndpointType.CLOB_ORDER_DELETE)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._clob.cancel, order_id
        )

    async def cancel_all_orders(self) -> Dict[str, Any]:
        """Cancel all open orders."""
        if not self._clob or not self.has_credentials:
            raise ValueError("API credentials required")

        await self._rate_limiter.acquire(EndpointType.CLOB_CANCEL_ALL)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._clob.cancel_all
        )

    async def get_orders(self) -> List[Dict[str, Any]]:
        """Get user's open orders."""
        if not self._clob or not self.has_credentials:
            raise ValueError("API credentials required")

        await self._rate_limiter.acquire(EndpointType.CLOB_GENERAL)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._clob.get_orders
        )

    # =========================================================================
    # Gamma API Methods (market data - no auth required)
    # =========================================================================

    async def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
        closed: bool = False,
        order: str = "id",
        ascending: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get events from Gamma API."""
        await self._rate_limiter.acquire(EndpointType.GAMMA_EVENTS)

        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "closed": str(closed).lower(),
            "order": order,
            "ascending": str(ascending).lower(),
        }

        response = await self._http_client.get(
            f"{self._gamma_url}/events",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_event(self, event_id: str) -> Dict[str, Any]:
        """Get a single event by ID."""
        await self._rate_limiter.acquire(EndpointType.GAMMA_EVENTS)

        response = await self._http_client.get(f"{self._gamma_url}/events/{event_id}")
        response.raise_for_status()
        return response.json()

    async def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        closed: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get markets from Gamma API."""
        await self._rate_limiter.acquire(EndpointType.GAMMA_MARKETS)

        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "closed": str(closed).lower(),
        }

        response = await self._http_client.get(
            f"{self._gamma_url}/markets",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_market(self, market_id: str) -> Dict[str, Any]:
        """Get a single market by ID."""
        await self._rate_limiter.acquire(EndpointType.GAMMA_MARKETS)

        response = await self._http_client.get(f"{self._gamma_url}/markets/{market_id}")
        response.raise_for_status()
        return response.json()

    async def search_markets(self, query: str) -> List[Dict[str, Any]]:
        """Search markets."""
        await self._rate_limiter.acquire(EndpointType.GAMMA_SEARCH)

        response = await self._http_client.get(
            f"{self._gamma_url}/search",
            params={"query": query},
        )
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Data API Methods (user data)
    # =========================================================================

    async def get_positions(self, address: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get positions for an address."""
        await self._rate_limiter.acquire(EndpointType.DATA_POSITIONS)

        addr = address or self._address
        if not addr:
            raise ValueError("Address required")

        response = await self._http_client.get(
            f"{self._data_url}/positions",
            params={"user": addr},
        )
        response.raise_for_status()
        return response.json()

    async def get_trades(
        self,
        address: Optional[str] = None,
        market: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get trade history."""
        await self._rate_limiter.acquire(EndpointType.DATA_TRADES)

        addr = address or self._address

        params: Dict[str, Any] = {"limit": limit}
        if addr:
            params["user"] = addr
        if market:
            params["market"] = market

        response = await self._http_client.get(
            f"{self._data_url}/trades",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_leaderboard(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trader leaderboard."""
        await self._rate_limiter.acquire(EndpointType.DATA_GENERAL)

        response = await self._http_client.get(
            f"{self._data_url}/v1/leaderboard",
            params={"limit": limit},
        )
        response.raise_for_status()
        return response.json()
