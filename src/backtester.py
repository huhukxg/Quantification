"""Core Stage 3 backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.config import CONTRACT_MULTIPLIER, FORCED_EXIT_TIME
from src.features import compute_session_features
from src.metrics import compute_equity_curve
from src.regime import EXTREME, RANGE, TREND, classify_regime_series
from src.risk_manager import RiskManager
from src.strategies import hybrid_signal, mr_signal, orb_signal

TRADING_STRATEGIES = {"ORB", "MR", "HYBRID", "ORB_FILTERED_HYBRID", "ORB_CONFIRMED_HYBRID"}
BENCHMARK_STRATEGIES = {"INTRADAY_LONG", "BUY_AND_HOLD", "FLAT"}


@dataclass
class Trade:
    """Store one completed round-trip trade."""

    date: int
    entry_time: int
    exit_time: int
    entry_datetime: pd.Timestamp
    exit_datetime: pd.Timestamp
    entry_price: float
    exit_price: float
    direction: int
    pnl_points: float
    pnl_hkd: float
    holding_bars: int
    exit_reason: str
    strategy_at_entry: str
    regime_at_entry: str


@dataclass
class BacktestResult:
    """Collect trades, bar positions, and realized PnL outputs."""

    trades: list[Trade]
    daily_pnl: dict[int, float]
    positions: pd.DataFrame
    equity_curve: pd.Series
    params: dict[str, Any]
    strategy_name: str


class Backtester:
    """Backtest Stage 3 signals with next-bar open execution."""

    def __init__(
        self,
        sessions: dict[int, pd.DataFrame],
        strategy: str,
        params: dict[str, Any],
        slippage: float,
        commission_rt: float,
        extreme_vol_threshold: float | None = None,
    ) -> None:
        strategy_name = strategy.upper()
        if strategy_name not in TRADING_STRATEGIES | BENCHMARK_STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy}")

        self.sessions = dict(sorted(sessions.items()))
        self.strategy = strategy_name
        self.params = dict(params)
        self.slippage = slippage
        self.commission_rt = commission_rt
        self.extreme_vol_threshold = extreme_vol_threshold
        self.risk_manager = RiskManager(
            stop_loss_points=float(self.params.get("stop_loss_points", 80)),
            take_profit_points=float(self.params.get("take_profit_points", 120)),
            max_trades=int(self.params.get("max_trades", 3)),
            max_daily_loss=float(self.params.get("max_daily_loss", 200)),
            forced_exit_time=int(self.params.get("forced_exit_time", FORCED_EXIT_TIME)),
        )

    def run(self) -> BacktestResult:
        """Run the configured trading strategy or benchmark."""
        if self.strategy == "FLAT":
            return self._run_flat()
        if self.strategy == "INTRADAY_LONG":
            return self._run_intraday_long()
        if self.strategy == "BUY_AND_HOLD":
            return self._run_buy_and_hold()

        all_trades: list[Trade] = []
        daily_pnl: dict[int, float] = {}
        position_rows: list[dict[str, Any]] = []
        for date, session_df in self.sessions.items():
            trades, positions = self._run_session(date, session_df)
            all_trades.extend(trades)
            daily_pnl[date] = float(sum(trade.pnl_points for trade in trades))
            position_rows.extend(positions)
        return self._build_result(all_trades, daily_pnl, position_rows)

    def _run_session(self, date: int, session_df: pd.DataFrame) -> tuple[list[Trade], list[dict[str, Any]]]:
        """Process one cleaned day session for ORB, MR, or HYBRID."""
        session = session_df.sort_values("datetime").reset_index(drop=True)
        features = compute_session_features(session, self.params)
        or_high = features.attrs["OR_high"]
        or_low = features.attrs["OR_low"]
        if self.strategy in {"HYBRID", "ORB_FILTERED_HYBRID", "ORB_CONFIRMED_HYBRID"}:
            threshold = self.extreme_vol_threshold if self.extreme_vol_threshold is not None else float("inf")
            regimes = classify_regime_series(
                features["ER"],
                features["RV"],
                float(self.params.get("er_threshold", 0.35)),
                threshold,
            )
        else:
            default_regime = TREND if self.strategy == "ORB" else RANGE
            regimes = pd.Series(default_regime, index=features.index)

        trades: list[Trade] = []
        position_rows: list[dict[str, Any]] = []
        direction = 0
        entry_index: int | None = None
        entry_row: pd.Series | None = None
        entry_price: float | None = None
        entry_strategy = ""
        entry_regime = ""
        session_realized_pnl = 0.0
        session_trade_count = 0

        for index in range(len(features)):
            row = features.iloc[index]
            position_rows.append(self._position_row(date, row, direction))
            if index >= len(features) - 1:
                continue

            next_row = features.iloc[index + 1]
            regime = str(regimes.iloc[index])
            exit_reason = None

            if direction != 0 and entry_price is not None and entry_row is not None and entry_index is not None:
                if self.risk_manager.check_stop_loss(entry_price, float(row["close"]), direction):
                    exit_reason = "stop_loss"
                elif self.risk_manager.check_take_profit(entry_price, float(row["close"]), direction):
                    exit_reason = "take_profit"
                elif self.risk_manager.check_session_end(int(row["time"])):
                    exit_reason = "session_end"
                elif (
                    self.strategy in {"HYBRID", "ORB_FILTERED_HYBRID", "ORB_CONFIRMED_HYBRID"}
                    and regime == EXTREME
                    and self.params.get("extreme_action", "close") == "close"
                ):
                    exit_reason = "regime_extreme"
                elif entry_strategy == "MR":
                    mr_target = mr_signal(
                        float(row["z_score"]),
                        float(self.params.get("z_entry", 2.0)),
                        float(self.params.get("z_exit", 0.25)),
                        direction,
                    )
                    if mr_target == 0:
                        exit_reason = "mr_exit"

                if exit_reason is not None:
                    exit_price = self._exit_price(float(next_row["open"]), direction)
                    trade = self._make_trade(
                        date,
                        entry_row,
                        next_row,
                        entry_price,
                        exit_price,
                        direction,
                        entry_index,
                        index + 1,
                        exit_reason,
                        entry_strategy,
                        entry_regime,
                    )
                    trades.append(trade)
                    session_realized_pnl += trade.pnl_points
                    direction = 0
                    entry_index = None
                    entry_row = None
                    entry_price = None
                    entry_strategy = ""
                    entry_regime = ""
                    continue

            if direction != 0 or not self.risk_manager.can_trade(session_trade_count, session_realized_pnl):
                continue

            target, signal_strategy = self._entry_signal(index, features, row, regime, or_high, or_low)
            if target == 0:
                continue

            direction = target
            entry_index = index + 1
            entry_row = next_row
            entry_price = self._entry_price(float(next_row["open"]), direction)
            entry_strategy = signal_strategy
            entry_regime = regime
            session_trade_count += 1

        if direction != 0 and entry_price is not None and entry_row is not None and entry_index is not None:
            final_row = features.iloc[-1]
            final_price = self._exit_price(float(final_row["close"]), direction)
            trades.append(
                self._make_trade(
                    date,
                    entry_row,
                    final_row,
                    entry_price,
                    final_price,
                    direction,
                    entry_index,
                    len(features) - 1,
                    "session_end",
                    entry_strategy,
                    entry_regime,
                )
            )

        return trades, position_rows

    def _entry_signal(
        self,
        index: int,
        features: pd.DataFrame,
        row: pd.Series,
        regime: str,
        or_high: float | None,
        or_low: float | None,
    ) -> tuple[int, str]:
        """Return entry target and sub-strategy for the current signal bar."""
        opening_window_passed = index >= int(self.params.get("opening_window", 30))
        if self.strategy == "ORB":
            if not opening_window_passed:
                return 0, "ORB"
            return (
                orb_signal(
                    float(row["close"]),
                    or_high,
                    or_low,
                    float(self.params.get("buffer_points", 10)),
                    0,
                ),
                "ORB",
            )
        if self.strategy == "MR":
            return (
                mr_signal(
                    float(row["z_score"]),
                    float(self.params.get("z_entry", 2.0)),
                    float(self.params.get("z_exit", 0.25)),
                    0,
                ),
                "MR",
            )
        if self.strategy in {"ORB_FILTERED_HYBRID", "ORB_CONFIRMED_HYBRID"}:
            if regime != TREND or not opening_window_passed:
                return 0, ""
            if self.strategy == "ORB_CONFIRMED_HYBRID" and not self._passes_trend_confirmation(row):
                return 0, ""
            if not self._passes_orb_confirmation_filters(index, features, row, or_high, or_low):
                return 0, ""
            return (
                orb_signal(
                    float(row["close"]),
                    or_high,
                    or_low,
                    float(self.params.get("buffer_points", 10)),
                    0,
                ),
                "ORB_CONFIRMED" if self.strategy == "ORB_CONFIRMED_HYBRID" else "ORB_FILTERED",
            )

        target = hybrid_signal(
            regime,
            float(row["close"]),
            float(row["z_score"]),
            or_high,
            or_low,
            float(self.params.get("buffer_points", 10)),
            float(self.params.get("z_entry", 2.0)),
            float(self.params.get("z_exit", 0.25)),
            0,
            opening_window_passed,
        )
        if target == 0:
            return 0, ""
        return target, "ORB" if regime == TREND else "MR"

    def _passes_orb_confirmation_filters(
        self,
        index: int,
        features: pd.DataFrame,
        row: pd.Series,
        or_high: float | None,
        or_low: float | None,
    ) -> bool:
        """Apply optional ORB entry filters for supplementary experiments."""
        if or_high is None or or_low is None:
            return False

        buffer_points = float(self.params.get("buffer_points", 10))
        upper_breakout = or_high + buffer_points
        lower_breakout = or_low - buffer_points

        if bool(self.params.get("use_two_bar_confirmation", False)):
            if index <= 0:
                return False
            previous_close = float(features.iloc[index - 1]["close"])
            current_close = float(row["close"])
            two_bar_long = current_close > upper_breakout and previous_close > upper_breakout
            two_bar_short = current_close < lower_breakout and previous_close < lower_breakout
            if not (two_bar_long or two_bar_short):
                return False

        if bool(self.params.get("use_volume_filter", False)):
            volume_window = int(self.params.get("volume_window", 30))
            volume_multiplier = float(self.params.get("volume_multiplier", 1.0))
            start = max(0, index - volume_window + 1)
            rolling_volume = float(features.iloc[start : index + 1]["volume"].mean())
            if float(row["volume"]) < rolling_volume * volume_multiplier:
                return False

        if bool(self.params.get("use_vwap_direction_filter", False)):
            current_close = float(row["close"])
            current_vwap = float(row["vwap"])
            long_breakout = current_close > upper_breakout
            short_breakout = current_close < lower_breakout
            if long_breakout and current_close <= current_vwap:
                return False
            if short_breakout and current_close >= current_vwap:
                return False

        latest_entry_time = self.params.get("latest_entry_time")
        if latest_entry_time is not None and int(row["time"]) > int(latest_entry_time):
            return False

        if bool(self.params.get("use_or_width_filter", False)):
            threshold = self.params.get("max_or_width_points")
            if threshold is None:
                return False
            if (or_high - or_low) > float(threshold):
                return False

        return True

    def _passes_trend_confirmation(self, row: pd.Series) -> bool:
        """Require stronger trend evidence for the confirmed supplementary variant."""
        er_margin = float(self.params.get("er_margin", 0))
        threshold = float(self.params.get("er_threshold", 0.35)) + er_margin
        return float(row["ER"]) > threshold

    def _run_flat(self) -> BacktestResult:
        """Return a zero-PnL flat benchmark."""
        daily_pnl = {date: 0.0 for date in self.sessions}
        positions = [
            self._position_row(date, row, 0)
            for date, session_df in self.sessions.items()
            for _, row in session_df.iterrows()
        ]
        return self._build_result([], daily_pnl, positions)

    def _run_intraday_long(self) -> BacktestResult:
        """Long the first bar open and exit the final bar close each session."""
        trades: list[Trade] = []
        positions: list[dict[str, Any]] = []
        daily_pnl: dict[int, float] = {}
        for date, session_df in self.sessions.items():
            session = session_df.sort_values("datetime").reset_index(drop=True)
            for _, row in session.iterrows():
                positions.append(self._position_row(date, row, 1))
            trade = self._make_trade(
                date,
                session.iloc[0],
                session.iloc[-1],
                self._entry_price(float(session.iloc[0]["open"]), 1),
                self._exit_price(float(session.iloc[-1]["close"]), 1),
                1,
                0,
                len(session) - 1,
                "session_end",
                "INTRADAY_LONG",
                RANGE,
            )
            trades.append(trade)
            daily_pnl[date] = trade.pnl_points
        return self._build_result(trades, daily_pnl, positions)

    def _run_buy_and_hold(self) -> BacktestResult:
        """Long the first available day-session open through the final close."""
        daily_pnl = {date: 0.0 for date in self.sessions}
        positions: list[dict[str, Any]] = []
        if not self.sessions:
            return self._build_result([], daily_pnl, positions)

        ordered_sessions = list(self.sessions.items())
        first_date, first_session = ordered_sessions[0]
        last_date, last_session = ordered_sessions[-1]
        first_session = first_session.sort_values("datetime").reset_index(drop=True)
        last_session = last_session.sort_values("datetime").reset_index(drop=True)
        holding_bars = 0
        for date, session_df in ordered_sessions:
            ordered = session_df.sort_values("datetime").reset_index(drop=True)
            holding_bars += len(ordered)
            for _, row in ordered.iterrows():
                positions.append(self._position_row(date, row, 1))
        trade = self._make_trade(
            first_date,
            first_session.iloc[0],
            last_session.iloc[-1],
            self._entry_price(float(first_session.iloc[0]["open"]), 1),
            self._exit_price(float(last_session.iloc[-1]["close"]), 1),
            1,
            0,
            max(holding_bars - 1, 0),
            "session_end",
            "BUY_AND_HOLD",
            RANGE,
        )
        daily_pnl[last_date] = trade.pnl_points
        return self._build_result([trade], daily_pnl, positions)

    def _build_result(
        self,
        trades: list[Trade],
        daily_pnl: dict[int, float],
        positions: list[dict[str, Any]],
    ) -> BacktestResult:
        """Build the standard result container."""
        return BacktestResult(
            trades=trades,
            daily_pnl=daily_pnl,
            positions=pd.DataFrame(positions),
            equity_curve=compute_equity_curve(daily_pnl),
            params=dict(self.params),
            strategy_name=self.strategy,
        )

    def _make_trade(
        self,
        date: int,
        entry_row: pd.Series,
        exit_row: pd.Series,
        entry_price: float,
        exit_price: float,
        direction: int,
        entry_index: int,
        exit_index: int,
        exit_reason: str,
        strategy_at_entry: str,
        regime_at_entry: str,
    ) -> Trade:
        """Create one realized trade record."""
        pnl_points = direction * (exit_price - entry_price) - self.commission_rt
        return Trade(
            date=int(date),
            entry_time=int(entry_row["time"]),
            exit_time=int(exit_row["time"]),
            entry_datetime=pd.Timestamp(entry_row["datetime"]),
            exit_datetime=pd.Timestamp(exit_row["datetime"]),
            entry_price=float(entry_price),
            exit_price=float(exit_price),
            direction=int(direction),
            pnl_points=float(pnl_points),
            pnl_hkd=float(pnl_points * CONTRACT_MULTIPLIER),
            holding_bars=max(int(exit_index - entry_index), 0),
            exit_reason=exit_reason,
            strategy_at_entry=strategy_at_entry,
            regime_at_entry=regime_at_entry,
        )

    def _entry_price(self, open_price: float, direction: int) -> float:
        """Apply one side of slippage to an entry open."""
        return open_price + self.slippage if direction == 1 else open_price - self.slippage

    def _exit_price(self, execution_price: float, direction: int) -> float:
        """Apply one side of slippage to an exit execution."""
        return execution_price - self.slippage if direction == 1 else execution_price + self.slippage

    def _position_row(self, date: int, row: pd.Series, direction: int) -> dict[str, Any]:
        """Serialize bar position state for later inspection."""
        return {
            "date": int(date),
            "datetime": pd.Timestamp(row["datetime"]),
            "time": int(row["time"]),
            "position": int(direction),
            "strategy": self.strategy,
        }
