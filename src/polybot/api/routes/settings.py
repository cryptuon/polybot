"""Settings endpoints.

Strategy config queries are routed through the state service via IPC.
"""

from fastapi import APIRouter, Depends

from polybot.api.schemas import (
    SettingsResponse,
    SettingsUpdateRequest,
    RiskSettings,
    StrategyConfig,
    RiskStatusResponse,
    SystemStatusResponse,
    ServiceStatus,
)
from polybot.config import get_settings, reload_settings
from polybot.db.state_client import StateClient, get_state_client
from polybot.strategies import STRATEGY_REGISTRY


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_current_settings(
    client: StateClient = Depends(get_state_client),
) -> SettingsResponse:
    """Get current settings."""
    settings = get_settings()

    # Get strategy configs from database
    strategy_configs = {}
    for name in STRATEGY_REGISTRY.keys():
        db_config = await client.get_strategy_config(name)
        if db_config:
            strategy_configs[name] = StrategyConfig(
                enabled=db_config["enabled"],
                shadow=db_config.get("shadow", False),
                config=db_config["config"],
            )
        else:
            strategy_configs[name] = StrategyConfig(enabled=False, shadow=False, config={})

    return SettingsResponse(
        risk=RiskSettings(
            max_position_size_usd=settings.risk.max_position_size_usd,
            max_total_exposure_usd=settings.risk.max_total_exposure_usd,
            daily_loss_limit_usd=settings.risk.daily_loss_limit_usd,
            max_open_orders=settings.risk.max_open_orders,
        ),
        strategies=strategy_configs,
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpdateRequest,
    client: StateClient = Depends(get_state_client),
) -> SettingsResponse:
    """Update settings.

    Note: Risk settings require restart to take effect.
    Strategy settings are applied immediately.
    """
    # Update strategy configs in database
    if request.strategies:
        for name, config in request.strategies.items():
            if name in STRATEGY_REGISTRY:
                await client.save_strategy_config(
                    name=name,
                    enabled=config.enabled,
                    config=config.config,
                    shadow=config.shadow,
                )

    # Return updated settings
    return await get_current_settings(client)


@router.get("/risk", response_model=RiskStatusResponse)
async def get_risk_status() -> RiskStatusResponse:
    """Get current risk status."""
    settings = get_settings()

    # In a real implementation, this would query the executor service
    # For now, return static data
    return RiskStatusResponse(
        daily_pnl=0,
        total_exposure=0,
        open_orders=0,
        open_positions=0,
        risk_limits={
            "daily_loss_limit": settings.risk.daily_loss_limit_usd,
            "max_exposure": settings.risk.max_total_exposure_usd,
            "max_position": settings.risk.max_position_size_usd,
            "max_orders": float(settings.risk.max_open_orders),
        },
    )


@router.get("/system", response_model=SystemStatusResponse)
async def get_system_status() -> SystemStatusResponse:
    """Get system status."""
    import time

    # In a real implementation, this would query the service manager
    # For now, return static data
    services = [
        ServiceStatus(name="scanner", status="unknown"),
        ServiceStatus(name="executor", status="unknown"),
        ServiceStatus(name="analytics", status="unknown"),
    ]

    return SystemStatusResponse(
        services=services,
        healthy=True,
        uptime_seconds=0,
    )


@router.post("/reload")
async def reload_configuration() -> dict:
    """Reload configuration from environment."""
    reload_settings()
    return {"message": "Configuration reloaded"}
