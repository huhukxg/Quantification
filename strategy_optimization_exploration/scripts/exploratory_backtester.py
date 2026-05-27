"""Exploratory backtester for isolated post-analysis strategy variants."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.backtester import BacktestResult, Trade
from src.config import CONTRACT_MULTIPLIER, FORCED_EXIT_TIME
from src.features import compute_session_features
from src.metrics import compute_equity_curve
from src.regime import EXTREME, RANGE, TREND, classify_regime_series
from src.risk_manager import RiskManager
from src.strategies import hybrid_signal, mr_signal, orb_signal


class ExploratoryBacktester:
    """Backtest exploratory strategy variants without modifying `src/backtester.py`."""

    def __init__(
        self,
        sessions: dict[int, pd.DataFrame],
        variant: str,
        params: dict[str, Any],
        slippage: float,
        commission_rt: float,
        extreme_vol_threshold: float | None = None,
        low_rv_threshold: float | None = None,
    ) -> None:
        self.sessions = dict(sorted(sessions.items()))
        self.variant = variant
        self.params = dict(params)
        self.slippage = float(slippage)
        self.commission_rt = float(commission_rt)
        self.extreme_vol_threshold = extreme_vol_threshold
        self.low_rv_threshold = low_rv_threshold
        self.risk_manager = RiskManager(
            stop_loss_points=float(self.params.get("stop_loss_points", 80)),
            take_profit_points=float(self.params.get("take_profit_points", 120)),
            max_trades=int(self.params.get("max_trades", 3)),
            max_daily_loss=float(self.params.get("max_daily_loss", 200)),
            forced_exit_time=int(self.params.get("forced_exit_time", FORCED_EXIT_TIME)),
        )

    def run(self) -> BacktestResult:
        """Run the exploratory variant across all sessions."""
        all_trades: list[Trade] = []
        daily_pnl: dict[int, float] = {}
        position_rows: list[dict[str, Any]] = []
        for date, session_df in self.sessions.items():
            trades, positions = self._run_session(date, session_df)
            all_trades.extend(trades)
            daily_pnl[date] = float(sum(trade.pnl_points for trade in trades))
            position_rows.extend(positions)
        return BacktestResult(
            trades=all_trades,
            daily_pnl=daily_pnl,
            positions=pd.DataFrame(position_rows),
            equity_curve=compute_equity_curve(daily_pnl),
            params=dict(self.params),
            strategy_name=self.variant,
        )

    def _run_session(self, date: int, session_df: pd.DataFrame) -> tuple[list[Trade], list[dict[str, Any]]]:
        session = session_df.sort_values("datetime").reset_index(drop=True)
        features = compute_session_features(session, self.params)
        regimes = self._classify(features)
        or_high = features.attrs["OR_high"]
        or_low = features.attrs["OR_low"]

        trades: list[Trade] = []
        positions: list[dict[str, Any]] = []
        direction = 0
        entry_index: int | None = None
        entry_row: pd.Series | None = None
        entry_price: float | None = None
        entry_strategy = ""
        entry_regime = ""
        session_realized_pnl = 0.0
        session_trade_count = 0
        cooldown_until = -1
        stopped_once = False

        for index in range(len(features)):
            row = features.iloc[index]
            regime = str(regimes.iloc[index])
            positions.append(self._position_row(date, row, direction, regime))
            if index >= len(features) - 1:
                continue

            next_row = features.iloc[index + 1]
            exit_reason = None
            if direction != 0 and entry_price is not None and entry_row is not None and entry_index is not None:
                exit_reason = self._exit_reason(row, regime, direction, entry_price, entry_strategy)
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
                    if exit_reason == "stop_loss":
                        stopped_once = True
                        cooldown_until = index + int(self.params.get("cooldown_bars", 0))
                    continue

            if direction != 0 or not self.risk_manager.can_trade(session_trade_count, session_realized_pnl):
                continue
            if index < cooldown_until:
                continue
            if stopped_once and bool(self.params.get("no_reentry_after_stop", False)):
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
        return trades, positions

    def _classify(self, features: pd.DataFrame) -> pd.Series:
        if self.variant.startswith(("ORB_ONLY", "LONG_OR_FLAT", "LONG_ONLY_ORB", "ORB_TO_CLOSE")):
            return pd.Series(TREND, index=features.index)
        if self.variant == "STRICT_MR_ONLY":
            return pd.Series(RANGE, index=features.index)
        threshold = self.extreme_vol_threshold
        if threshold is None:
            threshold = float("inf")
        return classify_regime_series(
            features["ER"],
            features["RV"],
            float(self.params.get("er_threshold", 0.35)),
            float(threshold),
        )

    def _exit_reason(
        self,
        row: pd.Series,
        regime: str,
        direction: int,
        entry_price: float,
        entry_strategy: str,
    ) -> str | None:
        if not bool(self.params.get("disable_stop_loss", False)) and self.risk_manager.check_stop_loss(entry_price, float(row["close"]), direction):
            return "stop_loss"
        if (
            not bool(self.params.get("hold_to_close", False))
            and not bool(self.params.get("disable_take_profit", False))
            and self.risk_manager.check_take_profit(entry_price, float(row["close"]), direction)
        ):
            return "take_profit"
        if self.risk_manager.check_session_end(int(row["time"])):
            return "session_end"
        if regime == EXTREME and bool(self.params.get("close_on_extreme", self.params.get("extreme_action", "close") == "close")):
            return "regime_extreme"
        if entry_strategy.startswith("MR"):
            target = mr_signal(
                float(row["z_score"]),
                float(self.params.get("z_entry", 2.0)),
                float(self.params.get("z_exit", 0.25)),
                direction,
            )
            if target == 0:
                return "mr_exit"
        return None

    def _entry_signal(
        self,
        index: int,
        features: pd.DataFrame,
        row: pd.Series,
        regime: str,
        or_high: float | None,
        or_low: float | None,
    ) -> tuple[int, str]:
        variant = self.variant
        opening_window_passed = index >= int(self.params.get("opening_window", 30))

        if variant.startswith("LONG_OR_FLAT"):
            if not opening_window_passed or not self._passes_long_day_filter(index, features, row, or_high, or_low, regime):
                return 0, ""
            return 1, "LONG_FILTERED"

        if variant.startswith("LONG_ONLY_ORB"):
            if not opening_window_passed or not self._passes_orb_filters(index, features, row, or_high, or_low):
                return 0, ""
            target = self._orb_target(row, or_high, or_low)
            return (1, "LONG_ONLY_ORB") if target == 1 else (0, "")

        if variant.startswith("ORB_TO_CLOSE"):
            if not opening_window_passed or not self._passes_orb_filters(index, features, row, or_high, or_low):
                return 0, ""
            target = self._orb_target(row, or_high, or_low)
            if bool(self.params.get("long_only", True)) and target != 1:
                return 0, ""
            return target, "ORB_TO_CLOSE" if target else ""

        if variant.startswith("EXTREME_TREND"):
            if regime != EXTREME or not opening_window_passed:
                return 0, ""
            if not self._passes_long_day_filter(index, features, row, or_high, or_low, regime):
                return 0, ""
            return 1, "EXTREME_LONG"

        if variant.startswith("ORB_ONLY"):
            if not opening_window_passed or not self._passes_orb_filters(index, features, row, or_high, or_low):
                return 0, ""
            target = self._orb_target(row, or_high, or_low)
            return target, "ORB" if target else ""

        if variant == "STRICT_MR_ONLY":
            target = self._strict_mr_target(index, features, row)
            return target, "MR_STRICT" if target else ""

        if variant.startswith("ORB_FILTERED_HYBRID"):
            if regime != TREND or not opening_window_passed:
                return 0, ""
            if not self._passes_trend_margin(row):
                return 0, ""
            if not self._passes_orb_filters(index, features, row, or_high, or_low):
                return 0, ""
            target = self._orb_target(row, or_high, or_low)
            return target, "ORB_FILTERED" if target else ""

        if variant == "STRICT_MR_HYBRID":
            if regime == TREND:
                if not opening_window_passed or not self._passes_orb_filters(index, features, row, or_high, or_low):
                    return 0, ""
                target = self._orb_target(row, or_high, or_low)
                return target, "ORB" if target else ""
            if regime == RANGE:
                target = self._strict_mr_target(index, features, row)
                return target, "MR_STRICT" if target else ""
            return 0, ""

        if variant.startswith("LOW_TURNOVER_HYBRID"):
            if not self._passes_no_boundary(row, regime):
                return 0, ""
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
            return target, "ORB" if target and regime == TREND else ("MR" if target else "")

        raise ValueError(f"Unknown exploratory variant: {variant}")

    def _orb_target(self, row: pd.Series, or_high: float | None, or_low: float | None) -> int:
        return orb_signal(
            float(row["close"]),
            or_high,
            or_low,
            float(self.params.get("buffer_points", 10)),
            0,
        )

    def _passes_trend_margin(self, row: pd.Series) -> bool:
        margin = float(self.params.get("er_margin", 0.0))
        threshold = float(self.params.get("er_threshold", 0.35)) + margin
        return float(row["ER"]) > threshold

    def _passes_no_boundary(self, row: pd.Series, regime: str) -> bool:
        margin = float(self.params.get("boundary_margin", 0.0))
        if margin <= 0 or regime == EXTREME:
            return True
        threshold = float(self.params.get("er_threshold", 0.35))
        return abs(float(row["ER"]) - threshold) > margin

    def _passes_orb_filters(
        self,
        index: int,
        features: pd.DataFrame,
        row: pd.Series,
        or_high: float | None,
        or_low: float | None,
    ) -> bool:
        if or_high is None or or_low is None:
            return False
        buffer_points = float(self.params.get("buffer_points", 10))
        upper = or_high + buffer_points
        lower = or_low - buffer_points
        current_close = float(row["close"])
        long_breakout = current_close > upper
        short_breakout = current_close < lower
        if not (long_breakout or short_breakout):
            return False

        if bool(self.params.get("use_two_bar_confirmation", False)):
            if index <= 0:
                return False
            previous_close = float(features.iloc[index - 1]["close"])
            if long_breakout and previous_close <= upper:
                return False
            if short_breakout and previous_close >= lower:
                return False

        if bool(self.params.get("use_volume_filter", False)):
            volume_window = int(self.params.get("volume_window", 30))
            multiplier = float(self.params.get("volume_multiplier", 1.0))
            start = max(0, index - volume_window + 1)
            rolling_volume = float(features.iloc[start : index + 1]["volume"].mean())
            if float(row["volume"]) < rolling_volume * multiplier:
                return False

        if bool(self.params.get("use_or_width_filter", False)):
            width = float(or_high - or_low)
            min_width = self.params.get("min_or_width_points")
            max_width = self.params.get("max_or_width_points")
            if min_width is not None and width < float(min_width):
                return False
            if max_width is not None and width > float(max_width):
                return False

        latest_entry_time = self.params.get("latest_entry_time")
        if latest_entry_time is not None and int(row["time"]) > int(latest_entry_time):
            return False
        return True

    def _passes_long_day_filter(
        self,
        index: int,
        features: pd.DataFrame,
        row: pd.Series,
        or_high: float | None,
        or_low: float | None,
        regime: str,
    ) -> bool:
        """Return whether opening evidence is strong enough for a long-or-flat day."""
        first_open = float(features.iloc[0]["open"])
        close = float(row["close"])
        opening_return_points = close - first_open
        min_points = float(self.params.get("min_opening_return_points", 0.0))
        if opening_return_points < min_points:
            return False

        if bool(self.params.get("require_close_above_vwap", False)) and close <= float(row["vwap"]):
            return False

        if bool(self.params.get("require_positive_opening_bar", False)) and close <= float(features.iloc[index - 1]["close"]):
            return False

        if bool(self.params.get("require_up_breakout", False)):
            if or_high is None:
                return False
            if close <= float(or_high) + float(self.params.get("buffer_points", 0)):
                return False

        min_er = self.params.get("min_er")
        if min_er is not None and float(row["ER"]) < float(min_er):
            return False

        max_rv = self.params.get("max_rv")
        if max_rv is not None and float(row["RV"]) > float(max_rv):
            return False

        if bool(self.params.get("avoid_extreme", False)) and regime == EXTREME:
            return False

        if bool(self.params.get("use_volume_filter", False)):
            volume_window = int(self.params.get("volume_window", 30))
            multiplier = float(self.params.get("volume_multiplier", 1.0))
            start = max(0, index - volume_window + 1)
            rolling_volume = float(features.iloc[start : index + 1]["volume"].mean())
            if float(row["volume"]) < rolling_volume * multiplier:
                return False

        latest_entry_time = self.params.get("latest_entry_time")
        if latest_entry_time is not None and int(row["time"]) > int(latest_entry_time):
            return False

        return True

    def _strict_mr_target(self, index: int, features: pd.DataFrame, row: pd.Series) -> int:
        if index <= 0:
            return 0
        strict_er = float(self.params.get("strict_er_threshold", 0.25))
        if float(row["ER"]) > strict_er:
            return 0
        if self.low_rv_threshold is not None and float(row["RV"]) > float(self.low_rv_threshold):
            return 0
        z_entry = float(self.params.get("z_entry", 2.0))
        close = float(row["close"])
        previous_close = float(features.iloc[index - 1]["close"])
        z = float(row["z_score"])
        if z < -z_entry and close > previous_close:
            return 1
        if z > z_entry and close < previous_close:
            return -1
        return 0

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
        return open_price + self.slippage if direction == 1 else open_price - self.slippage

    def _exit_price(self, execution_price: float, direction: int) -> float:
        return execution_price - self.slippage if direction == 1 else execution_price + self.slippage

    def _position_row(self, date: int, row: pd.Series, direction: int, regime: str) -> dict[str, Any]:
        return {
            "date": int(date),
            "datetime": pd.Timestamp(row["datetime"]),
            "time": int(row["time"]),
            "position": int(direction),
            "strategy": self.variant,
            "regime": regime,
        }
