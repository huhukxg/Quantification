"""Candidate grids and scoring for exploratory strategy optimization."""

from __future__ import annotations

from itertools import product
from typing import Any

import pandas as pd

from src.features import compute_realized_volatility, compute_returns
from src.optimization import BASE_PARAMS

from exploratory_strategies import StrategyCandidate, variant_family


def score_metrics(metrics: dict[str, Any] | pd.Series) -> float:
    """Cost-aware validation score used for exploratory selection."""
    sharpe = float(metrics.get("sharpe_ratio", 0.0))
    drawdown_penalty = abs(float(metrics.get("max_drawdown_points", 0.0))) / 1000.0
    turnover = float(metrics.get("trades_per_day", 0.0))
    profit_factor = float(metrics.get("profit_factor", 0.0))
    if profit_factor == float("inf"):
        profit_factor = 3.0
    profit_factor = min(profit_factor, 3.0)
    return float(sharpe - 0.25 * drawdown_penalty - 0.25 * turnover + 0.25 * profit_factor)


def compute_opening_width_thresholds(
    train_sessions: dict[int, pd.DataFrame],
    opening_window: int,
) -> dict[str, float]:
    """Compute training-only opening-range width quantiles."""
    widths = []
    for session in train_sessions.values():
        ordered = session.sort_values("datetime").reset_index(drop=True)
        if len(ordered) >= opening_window:
            opening = ordered.iloc[:opening_window]
            widths.append(float(opening["high"].max() - opening["low"].min()))
    series = pd.Series(widths, dtype=float)
    return {
        "q20": float(series.quantile(0.20)),
        "q80": float(series.quantile(0.80)),
        "q90": float(series.quantile(0.90)),
    }


def compute_low_rv_threshold(train_sessions: dict[int, pd.DataFrame], rv_window: int, quantile: float) -> float:
    """Compute a low-realized-volatility threshold from training only."""
    values = []
    for session in train_sessions.values():
        rv = compute_realized_volatility(compute_returns(session), rv_window)
        values.append(rv.loc[rv.gt(0)])
    if not values:
        return 0.0
    all_rv = pd.concat(values, ignore_index=True)
    return float(all_rv.quantile(quantile))


def compute_rv_threshold(train_sessions: dict[int, pd.DataFrame], rv_window: int, quantile: float) -> float:
    """Compute any realized-volatility quantile from training only."""
    return compute_low_rv_threshold(train_sessions, rv_window, quantile)


