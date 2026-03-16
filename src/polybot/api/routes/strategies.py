"""Strategy endpoints.

State queries are routed through the state service via IPC.
Analytics queries are routed through the analytics service via IPC.
"""

import dataclasses
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query

from polybot.api.schemas import (
    StrategyResponse,
    StrategyListResponse,
    StrategyToggleRequest,
    StrategyUpdateRequest,
    ShadowToggleRequest,
)
from polybot.db.state_client import StateClient, get_state_client
from polybot.db.analytics_client import AnalyticsClient, get_analytics_client
from polybot.db.strategy_runner_client import StrategyRunnerClient, get_strategy_runner_client
from polybot.strategies import STRATEGY_REGISTRY


router = APIRouter(prefix="/strategies", tags=["strategies"])


# Map strategy names to their config classes
STRATEGY_CONFIG_CLASSES = {}

def _init_config_classes():
    """Initialize config class mapping from strategy modules."""
    from polybot.strategies.arbitrage import ArbitrageConfig
    from polybot.strategies.stat_arb import StatArbConfig
    from polybot.strategies.ai_model import AIModelConfig
    from polybot.strategies.spread_farm import SpreadFarmConfig
    from polybot.strategies.copy_trade import CopyTradeConfig
    from polybot.strategies.resolution_arb import ResolutionArbConfig
    from polybot.strategies.calendar_spread import CalendarSpreadConfig
    from polybot.strategies.momentum import MomentumConfig
    from polybot.strategies.poll_divergence import PollDivergenceConfig
    from polybot.strategies.volume_spike import VolumeSpikeConfig

    global STRATEGY_CONFIG_CLASSES
    STRATEGY_CONFIG_CLASSES = {
        "arbitrage": ArbitrageConfig,
        "stat_arb": StatArbConfig,
        "ai_model": AIModelConfig,
        "spread_farm": SpreadFarmConfig,
        "copy_trade": CopyTradeConfig,
        "resolution_arb": ResolutionArbConfig,
        "calendar_spread": CalendarSpreadConfig,
        "momentum": MomentumConfig,
        "poll_divergence": PollDivergenceConfig,
        "volume_spike": VolumeSpikeConfig,
    }

_init_config_classes()


def get_default_config(name: str) -> Dict[str, Any]:
    """Get default configuration values for a strategy."""
    config_class = STRATEGY_CONFIG_CLASSES.get(name)
    if not config_class:
        return {}

    defaults = {}
    for field in dataclasses.fields(config_class):
        # Skip base class fields (enabled, max_position_size from StrategyConfig base)
        if field.name in ("enabled", "max_positions"):
            continue
        # Get default value
        if field.default is not dataclasses.MISSING:
            defaults[field.name] = field.default
        elif field.default_factory is not dataclasses.MISSING:
            defaults[field.name] = field.default_factory()

    return defaults


def get_strategy_info(
    name: str,
    db_config: Dict[str, Any] | None,
    runner_status: Dict[str, Any] | None = None,
) -> StrategyResponse:
    """Build strategy response from registry and config."""
    strategy_class = STRATEGY_REGISTRY.get(name)
    if not strategy_class:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {name}")

    enabled = db_config.get("enabled", False) if db_config else False
    shadow = db_config.get("shadow", False) if db_config else False
    saved_config = db_config.get("config", {}) if db_config else {}

    # Merge default config with saved config (saved values override defaults)
    default_config = get_default_config(name)
    config = {**default_config, **saved_config}

    # Get running status from strategy runner
    running = False
    positions = 0
    signals_sent = 0
    if runner_status and name in runner_status:
        status_info = runner_status[name]
        running = status_info.get("status") == "running"
        stats = status_info.get("stats", {})
        positions = len(stats.get("positions", {})) if isinstance(stats.get("positions"), dict) else stats.get("positions", 0)
        signals_sent = stats.get("signals_sent", 0)

    return StrategyResponse(
        name=name,
        description=strategy_class.description if hasattr(strategy_class, "description") else "",
        enabled=enabled,
        shadow=shadow,
        running=running,
        positions=positions,
        signals_sent=signals_sent,
        config=config,
    )


