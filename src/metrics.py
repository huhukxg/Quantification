"""Performance metrics for Stage 3 backtest results."""

from __future__ import annotations

from dataclasses import asdict
from math import sqrt
from typing import Any

import numpy as np
import pandas as pd

from src.config import CONTRACT_MULTIPLIER


def trades_to_dataframe(trades: list[Any]) -> pd.DataFrame:
    """Convert Trade dataclasses into a tabular log."""
    if not trades:
        return pd.DataFrame(
            columns=[
                "date",
                "entry_time",
                "exit_time",
                "entry_datetime",
                "exit_datetime",
                "entry_price",
                "exit_price",
                "direction",
                "pnl_points",
                "pnl_hkd",
                "holding_bars",
                "exit_reason",
                "strategy_at_entry",
                "regime_at_entry",
            ]
        )
    rows = [asdict(trade) if hasattr(trade, "__dataclass_fields__") else dict(trade) for trade in trades]
    return pd.DataFrame(rows)


def _daily_pnl_series(daily_pnl: dict[int, float] | pd.Series) -> pd.Series:
    """Normalize daily PnL into a sorted float Series."""
    series = daily_pnl.copy() if isinstance(daily_pnl, pd.Series) else pd.Series(daily_pnl, dtype=float)
    if series.empty:
        return pd.Series(dtype=float)
    return series.astype(float).sort_index()


def compute_equity_curve(daily_pnl: dict[int, float] | pd.Series) -> pd.Series:
    """Compute cumulative realized PnL in points."""
    return _daily_pnl_series(daily_pnl).cumsum().rename("equity_points")


def compute_drawdown(equity_curve: pd.Series) -> tuple[pd.Series, float, int]:
    """Compute point drawdown and longest drawdown duration."""
    if equity_curve.empty:
        return pd.Series(dtype=float), 0.0, 0
    drawdown = equity_curve - equity_curve.cummax()
    max_duration = 0
    duration = 0
    for value in drawdown:
        if value < 0:
            duration += 1
            max_duration = max(max_duration, duration)
        else:
            duration = 0
    return drawdown.rename("drawdown_points"), float(drawdown.min()), int(max_duration)


def compute_all_metrics(trades: list[Any], daily_pnl: dict[int, float] | pd.Series) -> dict[str, float | int]:
    """Compute daily, trade, risk, and drawdown metrics."""
    daily = _daily_pnl_series(daily_pnl)
    trades_df = trades_to_dataframe(trades)
    equity_curve = compute_equity_curve(daily)
    _, max_drawdown, max_drawdown_duration = compute_drawdown(equity_curve)

    cumulative = float(daily.sum()) if not daily.empty else 0.0
    avg_daily = float(daily.mean()) if not daily.empty else 0.0
    std_daily = float(daily.std(ddof=1)) if len(daily) > 1 else 0.0
    downside = daily.loc[daily < 0]
    downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    annualized_pnl = avg_daily * 252
    sharpe = avg_daily / std_daily * sqrt(252) if std_daily else 0.0
    sortino = avg_daily / downside_std * sqrt(252) if downside_std else 0.0
    calmar = annualized_pnl / abs(max_drawdown) if max_drawdown < 0 else 0.0

    pnl_trades = trades_df["pnl_points"] if not trades_df.empty else pd.Series(dtype=float)
    winners = pnl_trades.loc[pnl_trades > 0]
    losers = pnl_trades.loc[pnl_trades < 0]
    gross_profit = float(winners.sum()) if not winners.empty else 0.0
    gross_loss = abs(float(losers.sum())) if not losers.empty else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0)
    max_wins, max_losses = _compute_streaks(pnl_trades)

    return {
        "cumulative_pnl_points": cumulative,
        "cumulative_pnl_hkd": cumulative * CONTRACT_MULTIPLIER,
        "avg_daily_pnl": avg_daily,
        "std_daily_pnl": std_daily,
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "annualized_pnl": float(annualized_pnl),
        "max_drawdown_points": max_drawdown,
        "max_drawdown_duration_days": max_drawdown_duration,
        "calmar_ratio": float(calmar),
        "var_95": float(daily.quantile(0.05)) if not daily.empty else 0.0,
        "var_99": float(daily.quantile(0.01)) if not daily.empty else 0.0,
        "num_trades": int(len(pnl_trades)),
        "trades_per_day": float(len(pnl_trades) / len(daily)) if len(daily) else 0.0,
        "win_rate": float((pnl_trades > 0).mean()) if len(pnl_trades) else 0.0,
        "avg_winner": float(winners.mean()) if not winners.empty else 0.0,
        "avg_loser": float(losers.mean()) if not losers.empty else 0.0,
        "avg_pnl_per_trade": float(pnl_trades.mean()) if len(pnl_trades) else 0.0,
        "profit_factor": float(profit_factor),
        "avg_holding_bars": float(trades_df["holding_bars"].mean()) if not trades_df.empty else 0.0,
        "max_single_trade_loss": float(pnl_trades.min()) if len(pnl_trades) else 0.0,
        "max_consecutive_wins": max_wins,
        "max_consecutive_losses": max_losses,
    }


def compute_monthly_pnl(daily_pnl: dict[int, float] | pd.Series) -> pd.DataFrame:
    """Aggregate daily realized point PnL by calendar month."""
    daily = _daily_pnl_series(daily_pnl)
    if daily.empty:
        return pd.DataFrame(columns=["month", "pnl_points", "pnl_hkd"])
    dates = pd.to_datetime(daily.index.astype(str), format="%Y%m%d")
    monthly = daily.groupby(dates.to_period("M")).sum().rename("pnl_points").reset_index()
    monthly["month"] = monthly["index"].astype(str)
    monthly = monthly.drop(columns="index")
    monthly["pnl_hkd"] = monthly["pnl_points"] * CONTRACT_MULTIPLIER
    return monthly[["month", "pnl_points", "pnl_hkd"]]


def compute_regime_performance(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Summarize trade PnL by entry regime."""
    if trades_df.empty:
        return pd.DataFrame(columns=["regime_at_entry", "num_trades", "pnl_points", "win_rate", "avg_trade_pnl"])
    return (
        trades_df.groupby("regime_at_entry", dropna=False)["pnl_points"]
        .agg(num_trades="size", pnl_points="sum", win_rate=lambda pnl: float((pnl > 0).mean()), avg_trade_pnl="mean")
        .reset_index()
    )


def _compute_streaks(pnl_trades: pd.Series) -> tuple[int, int]:
    """Return longest winning and losing trade streaks."""
    max_wins = max_losses = current_wins = current_losses = 0
    for pnl in pnl_trades:
        if pnl > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        elif pnl < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)
        else:
            current_wins = 0
            current_losses = 0
    return max_wins, max_losses
