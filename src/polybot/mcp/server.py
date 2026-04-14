"""MCP server implementation for PolyBot.

Provides Model Context Protocol server that exposes trading tools to AI agents.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from polybot.config import get_settings
from polybot.mcp.tools import (
    get_readonly_tools,
    get_assessment_tools,
    get_shadow_tools,
    get_live_tools,
    get_cli_tools,
    handle_tool_call,
)
from polybot.mcp.audit import audit_log

logger = logging.getLogger(__name__)


def create_mcp_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("polybot")
    settings = get_settings()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return available tools based on configuration."""
        tools = []

        # Read-only tools are always available
        tools.extend(get_readonly_tools())

        # Strategy assessment tools (always available when MCP enabled)
        tools.extend(get_assessment_tools())

        # CLI tools (if allowed)
        if settings.mcp.allow_cli_execution:
            tools.extend(get_cli_tools())

        # Shadow trading tools
        if settings.mcp.ai_trading_mode in ("shadow", "live"):
            tools.extend(get_shadow_tools())

        # Live trading tools
        if settings.mcp.ai_trading_mode == "live":
            tools.extend(get_live_tools())

        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls with rate limiting and audit logging."""
        settings = get_settings()

        # Audit log the call
        if settings.mcp.audit_log_enabled:
            await audit_log(
                action="tool_call",
                tool=name,
                arguments=arguments,
                timestamp=datetime.utcnow(),
            )

        try:
            result = await handle_tool_call(name, arguments)
            return [TextContent(type="text", text=result)]
        except PermissionError as e:
            error_msg = f"Permission denied: {e}"
            logger.warning(f"Tool {name} permission denied: {e}")
            return [TextContent(type="text", text=error_msg)]
        except ValueError as e:
            error_msg = f"Invalid arguments: {e}"
            logger.warning(f"Tool {name} invalid arguments: {e}")
            return [TextContent(type="text", text=error_msg)]
        except Exception as e:
            error_msg = f"Error executing {name}: {e}"
            logger.exception(f"Tool {name} failed")
            return [TextContent(type="text", text=error_msg)]

    return server


async def run_mcp_server() -> None:
    """Run the MCP server using stdio transport."""
    settings = get_settings()

    if not settings.mcp.enabled:
        logger.error("MCP server is disabled. Set MCP_ENABLED=true to enable.")
        return

    logger.info(
        f"Starting MCP server (mode: {settings.mcp.ai_trading_mode}, "
        f"approval_required: {settings.mcp.require_approval})"
    )

    server = create_mcp_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Entry point for running MCP server."""
    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    main()
