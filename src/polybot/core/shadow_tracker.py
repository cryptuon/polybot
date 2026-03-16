"""Shadow position tracker for paper trading analysis.

Tracks simulated positions and PnL for strategies running in shadow mode.
Allows comparison of shadow vs real trading performance.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


logger = logging.getLogger(__name__)


class ShadowFillAssumption(str, Enum):
    """How to simulate order fills in shadow mode."""

    IMMEDIATE = "immediate"  # Assume immediate fill at signal price
    MIDPOINT = "midpoint"  # Fill at midpoint of bid/ask
    AGGRESSIVE = "aggressive"  # Fill at worse price (ask for buy, bid for sell)
    CONSERVATIVE = "conservative"  # Fill at better price (bid for buy, ask for sell)


@dataclass
class ShadowPosition:
    """A simulated position in shadow mode."""

    id: str
    strategy: str
    market_id: str
    token_id: str
    side: str  # "BUY" or "SELL"
    size: float
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    status: str = "open"  # "open", "closed"
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    realized_pnl: float = 0.0

    def update_price(self, price: float) -> None:
        """Update current price and unrealized PnL."""
        self.current_price = price
        if self.side == "BUY":
            self.unrealized_pnl = (price - self.entry_price) * self.size
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.size

    def close(self, exit_price: float) -> float:
        """Close the position and calculate realized PnL."""
        self.exit_price = exit_price
        self.exit_time = datetime.utcnow()
        self.status = "closed"

        if self.side == "BUY":
            self.realized_pnl = (exit_price - self.entry_price) * self.size
        else:
            self.realized_pnl = (self.entry_price - exit_price) * self.size

        self.unrealized_pnl = 0.0
        return self.realized_pnl

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        # Calculate unrealized PnL dynamically to ensure accuracy
        if self.status == "open" and self.current_price > 0:
            if self.side == "BUY":
                unrealized = (self.current_price - self.entry_price) * self.size
            else:
                unrealized = (self.entry_price - self.current_price) * self.size
        else:
            unrealized = self.unrealized_pnl

        return {
            "id": self.id,
            "strategy": self.strategy,
            "market_id": self.market_id,
            "token_id": self.token_id,
            "side": self.side,
            "size": self.size,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "current_price": self.current_price,
            "unrealized_pnl": round(unrealized, 4),
            "status": self.status,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "realized_pnl": self.realized_pnl,
        }


@dataclass
class ShadowTrade:
    """A simulated trade in shadow mode."""

    id: str
    strategy: str
    market_id: str
    token_id: str
    side: str
    price: float
    size: float
    notional: float
    timestamp: datetime
    signal_reason: str
    signal_confidence: float
    simulated_fill_price: float
    slippage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "strategy": self.strategy,
            "market_id": self.market_id,
            "token_id": self.token_id,
            "side": self.side,
            "price": self.price,
            "size": self.size,
            "notional": self.notional,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "signal_reason": self.signal_reason,
            "signal_confidence": self.signal_confidence,
            "simulated_fill_price": self.simulated_fill_price,
            "slippage": self.slippage,
        }


@dataclass
class ShadowStrategyStats:
    """Aggregated stats for a strategy in shadow mode."""

    strategy: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_volume: float = 0.0
    avg_trade_pnl: float = 0.0
    win_rate: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    open_positions: int = 0
    start_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strategy": self.strategy,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_realized_pnl": round(self.total_realized_pnl, 4),
            "total_unrealized_pnl": round(self.total_unrealized_pnl, 4),
            "total_pnl": round(self.total_realized_pnl + self.total_unrealized_pnl, 4),
            "total_volume": round(self.total_volume, 2),
            "avg_trade_pnl": round(self.avg_trade_pnl, 4),
            "win_rate": round(self.win_rate, 4),
            "largest_win": round(self.largest_win, 4),
            "largest_loss": round(self.largest_loss, 4),
            "open_positions": self.open_positions,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_trade_time": self.last_trade_time.isoformat() if self.last_trade_time else None,
        }


class ShadowPositionTracker:
    """Tracks simulated positions and PnL for shadow mode strategies.

    Features:
    - Simulates order fills at configurable prices
    - Tracks open positions per strategy
    - Calculates realized and unrealized PnL
    - Maintains trade history for analysis
    - Aggregates stats per strategy
    """

    def __init__(
        self,
        fill_assumption: ShadowFillAssumption = ShadowFillAssumption.IMMEDIATE,
        slippage_bps: float = 0.0,  # Slippage in basis points
    ) -> None:
        """Initialize the tracker.

        Args:
            fill_assumption: How to simulate order fills
            slippage_bps: Additional slippage in basis points (100 bps = 1%)
        """
        self._fill_assumption = fill_assumption
        self._slippage_bps = slippage_bps

        # Positions by strategy -> market:token -> position
        self._positions: Dict[str, Dict[str, ShadowPosition]] = {}

        # Trade history by strategy
        self._trades: Dict[str, List[ShadowTrade]] = {}

        # Stats per strategy
        self._stats: Dict[str, ShadowStrategyStats] = {}

        # Current prices for unrealized PnL calculation
        self._current_prices: Dict[str, float] = {}  # token_id -> price

        # Trade ID counter
        self._trade_counter = 0

    def simulate_signal(
        self,
        strategy: str,
        market_id: str,
        token_id: str,
        action: str,  # "BUY", "SELL", "CLOSE"
        signal_price: float,
        size: float,
        reason: str = "",
        confidence: float = 0.0,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
    ) -> Optional[ShadowTrade]:
        """Simulate a trading signal and create shadow trade/position.

        Args:
            strategy: Strategy name
            market_id: Market ID
            token_id: Token ID
            action: Signal action (BUY, SELL, CLOSE)
            signal_price: Price from signal
            size: Order size
            reason: Signal reason
            confidence: Signal confidence
            bid: Current bid price (for fill simulation)
            ask: Current ask price (for fill simulation)

        Returns:
            ShadowTrade if simulated, None if rejected
        """
        # Initialize strategy tracking if needed
        if strategy not in self._positions:
            self._positions[strategy] = {}
            self._trades[strategy] = []
            self._stats[strategy] = ShadowStrategyStats(
                strategy=strategy,
                start_time=datetime.utcnow(),
            )

        # Update current prices for all positions of this token (for unrealized PnL)
        # Use midpoint of bid/ask as the "current" market price
        if bid is not None and ask is not None:
            market_price = (bid + ask) / 2
        elif bid is not None:
            market_price = bid
        elif ask is not None:
            market_price = ask
        else:
            market_price = signal_price

        # Update existing positions with current price
        self.update_price(token_id, market_price)

        # Calculate simulated fill price
        fill_price = self._calculate_fill_price(
            signal_price, action, bid, ask
        )

        # Create trade record
        self._trade_counter += 1
        trade_id = f"shadow_{strategy}_{self._trade_counter}"

        trade = ShadowTrade(
            id=trade_id,
            strategy=strategy,
            market_id=market_id,
            token_id=token_id,
            side=action if action != "CLOSE" else "SELL",  # CLOSE = SELL
            price=signal_price,
            size=size,
            notional=fill_price * size,
            timestamp=datetime.utcnow(),
            signal_reason=reason,
            signal_confidence=confidence,
            simulated_fill_price=fill_price,
            slippage=abs(fill_price - signal_price),
        )

        self._trades[strategy].append(trade)

        # Update stats
        stats = self._stats[strategy]
        stats.total_trades += 1
        stats.total_volume += trade.notional
        stats.last_trade_time = trade.timestamp

        # Handle position
        pos_key = f"{market_id}:{token_id}"

        if action == "CLOSE":
            # Explicit close - close existing position
            if pos_key in self._positions[strategy]:
                position = self._positions[strategy][pos_key]
                pnl = position.close(fill_price)
                del self._positions[strategy][pos_key]

                stats.total_realized_pnl += pnl
                stats.open_positions = len(self._positions[strategy])

                if pnl > 0:
                    stats.winning_trades += 1
                    stats.largest_win = max(stats.largest_win, pnl)
                else:
                    stats.losing_trades += 1
                    stats.largest_loss = min(stats.largest_loss, pnl)

                logger.info(
                    f"[SHADOW] {strategy} closed position {pos_key}: "
                    f"PnL=${pnl:.4f}, total=${stats.total_realized_pnl:.4f}"
                )
        else:
            # BUY or SELL - check for opposing position first
            existing_pos = self._positions[strategy].get(pos_key)

            if existing_pos and existing_pos.side != action:
                # Opposing position exists - close or reduce it
                if size >= existing_pos.size:
                    # Full close (and possibly open reverse)
                    pnl = existing_pos.close(fill_price)
                    del self._positions[strategy][pos_key]

                    stats.total_realized_pnl += pnl
                    if pnl > 0:
                        stats.winning_trades += 1
                        stats.largest_win = max(stats.largest_win, pnl)
                    else:
                        stats.losing_trades += 1
                        stats.largest_loss = min(stats.largest_loss, pnl)

                    logger.info(
                        f"[SHADOW] {strategy} closed {existing_pos.side} position {pos_key}: "
                        f"PnL=${pnl:.4f}, total=${stats.total_realized_pnl:.4f}"
                    )

                    # If size exceeds existing, open new position with remainder
                    remainder = size - existing_pos.size
                    if remainder > 0.01:  # Minimum position size
                        position = ShadowPosition(
                            id=f"shadow_pos_{strategy}_{self._trade_counter}",
                            strategy=strategy,
                            market_id=market_id,
                            token_id=token_id,
                            side=action,
                            size=remainder,
                            entry_price=fill_price,
                            entry_time=datetime.utcnow(),
                            current_price=market_price,
                        )
                        self._positions[strategy][pos_key] = position
                        logger.info(
                            f"[SHADOW] {strategy} opened reverse {action} {remainder:.4f}@{fill_price:.4f}"
                        )
                else:
                    # Partial close - reduce existing position
                    close_size = size
                    # Calculate PnL for the closed portion
                    if existing_pos.side == "BUY":
                        pnl = (fill_price - existing_pos.entry_price) * close_size
                    else:
                        pnl = (existing_pos.entry_price - fill_price) * close_size

                    existing_pos.size -= close_size
                    stats.total_realized_pnl += pnl

                    if pnl > 0:
                        stats.winning_trades += 1
                        stats.largest_win = max(stats.largest_win, pnl)
                    else:
                        stats.losing_trades += 1
                        stats.largest_loss = min(stats.largest_loss, pnl)

                    logger.info(
                        f"[SHADOW] {strategy} reduced {existing_pos.side} by {close_size:.4f}: "
                        f"PnL=${pnl:.4f}, remaining={existing_pos.size:.4f}"
                    )

                stats.open_positions = len([p for p in self._positions[strategy].values() if p.status == "open"])

            elif existing_pos and existing_pos.side == action:
                # Same direction - add to existing position (average in)
                total_cost = existing_pos.entry_price * existing_pos.size + fill_price * size
                existing_pos.size += size
                existing_pos.entry_price = total_cost / existing_pos.size
                existing_pos.current_price = market_price

                logger.info(
                    f"[SHADOW] {strategy} added to {action} {size:.4f}@{fill_price:.4f}, "
                    f"avg={existing_pos.entry_price:.4f}, total={existing_pos.size:.4f}"
                )
            else:
                # No existing position - create new
                position = ShadowPosition(
                    id=f"shadow_pos_{strategy}_{self._trade_counter}",
                    strategy=strategy,
                    market_id=market_id,
                    token_id=token_id,
                    side=action,
                    size=size,
                    entry_price=fill_price,
                    entry_time=datetime.utcnow(),
                    current_price=market_price,
                )
                self._positions[strategy][pos_key] = position
                stats.open_positions = len(self._positions[strategy])

                logger.info(
                    f"[SHADOW] {strategy} {action} {size:.4f}@{fill_price:.4f} "
                    f"({reason}), confidence={confidence:.2f}"
                )

        # Recalculate aggregate stats
        self._update_stats(strategy)

        return trade

    def _calculate_fill_price(
        self,
        signal_price: float,
        action: str,
        bid: Optional[float],
        ask: Optional[float],
    ) -> float:
        """Calculate simulated fill price based on assumption.

        Args:
            signal_price: Original signal price
            action: BUY, SELL, or CLOSE
            bid: Current bid price
            ask: Current ask price

        Returns:
            Simulated fill price
        """
        # Default to signal price
        fill_price = signal_price

        if self._fill_assumption == ShadowFillAssumption.IMMEDIATE:
            fill_price = signal_price

        elif self._fill_assumption == ShadowFillAssumption.MIDPOINT:
            if bid and ask:
                fill_price = (bid + ask) / 2

        elif self._fill_assumption == ShadowFillAssumption.AGGRESSIVE:
            # Worse execution: buy at ask, sell at bid
            if action == "BUY":
                fill_price = ask if ask else signal_price
            else:
                fill_price = bid if bid else signal_price

        elif self._fill_assumption == ShadowFillAssumption.CONSERVATIVE:
            # Better execution: buy at bid, sell at ask
            if action == "BUY":
                fill_price = bid if bid else signal_price
            else:
                fill_price = ask if ask else signal_price

        # Apply slippage
        if self._slippage_bps > 0:
            slippage_pct = self._slippage_bps / 10000
            if action == "BUY":
                fill_price *= (1 + slippage_pct)
            else:
                fill_price *= (1 - slippage_pct)

        return fill_price

    def update_price(self, token_id: str, price: float) -> None:
        """Update current price for a token.

        Updates unrealized PnL for all positions holding this token.

        Args:
            token_id: Token ID
            price: Current price
        """
        self._current_prices[token_id] = price

        # Update all positions for this token
        for strategy, positions in self._positions.items():
            for pos_key, position in positions.items():
                if position.token_id == token_id and position.status == "open":
                    position.update_price(price)

            # Recalculate stats
            self._update_stats(strategy)

    def _update_stats(self, strategy: str) -> None:
        """Recalculate aggregate stats for a strategy."""
        if strategy not in self._stats:
            return

        stats = self._stats[strategy]

        # Calculate total unrealized PnL (dynamically calculated per position)
        total_unrealized = 0.0
        for p in self._positions.get(strategy, {}).values():
            if p.status == "open" and p.current_price > 0:
                if p.side == "BUY":
                    total_unrealized += (p.current_price - p.entry_price) * p.size
                else:
                    total_unrealized += (p.entry_price - p.current_price) * p.size
        stats.total_unrealized_pnl = total_unrealized
        stats.open_positions = len([p for p in self._positions.get(strategy, {}).values() if p.status == "open"])

        # Calculate win rate
        closed_trades = stats.winning_trades + stats.losing_trades
        if closed_trades > 0:
            stats.win_rate = stats.winning_trades / closed_trades
            stats.avg_trade_pnl = stats.total_realized_pnl / closed_trades

    def get_positions(self, strategy: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open positions.

        Args:
            strategy: Filter by strategy, or None for all

        Returns:
            List of position dictionaries
        """
        positions = []

        strategies = [strategy] if strategy else list(self._positions.keys())

        for strat in strategies:
            for position in self._positions.get(strat, {}).values():
                if position.status == "open":
                    positions.append(position.to_dict())

        return positions

    def get_trades(
        self,
        strategy: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get trade history.

        Args:
            strategy: Filter by strategy, or None for all
            limit: Maximum trades to return

        Returns:
            List of trade dictionaries
        """
        trades = []

        strategies = [strategy] if strategy else list(self._trades.keys())

        for strat in strategies:
            for trade in self._trades.get(strat, []):
                trades.append(trade.to_dict())

        # Sort by timestamp descending and limit
        trades.sort(key=lambda t: t["timestamp"] or "", reverse=True)
        return trades[:limit]

    def get_stats(self, strategy: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregated stats.

        Args:
            strategy: Specific strategy, or None for all

        Returns:
            Stats dictionary
        """
        if strategy:
            if strategy in self._stats:
                return self._stats[strategy].to_dict()
            return {}

        # Return all strategies
        return {
            "strategies": {
                name: stats.to_dict()
                for name, stats in self._stats.items()
            },
            "totals": {
                "total_realized_pnl": sum(s.total_realized_pnl for s in self._stats.values()),
                "total_unrealized_pnl": sum(s.total_unrealized_pnl for s in self._stats.values()),
                "total_trades": sum(s.total_trades for s in self._stats.values()),
                "total_volume": sum(s.total_volume for s in self._stats.values()),
                "open_positions": sum(s.open_positions for s in self._stats.values()),
            },
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get a high-level summary of all shadow trading.

        Returns:
            Summary dictionary
        """
        total_realized = sum(s.total_realized_pnl for s in self._stats.values())
        total_unrealized = sum(s.total_unrealized_pnl for s in self._stats.values())
        total_trades = sum(s.total_trades for s in self._stats.values())
        total_winning = sum(s.winning_trades for s in self._stats.values())
        total_losing = sum(s.losing_trades for s in self._stats.values())

        return {
            "total_pnl": round(total_realized + total_unrealized, 4),
            "realized_pnl": round(total_realized, 4),
            "unrealized_pnl": round(total_unrealized, 4),
            "total_trades": total_trades,
            "win_rate": round(total_winning / (total_winning + total_losing), 4) if (total_winning + total_losing) > 0 else 0,
            "strategies_count": len(self._stats),
            "open_positions": sum(s.open_positions for s in self._stats.values()),
        }

    def reset(self, strategy: Optional[str] = None) -> None:
        """Reset tracking data.

        Args:
            strategy: Reset specific strategy, or None for all
        """
        if strategy:
            self._positions.pop(strategy, None)
            self._trades.pop(strategy, None)
            self._stats.pop(strategy, None)
            logger.info(f"Reset shadow tracking for {strategy}")
        else:
            self._positions.clear()
            self._trades.clear()
            self._stats.clear()
            logger.info("Reset all shadow tracking")


# Global tracker instance
_shadow_tracker: Optional[ShadowPositionTracker] = None


def get_shadow_tracker() -> ShadowPositionTracker:
    """Get or create the global shadow position tracker."""
    global _shadow_tracker
    if _shadow_tracker is None:
        _shadow_tracker = ShadowPositionTracker(
            fill_assumption=ShadowFillAssumption.IMMEDIATE,  # Fill at signal price
            slippage_bps=25,  # 0.25% slippage (realistic for limit orders)
        )
    return _shadow_tracker
