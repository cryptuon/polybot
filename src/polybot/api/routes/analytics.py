"""Analytics endpoints.

All analytics queries are routed through the analytics service via IPC.
This avoids direct database access and DuckDB locking issues.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from polybot.api.schemas import (
    PerformanceSummary,
    DailyStatsResponse,
    AnalyticsHistoryResponse,
    PriceHistoryResponse,
    PriceCandle,
)
from polybot.db.analytics_client import AnalyticsClient, get_analytics_client


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=PerformanceSummary)
async def get_performance_summary(
    strategy: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    client: AnalyticsClient = Depends(get_analytics_client),
) -> PerformanceSummary:
    """Get performance summary."""
    summary = await client.get_performance_summary(strategy=strategy, days=days)

    return PerformanceSummary(
        total_trades=summary.get("total_trades", 0),
        total_wins=summary.get("total_wins", 0),
        total_losses=summary.get("total_losses", 0),
        win_rate=summary.get("win_rate", 0),
        total_pnl=summary.get("total_pnl", 0),
        total_volume=summary.get("total_volume", 0),
        total_fees=summary.get("total_fees", 0),
        avg_daily_pnl=summary.get("avg_daily_pnl", 0),
        best_day=summary.get("best_day", 0),
        worst_day=summary.get("worst_day", 0),
    )


@router.get("/history", response_model=AnalyticsHistoryResponse)
async def get_analytics_history(
    strategy: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    client: AnalyticsClient = Depends(get_analytics_client),
) -> AnalyticsHistoryResponse:
    """Get daily analytics history."""
    daily_stats = await client.get_daily_stats(strategy=strategy, days=days)
    summary = await client.get_performance_summary(strategy=strategy, days=days)

    return AnalyticsHistoryResponse(
        days=[
            DailyStatsResponse(
                date=datetime.fromisoformat(s["date"]) if isinstance(s["date"], str) else s["date"],
                strategy=s.get("strategy"),
                trades=s.get("trades", 0),
                wins=s.get("wins", 0),
                losses=s.get("losses", 0),
                pnl=s.get("pnl", 0),
                volume=s.get("volume", 0),
                fees=s.get("fees", 0),
            )
            for s in daily_stats
        ],
        summary=PerformanceSummary(
            total_trades=summary.get("total_trades", 0),
            total_wins=summary.get("total_wins", 0),
            total_losses=summary.get("total_losses", 0),
            win_rate=summary.get("win_rate", 0),
            total_pnl=summary.get("total_pnl", 0),
            total_volume=summary.get("total_volume", 0),
            total_fees=summary.get("total_fees", 0),
            avg_daily_pnl=summary.get("avg_daily_pnl", 0),
            best_day=summary.get("best_day", 0),
            worst_day=summary.get("worst_day", 0),
        ),
    )


@router.get("/prices/{market_id}", response_model=PriceHistoryResponse)
async def get_price_history(
    market_id: str,
    interval: str = Query("1h", pattern="^(1m|5m|15m|1h|4h|1d)$"),
    limit: int = Query(100, ge=1, le=1000),
    client: AnalyticsClient = Depends(get_analytics_client),
) -> PriceHistoryResponse:
    """Get OHLCV price history for a market."""
    candles = await client.get_price_history(
        market_id=market_id,
        interval=interval,
        limit=limit,
    )

    return PriceHistoryResponse(
        market_id=market_id,
        interval=interval,
        candles=[
            PriceCandle(
                time=c["time"],
                open=c.get("open") or 0,
                high=c.get("high") or 0,
                low=c.get("low") or 0,
                close=c.get("close") or 0,
                volume=c.get("volume"),
            )
            for c in candles
        ],
    )


@router.get("/strategies")
async def get_strategy_analytics(
    days: int = Query(30, ge=1, le=365),
    client: AnalyticsClient = Depends(get_analytics_client),
) -> dict:
    """Get analytics broken down by strategy."""
    from polybot.strategies import STRATEGY_REGISTRY

    results = {}

    for strategy_name in STRATEGY_REGISTRY.keys():
        summary = await client.get_performance_summary(strategy=strategy_name, days=days)
        daily = await client.get_daily_stats(strategy=strategy_name, days=days)

        results[strategy_name] = {
            "summary": {
                "total_trades": summary.get("total_trades", 0),
                "win_rate": summary.get("win_rate", 0),
                "total_pnl": summary.get("total_pnl", 0),
                "total_volume": summary.get("total_volume", 0),
            },
            "recent_days": len(daily) if daily else 0,
        }

    return results


@router.get("/correlations/{market_id}")
async def get_market_correlations(
    market_id: str,
    min_correlation: float = Query(0.7, ge=0, le=1),
    client: AnalyticsClient = Depends(get_analytics_client),
) -> dict:
    """Get markets correlated with the given market."""
    correlations = await client.get_correlated_markets(
        market_id=market_id,
        min_correlation=min_correlation,
    )

    return {
        "market_id": market_id,
        "correlations": correlations,
    }


@router.get("/trades")
async def get_trade_stats(
    strategy: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    client: AnalyticsClient = Depends(get_analytics_client),
) -> dict:
    """Get trade statistics."""
    stats = await client.get_trade_stats(
        strategy=strategy,
        start_time=start_date,
        end_time=end_date,
    )

    return stats
