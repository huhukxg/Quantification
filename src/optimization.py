"""Parameter grids and staged optimization workflow."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.backtester import Backtester
from src.config import FORCED_EXIT_TIME
from src.metrics import compute_all_metrics
from src.regime import compute_extreme_vol_threshold
from src.utils import ensure_dir

BASE_PARAMS = {
    "opening_window": 30,
    "buffer_points": 10,
    "rolling_window": 60,
    "z_entry": 2.0,
    "z_exit": 0.25,
    "use_vwap": True,
    "min_std_threshold": 5,
    "er_window": 60,
    "er_threshold": 0.35,
    "rv_window": 60,
    "extreme_vol_quantile": 0.90,
    "extreme_action": "close",
    "stop_loss_points": 80,
    "take_profit_points": 120,
    "max_trades": 3,
    "max_daily_loss": 200,
    "forced_exit_time": FORCED_EXIT_TIME,
}
METRIC_COLUMNS = {
    "strategy",
    "params_json",
    "extreme_vol_threshold",
    "cumulative_pnl_points",
    "cumulative_pnl_hkd",
    "avg_daily_pnl",
    "std_daily_pnl",
    "sharpe_ratio",
    "sortino_ratio",
    "annualized_pnl",
    "max_drawdown_points",
    "max_drawdown_duration_days",
    "calmar_ratio",
    "var_95",
    "var_99",
    "num_trades",
    "trades_per_day",
    "win_rate",
    "avg_winner",
    "avg_loser",
    "avg_pnl_per_trade",
    "profit_factor",
    "avg_holding_bars",
    "max_single_trade_loss",
    "max_consecutive_wins",
    "max_consecutive_losses",
}


def generate_orb_grid(fast: bool = False, medium: bool = False) -> list[dict[str, Any]]:
    """Return the ORB optimization grid."""
    if fast:
        values = {
            "opening_window": [30, 60],
            "buffer_points": [5, 10],
            "stop_loss_points": [50, 80],
            "take_profit_points": [80, 120],
            "max_trades": [2],
        }
    elif medium:
        values = {
            "opening_window": [30, 60],
            "buffer_points": [5, 10, 20],
            "stop_loss_points": [50, 80, 120],
            "take_profit_points": [80, 120, 180],
            "max_trades": [2, 3],
        }
    else:
        values = {
            "opening_window": [15, 30, 45, 60],
            "buffer_points": [0, 5, 10, 20],
            "stop_loss_points": [30, 50, 80, 120],
            "take_profit_points": [50, 80, 120, 180],
            "max_trades": [1, 2, 3],
        }
    return _grid(values)


def generate_mr_grid(fast: bool = False, medium: bool = False) -> list[dict[str, Any]]:
    """Return the mean-reversion optimization grid."""
    if fast:
        values = {
            "rolling_window": [60],
            "z_entry": [2.0],
            "z_exit": [0.25],
            "stop_loss_points": [50],
            "take_profit_points": [80],
            "use_vwap": [True],
        }
    elif medium:
        values = {
            "rolling_window": [30, 60, 120],
            "z_entry": [1.5, 2.0, 2.5],
            "z_exit": [0.25],
            "stop_loss_points": [50, 80],
            "take_profit_points": [80, 120],
            "use_vwap": [True],
        }
    else:
        values = {
            "rolling_window": [30, 60, 120],
            "z_entry": [1.5, 2.0, 2.5],
            "z_exit": [0, 0.25, 0.5],
            "stop_loss_points": [30, 50, 80],
            "take_profit_points": [50, 80, 120],
            "use_vwap": [True, False],
        }
    return _grid(values)


def generate_regime_grid(fast: bool = False, medium: bool = False) -> list[dict[str, Any]]:
    """Return the regime-classifier optimization grid."""
    if fast:
        values = {
            "er_window": [60],
            "er_threshold": [0.35, 0.45],
            "rv_window": [60],
            "extreme_vol_quantile": [0.90],
            "extreme_action": ["close"],
        }
    elif medium:
        values = {
            "er_window": [60, 120],
            "er_threshold": [0.35, 0.45],
            "rv_window": [60, 120],
            "extreme_vol_quantile": [0.90, 0.95],
            "extreme_action": ["close", "block_only"],
        }
    else:
        values = {
            "er_window": [30, 60, 120],
            "er_threshold": [0.25, 0.35, 0.45, 0.55],
            "rv_window": [30, 60, 120],
            "extreme_vol_quantile": [0.80, 0.90, 0.95],
            "extreme_action": ["close", "block_only"],
        }
    return _grid(values)


def run_grid_search(
    sessions: dict[int, pd.DataFrame],
    strategy: str,
    param_grid: list[dict[str, Any]],
    slippage: float,
    commission_rt: float,
) -> pd.DataFrame:
    """Run a strategy across parameter dictionaries and rank metrics."""
    rows: list[dict[str, Any]] = []
    for candidate in param_grid:
        params = {**BASE_PARAMS, **candidate}
        threshold = candidate.get("extreme_vol_threshold")
        if strategy.upper() == "HYBRID" and threshold is None:
            threshold = compute_extreme_vol_threshold(
                sessions,
                int(params["rv_window"]),
                float(params["extreme_vol_quantile"]),
            )
            params["extreme_vol_threshold"] = threshold
        result = Backtester(
            sessions,
            strategy,
            params,
            slippage,
            commission_rt,
            extreme_vol_threshold=threshold,
        ).run()
        rows.append(
            {
                "strategy": strategy.upper(),
                "params_json": json.dumps(params, sort_keys=True),
                **params,
                **compute_all_metrics(result.trades, result.daily_pnl),
            }
        )
    if not rows:
        return pd.DataFrame()
    return _rank_results(pd.DataFrame(rows))


def validate_top_params(
    train_results: pd.DataFrame,
    val_sessions: dict[int, pd.DataFrame],
    strategy: str,
    top_n: int = 5,
    slippage: float = 2,
    commission_rt: float = 2,
) -> pd.DataFrame:
    """Evaluate top training candidates on validation sessions."""
    if train_results.empty:
        return train_results.copy()
    top_params = [_params_from_row(row) for _, row in _rank_results(train_results).head(top_n).iterrows()]
    validation = run_grid_search(val_sessions, strategy, top_params, slippage, commission_rt)
    if validation.empty:
        return validation
    validation.insert(1, "validation_rank", range(1, len(validation) + 1))
    return validation


def choose_best_params(validation_results: pd.DataFrame) -> dict[str, Any]:
    """Select one parameter dictionary from validation results."""
    if validation_results.empty:
        raise ValueError("Validation results are empty.")
    best = _rank_results(validation_results).iloc[0]
    return _params_from_row(best)


def run_staged_optimization(
    train_sessions: dict[int, pd.DataFrame],
    val_sessions: dict[int, pd.DataFrame],
    fast: bool = False,
    medium: bool = False,
    slippage: float = 2,
    commission_rt: float = 2,
) -> dict[str, Any]:
    """Tune ORB, MR, then HYBRID regime parameters and save Stage 4 tables."""
    table_dir = ensure_dir(Path("outputs") / "tables")

    orb_train = run_grid_search(train_sessions, "ORB", generate_orb_grid(fast=fast, medium=medium), slippage, commission_rt)
    orb_validation = validate_top_params(orb_train, val_sessions, "ORB", 5, slippage, commission_rt)
    orb_params = choose_best_params(orb_validation)

    mr_train = run_grid_search(train_sessions, "MR", generate_mr_grid(fast=fast, medium=medium), slippage, commission_rt)
    mr_validation = validate_top_params(mr_train, val_sessions, "MR", 5, slippage, commission_rt)
    mr_params = choose_best_params(mr_validation)

    regime_candidates = [
        _merge_hybrid_params(orb_params, mr_params, regime_params)
        for regime_params in generate_regime_grid(fast=fast, medium=medium)
    ]
    regime_train = run_grid_search(train_sessions, "HYBRID", regime_candidates, slippage, commission_rt)
    regime_validation = validate_top_params(regime_train, val_sessions, "HYBRID", 5, slippage, commission_rt)
    hybrid_params = choose_best_params(regime_validation)

    files = {
        "orb_train_grid": orb_train,
        "orb_validation_top5": orb_validation,
        "mr_train_grid": mr_train,
        "mr_validation_top5": mr_validation,
        "regime_train_grid": regime_train,
        "regime_validation_top5": regime_validation,
    }
    for name, table in files.items():
        table.to_csv(table_dir / f"{name}.csv", index=False)

    selected = pd.DataFrame(
        [
            {"selection": "ORB", **orb_params},
            {"selection": "MR", **mr_params},
            {"selection": "HYBRID", **hybrid_params},
        ]
    )
    selected.to_csv(table_dir / "final_selected_params.csv", index=False)
    return {
        "orb_params": orb_params,
        "mr_params": mr_params,
        "hybrid_params": hybrid_params,
        "orb_train_grid": orb_train,
        "orb_validation_top5": orb_validation,
        "mr_train_grid": mr_train,
        "mr_validation_top5": mr_validation,
        "regime_train_grid": regime_train,
        "regime_validation_top5": regime_validation,
        "final_selected_params": selected,
    }


def _grid(values: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Expand a named product grid."""
    keys = list(values)
    return [dict(zip(keys, combination)) for combination in itertools.product(*(values[key] for key in keys))]


def _rank_results(results: pd.DataFrame) -> pd.DataFrame:
    """Rank search output by validation objective and light robustness tie-breakers."""
    ranked = results.copy()
    return ranked.sort_values(
        ["sharpe_ratio", "cumulative_pnl_points", "trades_per_day"],
        ascending=[False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)


def _params_from_row(row: pd.Series) -> dict[str, Any]:
    """Recover parameter values from an optimization result row."""
    if row.get("params_json"):
        return json.loads(row["params_json"])
    return {key: row[key] for key in row.index if key not in METRIC_COLUMNS and not key.endswith("_rank")}


def _merge_hybrid_params(
    orb_params: dict[str, Any],
    mr_params: dict[str, Any],
    regime_params: dict[str, Any],
) -> dict[str, Any]:
    """Build the flat parameter interface used by the current HYBRID engine."""
    return {**BASE_PARAMS, **orb_params, **mr_params, **regime_params}
