"""Approval workflow for AI agent live trades.

When MCP_REQUIRE_APPROVAL=true, live trading requests are queued
for human approval before execution.
"""

import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from polybot.config import get_settings

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of a pending approval."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# In-memory pending approvals (in production, use database)
_pending_approvals: dict[str, dict[str, Any]] = {}


async def submit_for_approval(
    order_type: str,
    arguments: dict[str, Any],
    expires_at: datetime,
    agent_id: str = "default",
) -> dict[str, Any]:
    """Submit a live trade for human approval.

    Args:
        order_type: Type of order (submit_order, close_position)
        arguments: Order arguments
        expires_at: When the approval expires
        agent_id: Identifier for the AI agent

    Returns:
        Approval record with ID
    """
    approval_id = str(uuid.uuid4())[:8]

    approval = {
        "id": approval_id,
        "order_type": order_type,
        "arguments": arguments,
        "agent_id": agent_id,
        "status": ApprovalStatus.PENDING.value,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "approved_by": None,
        "approved_at": None,
        "rejection_reason": None,
    }

    _pending_approvals[approval_id] = approval

    # Also persist to file for durability
    _save_approvals()

    logger.info(f"Trade submitted for approval: {approval_id}")

    return approval


async def approve_trade(approval_id: str, approved_by: str = "operator") -> dict[str, Any]:
    """Approve a pending trade.

    Args:
        approval_id: ID of the approval
        approved_by: Who approved (for audit)

    Returns:
        Updated approval record
    """
    if approval_id not in _pending_approvals:
        raise ValueError(f"Approval not found: {approval_id}")

    approval = _pending_approvals[approval_id]

    if approval["status"] != ApprovalStatus.PENDING.value:
        raise ValueError(f"Approval is not pending: {approval['status']}")

    # Check expiration
    if datetime.utcnow() > approval["expires_at"]:
        approval["status"] = ApprovalStatus.EXPIRED.value
        _save_approvals()
        raise ValueError("Approval has expired")

    # Mark as approved
    approval["status"] = ApprovalStatus.APPROVED.value
    approval["approved_by"] = approved_by
    approval["approved_at"] = datetime.utcnow()

    _save_approvals()

    # Execute the trade
    result = await _execute_approved_trade(approval)

    logger.info(f"Trade approved and executed: {approval_id}")

    return {**approval, "execution_result": result}


async def reject_trade(
    approval_id: str,
    reason: str = "Rejected by operator",
    rejected_by: str = "operator",
) -> dict[str, Any]:
    """Reject a pending trade.

    Args:
        approval_id: ID of the approval
        reason: Reason for rejection
        rejected_by: Who rejected (for audit)

    Returns:
        Updated approval record
    """
    if approval_id not in _pending_approvals:
        raise ValueError(f"Approval not found: {approval_id}")

    approval = _pending_approvals[approval_id]

    if approval["status"] != ApprovalStatus.PENDING.value:
        raise ValueError(f"Approval is not pending: {approval['status']}")

    approval["status"] = ApprovalStatus.REJECTED.value
    approval["rejection_reason"] = reason
    approval["approved_by"] = rejected_by
    approval["approved_at"] = datetime.utcnow()

    _save_approvals()

    logger.info(f"Trade rejected: {approval_id} - {reason}")

    return approval


def get_pending_approvals() -> list[dict[str, Any]]:
    """Get all pending approvals.

    Returns:
        List of pending approval records
    """
    _load_approvals()
    _expire_old_approvals()

    pending = [
        a for a in _pending_approvals.values()
        if a["status"] == ApprovalStatus.PENDING.value
    ]

    # Sort by creation time (oldest first)
    pending.sort(key=lambda x: x["created_at"])

    return pending


def get_approval(approval_id: str) -> dict[str, Any] | None:
    """Get a specific approval by ID.

    Args:
        approval_id: ID of the approval

    Returns:
        Approval record or None
    """
    _load_approvals()
    return _pending_approvals.get(approval_id)


def _expire_old_approvals() -> None:
    """Mark expired approvals."""
    now = datetime.utcnow()
    for approval in _pending_approvals.values():
        if (
            approval["status"] == ApprovalStatus.PENDING.value
            and now > approval["expires_at"]
        ):
            approval["status"] = ApprovalStatus.EXPIRED.value
    _save_approvals()


async def _execute_approved_trade(approval: dict[str, Any]) -> dict[str, Any]:
    """Execute an approved trade.

    Args:
        approval: Approval record

    Returns:
        Execution result
    """
    from polybot.db.executor_client import ExecutorClient

    order_type = approval["order_type"]
    args = approval["arguments"]

    client = ExecutorClient()
    await client.connect()

    try:
        if order_type == "submit_order":
            result = await client.submit_order(
                market_id=args["market_id"],
                side=args["side"],
                action=args["action"],
                size=args["size"],
                price=args.get("price"),
                reason=args["reason"],
                source="ai_agent_approved",
            )
        elif order_type == "close_position":
            result = await client.close_position(
                position_id=args["position_id"],
                reason=args["reason"],
            )
        else:
            result = {"error": f"Unknown order type: {order_type}"}

        return result
    finally:
        await client.close()


def _save_approvals() -> None:
    """Persist approvals to file."""
    data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    approvals_file = data_dir / "mcp_approvals.json"

    # Convert datetime objects to ISO strings for JSON
    data = {}
    for aid, approval in _pending_approvals.items():
        data[aid] = {
            **approval,
            "created_at": approval["created_at"].isoformat() if isinstance(approval["created_at"], datetime) else approval["created_at"],
            "expires_at": approval["expires_at"].isoformat() if isinstance(approval["expires_at"], datetime) else approval["expires_at"],
            "approved_at": approval["approved_at"].isoformat() if isinstance(approval.get("approved_at"), datetime) else approval.get("approved_at"),
        }

    try:
        with open(approvals_file, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save approvals: {e}")


def _load_approvals() -> None:
    """Load approvals from file."""
    global _pending_approvals

    data_dir = Path("./data")
    approvals_file = data_dir / "mcp_approvals.json"

    if not approvals_file.exists():
        return

    try:
        with open(approvals_file, "r") as f:
            data = json.load(f)

        # Convert ISO strings back to datetime
        for aid, approval in data.items():
            approval["created_at"] = datetime.fromisoformat(approval["created_at"])
            approval["expires_at"] = datetime.fromisoformat(approval["expires_at"])
            if approval.get("approved_at"):
                approval["approved_at"] = datetime.fromisoformat(approval["approved_at"])
            _pending_approvals[aid] = approval
    except Exception as e:
        logger.error(f"Failed to load approvals: {e}")
