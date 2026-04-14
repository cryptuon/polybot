"""Audit logging for MCP server.

All AI agent actions are logged for review and compliance.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from polybot.config import get_settings

logger = logging.getLogger(__name__)


async def audit_log(
    action: str,
    tool: str,
    arguments: dict[str, Any],
    timestamp: datetime,
    agent_id: str = "default",
    result: str | None = None,
    error: str | None = None,
) -> None:
    """Log an AI agent action to the audit log.

    Args:
        action: Type of action (tool_call, shadow_buy, etc.)
        tool: Tool name that was called
        arguments: Arguments passed to the tool
        timestamp: When the action occurred
        agent_id: Identifier for the AI agent
        result: Optional result summary
        error: Optional error message
    """
    settings = get_settings()

    if not settings.mcp.audit_log_enabled:
        return

    # Determine log file path
    data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    audit_file = data_dir / "mcp_audit.jsonl"

    # Create log entry
    entry = {
        "timestamp": timestamp.isoformat(),
        "action": action,
        "tool": tool,
        "arguments": arguments,
        "agent_id": agent_id,
        "ai_trading_mode": settings.mcp.ai_trading_mode,
    }

    if result:
        entry["result"] = result
    if error:
        entry["error"] = error

    # Append to JSONL file
    try:
        with open(audit_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")


def get_audit_logs(tail: int = 20, agent_id: str | None = None) -> list[dict[str, Any]]:
    """Read recent audit log entries.

    Args:
        tail: Number of recent entries to return
        agent_id: Optional filter by agent ID

    Returns:
        List of audit log entries (most recent first)
    """
    data_dir = Path("./data")
    audit_file = data_dir / "mcp_audit.jsonl"

    if not audit_file.exists():
        return []

    entries = []
    try:
        with open(audit_file, "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if agent_id is None or entry.get("agent_id") == agent_id:
                        entries.append(entry)
    except Exception as e:
        logger.error(f"Failed to read audit log: {e}")
        return []

    # Return most recent entries
    return entries[-tail:][::-1]


def get_audit_stats(days: int = 7) -> dict[str, Any]:
    """Get statistics from the audit log.

    Args:
        days: Number of days to analyze

    Returns:
        Dictionary of statistics
    """
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)
    data_dir = Path("./data")
    audit_file = data_dir / "mcp_audit.jsonl"

    if not audit_file.exists():
        return {"total_actions": 0, "period_days": days}

    total = 0
    by_tool: dict[str, int] = {}
    by_action: dict[str, int] = {}
    errors = 0

    try:
        with open(audit_file, "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry["timestamp"])
                    if ts >= cutoff:
                        total += 1
                        tool = entry.get("tool", "unknown")
                        action = entry.get("action", "unknown")
                        by_tool[tool] = by_tool.get(tool, 0) + 1
                        by_action[action] = by_action.get(action, 0) + 1
                        if entry.get("error"):
                            errors += 1
    except Exception as e:
        logger.error(f"Failed to analyze audit log: {e}")

    return {
        "period_days": days,
        "total_actions": total,
        "by_tool": by_tool,
        "by_action": by_action,
        "errors": errors,
    }