@router.get("", response_model=StrategyListResponse)
async def list_strategies(
    client: StateClient = Depends(get_state_client),
    runner_client: StrategyRunnerClient = Depends(get_strategy_runner_client),
) -> StrategyListResponse:
    """List all available strategies."""
    strategies = []

    # Get running status from strategy runner
    try:
        runner_status = await runner_client.get_status()
    except Exception:
        runner_status = None

    for name in STRATEGY_REGISTRY.keys():
        db_config = await client.get_strategy_config(name)
        strategies.append(get_strategy_info(name, db_config, runner_status))

    return StrategyListResponse(strategies=strategies)


@router.get("/{name}", response_model=StrategyResponse)
async def get_strategy(
    name: str,
    client: StateClient = Depends(get_state_client),
    runner_client: StrategyRunnerClient = Depends(get_strategy_runner_client),
) -> StrategyResponse:
    """Get a single strategy by name."""
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Get running status from strategy runner
    try:
        runner_status = await runner_client.get_status()
    except Exception:
        runner_status = None

    db_config = await client.get_strategy_config(name)
    return get_strategy_info(name, db_config, runner_status)


@router.post("/{name}/toggle", response_model=StrategyResponse)
async def toggle_strategy(
    name: str,
    request: StrategyToggleRequest,
    client: StateClient = Depends(get_state_client),
) -> StrategyResponse:
    """Enable or disable a strategy."""
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Get current config
    db_config = await client.get_strategy_config(name)
    config = db_config.get("config", {}) if db_config else {}
    shadow = db_config.get("shadow", False) if db_config else False

    # Update enabled status
    await client.save_strategy_config(name, request.enabled, config, shadow)

    # Return updated strategy info
    new_config = await client.get_strategy_config(name)
    return get_strategy_info(name, new_config)


@router.post("/{name}/shadow", response_model=StrategyResponse)
async def toggle_shadow_mode(
    name: str,
    request: ShadowToggleRequest,
    client: StateClient = Depends(get_state_client),
) -> StrategyResponse:
    """Toggle shadow mode for a strategy.

    Shadow mode: Strategy generates signals but they are logged without execution.
    Useful for paper trading and testing strategies before going live.
    """
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Get current config
    db_config = await client.get_strategy_config(name)
    enabled = db_config.get("enabled", False) if db_config else False
    config = db_config.get("config", {}) if db_config else {}

    # Update shadow mode
    await client.save_strategy_config(name, enabled, config, request.shadow)

    # Return updated strategy info
    new_config = await client.get_strategy_config(name)
    return get_strategy_info(name, new_config)


@router.put("/{name}", response_model=StrategyResponse)
async def update_strategy(
    name: str,
    request: StrategyUpdateRequest,
    client: StateClient = Depends(get_state_client),
) -> StrategyResponse:
    """Update strategy configuration."""
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Get current config
    db_config = await client.get_strategy_config(name)
    enabled = db_config.get("enabled", False) if db_config else False
    shadow = db_config.get("shadow", False) if db_config else False

    # Update config (preserve enabled and shadow)
    await client.save_strategy_config(name, enabled, request.config, shadow)

    # Return updated strategy info
    new_config = await client.get_strategy_config(name)
    return get_strategy_info(name, new_config)


# =============================================================================
# Strategy Runtime Control Endpoints
# =============================================================================


@router.get("/runner/status")
async def get_runner_status(
    runner: StrategyRunnerClient = Depends(get_strategy_runner_client),
) -> dict:
    """Get runtime status of all strategies.

    Returns the running state, enabled status, and any errors for each strategy.
    """
    try:
        status = await runner.get_status()
        return {"success": True, "strategies": status}
    except Exception as e:
        return {"success": False, "error": str(e), "strategies": {}}


@router.post("/{name}/start")
async def start_strategy(
    name: str,
    runner: StrategyRunnerClient = Depends(get_strategy_runner_client),
) -> dict:
    """Start a strategy.

    The strategy must be enabled in config to start successfully.
    """
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(status_code=404, detail="Strategy not found")

    try:
        await runner.start_strategy(name)
        return {"success": True, "message": f"Strategy {name} started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/stop")
async def stop_strategy(
    name: str,
    runner: StrategyRunnerClient = Depends(get_strategy_runner_client),
) -> dict:
    """Stop a running strategy."""
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(status_code=404, detail="Strategy not found")

    try:
        await runner.stop_strategy(name)
        return {"success": True, "message": f"Strategy {name} stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/restart")
