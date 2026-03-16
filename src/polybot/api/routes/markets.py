"""Market endpoints.

All market queries are routed through the state service via IPC.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from polybot.api.schemas import (
    MarketResponse,
    MarketListResponse,
    OrderBookResponse,
    OrderBookLevel,
)
from polybot.db.state_client import StateClient, get_state_client
from polybot.core.client import PolymarketClient


router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("", response_model=MarketListResponse)
async def list_markets(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    active: bool = Query(True),
    search: Optional[str] = None,
    tag: Optional[str] = None,
    client: StateClient = Depends(get_state_client),
) -> MarketListResponse:
    """List markets with optional filters."""
    markets = await client.get_active_markets(limit=limit)

    # Apply search filter
    if search:
        search_lower = search.lower()
        markets = [m for m in markets if search_lower in m.question.lower()]

    # Apply tag filter
    if tag:
        markets = [m for m in markets if tag in m.tags]

    # Apply offset
    total = len(markets)
    markets = markets[offset : offset + limit]

    return MarketListResponse(
        markets=[
            MarketResponse(
                id=m.id,
                question=m.question,
                slug=m.slug,
                description=m.description,
                outcome_yes_token=m.outcome_yes_token,
                outcome_no_token=m.outcome_no_token,
                yes_price=m.yes_price,
                no_price=m.no_price,
                spread=m.spread,
                volume_24h=m.volume_24h,
                liquidity=m.liquidity,
                active=m.active,
                closed=m.closed,
                end_date=m.end_date,
                tags=m.tags,
            )
            for m in markets
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{market_id}", response_model=MarketResponse)
async def get_market(
    market_id: str,
    client: StateClient = Depends(get_state_client),
) -> MarketResponse:
    """Get a single market by ID."""
    market = await client.get_market(market_id)

    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    return MarketResponse(
        id=market.id,
        question=market.question,
        slug=market.slug,
        description=market.description,
        outcome_yes_token=market.outcome_yes_token,
        outcome_no_token=market.outcome_no_token,
        yes_price=market.yes_price,
        no_price=market.no_price,
        spread=market.spread,
        volume_24h=market.volume_24h,
        liquidity=market.liquidity,
        active=market.active,
        closed=market.closed,
        end_date=market.end_date,
        tags=market.tags,
    )


@router.get("/{market_id}/orderbook", response_model=OrderBookResponse)
async def get_orderbook(
    market_id: str,
    token: str = Query(..., description="Token ID (YES or NO)"),
    client: StateClient = Depends(get_state_client),
) -> OrderBookResponse:
    """Get orderbook for a market token."""
    from datetime import datetime

    # Verify market exists
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    # Fetch orderbook from API
    async with PolymarketClient() as client:
        try:
            book = await client.get_orderbook(token)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch orderbook: {e}")

    # IMPORTANT: CLOB API does NOT return bids/asks sorted by price!
    # Sort bids descending (highest first), asks ascending (lowest first)
    bids = sorted(
        [
            OrderBookLevel(price=float(b["price"]), size=float(b["size"]))
            for b in book.get("bids", [])
        ],
        key=lambda x: x.price,
        reverse=True,
    )
    asks = sorted(
        [
            OrderBookLevel(price=float(a["price"]), size=float(a["size"]))
            for a in book.get("asks", [])
        ],
        key=lambda x: x.price,
    )

    best_bid = bids[0].price if bids else None
    best_ask = asks[0].price if asks else None
    spread = best_ask - best_bid if best_bid and best_ask else None

    return OrderBookResponse(
        market_id=market_id,
        token_id=token,
        bids=bids,
        asks=asks,
        best_bid=best_bid,
        best_ask=best_ask,
        spread=spread,
        timestamp=datetime.utcnow(),
    )
