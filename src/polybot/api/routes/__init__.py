"""API route modules."""

from polybot.api.routes.markets import router as markets_router
from polybot.api.routes.strategies import router as strategies_router
from polybot.api.routes.orders import router as orders_router
from polybot.api.routes.positions import router as positions_router
from polybot.api.routes.analytics import router as analytics_router
from polybot.api.routes.settings import router as settings_router
from polybot.api.routes.strategy_logs import router as strategy_logs_router
from polybot.api.routes.shadow import router as shadow_router

__all__ = [
    "markets_router",
    "strategies_router",
    "orders_router",
    "positions_router",
    "analytics_router",
    "settings_router",
    "strategy_logs_router",
    "shadow_router",
]
