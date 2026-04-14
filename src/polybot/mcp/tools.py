"""MCP tool definitions for PolyBot.

Tools are organized into categories:
- Read-only: Market data, positions, orders (always available)
- Assessment: Strategy analysis and improvement suggestions
- Shadow: Paper trading (requires shadow or live mode)
- Live: Real trading (requires live mode)
- CLI: Whitelisted CLI command execution
"""

import json
import logging
from typing import Any

from mcp.types import Tool

from polybot.config import get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# Tool Definitions
# =============================================================================


def get_readonly_tools() -> list[Tool]:
    """Get read-only market data tools."""
    return [
        Tool(
            name="list_markets",
            description="List available prediction markets with current prices",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 50, "description": "Max markets to return"},
                    "active_only": {"type": "boolean", "default": True, "description": "Only active markets"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags"},
                },
            },
        ),
        Tool(
            name="get_market",
            description="Get detailed information about a specific market",
            inputSchema={
                "type": "object",
                "properties": {
                    "market_id": {"type": "string", "description": "Market ID"},
                },
                "required": ["market_id"],
            },
        ),
        Tool(
            name="get_positions",
            description="List current open and closed positions",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                    "strategy": {"type": "string", "description": "Filter by strategy name"},
                },
            },
        ),
        Tool(
            name="get_orders",
            description="List order history",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["open", "filled", "cancelled", "all"], "default": "all"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        ),
        Tool(
            name="get_strategies",
            description="List all trading strategies with their enabled/shadow status",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_risk_status",
            description="Get current risk metrics, exposure, and limit utilization",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_shadow_performance",
            description="Get shadow trading performance statistics",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "default": 30, "description": "Lookback period in days"},
                },
            },
        ),
        Tool(
            name="analyze_market",
            description="Get AI prediction for a market using configured plugin",
            inputSchema={
                "type": "object",
                "properties": {
                    "market_id": {"type": "string", "description": "Market ID to analyze"},
                    "plugin": {"type": "string", "description": "AI plugin to use (optional)"},
                },
                "required": ["market_id"],
            },
        ),
    ]


def get_assessment_tools() -> list[Tool]:
    """Get strategy assessment and monitoring tools."""
    return [
        Tool(
            name="get_strategy_logs",
            description="Get strategy execution logs (signals, scans, errors)",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy": {"type": "string", "description": "Strategy name"},
                    "log_type": {"type": "string", "enum": ["signal", "scan", "error", "all"], "default": "all"},
                    "limit": {"type": "integer", "default": 100},
                },
                "required": ["strategy"],
            },
        ),
        Tool(
            name="get_strategy_performance",
            description="Get detailed strategy performance metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy": {"type": "string", "description": "Strategy name"},
                    "days": {"type": "integer", "default": 30, "description": "Lookback period"},
                },
                "required": ["strategy"],
            },
        ),
        Tool(
            name="get_strategy_config",
            description="Get current strategy configuration parameters",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy": {"type": "string", "description": "Strategy name"},
                },
                "required": ["strategy"],
            },
        ),
        Tool(
            name="analyze_strategy",
            description="Comprehensive AI analysis of strategy behavior with recommendations",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy": {"type": "string", "description": "Strategy name"},
                    "include_logs": {"type": "boolean", "default": True, "description": "Include recent logs in analysis"},
                },
                "required": ["strategy"],
            },
        ),
        Tool(
            name="get_strategy_signals",
            description="Get recent signals generated by a strategy",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy": {"type": "string", "description": "Strategy name"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["strategy"],
            },
        ),
        Tool(
            name="compare_strategies",
            description="Compare performance of all strategies side-by-side",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "default": 30, "description": "Lookback period"},
                },
            },
        ),
        Tool(
            name="get_strategy_code",
            description="Read strategy source code for review (read-only)",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy": {"type": "string", "description": "Strategy name"},
                },
                "required": ["strategy"],
            },
        ),
        Tool(
            name="suggest_strategy_improvements",
            description="Generate AI-powered improvement suggestions for a strategy",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy": {"type": "string", "description": "Strategy name"},
                    "focus": {
                        "type": "string",
                        "enum": ["general", "entry", "exit", "risk", "timing"],
                        "default": "general",
                        "description": "Area to focus suggestions on",
                    },
                },
                "required": ["strategy"],
            },
        ),
    ]


