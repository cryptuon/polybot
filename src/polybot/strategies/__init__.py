"""Trading strategies for PolyBot."""

from polybot.strategies.base import BaseStrategy, StrategyConfig
from polybot.strategies.arbitrage import ArbitrageStrategy
from polybot.strategies.stat_arb import StatArbStrategy
from polybot.strategies.ai_model import AIModelStrategy
from polybot.strategies.spread_farm import SpreadFarmStrategy
from polybot.strategies.copy_trade import CopyTradeStrategy
from polybot.strategies.resolution_arb import ResolutionArbStrategy
from polybot.strategies.calendar_spread import CalendarSpreadStrategy
from polybot.strategies.momentum import MomentumStrategy
from polybot.strategies.poll_divergence import PollDivergenceStrategy
from polybot.strategies.volume_spike import VolumeSpikeStrategy

__all__ = [
    "BaseStrategy",
    "StrategyConfig",
    "ArbitrageStrategy",
    "StatArbStrategy",
    "AIModelStrategy",
    "SpreadFarmStrategy",
    "CopyTradeStrategy",
    "ResolutionArbStrategy",
    "CalendarSpreadStrategy",
    "MomentumStrategy",
    "PollDivergenceStrategy",
    "VolumeSpikeStrategy",
]

# Strategy registry
STRATEGY_REGISTRY = {
    "arbitrage": ArbitrageStrategy,
    "stat_arb": StatArbStrategy,
    "ai_model": AIModelStrategy,
    "spread_farm": SpreadFarmStrategy,
    "copy_trade": CopyTradeStrategy,
    "resolution_arb": ResolutionArbStrategy,
    "calendar_spread": CalendarSpreadStrategy,
    "momentum": MomentumStrategy,
    "poll_divergence": PollDivergenceStrategy,
    "volume_spike": VolumeSpikeStrategy,
}
