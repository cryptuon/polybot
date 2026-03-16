"""Shadow trading endpoints.

Provides access to shadow (paper) trading performance data.
Shadow trading simulates trades without executing them, allowing
strategy evaluation before going live.

NOTE: Shadow data is stored in the executor service's in-memory tracker.
All queries are routed to the executor via IPC.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Query, Depends

from polybot.db.executor_client import ExecutorClient, get_executor_client
from polybot.db.state_client import StateClient, get_state_client
from polybot.strategies import STRATEGY_REGISTRY


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/shadow", tags=["shadow"])


async def get_shadow_mode_strategies(client: StateClient) -> List[str]:
    """Get list of strategies currently configured in shadow mode."""
    shadow_strategies = []
    for name in STRATEGY_REGISTRY.keys():
        config = await client.get_strategy_config(name)
        if config and config.get("shadow", False):
            shadow_strategies.append(name)
    return shadow_strategies


@router.get("/summary")
async def get_shadow_summary(
    state_client: StateClient = Depends(get_state_client),
    executor_client: ExecutorClient = Depends(get_executor_client),
) -> dict:
    """Get high-level summary of all shadow trading.

    Returns:
        Summary with total PnL, trade counts, win rate, and configured strategies
    """
    try:
        summary = await executor_client.get_shadow_summary()
    except Exception as e:
        logger.warning(f"Failed to get shadow summary from executor: {e}")
        summary = {
            "total_pnl": 0,
            "realized_pnl": 0,
            "unrealized_pnl": 0,
            "total_trades": 0,
            "win_rate": 0,
            "strategies_count": 0,
            "open_positions": 0,
        }

    # Add list of strategies currently in shadow mode
    shadow_strategies = await get_shadow_mode_strategies(state_client)
    summary["shadow_mode_strategies"] = shadow_strategies
    summary["strategies_in_shadow_mode"] = len(shadow_strategies)

    return summary


@router.get("/stats")
async def get_shadow_stats(
    strategy: Optional[str] = Query(None, description="Filter by strategy name"),
    executor_client: ExecutorClient = Depends(get_executor_client),
) -> dict:
    """Get detailed shadow trading statistics.

    Args:
        strategy: Filter by specific strategy, or get all

    Returns:
        Statistics including PnL, win rate, trade counts per strategy
    """
    try:
        return await executor_client.get_shadow_stats(strategy)
    except Exception as e:
        logger.warning(f"Failed to get shadow stats from executor: {e}")
        return {"strategies": {}, "totals": {}}


@router.get("/positions")
async def get_shadow_positions(
    strategy: Optional[str] = Query(None, description="Filter by strategy name"),
    executor_client: ExecutorClient = Depends(get_executor_client),
) -> dict:
    """Get open shadow positions.

    Args:
        strategy: Filter by specific strategy, or get all

    Returns:
        List of open shadow positions with unrealized PnL
    """
    try:
        positions = await executor_client.get_shadow_positions(strategy)
    except Exception as e:
        logger.warning(f"Failed to get shadow positions from executor: {e}")
        positions = []

    return {
        "positions": positions,
        "count": len(positions),
        "total_unrealized_pnl": sum(p.get("unrealized_pnl", 0) for p in positions),
    }


@router.get("/trades")
async def get_shadow_trades(
    strategy: Optional[str] = Query(None, description="Filter by strategy name"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum trades to return"),
    executor_client: ExecutorClient = Depends(get_executor_client),
) -> dict:
    """Get shadow trade history.

    Args:
        strategy: Filter by specific strategy, or get all
        limit: Maximum number of trades to return

    Returns:
        List of shadow trades with simulation details
    """
    try:
        trades = await executor_client.get_shadow_trades(strategy, limit)
    except Exception as e:
        logger.warning(f"Failed to get shadow trades from executor: {e}")
        trades = []

    return {
        "trades": trades,
        "count": len(trades),
        "total_volume": sum(t.get("notional", 0) for t in trades),
    }


@router.get("/strategies/{strategy}/stats")
async def get_strategy_shadow_stats(
    strategy: str,
    executor_client: ExecutorClient = Depends(get_executor_client),
) -> dict:
    """Get shadow stats for a specific strategy.

    Args:
        strategy: Strategy name

    Returns:
        Detailed statistics for the strategy
    """
    try:
        stats = await executor_client.get_shadow_stats(strategy)
    except Exception as e:
        logger.warning(f"Failed to get shadow stats from executor: {e}")
        stats = {}

    if not stats:
        return {
            "strategy": strategy,
            "status": "no_data",
            "message": "No shadow trading data for this strategy",
        }

    return stats


@router.get("/strategies/{strategy}/positions")
async def get_strategy_shadow_positions(
    strategy: str,
    executor_client: ExecutorClient = Depends(get_executor_client),
) -> dict:
    """Get open shadow positions for a specific strategy.

    Args:
        strategy: Strategy name

    Returns:
        List of open positions for the strategy
    """
    try:
        positions = await executor_client.get_shadow_positions(strategy)
    except Exception as e:
        logger.warning(f"Failed to get shadow positions from executor: {e}")
        positions = []

    return {
        "strategy": strategy,
        "positions": positions,
        "count": len(positions),
        "total_unrealized_pnl": sum(p.get("unrealized_pnl", 0) for p in positions),
    }


@router.get("/strategies/{strategy}/trades")
async def get_strategy_shadow_trades(
    strategy: str,
    limit: int = Query(100, ge=1, le=1000),
    executor_client: ExecutorClient = Depends(get_executor_client),
) -> dict:
    """Get shadow trade history for a specific strategy.

    Args:
        strategy: Strategy name
        limit: Maximum trades to return

    Returns:
        List of trades for the strategy
    """
    try:
        trades = await executor_client.get_shadow_trades(strategy, limit)
    except Exception as e:
        logger.warning(f"Failed to get shadow trades from executor: {e}")
        trades = []

    return {
        "strategy": strategy,
        "trades": trades,
        "count": len(trades),
        "total_volume": sum(t.get("notional", 0) for t in trades),
    }


@router.post("/reset")
async def reset_shadow_tracking(
    strategy: Optional[str] = Query(None, description="Strategy to reset, or all if not specified"),
    executor_client: ExecutorClient = Depends(get_executor_client),
) -> dict:
    """Reset shadow tracking data.

    Args:
        strategy: Reset specific strategy, or all if not specified

    Returns:
        Confirmation message
    """
    try:
        await executor_client.reset_shadow(strategy)
        return {
            "success": True,
            "message": f"Reset shadow tracking for {strategy or 'all strategies'}",
        }
    except Exception as e:
        logger.error(f"Failed to reset shadow tracking: {e}")
        return {
            "success": False,
            "message": f"Failed to reset: {e}",
        }


@router.get("/performance")
async def get_shadow_performance(
    state_client: StateClient = Depends(get_state_client),
    executor_client: ExecutorClient = Depends(get_executor_client),
) -> dict:
    """Get comprehensive shadow trading performance report.

    Returns a detailed breakdown of performance including:
    - Overall PnL summary
    - Per-strategy breakdown
    - Win/loss statistics
    - Position summary
    - Strategies configured in shadow mode
    """
    try:
        summary = await executor_client.get_shadow_summary()
        all_stats = await executor_client.get_shadow_stats()
        positions = await executor_client.get_shadow_positions()
    except Exception as e:
        logger.warning(f"Failed to get shadow performance from executor: {e}")
        summary = {"total_pnl": 0, "realized_pnl": 0, "unrealized_pnl": 0, "total_trades": 0, "win_rate": 0}
        all_stats = {"strategies": {}}
        positions = []

    # Get strategies configured in shadow mode
    shadow_strategies = await get_shadow_mode_strategies(state_client)

    # Calculate additional metrics
    strategies_data = all_stats.get("strategies", {})

    best_strategy = None
    worst_strategy = None
    best_pnl = float("-inf")
    worst_pnl = float("inf")

    for name, stats in strategies_data.items():
        total_pnl = stats.get("total_realized_pnl", 0) + stats.get("total_unrealized_pnl", 0)
        if total_pnl > best_pnl:
            best_pnl = total_pnl
            best_strategy = name
        if total_pnl < worst_pnl:
            worst_pnl = total_pnl
            worst_strategy = name

    return {
        "summary": summary,
        "strategies": strategies_data,
        "open_positions": len(positions),
        "shadow_mode_strategies": shadow_strategies,
        "strategies_in_shadow_mode": len(shadow_strategies),
        "best_performing": {
            "strategy": best_strategy,
            "pnl": round(best_pnl, 4) if best_strategy else None,
        },
        "worst_performing": {
            "strategy": worst_strategy,
            "pnl": round(worst_pnl, 4) if worst_strategy else None,
        },
    }