def build_candidates(
    hybrid_params: dict[str, Any],
    orb_params: dict[str, Any],
    mr_params: dict[str, Any],
    train_sessions: dict[int, pd.DataFrame],
    mode: str,
) -> list[StrategyCandidate]:
    """Create a staged, bounded exploratory candidate list."""
    fast = mode == "fast"
    opening_window = int(hybrid_params.get("opening_window", 30))
    width = compute_opening_width_thresholds(train_sessions, opening_window)
    low_rv_cutoff = compute_rv_threshold(train_sessions, int(hybrid_params.get("rv_window", 60)), 0.60)

    candidates: list[StrategyCandidate] = []

    def add(variant: str, base: dict[str, Any], overrides: dict[str, Any], serial: int) -> None:
        params = {**BASE_PARAMS, **base, **overrides}
        pid = f"{variant.lower()}_{serial:03d}"
        candidates.append(
            StrategyCandidate(
                strategy=variant,
                variant=variant,
                family=variant_family(variant),
                params_id=pid,
                params=params,
            )
        )

    er_thresholds = [0.35, 0.45] if fast else [0.35, 0.45, 0.55]
    er_margins = [0.0, 0.05] if fast else [0.0, 0.05, 0.10]
    stop_loss_values = [80, 120] if fast else [80, 120]
    take_profit_values = [120, 180] if fast else [120, 180]

    serial = 1
    for er_threshold in er_thresholds:
        add("ORB_FILTERED_HYBRID_BASIC", hybrid_params, {"er_threshold": er_threshold}, serial)
        serial += 1

    serial = 1
    confirm_grid = [
        {"use_two_bar_confirmation": True},
        {"use_volume_filter": True, "volume_window": 30, "volume_multiplier": 1.0},
        {"use_two_bar_confirmation": True, "use_volume_filter": True, "volume_window": 30, "volume_multiplier": 1.0},
    ]
    if not fast:
        confirm_grid.extend(
            [
                {"use_two_bar_confirmation": True, "use_volume_filter": True, "volume_window": 60, "volume_multiplier": 1.2},
                {"use_two_bar_confirmation": True, "use_or_width_filter": True, "max_or_width_points": width["q80"]},
            ]
        )
    for overrides in confirm_grid:
        add("ORB_FILTERED_HYBRID_CONFIRM", hybrid_params, overrides, serial)
        serial += 1

    serial = 1
    for er_margin in er_margins:
        add("ORB_FILTERED_HYBRID_STRICT_TREND", hybrid_params, {"er_margin": er_margin}, serial)
        serial += 1

    serial = 1
    for stop_loss, take_profit in product(stop_loss_values, take_profit_values):
        add(
            "ORB_ONLY_CONFIRM",
            orb_params,
            {
                "use_two_bar_confirmation": True,
                "max_trades": 1,
                "stop_loss_points": stop_loss,
                "take_profit_points": take_profit,
            },
            serial,
        )
        serial += 1

    serial = 1
    volume_grid = [(30, 1.0)] if fast else [(30, 1.0), (30, 1.2), (60, 1.0)]
    for volume_window, multiplier in volume_grid:
        add(
            "ORB_ONLY_VOLUME",
            orb_params,
            {
                "use_volume_filter": True,
                "volume_window": volume_window,
                "volume_multiplier": multiplier,
                "max_trades": 1,
            },
            serial,
        )
        serial += 1

    serial = 1
    width_filters = [{"use_or_width_filter": True, "max_or_width_points": width["q80"]}]
    if not fast:
        width_filters.append({"use_or_width_filter": True, "min_or_width_points": width["q20"], "max_or_width_points": width["q90"]})
    for overrides in width_filters:
        add("ORB_ONLY_RANGE_FILTER", orb_params, {**overrides, "max_trades": 1}, serial)
        serial += 1

    add(
        "ORB_ONLY_LOW_TURNOVER",
        orb_params,
        {"max_trades": 1, "cooldown_bars": 30, "no_reentry_after_stop": True},
        1,
    )

    serial = 1
    strict_er_values = [0.20, 0.25] if not fast else [0.25]
    for strict_er in strict_er_values:
        add(
            "STRICT_MR_ONLY",
            mr_params,
            {
                "strict_er_threshold": strict_er,
                "low_rv_quantile": 0.50,
                "z_entry": 2.5,
                "max_trades": 1,
            },
            serial,
        )
        serial += 1

    serial = 1
    for strict_er in strict_er_values:
        add(
            "STRICT_MR_HYBRID",
            hybrid_params,
            {
                "strict_er_threshold": strict_er,
                "low_rv_quantile": 0.50,
                "z_entry": 2.5,
                "max_trades": 2,
            },
            serial,
        )
        serial += 1

    serial = 1
    low_turnover_overrides = [
        {"max_trades": 1},
        {"max_trades": 2, "cooldown_bars": 30},
        {"max_trades": 2, "cooldown_bars": 60},
        {"max_trades": 2, "boundary_margin": 0.05},
    ]
    if not fast:
        low_turnover_overrides.append({"max_trades": 1, "boundary_margin": 0.10, "cooldown_bars": 60})
    for overrides in low_turnover_overrides:
        add("LOW_TURNOVER_HYBRID", hybrid_params, overrides, serial)
        serial += 1

    serial = 1
    long_filter_grid = [
        {"min_opening_return_points": 0, "require_close_above_vwap": True},
        {"min_opening_return_points": 20, "require_close_above_vwap": True},
        {"min_opening_return_points": 0, "require_up_breakout": True, "buffer_points": 0},
        {"min_opening_return_points": 20, "min_er": 0.25},
        {"min_opening_return_points": 0, "require_close_above_vwap": True, "max_rv": low_rv_cutoff},
    ]
    if not fast:
        long_filter_grid.extend(
            [
                {"min_opening_return_points": 40, "require_close_above_vwap": True},
                {"min_opening_return_points": 20, "require_close_above_vwap": True, "use_volume_filter": True, "volume_window": 30, "volume_multiplier": 1.0},
                {"min_opening_return_points": 0, "require_up_breakout": True, "buffer_points": 10, "min_er": 0.25},
            ]
        )
    for overrides in long_filter_grid:
        add(
            "LONG_OR_FLAT_FILTERED",
            hybrid_params,
            {
                **overrides,
                "max_trades": 1,
                "hold_to_close": True,
                "disable_take_profit": True,
                "close_on_extreme": False,
                "stop_loss_points": 160,
                "take_profit_points": 9999,
            },
            serial,
        )
        serial += 1

    serial = 1
    long_orb_grid = [
        {"buffer_points": 0, "max_trades": 1},
        {"buffer_points": 10, "max_trades": 1},
        {"buffer_points": 20, "max_trades": 1, "use_two_bar_confirmation": True},
        {"buffer_points": 10, "max_trades": 1, "use_volume_filter": True, "volume_window": 30, "volume_multiplier": 1.0},
    ]
    for overrides in long_orb_grid:
        add(
            "LONG_ONLY_ORB",
            orb_params,
            {**overrides, "stop_loss_points": 120, "take_profit_points": 180},
            serial,
        )
        serial += 1

    serial = 1
    orb_to_close_grid = [
        {"buffer_points": 0},
        {"buffer_points": 10},
        {"buffer_points": 20, "use_two_bar_confirmation": True},
        {"buffer_points": 10, "use_or_width_filter": True, "max_or_width_points": width["q80"]},
    ]
    for overrides in orb_to_close_grid:
        add(
            "ORB_TO_CLOSE",
            orb_params,
            {
                **overrides,
                "max_trades": 1,
                "long_only": True,
                "hold_to_close": True,
                "disable_take_profit": True,
                "stop_loss_points": 160,
                "take_profit_points": 9999,
            },
            serial,
        )
        serial += 1

    serial = 1
    extreme_grid = [
        {"min_opening_return_points": 0, "require_close_above_vwap": True},
        {"min_opening_return_points": 20, "require_close_above_vwap": True},
        {"min_opening_return_points": 0, "require_up_breakout": True, "buffer_points": 0},
    ]
    for overrides in extreme_grid:
        add(
            "EXTREME_TREND_FOLLOWING",
            hybrid_params,
            {
                **overrides,
                "max_trades": 1,
                "hold_to_close": True,
                "disable_take_profit": True,
                "close_on_extreme": False,
                "stop_loss_points": 180,
                "take_profit_points": 9999,
            },
            serial,
        )
        serial += 1

    return candidates
