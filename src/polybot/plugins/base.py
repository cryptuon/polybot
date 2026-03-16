"""AI model plugin interface.

Provides the base class for implementing custom AI/ML models
for probability prediction in the AI Model strategy.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MarketContext(BaseModel):
    """Context passed to AI model for prediction.

    Contains all relevant information about a market that
    the model can use to make probability predictions.
    """

    market_id: str = Field(description="Market condition ID")
    question: str = Field(description="Market question text")
    description: Optional[str] = Field(default=None, description="Market description")

    # Current prices
    current_yes_price: float = Field(description="Current YES price (0-1)")
    current_no_price: float = Field(description="Current NO price (0-1)")
    spread: float = Field(description="Current bid-ask spread")

    # Volume and liquidity
    volume_24h: Optional[float] = Field(default=None, description="24h volume in USD")
    liquidity: Optional[float] = Field(default=None, description="Current liquidity")

    # Timing
    end_date: Optional[str] = Field(default=None, description="Market end date ISO string")
    hours_remaining: Optional[float] = Field(default=None, description="Hours until resolution")

    # Categorization
    tags: List[str] = Field(default_factory=list, description="Market tags/categories")
    event_title: Optional[str] = Field(default=None, description="Parent event title")

    # Historical data (optional - plugin can request more)
    price_history: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Recent price history"
    )


class Prediction(BaseModel):
    """Model prediction output.

    Contains the model's probability estimate along with
    confidence and optional reasoning.
    """

    yes_probability: float = Field(
        ge=0, le=1, description="Predicted probability of YES outcome (0-1)"
    )
    confidence: float = Field(
        ge=0, le=1, description="Model's confidence in prediction (0-1)"
    )
    reasoning: Optional[str] = Field(
        default=None, description="Optional explanation of prediction"
    )

    # Additional metadata
    model_version: Optional[str] = Field(default=None, description="Model version used")
    features_used: Optional[List[str]] = Field(
        default=None, description="Features that influenced prediction"
    )

    @property
    def no_probability(self) -> float:
        """Get implied NO probability."""
        return 1 - self.yes_probability

    @property
    def edge_vs_market(self) -> float:
        """Calculate edge vs market price (requires context)."""
        # This would need market price context
        return 0.0


class AIModelPlugin(ABC):
    """Base class for AI model plugins.

    To create a custom prediction model:

    1. Subclass AIModelPlugin
    2. Implement the required methods:
       - initialize(): Load model weights, connect to APIs, etc.
       - predict(): Generate probability predictions
       - should_update(): Return True when model needs retraining

    3. Place your plugin in:
       - src/polybot/plugins/ (built-in)
       - Path specified by POLYBOT_AI_PLUGIN_PATH env var
       - Package with entry point: polybot.plugins

    Example:
        class MyModelPlugin(AIModelPlugin):
            name = "my_model"
            version = "1.0.0"

            async def initialize(self, config: dict) -> None:
                self.model = load_my_model(config["model_path"])

            async def predict(self, context: MarketContext) -> Prediction:
                prob = self.model.predict(context.question)
                return Prediction(
                    yes_probability=prob,
                    confidence=0.8,
                    reasoning="Based on historical patterns"
                )

            async def should_update(self) -> bool:
                return self.model.age_days > 7
    """

    # Plugin metadata - override in subclass
    name: str = "base"
    version: str = "1.0.0"
    description: str = "Base AI model plugin"

    # Capabilities
    supports_batch: bool = False
    supports_streaming: bool = False
    max_context_length: int = 10000

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the model.

        Called once when the plugin is loaded. Use this to:
        - Load model weights
        - Connect to external APIs
        - Initialize any resources

        Args:
            config: Configuration dict from AI_MODEL_CONFIG env var
        """
        pass

    @abstractmethod
    async def predict(self, context: MarketContext) -> Prediction:
        """Generate probability prediction for a market.

        This is the main prediction method. Given market context,
        return your model's probability estimate.

        Args:
            context: Market information and context

        Returns:
            Prediction with probability and confidence
        """
        pass

    @abstractmethod
    async def should_update(self) -> bool:
        """Return True if model needs retraining/updating.

        Called periodically to check if the model should be updated.
        Return True to trigger a call to update().

        Returns:
            True if update is needed
        """
        pass

    async def predict_batch(self, contexts: List[MarketContext]) -> List[Prediction]:
        """Batch prediction for multiple markets.

        Override for efficient batch processing. Default implementation
        calls predict() sequentially.

        Args:
            contexts: List of market contexts

        Returns:
            List of predictions
        """
        return [await self.predict(ctx) for ctx in contexts]

    async def update(self) -> None:
        """Update/retrain the model.

        Called when should_update() returns True. Use this to:
        - Retrain on recent data
        - Update model weights
        - Refresh external data sources
        """
        pass

    async def shutdown(self) -> None:
        """Cleanup resources.

        Called when the plugin is being unloaded. Use this to:
        - Close connections
        - Save state
        - Release resources
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """Get plugin information.

        Returns:
            Dict with plugin metadata
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "supports_batch": self.supports_batch,
            "supports_streaming": self.supports_streaming,
        }
