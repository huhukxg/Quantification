"""Matplotlib figures used by fast mode reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.metrics import compute_drawdown
from src.utils import ensure_dir


def plot_price_series(data: pd.DataFrame, filepath: str | Path) -> None:
    """Plot cleaned close-price history."""
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(data["datetime"], data["close"], linewidth=0.6)
    ax.set(title="HSI Futures Close Price", xlabel="Date", ylabel="Index points")
    _save(fig, filepath)


def plot_return_distribution(returns: pd.Series, filepath: str | Path) -> None:
    """Plot close-return histogram."""
    values = returns.replace([np.inf, -np.inf], np.nan).dropna()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(values, bins=80, color="#2b6cb0", alpha=0.85)
    ax.set(title="Intraday Return Distribution", xlabel="Return", ylabel="Bars")
    _save(fig, filepath)


def plot_intraday_pattern_return(data: pd.DataFrame, filepath: str | Path) -> None:
    """Plot average minute return by raw day-session time."""
    returns = data.groupby("date")["close"].pct_change().fillna(0)
    pattern = pd.DataFrame({"time": data["time"], "return": returns}).groupby("time")["return"].mean()
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(pattern.index.astype(str), pattern.values, linewidth=1.0)
    ax.set(title="Average Intraday Return Pattern", xlabel="Time", ylabel="Mean return")
    ax.tick_params(axis="x", labelrotation=70)
    ax.xaxis.set_major_locator(plt.MaxNLocator(12))
    _save(fig, filepath)


def plot_intraday_pattern_volume(data: pd.DataFrame, filepath: str | Path) -> None:
    """Plot average bar volume by raw day-session time."""
    pattern = data.groupby("time")["volume"].mean()
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(pattern.index.astype(str), pattern.values, linewidth=1.0, color="#2f855a")
    ax.set(title="Average Intraday Volume Pattern", xlabel="Time", ylabel="Mean volume")
    ax.tick_params(axis="x", labelrotation=70)
    ax.xaxis.set_major_locator(plt.MaxNLocator(12))
    _save(fig, filepath)


def plot_cumulative_pnl(equity_curves: Mapping[str, pd.Series], filepath: str | Path, title: str = "Cumulative PnL") -> None:
    """Plot strategy equity curves in point PnL."""
    fig, ax = plt.subplots(figsize=(10, 5))
    for name, curve in equity_curves.items():
        if curve.empty:
            continue
        ax.plot(_date_index(curve.index), curve.values, label=name, linewidth=1.2)
    ax.set(title=title, xlabel="Date", ylabel="Cumulative PnL points")
    ax.legend(loc="best", fontsize=8)
    _save(fig, filepath)


def plot_drawdown(equity_curve: pd.Series, filepath: str | Path) -> None:
    """Plot strategy drawdown from a point equity curve."""
    drawdown, _, _ = compute_drawdown(equity_curve)
    fig, ax = plt.subplots(figsize=(10, 4))
    if not drawdown.empty:
        ax.fill_between(_date_index(drawdown.index), drawdown.values, 0, alpha=0.55, color="#c53030")
    ax.set(title="HYBRID Drawdown", xlabel="Date", ylabel="Drawdown points")
    _save(fig, filepath)


def plot_trade_distribution(trades_df: pd.DataFrame, filepath: str | Path) -> None:
    """Plot realized trade PnL distribution."""
    fig, ax = plt.subplots(figsize=(7, 4))
    if not trades_df.empty:
        ax.hist(trades_df["pnl_points"], bins=40, color="#805ad5", alpha=0.85)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set(title="HYBRID Trade PnL Distribution", xlabel="PnL points", ylabel="Trades")
    _save(fig, filepath)


def plot_param_heatmap(
    results: pd.DataFrame,
    x_param: str,
    y_param: str,
    filepath: str | Path,
    value: str = "sharpe_ratio",
) -> None:
    """Plot mean grid metric for a two-parameter projection."""
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    if results.empty or x_param not in results or y_param not in results:
        ax.text(0.5, 0.5, "No parameter grid data", ha="center", va="center")
        ax.set_axis_off()
    else:
        pivot = results.pivot_table(index=y_param, columns=x_param, values=value, aggfunc="mean")
        matrix = pivot.to_numpy(dtype=float)
        image = ax.imshow(matrix, aspect="auto", cmap="RdYlGn")
        ax.set_xticks(range(len(pivot.columns)), [str(column) for column in pivot.columns])
        ax.set_yticks(range(len(pivot.index)), [str(index) for index in pivot.index])
        ax.set(xlabel=x_param, ylabel=y_param, title=f"{value} by {x_param} and {y_param}")
        fig.colorbar(image, ax=ax, shrink=0.85)
    _save(fig, filepath)


def plot_validation_candidate_bars(results: pd.DataFrame, filepath: str | Path) -> None:
    """Plot top validation candidates by Sharpe with key parameter labels."""
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    required = {"validation_rank", "sharpe_ratio", "stop_loss_points", "take_profit_points", "max_trades"}
    if results.empty or not required.issubset(results.columns):
        ax.text(0.5, 0.5, "No validation candidate data", ha="center", va="center")
        ax.set_axis_off()
    else:
        top = results.sort_values("validation_rank").head(5).copy()
        labels = [
            f"#{int(row.validation_rank)}\nSL {int(row.stop_loss_points)} / TP {int(row.take_profit_points)}\nmax {int(row.max_trades)}"
            for row in top.itertuples()
        ]
        values = top["sharpe_ratio"].astype(float).to_numpy()
        bars = ax.bar(labels, values, color="#4C78A8", edgecolor="#26394f", linewidth=0.8)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set(
            title="Top ORB validation candidates by Sharpe",
            xlabel="Validation rank and key risk parameters",
            ylabel="Validation Sharpe",
        )
        ax.set_ylim(0, max(values) * 1.22)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.3f}", ha="center", va="bottom")
        if {"opening_window", "buffer_points"}.issubset(top.columns):
            openings = sorted(top["opening_window"].dropna().unique())
            buffers = sorted(top["buffer_points"].dropna().unique())
            if len(openings) == 1 and len(buffers) == 1:
                note = f"All top-five candidates use opening window {int(openings[0])} and buffer {int(buffers[0])}."
                ax.text(0.5, -0.28, note, ha="center", va="top", transform=ax.transAxes, fontsize=9)
    _save(fig, filepath)


def plot_slippage_sensitivity(sensitivity: pd.DataFrame, filepath: str | Path) -> None:
    """Plot HYBRID PnL under slippage assumptions."""
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(sensitivity["slippage"], sensitivity["cumulative_pnl_points"], marker="o")
    ax.set(title="HYBRID Slippage Sensitivity", xlabel="Slippage points per side", ylabel="Cumulative PnL points")
    _save(fig, filepath)


def plot_sharpe_vs_slippage(sensitivity: pd.DataFrame, filepath: str | Path) -> None:
    """Plot HYBRID Sharpe under slippage assumptions."""
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(sensitivity["slippage"], sensitivity["sharpe_ratio"], marker="o", color="#dd6b20")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(title="Sharpe vs Slippage", xlabel="Slippage points per side", ylabel="Sharpe ratio")
    _save(fig, filepath)


def plot_monthly_pnl_heatmap(monthly_pnl: pd.DataFrame, filepath: str | Path) -> None:
    """Plot monthly point PnL as a year-by-month heatmap."""
    fig, ax = plt.subplots(figsize=(8, 3.8))
    if monthly_pnl.empty:
        ax.text(0.5, 0.5, "No monthly PnL", ha="center", va="center")
        ax.set_axis_off()
    else:
        months = pd.PeriodIndex(monthly_pnl["month"], freq="M")
        frame = monthly_pnl.assign(year=months.year, month_num=months.month)
        pivot = frame.pivot_table(index="year", columns="month_num", values="pnl_points", aggfunc="sum", fill_value=0)
        image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn")
        ax.set_xticks(range(len(pivot.columns)), [str(month) for month in pivot.columns])
        ax.set_yticks(range(len(pivot.index)), [str(year) for year in pivot.index])
        ax.set(title="Monthly HYBRID PnL", xlabel="Month", ylabel="Year")
        fig.colorbar(image, ax=ax, shrink=0.85)
    _save(fig, filepath)


def _date_index(index: pd.Index) -> pd.DatetimeIndex:
    """Parse integer YYYYMMDD date indexes for plots."""
    return pd.to_datetime(index.astype(str), format="%Y%m%d")


def _save(fig: plt.Figure, filepath: str | Path) -> None:
    """Finalize and save one figure."""
    path = Path(filepath)
    ensure_dir(path.parent)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
