"""Position endpoints.

All position queries are routed through the state service via IPC.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from polybot.api.schemas import (
    PositionResponse,
    PositionListResponse,
    PositionCloseRequest,
)
from polybot.db.state_client import StateClient, get_state_client


router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=PositionListResponse)
async def list_positions(
    status: Optional[str] = Query("OPEN", pattern="^(OPEN|CLOSED|ALL)$"),
    strategy: Optional[str] = None,
    market_id: Optional[str] = None,
    client: StateClient = Depends(get_state_client),
) -> PositionListResponse:
    """List positions with optional filters."""
    positions = await client.get_open_positions(strategy=strategy)

    # Apply additional filters
    if market_id:
        positions = [p for p in positions if p.market_id == market_id]

    # Calculate totals
    total_value = sum(p.current_value or 0 for p in positions)
    total_pnl = sum(p.total_pnl or 0 for p in positions)

    return PositionListResponse(
        positions=[
            PositionResponse(
                id=p.id or 0,
                market_id=p.market_id,
                token_id=p.token_id,
                side=p.side,
                size=p.size,
                entry_price=p.entry_price,
                current_price=p.current_price,
                status=p.status.value,
                realized_pnl=p.realized_pnl,
                unrealized_pnl=p.unrealized_pnl,
                strategy=p.strategy,
                opened_at=p.opened_at,
                closed_at=p.closed_at,
            )
            for p in positions
        ],
        total=len(positions),
        total_value=total_value,
        total_pnl=total_pnl,
    )


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: int,
    client: StateClient = Depends(get_state_client),
) -> PositionResponse:
    """Get a single position by ID."""
    position = await client.get_position(position_id)

    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    return PositionResponse(
        id=position.id or 0,
        market_id=position.market_id,
        token_id=position.token_id,
        side=position.side,
        size=position.size,
        entry_price=position.entry_price,
        current_price=position.current_price,
        status=position.status.value,
        realized_pnl=position.realized_pnl,
        unrealized_pnl=position.unrealized_pnl,
        strategy=position.strategy,
        opened_at=position.opened_at,
        closed_at=position.closed_at,
    )


@router.post("/{position_id}/close")
async def close_position(
    position_id: int,
    request: PositionCloseRequest,
    client: StateClient = Depends(get_state_client),
) -> dict:
    """Close a position."""
    from polybot.core.client import PolymarketClient
    from polybot.models.order import OrderSide

    position = await client.get_position(position_id)

    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    # Create closing order
    close_side = "SELL" if position.side == "YES" else "BUY"

    async with PolymarketClient() as client:
        try:
            # Get current price if not specified
            if request.price:
                price = request.price
            else:
                price_data = await client.get_price(position.token_id, close_side)
                price = float(price_data.get("price", 0))

            # Place closing order
            result = await client.place_order(
                token_id=position.token_id,
                side=close_side,
                price=price,
                size=position.size,
            )

            return {
                "message": "Position close order placed",
                "position_id": position_id,
                "order_id": result.get("orderID"),
            }

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary")
async def get_positions_summary(
    client: StateClient = Depends(get_state_client),
) -> dict:
    """Get summary of all positions."""
    positions = await client.get_open_positions()

    total_value = sum(p.current_value or 0 for p in positions)
    total_cost = sum(p.cost_basis for p in positions)
    total_realized = sum(p.realized_pnl for p in positions)
    total_unrealized = sum(p.unrealized_pnl or 0 for p in positions)

    # Group by strategy
    by_strategy: dict = {}
    for p in positions:
        strategy = p.strategy or "unknown"
        if strategy not in by_strategy:
            by_strategy[strategy] = {"count": 0, "value": 0, "pnl": 0}
        by_strategy[strategy]["count"] += 1
        by_strategy[strategy]["value"] += p.current_value or 0
        by_strategy[strategy]["pnl"] += p.total_pnl or 0

    return {
        "total_positions": len(positions),
        "total_value": total_value,
        "total_cost_basis": total_cost,
        "total_realized_pnl": total_realized,
        "total_unrealized_pnl": total_unrealized,
        "total_pnl": total_realized + total_unrealized,
        "by_strategy": by_strategy,
    }
