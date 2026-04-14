"""API routes for MCP server management and approvals."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from polybot.config import get_settings
from polybot.mcp.approval import (
    get_pending_approvals,
    get_approval,
    approve_trade,
    reject_trade,
)
from polybot.mcp.audit import get_audit_logs, get_audit_stats


router = APIRouter(prefix="/mcp", tags=["mcp"])


class MCPStatusResponse(BaseModel):
    """MCP server status response."""
    enabled: bool
    ai_trading_mode: str
    require_approval: bool
    max_position_usd: float
    daily_loss_limit_usd: float
    pending_approvals: int
    audit_stats: dict


class ApprovalResponse(BaseModel):
    """Approval record response."""
    id: str
    order_type: str
    arguments: dict
    status: str
    created_at: str
    expires_at: str
    agent_id: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejection_reason: Optional[str] = None


class ApproveRequest(BaseModel):
    """Request to approve a trade."""
    approved_by: str = "api_operator"


class RejectRequest(BaseModel):
    """Request to reject a trade."""
    reason: str = "Rejected by operator"
    rejected_by: str = "api_operator"


class UpdateMCPSettingsRequest(BaseModel):
    """Request to update MCP settings."""
    ai_trading_mode: Optional[str] = None
    require_approval: Optional[bool] = None
    max_position_usd: Optional[float] = None
    daily_loss_limit_usd: Optional[float] = None


@router.get("/status", response_model=MCPStatusResponse)
async def get_mcp_status() -> MCPStatusResponse:
    """Get MCP server status and settings."""
    settings = get_settings()
    pending = get_pending_approvals()
    stats = get_audit_stats(days=7)

    return MCPStatusResponse(
        enabled=settings.mcp.enabled,
        ai_trading_mode=settings.mcp.ai_trading_mode,
        require_approval=settings.mcp.require_approval,
        max_position_usd=settings.mcp.max_position_usd,
        daily_loss_limit_usd=settings.mcp.daily_loss_limit_usd,
        pending_approvals=len(pending),
        audit_stats=stats,
    )


@router.get("/pending")
async def list_pending_approvals() -> dict:
    """List pending trade approvals."""
    pending = get_pending_approvals()

    # Convert datetime to string for JSON serialization
    result = []
    for p in pending:
        result.append({
            **p,
            "created_at": p["created_at"].isoformat() if isinstance(p["created_at"], datetime) else p["created_at"],
            "expires_at": p["expires_at"].isoformat() if isinstance(p["expires_at"], datetime) else p["expires_at"],
        })

    return {"pending": result, "count": len(result)}


@router.get("/pending/{approval_id}")
async def get_pending_approval(approval_id: str) -> dict:
    """Get a specific pending approval."""
    approval = get_approval(approval_id)

    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval not found: {approval_id}")

    return {
        **approval,
        "created_at": approval["created_at"].isoformat() if isinstance(approval["created_at"], datetime) else approval["created_at"],
        "expires_at": approval["expires_at"].isoformat() if isinstance(approval["expires_at"], datetime) else approval["expires_at"],
    }


@router.post("/pending/{approval_id}/approve")
async def approve_pending_trade(approval_id: str, request: ApproveRequest) -> dict:
    """Approve a pending AI trade."""
    try:
        result = await approve_trade(approval_id, approved_by=request.approved_by)
        return {
            "success": True,
            "approval_id": approval_id,
            "status": "approved",
            "execution_result": result.get("execution_result"),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pending/{approval_id}/reject")
async def reject_pending_trade(approval_id: str, request: RejectRequest) -> dict:
    """Reject a pending AI trade."""
    try:
        await reject_trade(approval_id, reason=request.reason, rejected_by=request.rejected_by)
        return {
            "success": True,
            "approval_id": approval_id,
            "status": "rejected",
            "reason": request.reason,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/settings")
async def update_mcp_settings(request: UpdateMCPSettingsRequest) -> dict:
    """Update MCP settings (runtime only).

    Note: These are runtime changes. For persistence, update environment variables.
    """
    settings = get_settings()

    if request.ai_trading_mode is not None:
        if request.ai_trading_mode not in ("disabled", "shadow", "live"):
            raise HTTPException(status_code=400, detail="Invalid ai_trading_mode")
        settings.mcp.ai_trading_mode = request.ai_trading_mode  # type: ignore

    if request.require_approval is not None:
        settings.mcp.require_approval = request.require_approval  # type: ignore

    if request.max_position_usd is not None:
        settings.mcp.max_position_usd = request.max_position_usd  # type: ignore

    if request.daily_loss_limit_usd is not None:
        settings.mcp.daily_loss_limit_usd = request.daily_loss_limit_usd  # type: ignore

    return {
        "success": True,
        "settings": {
            "ai_trading_mode": settings.mcp.ai_trading_mode,
            "require_approval": settings.mcp.require_approval,
            "max_position_usd": settings.mcp.max_position_usd,
            "daily_loss_limit_usd": settings.mcp.daily_loss_limit_usd,
        },
    }


@router.get("/audit")
async def get_audit(tail: int = 50, agent_id: Optional[str] = None) -> dict:
    """Get AI agent audit log entries."""
    logs = get_audit_logs(tail=tail, agent_id=agent_id)
    return {"logs": logs, "count": len(logs)}


@router.get("/audit/stats")
async def get_audit_statistics(days: int = 7) -> dict:
    """Get audit log statistics."""
    stats = get_audit_stats(days=days)
    return stats