def get_shadow_tools() -> list[Tool]:
    """Get shadow (paper) trading tools."""
    return [
        Tool(
            name="shadow_buy",
            description="Submit a paper trade buy order (shadow mode)",
            inputSchema={
                "type": "object",
                "properties": {
                    "market_id": {"type": "string", "description": "Market ID"},
                    "side": {"type": "string", "enum": ["YES", "NO"], "description": "YES or NO outcome"},
                    "size": {"type": "number", "description": "Position size in USD"},
                    "reason": {"type": "string", "description": "Reasoning for the trade"},
                },
                "required": ["market_id", "side", "size", "reason"],
            },
        ),
        Tool(
            name="shadow_sell",
            description="Submit a paper trade sell order (shadow mode)",
            inputSchema={
                "type": "object",
                "properties": {
                    "market_id": {"type": "string", "description": "Market ID"},
                    "side": {"type": "string", "enum": ["YES", "NO"], "description": "YES or NO outcome"},
                    "size": {"type": "number", "description": "Position size in USD"},
                    "reason": {"type": "string", "description": "Reasoning for the trade"},
                },
                "required": ["market_id", "side", "size", "reason"],
            },
        ),
        Tool(
            name="shadow_close_position",
            description="Close a paper trading position",
            inputSchema={
                "type": "object",
                "properties": {
                    "position_id": {"type": "string", "description": "Position ID to close"},
                },
                "required": ["position_id"],
            },
        ),
    ]


def get_live_tools() -> list[Tool]:
    """Get live trading tools (requires approval if enabled)."""
    return [
        Tool(
            name="submit_order",
            description="Submit a real trading order (may require approval)",
            inputSchema={
                "type": "object",
                "properties": {
                    "market_id": {"type": "string", "description": "Market ID"},
                    "side": {"type": "string", "enum": ["YES", "NO"], "description": "YES or NO outcome"},
                    "action": {"type": "string", "enum": ["BUY", "SELL"], "description": "Buy or sell"},
                    "size": {"type": "number", "description": "Position size in USD"},
                    "price": {"type": "number", "description": "Limit price (optional, uses market if omitted)"},
                    "reason": {"type": "string", "description": "Reasoning for the trade"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1, "description": "Confidence level 0-1"},
                },
                "required": ["market_id", "side", "action", "size", "reason", "confidence"],
            },
        ),
        Tool(
            name="cancel_order",
            description="Cancel a pending order",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID to cancel"},
                },
                "required": ["order_id"],
            },
        ),
        Tool(
            name="close_position",
            description="Close an open position",
            inputSchema={
                "type": "object",
                "properties": {
                    "position_id": {"type": "string", "description": "Position ID to close"},
                    "reason": {"type": "string", "description": "Reason for closing"},
                },
                "required": ["position_id", "reason"],
            },
        ),
    ]


def get_cli_tools() -> list[Tool]:
    """Get CLI wrapper tools."""
    return [
        Tool(
            name="run_cli",
            description="Execute a whitelisted polybot CLI command",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "CLI command group (e.g., 'strategy', 'db')"},
                    "subcommand": {"type": "string", "description": "Subcommand (e.g., 'list', 'enable')"},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Command arguments"},
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="strategy_enable",
            description="Enable a trading strategy",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Strategy name"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="strategy_disable",
            description="Disable a trading strategy",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Strategy name"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="strategy_set_shadow",
            description="Enable or disable shadow mode for a strategy",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Strategy name"},
                    "enabled": {"type": "boolean", "description": "Enable or disable shadow mode"},
                },
                "required": ["name", "enabled"],
            },
        ),
        Tool(
            name="get_config",
            description="Get current PolyBot configuration",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="db_stats",
            description="Get database statistics and performance summary",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


# =============================================================================
# Tool Handlers
# =============================================================================


async def handle_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Dispatch tool call to appropriate handler."""
    settings = get_settings()

    # Import handlers lazily to avoid circular imports
    from polybot.mcp.handlers import (
        handle_readonly_tool,
        handle_assessment_tool,
        handle_shadow_tool,
        handle_live_tool,
        handle_cli_tool,
    )

    # Determine tool category and check permissions
    readonly_tools = {t.name for t in get_readonly_tools()}
    assessment_tools = {t.name for t in get_assessment_tools()}
    shadow_tools = {t.name for t in get_shadow_tools()}
    live_tools = {t.name for t in get_live_tools()}
    cli_tools = {t.name for t in get_cli_tools()}

    if name in readonly_tools:
        return await handle_readonly_tool(name, arguments)

    elif name in assessment_tools:
        if name == "get_strategy_code" and not settings.mcp.allow_code_read:
            raise PermissionError("Strategy code access is disabled")
        return await handle_assessment_tool(name, arguments)

    elif name in shadow_tools:
        if settings.mcp.ai_trading_mode not in ("shadow", "live"):
            raise PermissionError(f"Shadow trading requires mode 'shadow' or 'live', current: {settings.mcp.ai_trading_mode}")
        return await handle_shadow_tool(name, arguments)

    elif name in live_tools:
        if settings.mcp.ai_trading_mode != "live":
            raise PermissionError(f"Live trading requires mode 'live', current: {settings.mcp.ai_trading_mode}")
        return await handle_live_tool(name, arguments)

    elif name in cli_tools:
        if not settings.mcp.allow_cli_execution:
            raise PermissionError("CLI execution is disabled")
        return await handle_cli_tool(name, arguments)

    else:
        raise ValueError(f"Unknown tool: {name}")
