"""Base strategy interface for all trading strategies."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from polybot.config import Settings, get_settings
from polybot.core.nng import NNGSubscriber, NNGPusher, NNGPublisher
from polybot.db.state_client import StateClient, get_state_client
from polybot.db.strategy_logs_client import StrategyLogsClient, get_strategy_logs_client
from polybot.db.sqlite_store import SQLiteStore
from polybot.models.messages import PriceUpdate, Signal, SignalAction, EventType, SystemEvent
from polybot.models.position import Position


@dataclass
class StrategyConfig:
    """Base configuration for strategies.

    Note: 'enabled' is managed via database state, not config.
    """

    max_position_size: float = 100.0
    max_positions: int = 10


@dataclass
class StrategyState:
    """Runtime state for a strategy."""

    positions: Dict[str, Position] = field(default_factory=dict)
    signals_sent: int = 0
    last_scan_time: float = 0
    scans_performed: int = 0
    opportunities_found: int = 0
    entries: int = 0
    exits: int = 0
    errors: int = 0


class BaseStrategy(ABC):
    """Abstract base class for trading strategies.

    All strategies must implement:
    - scan(): Analyze prices and generate signals
    - should_exit(): Determine if positions should be closed

    Lifecycle:
    1. Strategy subscribes to price updates from scanner
    2. On each price update, scan() is called
    3. If scan() returns signals, they are sent to executor
    4. should_exit() is called for open positions
    """

    name: str = "base"
    description: str = "Base strategy"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize the strategy.

        Args:
            settings: Configuration settings
        """
        self._settings = settings or get_settings()
        self._config = self._get_config()
        self._state = StrategyState()
        self._running = False

        self._price_subscriber: Optional[NNGSubscriber] = None
        self._signal_pusher: Optional[NNGPusher] = None
        self._event_publisher: Optional[NNGPublisher] = None
        self._state_client: Optional[StateClient] = None
        self._logs_client: Optional[StrategyLogsClient] = None
        self._sqlite: Optional[SQLiteStore] = None

        self._logger = logging.getLogger(f"polybot.strategies.{self.name}")

        # Price cache
        self._prices: Dict[str, PriceUpdate] = {}

        # Scan logging interval (log every N scans to avoid spam)
        self._scan_log_interval = 100
        self._last_log_time = 0

        # Run tracking
        self._run_id: Optional[int] = None

    @abstractmethod
    def _get_config(self) -> StrategyConfig:
        """Get strategy-specific configuration.

        Override in subclass to return appropriate config.
        """
        pass

    @property
    def config(self) -> StrategyConfig:
        """Get strategy configuration."""
        return self._config

    async def start(self) -> None:
        """Start the strategy.

        Note: The caller (strategy runner) is responsible for checking
        if the strategy is enabled in the database before calling start().
        """
        self._logger.info(f"Starting {self.name} strategy...")

        # Initialize NNG sockets
        self._price_subscriber = NNGSubscriber(self._settings.nng.prices_address)
        await self._price_subscriber.open()

        self._signal_pusher = NNGPusher(self._settings.nng.signals_address)
        await self._signal_pusher.open()

        # Initialize event publisher for strategy events
        self._event_publisher = NNGPublisher(
            self._settings.nng.service_events_address(f"strategy_{self.name}")
        )
        await self._event_publisher.open()

        # Initialize state client (queries state service via NNG)
        self._state_client = await get_state_client()

        # Initialize SQLite store for direct market queries
        self._sqlite = SQLiteStore()
        await self._sqlite.connect()

        # Initialize strategy logs client
        try:
            self._logs_client = await get_strategy_logs_client()
            # Start a new run session
            config_dict = {k: v for k, v in vars(self._config).items() if not k.startswith("_")}
            self._run_id = await self._logs_client.start_run(self.name, config_dict)
            self._logger.info(f"Started run session #{self._run_id}")

            # Log strategy start
            await self._logs_client.log(
                strategy=self.name,
                log_type="start",
                level="INFO",
                message=f"Strategy {self.name} started",
                metadata=config_dict,
            )
        except Exception as e:
            self._logger.warning(f"Failed to connect to strategy logs service: {e}")
            self._logs_client = None

        # Load existing positions
        await self._load_positions()

        # Call subclass initialization
        await self._on_start()

        self._running = True
        self._logger.info(f"{self.name} strategy started")

        # Publish strategy started event
        await self._publish_event(EventType.STRATEGY_STARTED, {
            "strategy": self.name,
            "config": {k: v for k, v in vars(self._config).items() if not k.startswith("_")},
        })

    async def stop(self) -> None:
        """Stop the strategy."""
        self._logger.info(f"Stopping {self.name} strategy...")
        self._running = False

        await self._on_stop()

        # End the run session in strategy logs
        if self._logs_client and self._run_id:
            try:
                await self._logs_client.log(
                    strategy=self.name,
                    log_type="stop",
                    level="INFO",
                    message=f"Strategy {self.name} stopped",
                    metadata={
                        "scans": self._state.scans_performed,
                        "signals": self._state.signals_sent,
                        "opportunities": self._state.opportunities_found,
                        "entries": self._state.entries,
                        "exits": self._state.exits,
                        "errors": self._state.errors,
                    },
                )
                await self._logs_client.end_run(
                    run_id=self._run_id,
                    scans=self._state.scans_performed,
                    signals=self._state.signals_sent,
                    entries=self._state.entries,
                    exits=self._state.exits,
                    errors=self._state.errors,
                    status="stopped",
                )
                self._logger.info(f"Ended run session #{self._run_id}")
            except Exception as e:
                self._logger.warning(f"Failed to end run session: {e}")

        # Publish strategy stopped event before closing publisher
        await self._publish_event(EventType.STRATEGY_STOPPED, {
            "strategy": self.name,
            "scans_performed": self._state.scans_performed,
            "opportunities_found": self._state.opportunities_found,
            "signals_sent": self._state.signals_sent,
        })

        if self._price_subscriber:
            await self._price_subscriber.close()

        if self._signal_pusher:
            await self._signal_pusher.close()

        if self._event_publisher:
            await self._event_publisher.close()

        if self._sqlite:
            await self._sqlite.close()

        self._logger.info(f"{self.name} strategy stopped")

    async def run(self) -> None:
        """Run the strategy main loop."""
        await self.start()

        if not self._running:
            return

        try:
            await self._main_loop()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def _main_loop(self) -> None:
        """Main strategy loop - process price updates."""
        if not self._price_subscriber:
            return

        async for msg in self._price_subscriber.messages():
            if not self._running:
                break

            try:
                if msg.get("type") == "price":
                    price_update = PriceUpdate.from_dict(msg)
                    await self._handle_price_update(price_update)
            except Exception as e:
                self._logger.error(f"Error processing update: {e}")

    async def _handle_price_update(self, update: PriceUpdate) -> None:
        """Handle a price update.

        Args:
            update: Price update from scanner
        """
        # Cache price
        self._prices[update.token_id] = update

        # Track scan start time
        scan_start = time.time()

        # Run strategy scan
        signals = await self.scan(update)

        # Update scan stats
        scan_duration = time.time() - scan_start
        self._state.scans_performed += 1
        self._state.last_scan_time = scan_start

        # Log scan activity periodically (every 100 scans or every 60 seconds)
        now = time.time()
        if (
            self._state.scans_performed % self._scan_log_interval == 0
            or now - self._last_log_time > 60
        ):
            self._logger.info(
                f"Scan #{self._state.scans_performed}: "
                f"opportunities={self._state.opportunities_found}, "
                f"signals={self._state.signals_sent}, "
                f"positions={len(self._state.positions)}"
            )
            self._last_log_time = now

        # Send signals and publish events
        if signals:
            self._state.opportunities_found += len(signals)
            self._logger.info(
                f"Found {len(signals)} signal(s) for market {update.market_id[:8]}..."
            )

            for signal in signals:
                await self._send_signal(signal)

                # Publish signal event with details
                await self._publish_event(EventType.ALERT, {
                    "strategy": self.name,
                    "type": "signal",
                    "action": signal.action.value,
                    "market_id": signal.market_id,
                    "token_id": signal.token_id,
                    "price": signal.price,
                    "size": signal.size,
                    "reason": signal.reason,
                    "confidence": signal.confidence,
                })

        # Check exits for existing positions
        for key, position in list(self._state.positions.items()):
            if position.token_id == update.token_id:
                position.update_unrealized_pnl(update.mid)

                if await self.should_exit(position, update):
                    self._logger.info(
                        f"Exit condition met for position {position.market_id[:8]}..."
                    )
                    exit_signal = Signal(
                        strategy=self.name,
                        market_id=position.market_id,
                        token_id=position.token_id,
                        action=SignalAction.CLOSE,
                        price=update.mid,
                        size=position.size,
                        reason="Exit condition met",
                    )
                    await self._send_signal(exit_signal)

    async def _send_signal(self, signal: Signal) -> None:
        """Send a trading signal to executor.

        Args:
            signal: Trading signal
        """
        if not self._signal_pusher:
            return

        self._logger.info(
            f"Signal: {signal.action.value} {signal.size}@{signal.price} "
            f"for {signal.market_id} ({signal.reason})"
        )

        # Log signal to strategy logs service
        if self._logs_client:
            try:
                await self._logs_client.log(
                    strategy=self.name,
                    log_type="signal",
                    level="SIGNAL",
                    message=f"{signal.action.value} {signal.size:.4f}@{signal.price:.4f} - {signal.reason}",
                    market_id=signal.market_id,
                    token_id=signal.token_id,
                    price=signal.price,
                    size=signal.size,
                    action=signal.action.value,
                    reason=signal.reason,
                    confidence=signal.confidence,
                )
            except Exception as e:
                self._logger.warning(f"Failed to log signal: {e}")

        await self._signal_pusher.push(signal.to_dict())
        self._state.signals_sent += 1

    async def _load_positions(self) -> None:
        """Load existing positions for this strategy."""
        if not self._state_client:
            return

        positions = await self._state_client.get_open_positions(strategy=self.name)
        for pos in positions:
            key = f"{pos.market_id}:{pos.token_id}"
            self._state.positions[key] = pos

        self._logger.info(f"Loaded {len(positions)} positions")

    # =========================================================================
    # Abstract methods - must be implemented by subclasses
    # =========================================================================

    @abstractmethod
    async def scan(self, update: PriceUpdate) -> List[Signal]:
        """Scan for trading opportunities.

        Called on each price update. Analyze the update and return
        any trading signals.

        Args:
            update: Price update from scanner

        Returns:
            List of trading signals (empty if no opportunities)
        """
        pass

    @abstractmethod
    async def should_exit(self, position: Position, update: PriceUpdate) -> bool:
        """Determine if a position should be closed.

        Called for each open position when its token gets a price update.

        Args:
            position: Open position to evaluate
            update: Current price update

        Returns:
            True if position should be closed
        """
        pass

    # =========================================================================
    # Optional hooks - can be overridden by subclasses
    # =========================================================================

    async def _on_start(self) -> None:
        """Called when strategy starts. Override for custom initialization."""
        pass

    async def _on_stop(self) -> None:
        """Called when strategy stops. Override for custom cleanup."""
        pass

    # =========================================================================
    # Utility methods
    # =========================================================================

    def get_price(self, token_id: str) -> Optional[PriceUpdate]:
        """Get cached price for a token.

        Args:
            token_id: Token ID

        Returns:
            Cached price update or None
        """
        return self._prices.get(token_id)

    def get_position(self, market_id: str, token_id: str) -> Optional[Position]:
        """Get position for a market/token.

        Args:
            market_id: Market condition ID
            token_id: Token ID

        Returns:
            Position or None
        """
        return self._state.positions.get(f"{market_id}:{token_id}")

    def has_position(self, market_id: str) -> bool:
        """Check if strategy has a position in market.

        Args:
            market_id: Market condition ID

        Returns:
            True if position exists
        """
        return any(
            pos.market_id == market_id for pos in self._state.positions.values()
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics.

        Returns:
            Dict of statistics
        """
        return {
            "name": self.name,
            "running": self._running,
            "positions": len(self._state.positions),
            "signals_sent": self._state.signals_sent,
            "scans_performed": self._state.scans_performed,
            "opportunities_found": self._state.opportunities_found,
        }

    async def _publish_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """Publish a strategy event.

        Args:
            event_type: Type of event
            data: Event data
        """
        if not self._event_publisher:
            return

        event = SystemEvent(
            source=f"strategy_{self.name}",
            event_type=event_type,
            data=data,
        )
        await self._event_publisher.publish(event.to_dict())
