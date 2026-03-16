"""Market scanner service.

Responsible for:
- Fetching and caching active markets
- Polling prices at regular intervals
- Publishing price updates via NNG
- Managing WebSocket connections for real-time data
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from polybot.config import Settings
from polybot.core.client import PolymarketClient
from polybot.core.nng import NNGPublisher
from polybot.core.websocket import WebSocketManager, EventType as WSEventType
from polybot.db.state_client import StateClient, get_state_client
from polybot.models.market import Market, MarketSnapshot
from polybot.models.messages import PriceUpdate, BookUpdate
from polybot.services.base import BaseService


logger = logging.getLogger(__name__)


class ScannerService(BaseService):
    """Market scanner service.

    Scans markets, tracks prices, and publishes updates to strategies.
    """

    name = "scanner"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._client: Optional[PolymarketClient] = None
        self._ws_manager: Optional[WebSocketManager] = None
        self._price_publisher: Optional[NNGPublisher] = None

        self._state_client: Optional[StateClient] = None

        # Tracked markets
        self._markets: Dict[str, Market] = {}
        self._token_to_market: Dict[str, str] = {}  # token_id -> market_id

        # Price cache
        self._prices: Dict[str, Dict[str, float]] = {}  # token_id -> {bid, ask, mid}

    async def _on_start(self) -> None:
        """Initialize scanner resources."""
        # Initialize API client
        self._client = PolymarketClient()

        # Initialize state client (queries state service via NNG)
        self._state_client = await get_state_client()

        # Initialize price publisher
        self._price_publisher = NNGPublisher(self._settings.nng.prices_address)
        await self._price_publisher.open()

        # Initialize WebSocket manager
        self._ws_manager = WebSocketManager()

        # Register WebSocket handlers
        self._ws_manager.on_event(WSEventType.BOOK, self._handle_book_update)
        self._ws_manager.on_event(WSEventType.PRICE_CHANGE, self._handle_price_change)
        self._ws_manager.on_event(WSEventType.LAST_TRADE_PRICE, self._handle_trade)

        # Load initial markets
        await self._load_markets()

    async def _on_stop(self) -> None:
        """Cleanup scanner resources."""
        if self._ws_manager:
            await self._ws_manager.stop()

        if self._price_publisher:
            await self._price_publisher.close()

        if self._client:
            await self._client.close()

    async def _run(self) -> None:
        """Main scanner loop."""
        # Start WebSocket for real-time updates
        if self._ws_manager and self._token_to_market:
            token_ids = list(self._token_to_market.keys())
            await self._ws_manager.subscribe_market(token_ids)
            await self._ws_manager.start()

        # Start polling loop for markets without WebSocket coverage
        poll_task = self.create_task(self._poll_loop())

        # Start market refresh loop
        refresh_task = self.create_task(self._refresh_markets_loop())

        # Start price snapshot loop
        snapshot_task = self.create_task(self._snapshot_loop())

        # Wait for tasks
        await asyncio.gather(poll_task, refresh_task, snapshot_task, return_exceptions=True)

    async def _load_markets(self) -> None:
        """Load active markets from Gamma API.

        Only loads markets with sufficient liquidity to avoid overwhelming
        the API with requests for inactive markets.
        """
        if not self._client or not self._state_client:
            return

        self._logger.info("Loading active markets...")

        # Minimum liquidity to track a market (in USD)
        min_liquidity = 1000.0
        max_markets = 500  # Limit total markets to track

        try:
            # Fetch active markets directly from /markets endpoint
            market_count = 0
            skipped_low_liquidity = 0
            skipped_not_accepting = 0
            skipped_parse_failed = 0
            offset = 0
            limit = 100

            while market_count < max_markets:
                markets_data = await self._client.get_markets(
                    limit=limit, offset=offset, closed=False
                )

                if not markets_data:
                    break

                self._logger.debug(f"Fetched {len(markets_data)} markets (offset={offset})")

                for market_data in markets_data:
                    # Filter by liquidity
                    liquidity = float(market_data.get("liquidityNum", 0) or 0)
                    if liquidity < min_liquidity:
                        skipped_low_liquidity += 1
                        continue

                    # Must be accepting orders
                    if not market_data.get("acceptingOrders", False):
                        skipped_not_accepting += 1
                        continue

                    market = self._parse_market(market_data)
                    if market:
                        self._markets[market.id] = market
                        self._token_to_market[market.outcome_yes_token] = market.id
                        self._token_to_market[market.outcome_no_token] = market.id

                        # Save to database via state service
                        await self._state_client.save_market(market)
                        market_count += 1

                        if market_count >= max_markets:
                            break
                    else:
                        skipped_parse_failed += 1

                if len(markets_data) < limit:
                    break
                offset += limit

            self._logger.info(
                f"Loaded {market_count} markets | "
                f"Skipped: {skipped_low_liquidity} low liquidity, "
                f"{skipped_not_accepting} not accepting orders, "
                f"{skipped_parse_failed} parse failed"
            )

        except Exception as e:
            self._logger.error(f"Failed to load markets: {e}")

    def _parse_market(self, data: Dict[str, Any]) -> Optional[Market]:
        """Parse market data from API response."""
        try:
            # Get token IDs from clobTokenIds - it's a JSON string like '["id1", "id2"]'
            clob_token_ids_raw = data.get("clobTokenIds", "[]")
            try:
                clob_token_ids = json.loads(clob_token_ids_raw) if isinstance(clob_token_ids_raw, str) else clob_token_ids_raw
            except json.JSONDecodeError:
                return None

            if not clob_token_ids or len(clob_token_ids) < 2:
                return None

            yes_token_id = clob_token_ids[0]
            no_token_id = clob_token_ids[1]

            # Parse prices from outcomePrices JSON string (e.g., '["0.55", "0.45"]')
            outcome_prices = data.get("outcomePrices", "")
            yes_price = None
            no_price = None
            if outcome_prices:
                try:
                    prices = json.loads(outcome_prices)
                    if len(prices) >= 2:
                        yes_price = float(prices[0])
                        no_price = float(prices[1])
                except (ValueError, json.JSONDecodeError):
                    pass

            return Market(
                id=data.get("conditionId", data.get("id", "")),
                question=data.get("question", ""),
                slug=data.get("slug"),
                description=data.get("description"),
                outcome_yes_token=yes_token_id,
                outcome_no_token=no_token_id,
                yes_price=yes_price,
                no_price=no_price,
                volume=float(data.get("volumeNum", 0)) if data.get("volumeNum") else None,
                volume_24h=float(data.get("volume24hr", 0)) if data.get("volume24hr") else None,
                liquidity=float(data.get("liquidityNum", 0)) if data.get("liquidityNum") else None,
                active=data.get("active", True),
                closed=data.get("closed", False),
                end_date=datetime.fromisoformat(data["endDateIso"].replace("Z", "+00:00"))
                if data.get("endDateIso")
                else None,
            )
        except Exception as e:
            self._logger.warning(f"Failed to parse market: {e}")
            return None

    async def _poll_loop(self) -> None:
        """Poll prices at regular intervals.

        Note: This is a fallback for markets not covered by WebSocket.
        The WebSocket provides real-time updates for subscribed markets.
        """
        poll_interval = 30.0  # seconds - less aggressive since WebSocket handles real-time
        poll_count = 0

        while self._running:
            try:
                poll_count += 1
                self._logger.info(f"Starting price poll #{poll_count}")
                await self._poll_prices()
                self._logger.info(f"Next poll in {poll_interval}s")
                await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Poll error: {e}")
                await asyncio.sleep(30)

    async def _poll_prices(self) -> None:
        """Poll current prices for all tracked markets."""
        if not self._client:
            return

        # Get all YES token IDs
        token_ids = [m.outcome_yes_token for m in self._markets.values()]

        if not token_ids:
            self._logger.debug("No token IDs to poll")
            return

        total_tokens = len(token_ids)
        chunk_size = 20  # Smaller chunks
        delay_between_chunks = 0.5  # 500ms between API calls
        total_chunks = (total_tokens + chunk_size - 1) // chunk_size

        self._logger.info(f"Polling prices for {total_tokens} tokens in {total_chunks} chunks")

        books_fetched = 0
        prices_updated = 0

        for i in range(0, total_tokens, chunk_size):
            if not self._running:
                break

            chunk_num = i // chunk_size + 1
            chunk = token_ids[i : i + chunk_size]

            try:
                # Get orderbook data for price info
                books = await self._client.get_orderbooks(chunk)
                books_fetched += len(books)

                for book in books:
                    updated = await self._process_book(book)
                    if updated:
                        prices_updated += 1

                self._logger.debug(f"Chunk {chunk_num}/{total_chunks}: fetched {len(books)} books")

                # Rate limit between chunks
                await asyncio.sleep(delay_between_chunks)

            except Exception as e:
                self._logger.error(f"Price fetch error (chunk {chunk_num}): {e}")

        self._logger.info(f"Poll complete: {books_fetched} books fetched, {prices_updated} prices updated")

    async def _process_book(self, book: Dict[str, Any]) -> bool:
        """Process orderbook data and publish price update.

        Returns:
            True if price was updated, False otherwise.
        """
        token_id = book.get("asset_id", "")
        market_id = self._token_to_market.get(token_id)

        if not market_id:
            return False

        bids = book.get("bids", [])
        asks = book.get("asks", [])

        if not bids and not asks:
            return False

        # IMPORTANT: CLOB API does NOT return bids/asks sorted by price!
        # We must find the actual best bid (highest) and best ask (lowest)
        best_bid = max((float(b["price"]) for b in bids), default=0) if bids else 0
        best_ask = min((float(a["price"]) for a in asks), default=1) if asks else 1
        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        # Update cache
        self._prices[token_id] = {
            "bid": best_bid,
            "ask": best_ask,
            "mid": mid,
        }

        # Publish price update
        if self._price_publisher:
            update = PriceUpdate(
                market_id=market_id,
                token_id=token_id,
                bid=best_bid,
                ask=best_ask,
                mid=mid,
                spread=spread,
            )
            await self._price_publisher.publish(update.to_dict())

        return True

    def _handle_book_update(self, data: Dict[str, Any]) -> None:
        """Handle WebSocket book update."""
        asyncio.create_task(self._process_ws_book(data))

    async def _process_ws_book(self, data: Dict[str, Any]) -> None:
        """Process WebSocket book update."""
        token_id = data.get("asset_id", "")
        market_id = self._token_to_market.get(token_id)

        if not market_id:
            return

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        # IMPORTANT: CLOB API does NOT return bids/asks sorted by price!
        # We must find the actual best bid (highest) and best ask (lowest)
        best_bid = max((float(b["price"]) for b in bids), default=0) if bids else 0
        best_ask = min((float(a["price"]) for a in asks), default=1) if asks else 1
        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        self._prices[token_id] = {"bid": best_bid, "ask": best_ask, "mid": mid}

        if self._price_publisher:
            update = PriceUpdate(
                market_id=market_id,
                token_id=token_id,
                bid=best_bid,
                ask=best_ask,
                mid=mid,
                spread=spread,
            )
            await self._price_publisher.publish(update.to_dict())

    def _handle_price_change(self, data: Dict[str, Any]) -> None:
        """Handle WebSocket price change."""
        # Price changes are incremental - handled in book updates
        pass

    def _handle_trade(self, data: Dict[str, Any]) -> None:
        """Handle WebSocket trade event."""
        # Log trade for analytics
        self._logger.debug(f"Trade: {data}")

    async def _refresh_markets_loop(self) -> None:
        """Periodically refresh market list."""
        refresh_interval = 300  # 5 minutes

        while self._running:
            try:
                await asyncio.sleep(refresh_interval)
                await self._load_markets()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Market refresh error: {e}")

    async def _snapshot_loop(self) -> None:
        """Store price snapshots for analytics."""
        snapshot_interval = 60  # 1 minute

        while self._running:
            try:
                await asyncio.sleep(snapshot_interval)
                await self._store_snapshots()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Snapshot error: {e}")

    async def _store_snapshots(self) -> None:
        """Publish current prices as snapshots for analytics to store."""
        now = datetime.utcnow()

        snapshots = []
        for token_id, prices in self._prices.items():
            market_id = self._token_to_market.get(token_id)
            if market_id:
                snapshots.append({
                    "market_id": market_id,
                    "token_id": token_id,
                    "timestamp": now.isoformat(),
                    "bid": prices["bid"],
                    "ask": prices["ask"],
                    "mid": prices["mid"],
                    "spread": prices["ask"] - prices["bid"],
                })

        if snapshots and self._event_publisher:
            await self._event_publisher.publish({
                "event_type": "price_snapshots",
                "data": {"snapshots": snapshots},
            })

    # =========================================================================
    # Public API
    # =========================================================================

    def get_market(self, market_id: str) -> Optional[Market]:
        """Get a market by ID."""
        return self._markets.get(market_id)

    def get_price(self, token_id: str) -> Optional[Dict[str, float]]:
        """Get current price for a token."""
        return self._prices.get(token_id)

    def get_all_prices(self) -> Dict[str, Dict[str, float]]:
        """Get all current prices."""
        return self._prices.copy()
