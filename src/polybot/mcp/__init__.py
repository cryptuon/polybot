"""MCP (Model Context Protocol) server for AI agent integration.

This package provides an MCP server that allows AI agents (like Claude) to:
- Query markets, positions, and orders
- Execute shadow (paper) or live trades
- Analyze and assess strategy performance
- Run whitelisted CLI commands

Usage:
    polybot mcp start  # Start MCP server
    polybot mcp status  # Check server status
"""

from polybot.mcp.server import create_mcp_server, run_mcp_server

__all__ = ["create_mcp_server", "run_mcp_server"]