async def restart_strategy(
    name: str,
    runner: StrategyRunnerClient = Depends(get_strategy_runner_client),
) -> dict:
    """Restart a strategy."""
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(status_code=404, detail="Strategy not found")

    try:
        await runner.restart_strategy(name)
        return {"success": True, "message": f"Strategy {name} restarted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runner/start-all")
async def start_all_strategies(
    runner: StrategyRunnerClient = Depends(get_strategy_runner_client),
) -> dict:
    """Start all enabled strategies."""
    try:
        await runner.start_all()
        return {"success": True, "message": "All enabled strategies started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runner/stop-all")
async def stop_all_strategies(
    runner: StrategyRunnerClient = Depends(get_strategy_runner_client),
) -> dict:
    """Stop all running strategies."""
    try:
        await runner.stop_all()
        return {"success": True, "message": "All strategies stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Statistical Arbitrage Specific Endpoints
# =============================================================================


@router.get("/stat_arb/correlations")
async def get_correlations(
    min_correlation: float = Query(0.5, ge=0, le=1),
    limit: int = Query(50, ge=1, le=200),
    analytics: AnalyticsClient = Depends(get_analytics_client),
    state: StateClient = Depends(get_state_client),
) -> dict:
    """Get all computed market correlations.

    Returns pairs of markets with their correlation coefficients.
    Higher absolute correlation indicates markets that move together.
    """
    # Get all markets for name lookup
    markets = await state.get_active_markets(limit=200)
    market_names = {m.id: m.question[:60] for m in markets}

    # Query all correlations via analytics service
    raw_correlations = await analytics.get_all_correlations(
        min_correlation=min_correlation,
        limit=limit,
    )

    correlations = []
    for corr in raw_correlations:
        correlations.append({
            "market_a": {
                "id": corr["market_a"],
                "question": market_names.get(corr["market_a"], "Unknown"),
            },
            "market_b": {
                "id": corr["market_b"],
                "question": market_names.get(corr["market_b"], "Unknown"),
            },
            "correlation": corr["correlation"],
            "lookback_hours": corr["lookback_hours"],
            "calculated_at": corr["calculated_at"],
        })

    return {
        "total": len(correlations),
        "min_correlation": min_correlation,
        "correlations": correlations,
    }


@router.get("/stat_arb/pairs/{market_id}")
async def get_correlated_pairs(
    market_id: str,
    min_correlation: float = Query(0.7, ge=0, le=1),
    analytics: AnalyticsClient = Depends(get_analytics_client),
    state: StateClient = Depends(get_state_client),
) -> dict:
    """Get markets correlated with a specific market.

    Useful for understanding which markets move together
    and potential stat arb opportunities.
    """
    # Get market info
    market = await state.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    # Get correlated markets via analytics service
    correlations = await analytics.get_correlated_markets(
        market_id=market_id,
        min_correlation=min_correlation,
    )

    # Enrich with market names
    enriched = []
    for corr in correlations:
        other_market = await state.get_market(corr["market_id"])
        enriched.append({
            "market_id": corr["market_id"],
            "question": other_market.question if other_market else "Unknown",
            "correlation": corr["correlation"],
            "calculated_at": corr["calculated_at"],
        })

    return {
        "market": {
            "id": market_id,
            "question": market.question,
        },
        "correlated_markets": enriched,
    }


@router.get("/stat_arb/opportunities")
async def get_stat_arb_opportunities(
    spread_threshold: float = Query(0.04, ge=0.01, le=0.20),
    min_correlation: float = Query(0.7, ge=0.5, le=1),
    analytics: AnalyticsClient = Depends(get_analytics_client),
    state: StateClient = Depends(get_state_client),
) -> dict:
    """Find current statistical arbitrage opportunities.

    Scans correlated pairs for those where the spread exceeds the threshold,
    indicating a potential mean reversion opportunity.

    Note: This is a snapshot view. The actual strategy runs continuously.
    """
    # Get all correlations above threshold via analytics service
    raw_correlations = await analytics.get_all_correlations(
        min_correlation=min_correlation,
        limit=200,
    )

    opportunities = []

    for corr in raw_correlations:
        market_a_id = corr["market_a"]
        market_b_id = corr["market_b"]
        correlation = corr["correlation"]

        # Get market info
        market_a = await state.get_market(market_a_id)
        market_b = await state.get_market(market_b_id)

        if not market_a or not market_b:
            continue

        # Check if we have prices (from market cache)
        price_a = market_a.yes_price
        price_b = market_b.yes_price

        if price_a is None or price_b is None:
            continue

        spread = abs(price_a - price_b)

        if spread >= spread_threshold:
            # Determine long/short
            if price_a > price_b:
                long_market = market_b
                short_market = market_a
            else:
                long_market = market_a
                short_market = market_b

            opportunities.append({
                "spread": spread,
                "spread_pct": f"{spread*100:.2f}%",
                "correlation": correlation,
                "long_market": {
                    "id": long_market.id,
                    "question": long_market.question[:80],
                    "price": long_market.yes_price,
                },
                "short_market": {
                    "id": short_market.id,
                    "question": short_market.question[:80],
                    "price": short_market.yes_price,
                },
            })

    # Sort by spread descending
    opportunities.sort(key=lambda x: x["spread"], reverse=True)

    return {
        "threshold": spread_threshold,
        "min_correlation": min_correlation,
        "opportunities_found": len(opportunities),
        "opportunities": opportunities[:20],  # Top 20
    }


@router.get("/stat_arb/price_history")
async def get_pair_price_history(
    market_a: str = Query(..., description="First market ID"),
    market_b: str = Query(..., description="Second market ID"),
    hours: int = Query(24, ge=1, le=168),
    analytics: AnalyticsClient = Depends(get_analytics_client),
    state: StateClient = Depends(get_state_client),
) -> dict:
    """Get price history for a pair of markets.

    Useful for visualizing correlation and spread over time.
    """
    # Get market info
    market_a_info = await state.get_market(market_a)
    market_b_info = await state.get_market(market_b)

    if not market_a_info or not market_b_info:
        raise HTTPException(status_code=404, detail="One or both markets not found")

    # Get price history for both via analytics service
    history_a = await analytics.get_market_price_history(
        market_id=market_a,
        token_id=market_a_info.outcome_yes_token,
        hours=hours,
    )

    history_b = await analytics.get_market_price_history(
        market_id=market_b,
        token_id=market_b_info.outcome_yes_token,
        hours=hours,
    )

    # Get correlation
    correlations = await analytics.get_correlated_markets(market_a, min_correlation=0)
    correlation = next(
        (c["correlation"] for c in correlations if c["market_id"] == market_b),
        None
    )

    return {
        "market_a": {
            "id": market_a,
            "question": market_a_info.question,
            "price_history": history_a,
        },
        "market_b": {
            "id": market_b,
            "question": market_b_info.question,
            "price_history": history_b,
        },
        "correlation": correlation,
        "hours": hours,
    }


# =============================================================================
# AI Model Strategy Endpoints
# =============================================================================


@router.get("/ai_model/plugins")
async def list_ai_plugins() -> dict:
    """List all available AI model plugins.

    Returns information about each registered plugin.
    """
    from polybot.plugins.example_plugin import get_all_plugins

    plugins = get_all_plugins()

    plugin_list = []
    for name, plugin_class in plugins.items():
        instance = plugin_class()
        plugin_list.append({
            "name": name,
            "version": instance.version,
            "description": instance.description,
            "supports_batch": instance.supports_batch,
        })

    return {
        "total": len(plugin_list),
        "plugins": plugin_list,
    }


@router.get("/ai_model/plugin/{name}")
async def get_ai_plugin_info(name: str) -> dict:
    """Get detailed information about a specific plugin.

    Args:
        name: Plugin name
    """
    from polybot.plugins.example_plugin import get_all_plugins

    plugins = get_all_plugins()

    if name not in plugins:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {name}")

    plugin_class = plugins[name]
    instance = plugin_class()

    return instance.get_info()


@router.post("/ai_model/predict/{market_id}")
async def get_ai_prediction(
    market_id: str,
    plugin_name: str = Query("simple_heuristic", description="Plugin to use"),
    plugin_config: str = Query("{}", description="Plugin config JSON"),
    state: StateClient = Depends(get_state_client),
) -> dict:
    """Get AI prediction for a specific market.

    This is a test endpoint to get predictions without trading.

    Args:
        market_id: Market ID to predict
        plugin_name: Name of plugin to use
        plugin_config: JSON config for the plugin
    """
    import json
    from datetime import datetime
    from polybot.plugins.example_plugin import get_all_plugins
    from polybot.plugins.base import MarketContext

    # Get market info
    market = await state.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    # Load plugin
    plugins = get_all_plugins()
    if plugin_name not in plugins:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")

    try:
        config = json.loads(plugin_config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid plugin config JSON")

    plugin = plugins[plugin_name]()

    try:
        await plugin.initialize(config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Plugin initialization failed: {e}")

    # Build context
    context = MarketContext(
        market_id=market.id,
        question=market.question,
        description=market.description,
        current_yes_price=market.yes_price or 0.5,
        current_no_price=1 - (market.yes_price or 0.5),
        spread=0.02,  # Default spread
        volume_24h=market.volume_24h,
        liquidity=market.liquidity,
        end_date=market.end_date.isoformat() if market.end_date else None,
        hours_remaining=(
            (market.end_date - datetime.utcnow()).total_seconds() / 3600
            if market.end_date
            else None
        ),
        tags=market.tags,
    )

    # Get prediction
    try:
        prediction = await plugin.predict(context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")
    finally:
        await plugin.shutdown()

    # Calculate edge
    market_price = market.yes_price or 0.5
    edge = prediction.yes_probability - market_price

    return {
        "market": {
            "id": market.id,
            "question": market.question[:100],
            "current_price": market_price,
        },
        "prediction": {
            "yes_probability": prediction.yes_probability,
            "no_probability": prediction.no_probability,
            "confidence": prediction.confidence,
            "reasoning": prediction.reasoning,
            "model_version": prediction.model_version,
            "features_used": prediction.features_used,
        },
        "edge": edge,
        "edge_pct": f"{edge*100:.2f}%",
        "recommendation": (
            "BUY YES" if edge > 0.05
            else "BUY NO" if edge < -0.05
            else "HOLD"
        ),
        "plugin": plugin_name,
    }


@router.post("/ai_model/batch_predict")
async def batch_ai_predict(
    market_ids: List[str],
    plugin_name: str = Query("simple_heuristic"),
    plugin_config: str = Query("{}"),
    state: StateClient = Depends(get_state_client),
) -> dict:
    """Get AI predictions for multiple markets.

    Useful for scanning opportunities across many markets at once.

    Args:
        market_ids: List of market IDs to predict
        plugin_name: Plugin to use
        plugin_config: Plugin config JSON
    """
    import json
    from datetime import datetime
    from polybot.plugins.example_plugin import get_all_plugins
    from polybot.plugins.base import MarketContext

    plugins = get_all_plugins()
    if plugin_name not in plugins:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")

    try:
        config = json.loads(plugin_config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid plugin config JSON")

    plugin = plugins[plugin_name]()
    await plugin.initialize(config)

    predictions = []
    errors = []

    for market_id in market_ids[:20]:  # Limit to 20 markets
        market = await state.get_market(market_id)
        if not market:
            errors.append({"market_id": market_id, "error": "Not found"})
            continue

        context = MarketContext(
            market_id=market.id,
            question=market.question,
            description=market.description,
            current_yes_price=market.yes_price or 0.5,
            current_no_price=1 - (market.yes_price or 0.5),
            spread=0.02,
            volume_24h=market.volume_24h,
            liquidity=market.liquidity,
            end_date=market.end_date.isoformat() if market.end_date else None,
            hours_remaining=(
                (market.end_date - datetime.utcnow()).total_seconds() / 3600
                if market.end_date
                else None
            ),
            tags=market.tags,
        )

        try:
            pred = await plugin.predict(context)
            market_price = market.yes_price or 0.5
            edge = pred.yes_probability - market_price

            predictions.append({
                "market_id": market.id,
                "question": market.question[:80],
                "market_price": market_price,
                "predicted_prob": pred.yes_probability,
                "confidence": pred.confidence,
                "edge": edge,
                "edge_pct": f"{edge*100:.2f}%",
            })
        except Exception as e:
            errors.append({"market_id": market_id, "error": str(e)})

    await plugin.shutdown()

    # Sort by absolute edge
    predictions.sort(key=lambda x: abs(x["edge"]), reverse=True)

    return {
        "plugin": plugin_name,
        "total_predicted": len(predictions),
        "total_errors": len(errors),
        "predictions": predictions,
        "errors": errors if errors else None,
    }
