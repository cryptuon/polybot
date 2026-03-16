"""Order endpoints.

All order queries are routed through the state service via IPC.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from polybot.api.schemas import (
    OrderCreate,
    OrderResponse,
    OrderListResponse,
)
from polybot.db.state_client import StateClient, get_state_client
from polybot.core.client import PolymarketClient


router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=OrderListResponse)
async def list_orders(
    status: Optional[str] = Query(None, pattern="^(PENDING|OPEN|FILLED|CANCELLED|FAILED)$"),
    strategy: Optional[str] = None,
    market_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    client: StateClient = Depends(get_state_client),
) -> OrderListResponse:
    """List orders with optional filters."""
    # Get open orders
    orders = await client.get_open_orders(strategy=strategy)

    # Apply additional filters
    if status:
        orders = [o for o in orders if o.status.value == status]

    if market_id:
        orders = [o for o in orders if o.market_id == market_id]

    # Limit results
    total = len(orders)
    orders = orders[:limit]

    return OrderListResponse(
        orders=[
            OrderResponse(
                id=o.id or "",
                market_id=o.market_id,
                token_id=o.token_id,
                side=o.side.value,
                price=o.price,
                size=o.size,
                order_type=o.order_type.value,
                status=o.status.value,
                filled_size=o.filled_size,
                average_fill_price=o.average_fill_price,
                strategy=o.strategy,
                created_at=o.created_at,
                updated_at=o.updated_at,
            )
            for o in orders
        ],
        total=total,
    )


@router.post("", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    client: StateClient = Depends(get_state_client),
) -> OrderResponse:
    """Create a new order (manual trade)."""
    from datetime import datetime
    from polybot.models.order import Order, OrderSide, OrderStatus, OrderType

    # Create order object
    new_order = Order(
        market_id=order.market_id,
        token_id=order.token_id,
        side=OrderSide(order.side),
        price=order.price,
        size=order.size,
        order_type=OrderType(order.order_type),
        status=OrderStatus.PENDING,
        strategy="manual",
    )

    # Submit order via API
    async with PolymarketClient() as client:
        try:
            result = await client.place_order(
                token_id=order.token_id,
                side=order.side,
                price=order.price,
                size=order.size,
                order_type=order.order_type,
            )

            new_order.id = result.get("orderID", "")
            new_order.order_hash = result.get("orderHash")
            new_order.status = OrderStatus.OPEN

        except Exception as e:
            new_order.status = OrderStatus.FAILED
            new_order.error_message = str(e)
            await client.save_order(new_order)
            raise HTTPException(status_code=400, detail=str(e))

    # Save to database
    await client.save_order(new_order)

    return OrderResponse(
        id=new_order.id or "",
        market_id=new_order.market_id,
        token_id=new_order.token_id,
        side=new_order.side.value,
        price=new_order.price,
        size=new_order.size,
        order_type=new_order.order_type.value,
        status=new_order.status.value,
        filled_size=new_order.filled_size,
        average_fill_price=new_order.average_fill_price,
        strategy=new_order.strategy,
        created_at=new_order.created_at,
        updated_at=new_order.updated_at,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    client: StateClient = Depends(get_state_client),
) -> OrderResponse:
    """Get a single order by ID."""
    order = await client.get_order(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderResponse(
        id=order.id or "",
        market_id=order.market_id,
        token_id=order.token_id,
        side=order.side.value,
        price=order.price,
        size=order.size,
        order_type=order.order_type.value,
        status=order.status.value,
        filled_size=order.filled_size,
        average_fill_price=order.average_fill_price,
        strategy=order.strategy,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.delete("/{order_id}")
async def cancel_order(
    order_id: str,
    client: StateClient = Depends(get_state_client),
) -> dict:
    """Cancel an order."""
    from datetime import datetime
    from polybot.models.order import OrderStatus

    order = await client.get_order(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")

    # Cancel via API
    async with PolymarketClient() as client:
        try:
            await client.cancel_order(order_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Update in database
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.utcnow()
    await client.save_order(order)

    return {"message": "Order cancelled", "order_id": order_id}


@router.delete("")
async def cancel_all_orders() -> dict:
    """Cancel all open orders."""
    async with PolymarketClient() as client:
        try:
            await client.cancel_all_orders()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    return {"message": "All orders cancelled"}
