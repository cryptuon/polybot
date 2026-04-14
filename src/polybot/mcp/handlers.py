"""Tool handlers for MCP server.

Implements the actual logic for each MCP tool.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from polybot.config import get_settings
from polybot.strategies import STRATEGY_REGISTRY
from polybot.mcp.approval import submit_for_approval, ApprovalStatus

logger = logging.getLogger(__name__)


# =============================================================================
# Read-Only Tool Handlers
# =============================================================================


async def handle_readonly_tool(name: str, arguments: dict[str, Any]) -> str:
    """Handle read-only tool calls."""
    from polybot.db.sqlite_store import SQLiteStore
    from polybot.db.duckdb_store import get_duckdb_store

    if name == "list_markets":
        limit = arguments.get("limit", 50)
        active_only = arguments.get("active_only", True)
        tags = arguments.get("tags", [])

        store = SQLiteStore()
        await store.connect()
        try:
            markets = await store.get_active_markets(limit=limit) if active_only else await store.get_markets(limit=limit)
            result = []
            for m in markets:
                if tags and not any(t in (m.tags or []) for t in tags):
                    continue
                result.append({
                    "id": m.id,
                    "question": m.question,
                    "yes_price": m.yes_price,
                    "no_price": m.no_price,
                    "volume_24h": m.volume_24h,
                    "liquidity": m.liquidity,
                    "end_date": m.end_date.isoformat() if m.end_date else None,
                })
            return json.dumps({"markets": result, "count": len(result)}, indent=2)
        finally:
            await store.close()

    elif name == "get_market":
        market_id = arguments["market_id"]
        store = SQLiteStore()
        await store.connect()
        try:
            market = await store.get_market(market_id)
            if not market:
                return json.dumps({"error": f"Market not found: {market_id}"})
            return json.dumps({
                "id": market.id,
                "question": market.question,
                "description": market.description,
                "yes_price": market.yes_price,
                "no_price": market.no_price,
                "spread": market.spread if hasattr(market, 'spread') else None,
                "volume_24h": market.volume_24h,
                "liquidity": market.liquidity,
                "end_date": market.end_date.isoformat() if market.end_date else None,
                "active": market.active,
                "tags": market.tags,
            }, indent=2)
        finally:
            await store.close()

    elif name == "get_positions":
        status = arguments.get("status", "open")
        strategy = arguments.get("strategy")

        from polybot.db.state_client import StateClient
        client = StateClient()
        await client.connect()
        try:
            positions = await client.get_positions(status=status)
            if strategy:
                positions = [p for p in positions if p.get("strategy") == strategy]
            return json.dumps({"positions": positions, "count": len(positions)}, indent=2)
        finally:
            await client.close()

    elif name == "get_orders":
        status = arguments.get("status", "all")
        limit = arguments.get("limit", 50)

        from polybot.db.state_client import StateClient
        client = StateClient()
        await client.connect()
        try:
            orders = await client.get_orders(status=status, limit=limit)
            return json.dumps({"orders": orders, "count": len(orders)}, indent=2)
        finally:
            await client.close()

    elif name == "get_strategies":
        from polybot.db.state_client import StateClient
        client = StateClient()
        await client.connect()
        try:
            result = []
            for name, cls in STRATEGY_REGISTRY.items():
                config = await client.get_strategy_config(name)
                result.append({
                    "name": name,
                    "description": getattr(cls, "description", ""),
                    "enabled": config.get("enabled", False) if config else False,
                    "shadow": config.get("shadow", False) if config else False,
                })
            return json.dumps({"strategies": result}, indent=2)
        finally:
            await client.close()

    elif name == "get_risk_status":
        settings = get_settings()
        from polybot.db.state_client import StateClient
        client = StateClient()
        await client.connect()
        try:
            positions = await client.get_positions(status="open")
            total_exposure = sum(p.get("size", 0) * p.get("entry_price", 0) for p in positions)
            return json.dumps({
                "total_exposure_usd": total_exposure,
                "max_exposure_usd": settings.risk.max_total_exposure_usd,
                "exposure_utilization": total_exposure / settings.risk.max_total_exposure_usd if settings.risk.max_total_exposure_usd > 0 else 0,
                "max_position_size_usd": settings.risk.max_position_size_usd,
                "daily_loss_limit_usd": settings.risk.daily_loss_limit_usd,
                "open_positions": len(positions),
                "ai_limits": {
                    "max_position_usd": settings.mcp.max_position_usd,
                    "max_daily_trades": settings.mcp.max_daily_trades,
                    "daily_loss_limit_usd": settings.mcp.daily_loss_limit_usd,
                },
            }, indent=2)
        finally:
            await client.close()

    elif name == "get_shadow_performance":
        days = arguments.get("days", 30)
        duckdb = get_duckdb_store()
        summary = duckdb.get_performance_summary(days=days)
        return json.dumps({
            "period_days": days,
            "total_trades": summary.get("total_trades", 0),
            "win_rate": summary.get("win_rate", 0),
            "total_pnl": summary.get("total_pnl", 0),
            "total_volume": summary.get("total_volume", 0),
        }, indent=2)

    elif name == "analyze_market":
        market_id = arguments["market_id"]
        plugin_name = arguments.get("plugin", "simple_heuristic")

        from polybot.db.sqlite_store import SQLiteStore
        from polybot.plugins.example_plugin import get_all_plugins
        from polybot.plugins.base import MarketContext

        store = SQLiteStore()
        await store.connect()
        try:
            market = await store.get_market(market_id)
            if not market:
                return json.dumps({"error": f"Market not found: {market_id}"})

            plugins = get_all_plugins()
            if plugin_name not in plugins:
                return json.dumps({"error": f"Plugin not found: {plugin_name}"})

            plugin = plugins[plugin_name]()
            await plugin.initialize({})

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
                    if market.end_date else None
                ),
                tags=market.tags,
            )

            prediction = await plugin.predict(context)
            await plugin.shutdown()

            market_price = market.yes_price or 0.5
            edge = prediction.yes_probability - market_price

            return json.dumps({
                "market_id": market_id,
                "question": market.question[:100],
                "current_price": market_price,
                "predicted_probability": prediction.yes_probability,
                "confidence": prediction.confidence,
                "edge": edge,
                "recommendation": "BUY YES" if edge > 0.05 else ("BUY NO" if edge < -0.05 else "HOLD"),
                "reasoning": prediction.reasoning,
            }, indent=2)
        finally:
            await store.close()

    return json.dumps({"error": f"Unknown read-only tool: {name}"})


# =============================================================================
# Assessment Tool Handlers
# =============================================================================


async def handle_assessment_tool(name: str, arguments: dict[str, Any]) -> str:
    """Handle strategy assessment tool calls."""
    from polybot.db.duckdb_store import get_duckdb_store
    from polybot.db.state_client import StateClient

    if name == "get_strategy_logs":
        strategy = arguments["strategy"]
        log_type = arguments.get("log_type", "all")
        limit = arguments.get("limit", 100)

        # Query strategy logs from DuckDB
        duckdb = get_duckdb_store()
        logs = duckdb.get_strategy_logs(strategy=strategy, log_type=log_type, limit=limit)
        return json.dumps({"strategy": strategy, "logs": logs, "count": len(logs)}, indent=2)

    elif name == "get_strategy_performance":
        strategy = arguments["strategy"]
        days = arguments.get("days", 30)

        duckdb = get_duckdb_store()
        perf = duckdb.get_strategy_performance(strategy=strategy, days=days)
        return json.dumps({"strategy": strategy, "period_days": days, **perf}, indent=2)

    elif name == "get_strategy_config":
        strategy = arguments["strategy"]

        if strategy not in STRATEGY_REGISTRY:
            return json.dumps({"error": f"Unknown strategy: {strategy}"})

        client = StateClient()
        await client.connect()
        try:
            config = await client.get_strategy_config(strategy)
            return json.dumps({"strategy": strategy, "config": config or {}}, indent=2)
        finally:
            await client.close()

    elif name == "analyze_strategy":
        strategy = arguments["strategy"]
        include_logs = arguments.get("include_logs", True)

        if strategy not in STRATEGY_REGISTRY:
            return json.dumps({"error": f"Unknown strategy: {strategy}"})

        # Gather data for analysis
        duckdb = get_duckdb_store()
        settings = get_settings()

        perf = duckdb.get_strategy_performance(strategy=strategy, days=settings.mcp.assessment_lookback_days)
        logs = duckdb.get_strategy_logs(strategy=strategy, limit=50) if include_logs else []

        # Generate analysis
        analysis = {
            "strategy": strategy,
            "description": getattr(STRATEGY_REGISTRY[strategy], "description", ""),
            "performance": perf,
            "recent_activity": len(logs),
            "health": "good" if perf.get("win_rate", 0) > 0.5 else "needs_attention",
            "observations": [],
            "recommendations": [],
        }

        # Add observations based on data
        if perf.get("total_trades", 0) == 0:
            analysis["observations"].append("No trades recorded in analysis period")
            analysis["recommendations"].append("Check if strategy is enabled and scanning")
        elif perf.get("win_rate", 0) < 0.4:
            analysis["observations"].append(f"Low win rate: {perf.get('win_rate', 0)*100:.1f}%")
            analysis["recommendations"].append("Review entry conditions and timing")

        if perf.get("total_pnl", 0) < 0:
            analysis["observations"].append(f"Negative P&L: ${perf.get('total_pnl', 0):.2f}")

        return json.dumps(analysis, indent=2)

    elif name == "get_strategy_signals":
        strategy = arguments["strategy"]
        limit = arguments.get("limit", 50)

        duckdb = get_duckdb_store()
        signals = duckdb.get_strategy_signals(strategy=strategy, limit=limit)
        return json.dumps({"strategy": strategy, "signals": signals, "count": len(signals)}, indent=2)

    elif name == "compare_strategies":
        days = arguments.get("days", 30)

        duckdb = get_duckdb_store()
        comparisons = []

        for strat_name in STRATEGY_REGISTRY.keys():
            perf = duckdb.get_strategy_performance(strategy=strat_name, days=days)
            comparisons.append({
                "strategy": strat_name,
                "total_trades": perf.get("total_trades", 0),
                "win_rate": perf.get("win_rate", 0),
                "total_pnl": perf.get("total_pnl", 0),
            })

        # Sort by P&L
        comparisons.sort(key=lambda x: x["total_pnl"], reverse=True)
        return json.dumps({"period_days": days, "strategies": comparisons}, indent=2)

    elif name == "get_strategy_code":
        strategy = arguments["strategy"]

        if strategy not in STRATEGY_REGISTRY:
            return json.dumps({"error": f"Unknown strategy: {strategy}"})

        settings = get_settings()
        if not settings.mcp.allow_code_read:
            return json.dumps({"error": "Code read access is disabled"})

        # Map strategy name to file path
        strategy_dir = Path(__file__).parent.parent / "strategies"
        strategy_file = strategy_dir / f"{strategy}.py"

        if not strategy_file.exists():
            # Try alternate naming
            strategy_file = strategy_dir / f"{strategy.replace('_', '')}.py"

        if not strategy_file.exists():
            return json.dumps({"error": f"Strategy file not found for: {strategy}"})

        code = strategy_file.read_text()
        return json.dumps({
            "strategy": strategy,
            "file_path": str(strategy_file),
            "code": code,
        }, indent=2)

    elif name == "suggest_strategy_improvements":
        strategy = arguments["strategy"]
        focus = arguments.get("focus", "general")

        if strategy not in STRATEGY_REGISTRY:
            return json.dumps({"error": f"Unknown strategy: {strategy}"})

        # Gather data
        duckdb = get_duckdb_store()
        settings = get_settings()

        perf = duckdb.get_strategy_performance(strategy=strategy, days=settings.mcp.assessment_lookback_days)
        logs = duckdb.get_strategy_logs(strategy=strategy, log_type="error", limit=20)

        suggestions = []

        # Generate suggestions based on focus area
        if focus in ("general", "entry"):
            if perf.get("win_rate", 0) < 0.5:
                suggestions.append({
                    "area": "entry",
                    "suggestion": "Consider tightening entry criteria - current win rate is below 50%",
                    "priority": "high",
                })

        if focus in ("general", "exit"):
            if perf.get("avg_hold_time", 0) > 24:  # hours
                suggestions.append({
                    "area": "exit",
                    "suggestion": "Average hold time is high - consider adding time-based exit conditions",
                    "priority": "medium",
                })

        if focus in ("general", "risk"):
            suggestions.append({
                "area": "risk",
                "suggestion": "Ensure position sizing is appropriate for current market volatility",
                "priority": "medium",
            })

        if len(logs) > 10:
            suggestions.append({
                "area": "stability",
                "suggestion": f"High error rate detected ({len(logs)} errors) - review error logs",
                "priority": "high",
            })

        return json.dumps({
            "strategy": strategy,
            "focus": focus,
            "suggestions": suggestions,
            "data_period_days": settings.mcp.assessment_lookback_days,
        }, indent=2)

    return json.dumps({"error": f"Unknown assessment tool: {name}"})


# =============================================================================
# Shadow Trading Tool Handlers
# =============================================================================


async def handle_shadow_tool(name: str, arguments: dict[str, Any]) -> str:
    """Handle shadow (paper) trading tool calls."""
    from polybot.db.state_client import StateClient
    from polybot.mcp.audit import audit_log

    settings = get_settings()

    # Check AI position limits
    size = arguments.get("size", 0)
    if size > settings.mcp.max_position_usd:
        return json.dumps({
            "error": f"Position size ${size} exceeds AI limit ${settings.mcp.max_position_usd}"
        })

    if name == "shadow_buy":
        market_id = arguments["market_id"]
        side = arguments["side"]
        reason = arguments["reason"]

        # Log shadow trade
        await audit_log(
            action="shadow_buy",
            tool=name,
            arguments=arguments,
            timestamp=datetime.utcnow(),
        )

        # Create shadow position via state service
        client = StateClient()
        await client.connect()
        try:
            result = await client.create_shadow_position(
                market_id=market_id,
                side=side,
                size=size,
                reason=reason,
                source="ai_agent",
            )
            return json.dumps({
                "success": True,
                "action": "shadow_buy",
                "market_id": market_id,
                "side": side,
                "size": size,
                "position_id": result.get("position_id"),
            }, indent=2)
        finally:
            await client.close()

    elif name == "shadow_sell":
        market_id = arguments["market_id"]
        side = arguments["side"]
        reason = arguments["reason"]

        await audit_log(
            action="shadow_sell",
            tool=name,
            arguments=arguments,
            timestamp=datetime.utcnow(),
        )

        client = StateClient()
        await client.connect()
        try:
            result = await client.create_shadow_position(
                market_id=market_id,
                side=side,
                size=-size,  # Negative for sell
                reason=reason,
                source="ai_agent",
            )
            return json.dumps({
                "success": True,
                "action": "shadow_sell",
                "market_id": market_id,
                "side": side,
                "size": size,
                "position_id": result.get("position_id"),
            }, indent=2)
        finally:
            await client.close()

    elif name == "shadow_close_position":
        position_id = arguments["position_id"]

        await audit_log(
            action="shadow_close",
            tool=name,
            arguments=arguments,
            timestamp=datetime.utcnow(),
        )

        client = StateClient()
        await client.connect()
        try:
            result = await client.close_shadow_position(position_id=position_id)
            return json.dumps({
                "success": True,
                "action": "shadow_close",
                "position_id": position_id,
                "realized_pnl": result.get("realized_pnl"),
            }, indent=2)
        finally:
            await client.close()

    return json.dumps({"error": f"Unknown shadow tool: {name}"})


# =============================================================================
# Live Trading Tool Handlers
# =============================================================================


async def handle_live_tool(name: str, arguments: dict[str, Any]) -> str:
    """Handle live trading tool calls."""
    settings = get_settings()

    # Check AI position limits
    size = arguments.get("size", 0)
    if size > settings.mcp.max_position_usd:
        return json.dumps({
            "error": f"Position size ${size} exceeds AI limit ${settings.mcp.max_position_usd}"
        })

    if name == "submit_order":
        # If approval required, submit to approval queue
        if settings.mcp.require_approval:
            approval = await submit_for_approval(
                order_type="submit_order",
                arguments=arguments,
                expires_at=datetime.utcnow() + timedelta(seconds=settings.mcp.approval_timeout_sec),
            )
            return json.dumps({
                "status": "pending_approval",
                "approval_id": approval["id"],
                "message": "Order submitted for human approval",
                "expires_at": approval["expires_at"].isoformat(),
            }, indent=2)

        # Execute immediately if no approval required
        from polybot.db.executor_client import ExecutorClient
        client = ExecutorClient()
        await client.connect()
        try:
            result = await client.submit_order(
                market_id=arguments["market_id"],
                side=arguments["side"],
                action=arguments["action"],
                size=arguments["size"],
                price=arguments.get("price"),
                reason=arguments["reason"],
                source="ai_agent",
            )
            return json.dumps({
                "success": result.get("success", False),
                "order_id": result.get("order_id"),
                "status": result.get("status"),
            }, indent=2)
        finally:
            await client.close()

    elif name == "cancel_order":
        order_id = arguments["order_id"]

        from polybot.db.executor_client import ExecutorClient
        client = ExecutorClient()
        await client.connect()
        try:
            result = await client.cancel_order(order_id=order_id)
            return json.dumps({
                "success": result.get("success", False),
                "order_id": order_id,
            }, indent=2)
        finally:
            await client.close()

    elif name == "close_position":
        position_id = arguments["position_id"]
        reason = arguments["reason"]

        if settings.mcp.require_approval:
            approval = await submit_for_approval(
                order_type="close_position",
                arguments=arguments,
                expires_at=datetime.utcnow() + timedelta(seconds=settings.mcp.approval_timeout_sec),
            )
            return json.dumps({
                "status": "pending_approval",
                "approval_id": approval["id"],
                "message": "Position close submitted for human approval",
            }, indent=2)

        from polybot.db.executor_client import ExecutorClient
        client = ExecutorClient()
        await client.connect()
        try:
            result = await client.close_position(position_id=position_id, reason=reason)
            return json.dumps({
                "success": result.get("success", False),
                "position_id": position_id,
                "realized_pnl": result.get("realized_pnl"),
            }, indent=2)
        finally:
            await client.close()

    return json.dumps({"error": f"Unknown live tool: {name}"})


# =============================================================================
# CLI Tool Handlers
# =============================================================================


# Whitelist of allowed CLI commands
ALLOWED_CLI_COMMANDS = {
    "strategy": ["list", "enable", "disable", "shadow", "run"],
    "mcp": ["status", "mode", "approve", "reject", "audit"],
    "ai": ["plugins", "info", "predict", "scan"],
    "db": ["init", "stats"],
    "config": [],
    "statarb": ["correlations", "compute", "opportunities", "prices"],
}

BLOCKED_CLI_COMMANDS = {"auth", "start"}


async def handle_cli_tool(name: str, arguments: dict[str, Any]) -> str:
    """Handle CLI wrapper tool calls."""
    from polybot.db.state_client import StateClient

    if name == "run_cli":
        command = arguments["command"]
        subcommand = arguments.get("subcommand", "")
        args = arguments.get("args", [])

        # Security check
        if command in BLOCKED_CLI_COMMANDS:
            return json.dumps({"error": f"Command '{command}' is blocked for security reasons"})

        if command not in ALLOWED_CLI_COMMANDS:
            return json.dumps({"error": f"Command '{command}' is not in the allowed list"})

        allowed_subs = ALLOWED_CLI_COMMANDS[command]
        if allowed_subs and subcommand and subcommand not in allowed_subs:
            return json.dumps({"error": f"Subcommand '{subcommand}' is not allowed for '{command}'"})

        # Execute command
        import subprocess
        cmd = ["polybot", command]
        if subcommand:
            cmd.append(subcommand)
        cmd.extend(args)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return json.dumps({
                "command": " ".join(cmd),
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }, indent=2)
        except subprocess.TimeoutExpired:
            return json.dumps({"error": "Command timed out after 30 seconds"})
        except Exception as e:
            return json.dumps({"error": f"Command execution failed: {e}"})

    elif name == "strategy_enable":
        strategy_name = arguments["name"]

        if strategy_name not in STRATEGY_REGISTRY:
            return json.dumps({"error": f"Unknown strategy: {strategy_name}"})

        client = StateClient()
        await client.connect()
        try:
            current = await client.get_strategy_config(strategy_name)
            shadow = current.get("shadow", False) if current else False
            config = current.get("config", {}) if current else {}

            await client.save_strategy_config(
                name=strategy_name,
                enabled=True,
                config=config,
                shadow=shadow,
            )
            return json.dumps({
                "success": True,
                "strategy": strategy_name,
                "enabled": True,
            }, indent=2)
        finally:
            await client.close()

    elif name == "strategy_disable":
        strategy_name = arguments["name"]

        if strategy_name not in STRATEGY_REGISTRY:
            return json.dumps({"error": f"Unknown strategy: {strategy_name}"})

        client = StateClient()
        await client.connect()
        try:
            current = await client.get_strategy_config(strategy_name)
            shadow = current.get("shadow", False) if current else False
            config = current.get("config", {}) if current else {}

            await client.save_strategy_config(
                name=strategy_name,
                enabled=False,
                config=config,
                shadow=shadow,
            )
            return json.dumps({
                "success": True,
                "strategy": strategy_name,
                "enabled": False,
            }, indent=2)
        finally:
            await client.close()

    elif name == "strategy_set_shadow":
        strategy_name = arguments["name"]
        shadow_enabled = arguments["enabled"]

        if strategy_name not in STRATEGY_REGISTRY:
            return json.dumps({"error": f"Unknown strategy: {strategy_name}"})

        client = StateClient()
        await client.connect()
        try:
            current = await client.get_strategy_config(strategy_name)
            enabled = current.get("enabled", False) if current else False
            config = current.get("config", {}) if current else {}

            await client.save_strategy_config(
                name=strategy_name,
                enabled=enabled,
                config=config,
                shadow=shadow_enabled,
            )
            return json.dumps({
                "success": True,
                "strategy": strategy_name,
                "shadow": shadow_enabled,
            }, indent=2)
        finally:
            await client.close()

    elif name == "get_config":
        settings = get_settings()
        return json.dumps({
            "api": {"host": settings.api.host, "port": settings.api.port},
            "risk": {
                "max_position_size_usd": settings.risk.max_position_size_usd,
                "max_total_exposure_usd": settings.risk.max_total_exposure_usd,
                "daily_loss_limit_usd": settings.risk.daily_loss_limit_usd,
            },
            "mcp": {
                "enabled": settings.mcp.enabled,
                "ai_trading_mode": settings.mcp.ai_trading_mode,
                "max_position_usd": settings.mcp.max_position_usd,
                "require_approval": settings.mcp.require_approval,
            },
        }, indent=2)

    elif name == "db_stats":
        from polybot.db.duckdb_store import get_duckdb_store
        duckdb = get_duckdb_store()
        summary = duckdb.get_performance_summary(days=30)
        return json.dumps({
            "period": "30 days",
            "total_trades": summary.get("total_trades", 0),
            "win_rate": summary.get("win_rate", 0),
            "total_pnl": summary.get("total_pnl", 0),
            "total_volume": summary.get("total_volume", 0),
            "total_fees": summary.get("total_fees", 0),
        }, indent=2)

    return json.dumps({"error": f"Unknown CLI tool: {name}"})
