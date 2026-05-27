"""Plot helpers for exploratory strategy outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.metrics import compute_drawdown


def save_cumulative_pnl(equity_curves: Mapping[str, pd.Series], filepath: str | Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for label, curve in equity_curves.items():
        if curve.empty:
            continue
        ax.plot(_date_index(curve.index), curve.values, linewidth=1.3, label=label)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(title=title, xlabel="Date", ylabel="Cumulative PnL points")
    ax.legend(fontsize=8)
    _save(fig, filepath)


def save_validation_ranking(ranking: pd.DataFrame, filepath: str | Path) -> None:
    top = ranking.head(12).copy()
    fig, ax = plt.subplots(figsize=(10, 5))
    labels = top["variant"].astype(str) + "\n" + top["params_id"].astype(str)
    ax.bar(labels, top["score"], color="#4C78A8")
    ax.set(title="Validation Ranking", ylabel="Validation score")
    ax.tick_params(axis="x", labelrotation=60)
    _save(fig, filepath)


def save_metric_bar(results: pd.DataFrame, metric: str, filepath: str | Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    table = results.copy()
    ax.bar(table["strategy"], table[metric], color="#59A14F")
    ax.set(title=title, ylabel=metric)
    ax.tick_params(axis="x", labelrotation=35)
    _save(fig, filepath)


def save_drawdown_comparison(equity_curves: Mapping[str, pd.Series], filepath: str | Path) -> None:
    rows = []
    for label, curve in equity_curves.items():
        _, max_drawdown, _ = compute_drawdown(curve)
        rows.append({"strategy": label, "max_drawdown_points": max_drawdown})
    save_metric_bar(pd.DataFrame(rows), "max_drawdown_points", filepath, "Test Drawdown Comparison")


def save_pnl_vs_turnover(results: pd.DataFrame, filepath: str | Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(results["trades_per_day"], results["cumulative_pnl_points"], s=60, color="#E15759")
    for _, row in results.iterrows():
        ax.annotate(str(row["strategy"]), (row["trades_per_day"], row["cumulative_pnl_points"]), fontsize=8)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(title="PnL vs Turnover", xlabel="Trades per day", ylabel="Cumulative PnL points")
    _save(fig, filepath)


def save_family_comparison(validation: pd.DataFrame, filepath: str | Path) -> None:
    grouped = (
        validation.groupby("family", as_index=False)
        .agg(best_score=("score", "max"), best_sharpe=("sharpe_ratio", "max"), median_score=("score", "median"))
        .sort_values("best_score", ascending=False)
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(grouped["family"], grouped["best_score"], color="#F28E2B")
    ax.set(title="Strategy Family Comparison", ylabel="Best validation score")
    ax.tick_params(axis="x", labelrotation=25)
    _save(fig, filepath)


def _date_index(index: pd.Index) -> pd.DatetimeIndex:
    return pd.to_datetime(index.astype(str), format="%Y%m%d")


def _save(fig: plt.Figure, filepath: str | Path) -> None:
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)

