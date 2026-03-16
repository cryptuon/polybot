"""Order executor service.

Responsible for:
- Receiving trading signals from strategies
- Validating orders against risk limits
- Executing orders via CLOB API
- Managing order lifecycle
- Position management
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from polybot.config import Settings
from polybot.core.client import PolymarketClient
from polybot.core.nng import NNGReplier, NNGPuller, NNGPublisher
from polybot.core.shadow_tracker import ShadowPositionTracker, get_shadow_tracker
from polybot.core.websocket import WebSocketManager, EventType as WSEventType
from polybot.db.state_client import StateClient, get_state_client
from polybot.db.strategy_logs_client import StrategyLogsClient, get_strategy_logs_client
from polybot.models.order import Order, OrderSide, OrderStatus, OrderType
from polybot.models.position import Position, PositionStatus
from polybot.models.trade import Trade
from polybot.models.messages import (
    Signal,
    SignalAction,
    OrderRequest,
    OrderResponse,
    EventType,
)
from polybot.risk import get_risk_manager, RiskManager, VenuePosition, AssetClass
from polybot.services.base import BaseService


logger = logging.getLogger(__name__)


class ExecutorService(BaseService):
    """Order execution service.

    Receives signals, validates risk, executes orders, and manages positions.
    """

    name = "executor"

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)

        self._client: Optional[PolymarketClient] = None
        self._ws_manager: Optional[WebSocketManager] = None

        self._signal_puller: Optional[NNGPuller] = None
        self._request_replier: Optional[NNGReplier] = None

        self._state_client: Optional[StateClient] = None
        self._logs_client: Optional[StrategyLogsClient] = None

        # Order tracking
        self._pending_orders: Dict[str, Order] = {}
        self._open_positions: Dict[str, Position] = {}

        # Risk manager - unified cross-venue risk layer
        self._risk_manager: RiskManager = get_risk_manager()

        # Shadow mode cache: strategy_name -> is_shadow
        self._shadow_mode_cache: Dict[str, bool] = {}

        # Shadow position tracker for paper trading analysis
        self._shadow_tracker: ShadowPositionTracker = get_shadow_tracker()

    async def _on_start(self) -> None:
        """Initialize executor resources."""
        # Initialize API client
        self._client = PolymarketClient()

        # Ensure L2 credentials
        if not self._client.has_credentials:
            self._logger.info("Creating API credentials...")
            await self._client.create_or_derive_api_key()

        # Initialize state client (queries state service via NNG)
        self._state_client = await get_state_client()

        # Initialize strategy logs client for execution logging
        try:
            self._logs_client = await get_strategy_logs_client()
            self._logger.info("Connected to strategy logs service")
        except Exception as e:
            self._logger.warning(f"Failed to connect to strategy logs service: {e}")
            self._logs_client = None

        # Initialize NNG sockets
        self._signal_puller = NNGPuller(self._settings.nng.signals_address)
        await self._signal_puller.open()

        self._request_replier = NNGReplier(self._settings.nng.executor_address)
        await self._request_replier.open()

        # Initialize WebSocket for order updates
        self._ws_manager = WebSocketManager()
        self._ws_manager.on_event(WSEventType.ORDER, self._handle_order_update)
        self._ws_manager.on_event(WSEventType.TRADE, self._handle_trade_update)

        # Load open positions
        await self._load_positions()

    async def _on_stop(self) -> None:
        """Cleanup executor resources."""
        if self._ws_manager:
            await self._ws_manager.stop()

        if self._signal_puller:
            await self._signal_puller.close()

        if self._request_replier:
            await self._request_replier.close()

        if self._client:
            await self._client.close()

    async def _run(self) -> None:
        """Main executor loop."""
        # Start WebSocket for order updates
        if self._ws_manager:
            await self._ws_manager.start()

        # Start signal processing
        signal_task = self.create_task(self._process_signals())

        # Start request handling
        request_task = self.create_task(self._handle_requests())

        # Start order monitoring
        monitor_task = self.create_task(self._monitor_orders())

        await asyncio.gather(signal_task, request_task, monitor_task, return_exceptions=True)

    async def _load_positions(self) -> None:
        """Load open positions from database and sync with RiskManager."""
        if not self._state_client:
            return

        positions = await self._state_client.get_open_positions()
        for pos in positions:
            self._open_positions[f"{pos.market_id}:{pos.token_id}"] = pos

            # Sync position to RiskManager
            venue_position = VenuePosition(
                venue="polymarket",
                asset_class=AssetClass.PREDICTION,
                symbol=pos.market_id,
                token_id=pos.token_id,
                side="long" if pos.side == "YES" else "short",
                size=pos.size,
                entry_price=pos.entry_price,
                current_price=pos.entry_price,  # Will be updated by price feeds
                notional_usd=pos.cost_basis,
                delta=1.0,  # Prediction markets have delta of 1
            )
            self._risk_manager.update_position(venue_position)

        self._logger.info(f"Loaded {len(positions)} open positions")

    async def _process_signals(self) -> None:
        """Process incoming trading signals."""
        if not self._signal_puller:
            return

        async for msg in self._signal_puller.messages():
            if not self._running:
                break

            try:
                if msg.get("type") == "signal":
                    signal = Signal.from_dict(msg)
                    await self._execute_signal(signal)
            except Exception as e:
                self._logger.error(f"Signal processing error: {e}")

    async def _handle_requests(self) -> None:
        """Handle order and query requests via REQ/REP."""
        if not self._request_replier:
            return

        async for msg in self._request_replier.requests():
            if not self._running:
                break

            try:
                msg_type = msg.get("type", "")

                if msg_type == "order_req":
                    request_id = msg.get("request_id", "")
                    signal_data = msg.get("signal", {})
                    signal = Signal.from_dict(signal_data)

                    result = await self._execute_signal(signal)

                    response = OrderResponse(
                        request_id=request_id,
                        success=result.get("success", False),
                        order_id=result.get("order_id"),
                        error=result.get("error"),
                    )
                    await self._request_replier.reply(response.to_dict())

                elif msg_type == "shadow_summary":
                    summary = self._shadow_tracker.get_summary()
                    await self._request_replier.reply({"success": True, "data": summary})

                elif msg_type == "shadow_stats":
                    strategy = msg.get("strategy")
                    stats = self._shadow_tracker.get_stats(strategy)
                    await self._request_replier.reply({"success": True, "data": stats})

                elif msg_type == "shadow_positions":
                    strategy = msg.get("strategy")
                    positions = self._shadow_tracker.get_positions(strategy)
                    await self._request_replier.reply({"success": True, "data": positions})

                elif msg_type == "shadow_trades":
                    strategy = msg.get("strategy")
                    limit = msg.get("limit", 100)
                    trades = self._shadow_tracker.get_trades(strategy, limit)
                    await self._request_replier.reply({"success": True, "data": trades})

                elif msg_type == "shadow_reset":
                    strategy = msg.get("strategy")
                    self._shadow_tracker.reset(strategy)
                    await self._request_replier.reply({"success": True})

                else:
                    await self._request_replier.reply({"success": False, "error": f"Unknown request type: {msg_type}"})

            except Exception as e:
                self._logger.error(f"Request handling error: {e}")
                response = OrderResponse(
                    request_id=msg.get("request_id", ""),
                    success=False,
                    error=str(e),
                )
                await self._request_replier.reply(response.to_dict())

    async def _is_shadow_mode(self, strategy: str) -> bool:
        """Check if a strategy is in shadow mode.

        Args:
            strategy: Strategy name

        Returns:
            True if strategy is in shadow mode
        """
        # Check cache first
        if strategy in self._shadow_mode_cache:
            return self._shadow_mode_cache[strategy]

        # Query state service
        if self._state_client:
            try:
                config = await self._state_client.get_strategy_config(strategy)
                is_shadow = config.get("shadow", False) if config else False
                self._shadow_mode_cache[strategy] = is_shadow
                return is_shadow
            except Exception as e:
                self._logger.warning(f"Failed to check shadow mode for {strategy}: {e}")

        return False

    def clear_shadow_cache(self, strategy: Optional[str] = None) -> None:
        """Clear shadow mode cache.

        Args:
            strategy: Strategy to clear, or None to clear all
        """
        if strategy:
            self._shadow_mode_cache.pop(strategy, None)
        else:
            self._shadow_mode_cache.clear()

    async def _execute_signal(self, signal: Signal) -> Dict[str, Any]:
        """Execute a trading signal.

        Args:
            signal: Trading signal from strategy

        Returns:
            Execution result dict
        """
        # Check if strategy is in shadow mode
        is_shadow = await self._is_shadow_mode(signal.strategy)

        if is_shadow:
            self._logger.info(
                f"[SHADOW] Signal from {signal.strategy}: {signal.action.value} "
                f"{signal.size}@{signal.price} for {signal.market_id} "
                f"(reason: {signal.reason})"
            )

            # Simulate the trade using shadow tracker
            shadow_trade = self._shadow_tracker.simulate_signal(
                strategy=signal.strategy,
                market_id=signal.market_id,
                token_id=signal.token_id,
                action=signal.action.value,
                signal_price=signal.price,
                size=signal.size,
                reason=signal.reason,
                confidence=signal.confidence,
                bid=signal.bid,
                ask=signal.ask,
            )

            # Get current shadow stats for this strategy
            shadow_stats = self._shadow_tracker.get_stats(signal.strategy)

            # Log shadow signal to strategy logs
            if self._logs_client:
                try:
                    await self._logs_client.log(
                        strategy=signal.strategy,
                        log_type="signal",
                        level="INFO",
                        message=f"[SHADOW] {signal.action.value} {signal.size:.4f}@{signal.price:.4f} - {signal.reason}",
                        market_id=signal.market_id,
                        token_id=signal.token_id,
                        price=signal.price,
                        size=signal.size,
                        action=signal.action.value,
                        reason=signal.reason,
                        confidence=signal.confidence,
                        metadata={
                            "shadow": True,
                            "shadow_trade_id": shadow_trade.id if shadow_trade else None,
                            "shadow_fill_price": shadow_trade.simulated_fill_price if shadow_trade else None,
                            "shadow_total_pnl": shadow_stats.get("total_realized_pnl", 0) + shadow_stats.get("total_unrealized_pnl", 0) if shadow_stats else 0,
                        },
                    )
                except Exception as log_err:
                    self._logger.warning(f"Failed to log shadow signal: {log_err}")

            # Publish shadow event for monitoring (with PnL info)
            await self._publish_event(
                EventType.ALERT,
                {
                    "type": "shadow_signal",
                    "strategy": signal.strategy,
                    "action": signal.action.value,
                    "market_id": signal.market_id,
                    "token_id": signal.token_id,
                    "price": signal.price,
                    "size": signal.size,
                    "reason": signal.reason,
                    "shadow_pnl": shadow_stats.get("total_realized_pnl", 0) + shadow_stats.get("total_unrealized_pnl", 0) if shadow_stats else 0,
                    "shadow_trades": shadow_stats.get("total_trades", 0) if shadow_stats else 0,
                },
            )
            return {
                "success": True,
                "shadow": True,
                "message": "Shadow mode - trade simulated",
                "shadow_trade_id": shadow_trade.id if shadow_trade else None,
                "shadow_stats": shadow_stats,
            }

        self._logger.info(
            f"Executing signal: {signal.strategy} {signal.action.value} "
            f"{signal.size}@{signal.price} for {signal.market_id}"
        )

        # Validate risk limits
        if not self._validate_risk(signal):
            return {"success": False, "error": "Risk limit exceeded"}

        # Execute based on action
        if signal.action == SignalAction.CLOSE:
            return await self._close_position(signal)
        else:
            return await self._place_order(signal)

    def _validate_risk(self, signal: Signal) -> bool:
        """Validate signal against risk limits using RiskManager.

        Args:
            signal: Trading signal

        Returns:
            True if signal passes risk checks
        """
        # Use unified risk manager for pre-trade checks
        result = self._risk_manager.check_pre_trade(
            venue="polymarket",
            symbol=signal.market_id,
            side=signal.action.value.lower(),
            size=signal.size,
            price=signal.price,
            strategy=signal.strategy,
        )

        if not result.approved:
            self._logger.warning(f"Risk check failed: {result.reason}")
            return False

        # Log any warnings
        for warning in result.warnings:
            self._logger.warning(f"Risk warning: {warning}")

        # Update signal size if adjusted by risk manager
        if result.adjusted_size is not None:
            self._logger.info(
                f"Size adjusted by risk manager: {signal.size} -> {result.adjusted_size}"
            )
            signal.size = result.adjusted_size

        return True

    async def _place_order(self, signal: Signal) -> Dict[str, Any]:
        """Place an order via CLOB API.

        Args:
            signal: Trading signal

        Returns:
            Execution result
        """
        if not self._client or not self._state_client:
            return {"success": False, "error": "Client not initialized"}

        # Create order
        order = Order(
            id=str(uuid.uuid4()),
            market_id=signal.market_id,
            token_id=signal.token_id,
            side=OrderSide.BUY if signal.action == SignalAction.BUY else OrderSide.SELL,
            price=signal.price,
            size=signal.size,
            order_type=OrderType.GTC,
            status=OrderStatus.PENDING,
            strategy=signal.strategy,
        )

        try:
            # Place order via API
            result = await self._client.place_order(
                token_id=order.token_id,
                side=order.side.value,
                price=order.price,
                size=order.size,
            )

            # Update order with API response
            order.id = result.get("orderID", order.id)
            order.order_hash = result.get("orderHash")
            order.status = OrderStatus.OPEN
            order.updated_at = datetime.utcnow()

            # Track order
            self._pending_orders[order.id] = order

            # Save to database via state service
            await self._state_client.save_order(order)

            # Publish event
            await self._publish_event(
                EventType.ORDER_PLACED,
                {
                    "order_id": order.id,
                    "market_id": order.market_id,
                    "strategy": order.strategy,
                    "side": order.side.value,
                    "price": order.price,
                    "size": order.size,
                },
            )

            # Log successful execution to strategy logs
            if self._logs_client and signal.strategy:
                try:
                    await self._logs_client.log(
                        strategy=signal.strategy,
                        log_type="entry",
                        level="INFO",
                        message=f"Order placed: {order.side.value} {order.size:.4f}@{order.price:.4f}",
                        market_id=order.market_id,
                        token_id=order.token_id,
                        price=order.price,
                        size=order.size,
                        action=order.side.value,
                        metadata={"order_id": order.id, "order_hash": order.order_hash},
                    )
                except Exception as log_err:
                    self._logger.warning(f"Failed to log execution: {log_err}")

            self._logger.info(f"Order placed: {order.id}")
            return {"success": True, "order_id": order.id}

        except Exception as e:
            import traceback
            error_msg = str(e)
            self._logger.error(f"Order failed: {e}\n{traceback.format_exc()}")

            order.status = OrderStatus.FAILED
            order.error_message = error_msg

            try:
                await self._state_client.save_order(order)
            except Exception as save_err:
                self._logger.error(f"Failed to save failed order: {save_err}")

            # Log failed execution to strategy logs
            if self._logs_client and signal.strategy:
                try:
                    await self._logs_client.log(
                        strategy=signal.strategy,
                        log_type="error",
                        level="ERROR",
                        message=f"Order failed: {error_msg}",
                        market_id=order.market_id,
                        token_id=order.token_id,
                        price=order.price,
                        size=order.size,
                        action=order.side.value,
                        metadata={"error": error_msg, "order_id": order.id},
                    )
                except Exception as log_err:
                    self._logger.warning(f"Failed to log error: {log_err}")

            await self._publish_event(
                EventType.ORDER_FAILED,
                {"order_id": order.id, "error": error_msg},
            )

            return {"success": False, "error": error_msg}

    async def _close_position(self, signal: Signal) -> Dict[str, Any]:
        """Close an existing position.

        Args:
            signal: Close signal

        Returns:
            Execution result
        """
        key = f"{signal.market_id}:{signal.token_id}"
        position = self._open_positions.get(key)

        if not position:
            return {"success": False, "error": "Position not found"}

        # Create closing order (opposite side)
        close_signal = Signal(
            type=signal.type,
            strategy=signal.strategy,
            market_id=signal.market_id,
            token_id=signal.token_id,
            action=SignalAction.SELL if position.side == "YES" else SignalAction.BUY,
            price=signal.price,
            size=position.size,
            reason=f"Close: {signal.reason}",
        )

        return await self._place_order(close_signal)

    def _handle_order_update(self, data: Dict[str, Any]) -> None:
        """Handle WebSocket order update."""
        asyncio.create_task(self._process_order_update(data))

    async def _process_order_update(self, data: Dict[str, Any]) -> None:
        """Process order status update."""
        order_id = data.get("order_id", "")
        update_type = data.get("type", "")  # PLACEMENT, UPDATE, CANCELLATION

        order = self._pending_orders.get(order_id)
        if not order or not self._state_client:
            return

        if update_type == "CANCELLATION":
            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.utcnow()
            del self._pending_orders[order_id]

            await self._publish_event(
                EventType.ORDER_CANCELLED,
                {"order_id": order_id},
            )

        elif update_type == "UPDATE":
            order.filled_size = float(data.get("size_matched", 0))
            if order.filled_size >= order.size:
                order.status = OrderStatus.FILLED
                order.filled_at = datetime.utcnow()
                del self._pending_orders[order_id]

                await self._publish_event(
                    EventType.ORDER_FILLED,
                    {"order_id": order_id, "filled_size": order.filled_size},
                )

        order.updated_at = datetime.utcnow()
        await self._state_client.save_order(order)

    def _handle_trade_update(self, data: Dict[str, Any]) -> None:
        """Handle WebSocket trade update."""
        asyncio.create_task(self._process_trade_update(data))

    async def _process_trade_update(self, data: Dict[str, Any]) -> None:
        """Process trade execution update."""
        if not self._state_client:
            return

        # Create trade record
        trade = Trade(
            id=data.get("trade_id", str(uuid.uuid4())),
            order_id=data.get("order_id"),
            market_id=data.get("market", ""),
            token_id=data.get("asset_id", ""),
            side=OrderSide(data.get("side", "BUY")),
            price=float(data.get("price", 0)),
            size=float(data.get("size", 0)),
            fee=float(data.get("fee", 0)),
            notional=float(data.get("price", 0)) * float(data.get("size", 0)),
            timestamp=datetime.utcnow(),
        )

        await self._state_client.save_trade(trade)

        # Update position
        await self._update_position(trade)

    async def _update_position(self, trade: Trade) -> None:
        """Update position based on trade and sync with RiskManager.

        Args:
            trade: Executed trade
        """
        if not self._state_client:
            return

        key = f"{trade.market_id}:{trade.token_id}"
        position = self._open_positions.get(key)

        if trade.side == OrderSide.BUY:
            if position:
                # Add to existing position
                total_cost = position.entry_price * position.size + trade.price * trade.size
                position.size += trade.size
                position.entry_price = total_cost / position.size
            else:
                # Create new position
                position = Position(
                    market_id=trade.market_id,
                    token_id=trade.token_id,
                    side="YES",  # Simplified - would need to determine from token
                    size=trade.size,
                    entry_price=trade.price,
                    strategy=trade.strategy,
                )
                self._open_positions[key] = position

                await self._publish_event(
                    EventType.POSITION_OPENED,
                    {
                        "market_id": trade.market_id,
                        "size": trade.size,
                        "entry_price": trade.price,
                    },
                )

            # Sync position to RiskManager
            venue_position = VenuePosition(
                venue="polymarket",
                asset_class=AssetClass.PREDICTION,
                symbol=trade.market_id,
                token_id=trade.token_id,
                side="long" if position.side == "YES" else "short",
                size=position.size,
                entry_price=position.entry_price,
                current_price=trade.price,
                notional_usd=position.size * trade.price,
                delta=1.0,
            )
            self._risk_manager.update_position(venue_position)

        else:  # SELL
            if position:
                pnl = position.close(trade.price)

                # Record PnL in RiskManager
                self._risk_manager.record_pnl("polymarket", pnl)

                # Close position in RiskManager
                self._risk_manager.close_position(
                    venue="polymarket",
                    symbol=trade.market_id,
                    token_id=trade.token_id,
                    realized_pnl=pnl,
                )

                del self._open_positions[key]

                await self._publish_event(
                    EventType.POSITION_CLOSED,
                    {
                        "market_id": trade.market_id,
                        "exit_price": trade.price,
                        "pnl": pnl,
                    },
                )

        if position:
            await self._state_client.save_position(position)

    async def _monitor_orders(self) -> None:
        """Monitor pending orders and handle timeouts."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                # Check for stale orders
                now = datetime.utcnow()
                stale_orders = [
                    order_id
                    for order_id, order in self._pending_orders.items()
                    if (now - order.created_at).total_seconds() > 3600  # 1 hour timeout
                ]

                for order_id in stale_orders:
                    self._logger.warning(f"Cancelling stale order: {order_id}")
                    if self._client:
                        try:
                            await self._client.cancel_order(order_id)
                        except Exception as e:
                            self._logger.error(f"Failed to cancel order: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Order monitoring error: {e}")

    # =========================================================================
    # Public API
    # =========================================================================

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancellation succeeded
        """
        if not self._client:
            return False

        try:
            await self._client.cancel_order(order_id)
            return True
        except Exception as e:
            self._logger.error(f"Cancel failed: {e}")
            return False

    async def cancel_all_orders(self) -> bool:
        """Cancel all open orders.

        Returns:
            True if cancellation succeeded
        """
        if not self._client:
            return False

        try:
            await self._client.cancel_all_orders()
            self._pending_orders.clear()
            return True
        except Exception as e:
            self._logger.error(f"Cancel all failed: {e}")
            return False

    def get_open_orders(self) -> list[Order]:
        """Get list of open orders."""
        return list(self._pending_orders.values())

    def get_open_positions(self) -> list[Position]:
        """Get list of open positions."""
        return list(self._open_positions.values())

    def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status from RiskManager."""
        # Get comprehensive status from RiskManager
        risk_status = self._risk_manager.get_risk_status()

        # Add local order tracking
        risk_status["open_orders"] = len(self._pending_orders)
        risk_status["local_positions"] = len(self._open_positions)

        return risk_status

    # =========================================================================
    # Shadow Trading API
    # =========================================================================

    def get_shadow_summary(self) -> Dict[str, Any]:
        """Get high-level summary of shadow trading performance."""
        return self._shadow_tracker.get_summary()

    def get_shadow_stats(self, strategy: Optional[str] = None) -> Dict[str, Any]:
        """Get shadow trading stats.

        Args:
            strategy: Specific strategy, or None for all

        Returns:
            Stats dictionary
        """
        return self._shadow_tracker.get_stats(strategy)

    def get_shadow_positions(self, strategy: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open shadow positions.

        Args:
            strategy: Filter by strategy, or None for all

        Returns:
            List of position dictionaries
        """
        return self._shadow_tracker.get_positions(strategy)

    def get_shadow_trades(
        self,
        strategy: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get shadow trade history.

        Args:
            strategy: Filter by strategy, or None for all
            limit: Maximum trades to return

        Returns:
            List of trade dictionaries
        """
        return self._shadow_tracker.get_trades(strategy, limit)

    def reset_shadow_tracking(self, strategy: Optional[str] = None) -> None:
        """Reset shadow tracking data.

        Args:
            strategy: Reset specific strategy, or None for all
        """
        self._shadow_tracker.reset(strategy)
        self._logger.info(f"Reset shadow tracking for {strategy or 'all strategies'}")
