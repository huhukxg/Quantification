"""Risk checks shared by later trading loops."""

from __future__ import annotations


class RiskManager:
    """Evaluate point-based trade and session risk limits."""

    def __init__(
        self,
        stop_loss_points: float,
        take_profit_points: float,
        max_trades: int,
        max_daily_loss: float,
        forced_exit_time: int,
    ) -> None:
        self.stop_loss_points = stop_loss_points
        self.take_profit_points = take_profit_points
        self.max_trades = max_trades
        self.max_daily_loss = max_daily_loss
        self.forced_exit_time = forced_exit_time

    def check_stop_loss(self, entry_price: float, current_close: float, direction: int) -> bool:
        """Return whether an open trade has breached its stop loss."""
        if direction == 1:
            return current_close <= entry_price - self.stop_loss_points
        if direction == -1:
            return current_close >= entry_price + self.stop_loss_points
        return False

    def check_take_profit(self, entry_price: float, current_close: float, direction: int) -> bool:
        """Return whether an open trade has reached its take profit."""
        if direction == 1:
            return current_close >= entry_price + self.take_profit_points
        if direction == -1:
            return current_close <= entry_price - self.take_profit_points
        return False

    def check_session_end(self, current_time: int) -> bool:
        """Return whether forced-exit signaling time has been reached."""
        return current_time >= self.forced_exit_time

    def can_trade(self, session_trade_count: int, session_realized_pnl: float) -> bool:
        """Return whether session trade-count and daily-loss limits permit entry."""
        max_loss_hit = session_realized_pnl <= -self.max_daily_loss
        return session_trade_count < self.max_trades and not max_loss_hit
