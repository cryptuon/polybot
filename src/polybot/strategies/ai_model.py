"""AI probability model strategy.

Uses machine learning models to estimate true probabilities and trades
when the model prediction differs significantly from market price.

Supports pluggable AI models via the plugin system, allowing different
prediction approaches (LLMs, statistical models, ensemble methods).

Example:
    Model predicts "Trump wins" at 60% probability
    Market price is 52%
    Edge = 8% -> Signal to BUY YES

Production improvements:
    - Cooldown per market to prevent signal spam
    - Max concurrent positions limit
    - Prediction staleness tracking
    - Confidence decay over time
    - Better exit logic with trailing edge
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import importlib
import json

from polybot.config import Settings
from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction
from polybot.plugins.example_plugin import get_all_plugins
from polybot.models.messages import PriceUpdate, Signal, SignalAction
from polybot.models.position import Position
from polybot.strategies.base import BaseStrategy, StrategyConfig


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class AIModelConfig(StrategyConfig):
    """AI model strategy configuration.

    Attributes:
        plugin_name: Name of the AI plugin to use
        plugin_config: Configuration dict passed to the plugin
        min_confidence: Minimum model confidence to consider signal
        min_edge: Minimum edge (model - market) to trigger entry
        max_position_size: Maximum USD per position
        max_concurrent_positions: Maximum number of simultaneous positions
        signal_cooldown_sec: Minimum seconds between signals for same market
        update_interval_hours: How often to refresh model weights
        prediction_max_age_sec: Maximum age of cached prediction before stale
        edge_decay_rate: How much edge decays per hour (for exit logic)
        min_price: Minimum token price (prevents extreme sizes)
        max_price: Maximum token price
    """
    plugin_name: str = "simple_heuristic"
    plugin_config: Dict[str, Any] = field(default_factory=dict)
    min_confidence: float = 0.7
    min_edge: float = 0.05  # 5% edge required
    max_position_size: float = 200.0
    max_concurrent_positions: int = 10
    signal_cooldown_sec: float = 300.0  # 5 minute cooldown
    update_interval_hours: int = 24
    prediction_max_age_sec: float = 3600.0  # 1 hour max prediction age
    edge_decay_rate: float = 0.01  # 1% per hour
    min_price: float = 0.05
    max_price: float = 0.95


# =============================================================================
# State Tracking
# =============================================================================

@dataclass
class CachedPrediction:
    """Cached prediction with timestamp for staleness tracking.

    Attributes:
        prediction: The model's prediction
        timestamp: When prediction was made
        market_price_at_prediction: Market price when prediction was made
    """
    prediction: Prediction
    timestamp: datetime
    market_price_at_prediction: float

    def age_seconds(self) -> float:
        """Get age of this prediction in seconds."""
        return (datetime.utcnow() - self.timestamp).total_seconds()

    def age_hours(self) -> float:
        """Get age of this prediction in hours."""
        return self.age_seconds() / 3600

    def is_stale(self, max_age_sec: float) -> bool:
        """Check if prediction is stale.

        Args:
            max_age_sec: Maximum age in seconds

        Returns:
            True if prediction is older than max age
        """
        return self.age_seconds() > max_age_sec


@dataclass
class AIPosition:
    """Tracks an AI-driven position.

    Attributes:
        market_id: Market ID
        token_id: Token ID
        side: YES or NO
        entry_edge: Edge at entry
        entry_confidence: Model confidence at entry
        entry_time: When position was opened
    """
    market_id: str
    token_id: str
    side: str
    entry_edge: float
    entry_confidence: float
    entry_time: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# Strategy Implementation
# =============================================================================

class AIModelStrategy(BaseStrategy):
    """AI-powered prediction strategy.

    Uses configurable AI/ML models to estimate probabilities and trades
    when model has sufficient edge over market price.

    Workflow:
        1. Load configured AI model plugin
        2. For each market update, get model prediction
        3. Calculate edge (model probability - market price)
        4. If confidence high and edge > threshold, generate signal
        5. Exit when edge disappears or confidence drops

    Risk Management:
        - Cooldown prevents repeated signals for same market
        - Max concurrent positions limits exposure
        - Prediction staleness check ensures fresh data
        - Edge decay for exit logic
    """

    name = "ai_model"
    description = "AI-powered probability prediction"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize AI model strategy.

        Args:
            settings: Application settings, uses defaults if not provided
        """
        super().__init__(settings)

        # AI plugin instance
        self._plugin: Optional[AIModelPlugin] = None

        # Prediction cache: market_id -> CachedPrediction
        self._predictions: Dict[str, CachedPrediction] = {}

        # Last model update time
        self._last_model_update: Optional[datetime] = None

        # Cooldown tracking: market_id -> last_signal_timestamp
        self._last_signal_time: Dict[str, float] = {}

        # Active AI positions: market_id -> AIPosition
        self._ai_positions: Dict[str, AIPosition] = {}

    def _get_config(self) -> StrategyConfig:
        """Load AI model configuration from settings."""
        ai_settings = self._settings.ai_model
        plugin_config = {}

        # Parse plugin config JSON
        try:
            if ai_settings.model_config_json:
                plugin_config = json.loads(ai_settings.model_config_json)
        except json.JSONDecodeError:
            self._logger.warning("Failed to parse AI model config JSON")

        return AIModelConfig(
            plugin_name=ai_settings.model_plugin,
            plugin_config=plugin_config,
            min_confidence=ai_settings.min_confidence,
            min_edge=ai_settings.min_edge,
        )

    @property
    def ai_config(self) -> AIModelConfig:
        """Get typed configuration."""
        return self._config  # type: ignore

    async def _on_start(self) -> None:
        """Load and initialize AI model plugin."""
        plugin_name = self.ai_config.plugin_name
        self._logger.info(f"Loading AI plugin: {plugin_name}")

        self._plugin = await self._load_plugin(plugin_name)

        if self._plugin:
            await self._plugin.initialize(self.ai_config.plugin_config)
            self._logger.info(
                f"Loaded AI plugin: {self._plugin.name} v{self._plugin.version}"
            )
            self._last_model_update = datetime.utcnow()
        else:
            self._logger.error(f"Failed to load AI plugin: {plugin_name}")

    async def _on_stop(self) -> None:
        """Clean up plugin resources."""
        if self._plugin:
            await self._plugin.shutdown()

    async def _load_plugin(self, name: str) -> Optional[AIModelPlugin]:
        """Load an AI model plugin by name.

        Searches in order:
            1. Registered plugins (from example_plugin.get_all_plugins())
            2. polybot.plugins.<name> module
            3. polybot.plugins.<name>_plugin module

        Args:
            name: Plugin name to load

        Returns:
            Plugin instance or None if not found
        """
        # Check registered plugins first
        all_plugins = get_all_plugins()
        if name in all_plugins:
            return all_plugins[name]()

        # Try loading from module
        for module_name in [f"polybot.plugins.{name}", f"polybot.plugins.{name}_plugin"]:
            try:
                module = importlib.import_module(module_name)
                plugin_class = getattr(module, "Plugin", None)
                if plugin_class and issubclass(plugin_class, AIModelPlugin):
                    return plugin_class()
            except (ImportError, AttributeError):
                continue

        return None

    async def scan(self, update: PriceUpdate) -> List[Signal]:
        """Scan for AI-predicted opportunities.

        Gets model prediction for the market and generates signal
        if edge exceeds threshold.

        Args:
            update: Price update

        Returns:
            List of signals (0 or 1)
        """
        signals: List[Signal] = []
        now = time.time()

        # =================================================================
        # Step 1: Validate preconditions
        # =================================================================

        if not self._plugin or not self._sqlite:
            return signals

        if not self._is_valid_price(update):
            return signals

        # =================================================================
        # Step 2: Check max concurrent positions
        # =================================================================

        if len(self._ai_positions) >= self.ai_config.max_concurrent_positions:
            return signals

        # =================================================================
        # Step 3: Check if we already have a position
        # =================================================================

        if update.market_id in self._ai_positions:
            return signals

        # =================================================================
        # Step 4: Check cooldown for this market
        # =================================================================

        last_signal = self._last_signal_time.get(update.market_id, 0)
        if (now - last_signal) < self.ai_config.signal_cooldown_sec:
            return signals

        # =================================================================
        # Step 5: Get market info
        # =================================================================

        market = await self._sqlite.get_market(update.market_id)
        if not market:
            return signals

        # =================================================================
        # Step 6: Get or refresh prediction
        # =================================================================

        prediction = await self._get_prediction(market, update)
        if not prediction:
            return signals

        # =================================================================
        # Step 7: Check confidence threshold
        # =================================================================

        if prediction.confidence < self.ai_config.min_confidence:
            return signals

        # =================================================================
        # Step 8: Calculate edge
        # =================================================================

        # Edge = model probability - market price
        # Positive edge on YES means model thinks YES is underpriced
        edge = prediction.yes_probability - update.mid

        if abs(edge) < self.ai_config.min_edge:
            return signals

        # =================================================================
        # Step 9: Generate signal
        # =================================================================

        position_size_usd = min(
            self.ai_config.max_position_size,
            self._settings.risk.max_position_size_usd,
        )

        if edge > 0:
            # Model thinks YES is underpriced -> BUY YES
            token_id = market.outcome_yes_token
            price = update.ask
            side = "YES"
            size = position_size_usd / price

            signals.append(
                Signal(
                    strategy=self.name,
                    market_id=market.id,
                    token_id=token_id,
                    action=SignalAction.BUY,
                    price=price,
                    size=size,
                    reason=(
                        f"AI: pred={prediction.yes_probability:.2f} vs market={update.mid:.2f}, "
                        f"edge={edge*100:.1f}%, conf={prediction.confidence:.2f}"
                    ),
                    confidence=prediction.confidence,
                    metadata={
                        "model_prediction": prediction.yes_probability,
                        "market_price": update.mid,
                        "edge": edge,
                        "reasoning": prediction.reasoning,
                    },
                )
            )
        else:
            # Model thinks YES is overpriced -> BUY NO (short proxy)
            token_id = market.outcome_no_token
            # NO price = 1 - YES bid (what we pay for NO)
            price = 1.0 - update.bid
            side = "NO"
            size = position_size_usd / price

            signals.append(
                Signal(
                    strategy=self.name,
                    market_id=market.id,
                    token_id=token_id,
                    action=SignalAction.BUY,
                    price=price,
                    size=size,
                    reason=(
                        f"AI: pred={prediction.yes_probability:.2f} vs market={update.mid:.2f}, "
                        f"edge={abs(edge)*100:.1f}% (SHORT), conf={prediction.confidence:.2f}"
                    ),
                    confidence=prediction.confidence,
                    metadata={
                        "model_prediction": prediction.yes_probability,
                        "market_price": update.mid,
                        "edge": edge,
                        "reasoning": prediction.reasoning,
                    },
                )
            )

        # =================================================================
        # Step 10: Track position and cooldown
        # =================================================================

        if signals:
            self._last_signal_time[update.market_id] = now
            self._ai_positions[update.market_id] = AIPosition(
                market_id=update.market_id,
                token_id=token_id,
                side=side,
                entry_edge=abs(edge),
                entry_confidence=prediction.confidence,
            )

            self._logger.info(
                f"AI signal: {market.question[:50]}...\n"
                f"  Prediction: {prediction.yes_probability:.2f} vs Market: {update.mid:.2f}\n"
                f"  Edge: {edge*100:.1f}%, Confidence: {prediction.confidence:.2f}"
            )

        # =================================================================
        # Step 11: Check if model needs updating
        # =================================================================

        await self._check_model_update()

        return signals

    def _is_valid_price(self, update: PriceUpdate) -> bool:
        """Validate that price update has valid values.

        Args:
            update: Price update to validate

        Returns:
            True if price is valid for trading
        """
        min_price = self.ai_config.min_price
        max_price = self.ai_config.max_price

        # Check for zero/null prices
        if not update.bid or not update.ask:
            return False

        if update.bid <= 0 or update.ask <= 0:
            return False

        # Check price bounds
        if update.bid < min_price or update.ask > max_price:
            return False

        # Check for invalid spread
        if update.bid >= update.ask:
            return False

        return True

    async def _get_prediction(
        self, market: Any, update: PriceUpdate
    ) -> Optional[Prediction]:
        """Get prediction for a market, using cache if fresh.

        Args:
            market: Market object
            update: Current price update

        Returns:
            Prediction or None if unavailable
        """
        cached = self._predictions.get(market.id)

        # Use cached prediction if fresh enough
        if cached and not cached.is_stale(self.ai_config.prediction_max_age_sec):
            return cached.prediction

        # Get fresh prediction from model
        try:
            context = MarketContext(
                market_id=market.id,
                question=market.question,
                description=market.description,
                current_yes_price=update.mid,
                current_no_price=1 - update.mid,
                spread=update.spread,
                volume_24h=market.volume_24h,
                liquidity=market.liquidity,
                end_date=market.end_date.isoformat() if market.end_date else None,
                hours_remaining=(
                    (market.end_date - datetime.utcnow()).total_seconds() / 3600
                    if market.end_date
                    else None
                ),
                tags=market.tags,
            )

            prediction = await self._plugin.predict(context)

            # Cache the prediction
            self._predictions[market.id] = CachedPrediction(
                prediction=prediction,
                timestamp=datetime.utcnow(),
                market_price_at_prediction=update.mid,
            )

            return prediction

        except Exception as e:
            self._logger.error(f"Prediction error for {market.id[:8]}: {e}")
            return None

    async def should_exit(self, position: Position, update: PriceUpdate) -> bool:
        """Check if AI position should exit.

        Exit conditions:
            1. Edge has disappeared (price moved to model's target)
            2. Model confidence dropped below threshold
            3. Prediction is stale and edge reversed
            4. Stop loss on significant unrealized loss

        Args:
            position: Current position
            update: Price update

        Returns:
            True if position should be closed
        """
        ai_pos = self._ai_positions.get(position.market_id)
        cached = self._predictions.get(position.market_id)

        if not cached:
            # No prediction cached, exit if position is old
            if ai_pos and ai_pos.entry_time:
                hours_open = (datetime.utcnow() - ai_pos.entry_time).total_seconds() / 3600
                if hours_open > 24:
                    self._logger.info(f"AI exit: no prediction and position open {hours_open:.1f}h")
                    self._cleanup_position(position.market_id)
                    return True
            return False

        prediction = cached.prediction

        # -----------------------------------------------------------------
        # Exit condition 1: Edge disappeared
        # -----------------------------------------------------------------

        if position.side == "YES":
            current_edge = prediction.yes_probability - update.mid
        else:
            # For NO position, edge is inverted
            current_edge = update.mid - prediction.yes_probability

        # Apply time decay to entry edge
        hours_open = 0
        if ai_pos and ai_pos.entry_time:
            hours_open = (datetime.utcnow() - ai_pos.entry_time).total_seconds() / 3600

        decayed_min_edge = max(
            self.ai_config.min_edge / 2,
            ai_pos.entry_edge - (self.ai_config.edge_decay_rate * hours_open) if ai_pos else self.ai_config.min_edge / 2
        )

        if current_edge < decayed_min_edge:
            self._logger.info(
                f"AI exit: edge reduced to {current_edge*100:.1f}% "
                f"(min: {decayed_min_edge*100:.1f}%)"
            )
            self._cleanup_position(position.market_id)
            return True

        # -----------------------------------------------------------------
        # Exit condition 2: Confidence dropped
        # -----------------------------------------------------------------

        min_confidence_exit = self.ai_config.min_confidence * 0.8
        if prediction.confidence < min_confidence_exit:
            self._logger.info(
                f"AI exit: confidence dropped to {prediction.confidence:.2f} "
                f"(min: {min_confidence_exit:.2f})"
            )
            self._cleanup_position(position.market_id)
            return True

        # -----------------------------------------------------------------
        # Exit condition 3: Stop loss (20% of position value)
        # -----------------------------------------------------------------

        if position.unrealized_pnl and position.cost_basis:
            loss_pct = -position.unrealized_pnl / position.cost_basis
            if loss_pct > 0.2:  # 20% loss
                self._logger.info(
                    f"AI exit: stop loss triggered at {loss_pct*100:.1f}% loss"
                )
                self._cleanup_position(position.market_id)
                return True

        return False

    def _cleanup_position(self, market_id: str) -> None:
        """Clean up position tracking.

        Args:
            market_id: Market ID to clean up
        """
        self._ai_positions.pop(market_id, None)

    async def _check_model_update(self) -> None:
        """Check if model needs updating and trigger update if needed."""
        if not self._plugin:
            return

        now = datetime.utcnow()

        # Check update interval
        if self._last_model_update:
            hours_since_update = (now - self._last_model_update).total_seconds() / 3600
            if hours_since_update < self.ai_config.update_interval_hours:
                return

        # Check if model wants update
        try:
            if await self._plugin.should_update():
                self._logger.info("Updating AI model...")
                await self._plugin.update()
                self._last_model_update = now

                # Clear prediction cache on model update
                self._predictions.clear()
                self._logger.info("AI model updated, cleared prediction cache")
        except Exception as e:
            self._logger.error(f"Model update error: {e}")

    # =========================================================================
    # Status Methods
    # =========================================================================

    def get_predictions(self) -> Dict[str, Dict[str, Any]]:
        """Get recent predictions with freshness info.

        Returns:
            Dictionary of market_id -> prediction details
        """
        return {
            market_id: {
                "yes_probability": cached.prediction.yes_probability,
                "confidence": cached.prediction.confidence,
                "reasoning": cached.prediction.reasoning,
                "age_seconds": cached.age_seconds(),
                "market_price_at_prediction": cached.market_price_at_prediction,
                "is_stale": cached.is_stale(self.ai_config.prediction_max_age_sec),
            }
            for market_id, cached in self._predictions.items()
        }

    def get_active_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get active AI positions.

        Returns:
            Dictionary of market_id -> position details
        """
        return {
            market_id: {
                "token_id": pos.token_id,
                "side": pos.side,
                "entry_edge": pos.entry_edge,
                "entry_confidence": pos.entry_confidence,
                "entry_time": pos.entry_time.isoformat(),
                "hours_open": (datetime.utcnow() - pos.entry_time).total_seconds() / 3600,
            }
            for market_id, pos in self._ai_positions.items()
        }

    def get_plugin_info(self) -> Optional[Dict[str, Any]]:
        """Get plugin information.

        Returns:
            Plugin info dict or None if no plugin loaded
        """
        if self._plugin:
            return self._plugin.get_info()
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        base_stats = super().get_stats()

        # Count fresh vs stale predictions
        fresh_predictions = sum(
            1 for c in self._predictions.values()
            if not c.is_stale(self.ai_config.prediction_max_age_sec)
        )
        stale_predictions = len(self._predictions) - fresh_predictions

        base_stats.update({
            "plugin_loaded": self._plugin is not None,
            "plugin_name": self._plugin.name if self._plugin else None,
            "active_positions": len(self._ai_positions),
            "cached_predictions": len(self._predictions),
            "fresh_predictions": fresh_predictions,
            "stale_predictions": stale_predictions,
            "last_model_update": self._last_model_update.isoformat() if self._last_model_update else None,
        })

        return base_stats
