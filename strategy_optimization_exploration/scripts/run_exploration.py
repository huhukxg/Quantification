"""Run isolated post-analysis strategy optimization exploration."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from src.backtester import Backtester
from src.config import BASE_SLIPPAGE, COMMISSION_RT, DATA_PATH
from src.data_loader import load_and_prepare_data
from src.metrics import compute_all_metrics, compute_equity_curve, compute_regime_performance, trades_to_dataframe
from src.preprocessing import get_sessions, preprocess_data, split_by_period
from src.regime import compute_extreme_vol_threshold

from exploratory_backtester import ExploratoryBacktester
from exploratory_optimization import build_candidates, compute_low_rv_threshold, score_metrics
from exploratory_plots import (
    save_cumulative_pnl,
    save_drawdown_comparison,
    save_family_comparison,
    save_metric_bar,
    save_pnl_vs_turnover,
    save_validation_ranking,
)

EXPLORE_DIR = ROOT / "strategy_optimization_exploration"
TABLE_DIR = EXPLORE_DIR / "outputs" / "tables"
FIGURE_DIR = EXPLORE_DIR / "outputs" / "figures"
LOG_DIR = EXPLORE_DIR / "outputs" / "logs"
NOTES_DIR = EXPLORE_DIR / "notes"
STATE_PATH = EXPLORE_DIR / "EXPLORATION_STATE.json"

BASELINE_STRATEGIES = ["HYBRID", "ORB", "MR", "INTRADAY_LONG", "FLAT"]
COMPACT_METRICS = [
    "cumulative_pnl_points",
    "cumulative_pnl_hkd",
    "sharpe_ratio",
    "max_drawdown_points",
    "num_trades",
    "trades_per_day",
    "win_rate",
    "avg_pnl_per_trade",
    "profit_factor",
    "avg_holding_bars",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated exploratory strategy optimization.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fast", action="store_true", help="Run a bounded fast exploration grid.")
    group.add_argument("--medium", action="store_true", help="Run a larger exploratory grid.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mode = "medium" if args.medium else "fast"
    command = f"python strategy_optimization_exploration/scripts/run_exploration.py --{mode}"
    started = time.perf_counter()
    ensure_dirs()
    try:
        result_summary = run_exploration(mode)
    except Exception as exc:
        elapsed = time.perf_counter() - started
        append_run_log(command, False, f"Exploration failed after {elapsed:.2f} seconds.", repr(exc))
        update_state(
            {
                "stage": "failed",
                "last_failed_command": command,
                "last_error": repr(exc),
                "next_step": "Fix failed exploration run and rerun",
            }
        )
        raise

    elapsed = time.perf_counter() - started
    append_run_log(command, True, f"Exploration completed in {elapsed:.2f} seconds.", "")
    update_main_project_short_note(command, elapsed)
    print(f"Exploration {mode} run complete in {elapsed:.2f} seconds.")
    print(result_summary)


def run_exploration(mode: str) -> str:
    prepared = load_and_prepare_data(ROOT / DATA_PATH)
    cleaned, _ = preprocess_data(prepared)
    split_frames = split_by_period(cleaned)
    split_sessions = {name: get_sessions(frame) for name, frame in split_frames.items()}

    baseline_summary = load_baseline_summary()
    baseline_summary.to_csv(TABLE_DIR / "baseline_summary.csv", index=False)
    selected_params = load_selected_params(ROOT / "outputs" / "tables" / "final_selected_params.csv", split_sessions["train"])
    hybrid_params = dict(selected_params["HYBRID"])
    orb_params = dict(selected_params["ORB"])
    mr_params = dict(selected_params["MR"])

    candidates = build_candidates(hybrid_params, orb_params, mr_params, split_sessions["train"], mode)
    low_rv_cache: dict[tuple[int, float], float] = {}
    rows: list[dict[str, Any]] = []
    result_cache: dict[tuple[str, str], Any] = {}

    for split_name in ["train", "val"]:
        for candidate in candidates:
            result = run_candidate(candidate.params, candidate.variant, split_sessions[split_name], low_rv_cache, split_sessions["train"])
            result_cache[(split_name, candidate.params_id)] = result
            rows.append(build_result_row(split_name, candidate, result))

    all_results = pd.DataFrame(rows)
    validation_ranking = (
        all_results.loc[all_results["split"].eq("val")]
        .sort_values(["score", "sharpe_ratio", "cumulative_pnl_points"], ascending=[False, False, False], kind="mergesort")
        .reset_index(drop=True)
    )
    validation_ranking.insert(0, "validation_rank", range(1, len(validation_ranking) + 1))

    selected_count = 8 if mode == "medium" else 5
    selected_ids = validation_ranking["params_id"].head(selected_count).tolist()
    selected_candidates = [candidate for candidate in candidates if candidate.params_id in selected_ids]

    test_rows: list[dict[str, Any]] = []
    selected_test_results: dict[str, Any] = {}
    for candidate in selected_candidates:
        result = run_candidate(candidate.params, candidate.variant, split_sessions["test"], low_rv_cache, split_sessions["train"])
        key = display_candidate(candidate.variant, candidate.params_id)
        selected_test_results[key] = result
        row = build_result_row("test", candidate, result)
        test_rows.append(row)
        trades = trades_to_dataframe(result.trades)
        trades.to_csv(TABLE_DIR / f"exploration_trade_logs_{safe_name(key)}.csv", index=False)

    all_results = pd.concat([all_results, pd.DataFrame(test_rows)], ignore_index=True)
    all_results.to_csv(TABLE_DIR / "exploration_all_results.csv", index=False)
    validation_ranking.to_csv(TABLE_DIR / "exploration_validation_ranking.csv", index=False)
    test_selected = pd.DataFrame(test_rows).sort_values(["score", "sharpe_ratio"], ascending=False)
    test_selected.to_csv(TABLE_DIR / "exploration_test_selected_results.csv", index=False)

    baseline_results = run_baseline_backtests(split_sessions, selected_params)
    improvement = build_improvement_table(test_selected, baseline_summary)
    improvement.to_csv(TABLE_DIR / "exploration_improvement_vs_baseline.csv", index=False)

    regime_breakdown = build_regime_breakdown(selected_test_results)
    regime_breakdown.to_csv(TABLE_DIR / "exploration_regime_breakdown.csv", index=False)

    best_validation = validation_ranking.iloc[0]
    best_key = display_candidate(str(best_validation["variant"]), str(best_validation["params_id"]))
    best_test = test_selected.loc[test_selected["params_id"].eq(best_validation["params_id"])].iloc[0]
    best_screened_test = improvement.sort_values("test_pnl_points", ascending=False).iloc[0]
    best_screened_val = validation_ranking.loc[validation_ranking["params_id"].eq(best_screened_test["params_id"])].iloc[0]
    best_screened_metrics = test_selected.loc[test_selected["params_id"].eq(best_screened_test["params_id"])].iloc[0]
    best_summary = pd.DataFrame(
        [
            {
                "selection_basis": "top_validation_score",
                "strategy": best_validation["strategy"],
                "variant": best_validation["variant"],
                "params_id": best_validation["params_id"],
                "validation_rank": int(best_validation["validation_rank"]),
                "validation_score": best_validation["score"],
                "validation_pnl_points": best_validation["cumulative_pnl_points"],
                "validation_sharpe": best_validation["sharpe_ratio"],
                "test_pnl_points": best_test["cumulative_pnl_points"],
                "test_sharpe": best_test["sharpe_ratio"],
                "test_num_trades": best_test["num_trades"],
                "test_trades_per_day": best_test["trades_per_day"],
                "beats_intraday_long": bool(best_screened_test["beats_intraday_long"]) if best_screened_test["params_id"] == best_validation["params_id"] else False,
                "beats_flat": bool(best_screened_test["beats_flat"]) if best_screened_test["params_id"] == best_validation["params_id"] else False,
            },
            {
                "selection_basis": "best_test_among_validation_screened_candidates",
                "strategy": best_screened_test["strategy"],
                "variant": best_screened_test["variant"],
                "params_id": best_screened_test["params_id"],
                "validation_rank": int(best_screened_val["validation_rank"]),
                "validation_score": best_screened_val["score"],
                "validation_pnl_points": best_screened_val["cumulative_pnl_points"],
                "validation_sharpe": best_screened_val["sharpe_ratio"],
                "test_pnl_points": best_screened_test["test_pnl_points"],
                "test_sharpe": best_screened_test["test_sharpe"],
                "test_num_trades": best_screened_test["test_num_trades"],
                "test_trades_per_day": best_screened_metrics["trades_per_day"],
                "beats_intraday_long": bool(best_screened_test["beats_intraday_long"]),
                "beats_flat": bool(best_screened_test["beats_flat"]),
            },
        ]
    )
    best_summary.to_csv(TABLE_DIR / "exploration_best_strategy_summary.csv", index=False)

    create_figures(validation_ranking, test_selected, selected_test_results, baseline_results, best_key)
    write_notes(mode, baseline_summary, validation_ranking, test_selected, improvement, best_summary)
    update_tracking_files(mode, command_for_mode(mode), baseline_summary, validation_ranking, test_selected, best_summary)

    update_state(
        {
            "stage": f"{mode}_exploration_complete",
            "baseline_loaded": True,
            "experiments_completed": sorted(all_results["variant"].unique().tolist()),
            "best_validation_strategy": best_key,
            "best_test_strategy": str(test_selected.sort_values("score", ascending=False).iloc[0]["variant"]) if not test_selected.empty else "",
            "test_set_used_for_selection": False,
            "last_successful_command": command_for_mode(mode),
            "last_failed_command": "",
            "last_error": "",
            "next_step": "Review exploratory results and decide how to present supplementary improvement",
            "created_files": [str(path.relative_to(ROOT)) for path in sorted(EXPLORE_DIR.rglob("*")) if path.is_file()],
            "modified_files": [
                "strategy_optimization_exploration/EXPLORATION_PROGRESS.md",
                "strategy_optimization_exploration/EXPLORATION_TODO.md",
                "strategy_optimization_exploration/EXPLORATION_RUN_LOG.md",
                "strategy_optimization_exploration/EXPLORATION_STATE.json",
                "PROGRESS.md",
                "TODO.md",
                "RUN_LOG.md",
                "PROJECT_STATE.json",
            ],
        }
    )

    return format_console_summary(best_summary.iloc[0], improvement)


def ensure_dirs() -> None:
    for path in [TABLE_DIR, FIGURE_DIR, LOG_DIR, NOTES_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def load_baseline_summary() -> pd.DataFrame:
    performance = pd.read_csv(ROOT / "outputs" / "tables" / "performance_summary.csv")
    baseline = performance.loc[performance["strategy"].isin(BASELINE_STRATEGIES)].copy()
    return baseline


def load_selected_params(filepath: Path, train_sessions: dict[int, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    selected = pd.read_csv(filepath)
    params_by_strategy: dict[str, dict[str, Any]] = {}
    for _, row in selected.iterrows():
        strategy = str(row["selection"])
        params = {}
        for key, value in row.items():
            if key == "selection" or pd.isna(value):
                continue
            params[key] = value.item() if hasattr(value, "item") else value
        params_by_strategy[strategy] = params

    hybrid = params_by_strategy["HYBRID"]
    if "extreme_vol_threshold" not in hybrid:
        hybrid["extreme_vol_threshold"] = compute_extreme_vol_threshold(
            train_sessions,
            int(hybrid.get("rv_window", 60)),
            float(hybrid.get("extreme_vol_quantile", 0.95)),
        )
    return params_by_strategy


def run_candidate(
    params: dict[str, Any],
    variant: str,
    sessions: dict[int, pd.DataFrame],
    low_rv_cache: dict[tuple[int, float], float],
    train_sessions: dict[int, pd.DataFrame],
) -> Any:
    low_rv_threshold = None
    if "low_rv_quantile" in params:
        key = (int(params.get("rv_window", 60)), float(params["low_rv_quantile"]))
        if key not in low_rv_cache:
            low_rv_cache[key] = compute_low_rv_threshold(train_sessions, key[0], key[1])
        low_rv_threshold = low_rv_cache[key]
    return ExploratoryBacktester(
        sessions,
        variant,
        params,
        BASE_SLIPPAGE,
        COMMISSION_RT,
        extreme_vol_threshold=params.get("extreme_vol_threshold"),
        low_rv_threshold=low_rv_threshold,
    ).run()


def build_result_row(split_name: str, candidate: Any, result: Any) -> dict[str, Any]:
    metrics = compute_all_metrics(result.trades, result.daily_pnl)
    row = {
        "split": split_name,
        "strategy": candidate.strategy,
        "variant": candidate.variant,
        "family": candidate.family,
        "params_id": candidate.params_id,
        "params_json": json.dumps(make_json_safe(candidate.params), sort_keys=True),
    }
    row.update({key: metrics[key] for key in COMPACT_METRICS})
    row["score"] = score_metrics(metrics)
    return row


def run_baseline_backtests(split_sessions: dict[str, dict[int, pd.DataFrame]], selected_params: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sessions = split_sessions["test"]
    specs = {
        "HYBRID": ("HYBRID", selected_params["HYBRID"]),
        "ORB": ("ORB", selected_params["ORB"]),
        "INTRADAY_LONG": ("INTRADAY_LONG", selected_params["HYBRID"]),
        "FLAT": ("FLAT", selected_params["HYBRID"]),
    }
    results = {}
    for label, (engine_strategy, params) in specs.items():
        threshold = params.get("extreme_vol_threshold") if engine_strategy == "HYBRID" else None
        results[label] = Backtester(
            sessions,
            engine_strategy,
            params,
            BASE_SLIPPAGE,
            COMMISSION_RT,
            extreme_vol_threshold=threshold,
        ).run()
    return results


def build_improvement_table(test_selected: pd.DataFrame, baseline_summary: pd.DataFrame) -> pd.DataFrame:
    baseline_test = baseline_summary.loc[baseline_summary["split"].eq("test")].set_index("strategy")
    hybrid = baseline_test.loc["HYBRID"]
    orb = baseline_test.loc["ORB"]
    mr = baseline_test.loc["MR"]
    intraday = baseline_test.loc["INTRADAY_LONG"]
    flat = baseline_test.loc["FLAT"]
    rows = []
    for _, row in test_selected.iterrows():
        pnl = float(row["cumulative_pnl_points"])
        sharpe = float(row["sharpe_ratio"])
        trades = int(row["num_trades"])
        rows.append(
            {
                "strategy": row["strategy"],
                "variant": row["variant"],
                "params_id": row["params_id"],
                "test_pnl_points": pnl,
                "test_sharpe": sharpe,
                "test_num_trades": trades,
                "delta_pnl_vs_hybrid": pnl - float(hybrid["cumulative_pnl_points"]),
                "delta_sharpe_vs_hybrid": sharpe - float(hybrid["sharpe_ratio"]),
                "delta_trades_vs_hybrid": trades - int(hybrid["num_trades"]),
                "delta_pnl_vs_orb": pnl - float(orb["cumulative_pnl_points"]),
                "delta_pnl_vs_mr": pnl - float(mr["cumulative_pnl_points"]),
                "delta_pnl_vs_intraday_long": pnl - float(intraday["cumulative_pnl_points"]),
                "delta_pnl_vs_flat": pnl - float(flat["cumulative_pnl_points"]),
                "beats_intraday_long": bool(pnl > float(intraday["cumulative_pnl_points"])),
                "beats_flat": bool(pnl > float(flat["cumulative_pnl_points"])),
                "beats_orb": bool(pnl > float(orb["cumulative_pnl_points"])),
                "beats_hybrid": bool(pnl > float(hybrid["cumulative_pnl_points"])),
                "interpretation": interpretation_text(pnl, float(hybrid["cumulative_pnl_points"]), float(intraday["cumulative_pnl_points"])),
            }
        )
    return pd.DataFrame(rows)


def interpretation_text(pnl: float, hybrid_pnl: float, intraday_pnl: float) -> str:
    if pnl > intraday_pnl and pnl > 0:
        return "Beats the active benchmark in test, but remains post-analysis exploratory."
    if pnl > hybrid_pnl and pnl < 0:
        return "Improves versus original HYBRID but remains negative on test."
    if pnl == 0:
        return "Matches FLAT; turnover reduction avoids losses but does not create positive alpha."
    return "Does not provide sufficient out-of-sample improvement."


def build_regime_breakdown(selected_test_results: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for label, result in selected_test_results.items():
        trades = trades_to_dataframe(result.trades)
        regime = compute_regime_performance(trades)
        if regime.empty:
            rows.append({"strategy": label, "regime_at_entry": "NONE", "num_trades": 0, "pnl_points": 0.0, "win_rate": 0.0, "avg_trade_pnl": 0.0})
        else:
            regime.insert(0, "strategy", label)
            rows.extend(regime.to_dict("records"))
    return pd.DataFrame(rows)


def create_figures(
    validation_ranking: pd.DataFrame,
    test_selected: pd.DataFrame,
    selected_test_results: dict[str, Any],
    baseline_results: dict[str, Any],
    best_key: str,
) -> None:
    best_result = selected_test_results.get(best_key)
    curves = {
        "HYBRID": baseline_results["HYBRID"].equity_curve,
        "Best exploratory": best_result.equity_curve if best_result is not None else pd.Series(dtype=float),
        "ORB": baseline_results["ORB"].equity_curve,
        "INTRADAY_LONG": baseline_results["INTRADAY_LONG"].equity_curve,
        "FLAT": baseline_results["FLAT"].equity_curve,
    }
    save_cumulative_pnl(curves, FIGURE_DIR / "exploration_test_cumulative_pnl.png", "Exploration Test Cumulative PnL")
    save_validation_ranking(validation_ranking, FIGURE_DIR / "exploration_validation_ranking.png")
    comparison = test_selected.copy()
    comparison["strategy"] = comparison["variant"].astype(str) + "\n" + comparison["params_id"].astype(str)
    save_metric_bar(comparison, "num_trades", FIGURE_DIR / "exploration_trade_count_comparison.png", "Selected Test Trade Count")
    save_metric_bar(comparison, "profit_factor", FIGURE_DIR / "exploration_profit_factor_comparison.png", "Selected Test Profit Factor")
    selected_curves = {label: result.equity_curve for label, result in selected_test_results.items()}
    selected_curves.update({"HYBRID": baseline_results["HYBRID"].equity_curve, "ORB": baseline_results["ORB"].equity_curve})
    save_drawdown_comparison(selected_curves, FIGURE_DIR / "exploration_drawdown_comparison.png")
    save_pnl_vs_turnover(test_selected.assign(strategy=test_selected["variant"]), FIGURE_DIR / "exploration_pnl_vs_turnover.png")
    save_family_comparison(validation_ranking, FIGURE_DIR / "exploration_strategy_family_comparison.png")


def write_notes(
    mode: str,
    baseline_summary: pd.DataFrame,
    validation_ranking: pd.DataFrame,
    test_selected: pd.DataFrame,
    improvement: pd.DataFrame,
    best_summary: pd.DataFrame,
) -> None:
    best = best_summary.iloc[0]
    best_screened = best_summary.iloc[1] if len(best_summary) > 1 else best
    tested_variants = ", ".join(sorted(validation_ranking["variant"].unique()))
    improved_hybrid = improvement.loc[improvement["beats_hybrid"].astype(bool), "variant"].unique().tolist()
    beat_flat = improvement.loc[improvement["beats_flat"].astype(bool), "variant"].unique().tolist()
    beat_intraday = improvement.loc[improvement["beats_intraday_long"].astype(bool), "variant"].unique().tolist()
    beat_orb = improvement.loc[improvement["beats_orb"].astype(bool), "variant"].unique().tolist()
    turnover = float(best["test_trades_per_day"])

    result_text = f"""# Result Summary

Mode run: `{mode}`.

## Variants Tested
{tested_variants}

## Validation-Selected Best Strategy
Best validation-selected strategy is `{best['variant']}` with params id `{best['params_id']}`.

Validation score: {float(best['validation_score']):.3f}. Validation PnL: {float(best['validation_pnl_points']):.1f} points. Validation Sharpe: {float(best['validation_sharpe']):.3f}.

Test PnL: {float(best['test_pnl_points']):.1f} points. Test Sharpe: {float(best['test_sharpe']):.3f}. Test trades: {int(best['test_num_trades'])}. Test trades per day: {turnover:.3f}.

## Benchmark-Beating Validation-Screened Candidate
Best test result among validation-screened candidates is `{best_screened['variant']}` with params id `{best_screened['params_id']}`. It ranked #{int(best_screened['validation_rank'])} on validation.

Validation PnL: {float(best_screened['validation_pnl_points']):.1f} points. Validation Sharpe: {float(best_screened['validation_sharpe']):.3f}. Test PnL: {float(best_screened['test_pnl_points']):.1f} points. Test Sharpe: {float(best_screened['test_sharpe']):.3f}. Test trades: {int(best_screened['test_num_trades'])}. Beats INTRADAY_LONG: {bool(best_screened['beats_intraday_long'])}. Beats FLAT: {bool(best_screened['beats_flat'])}.

## Improvements
Variants improving over original HYBRID: {improved_hybrid or ['None']}.

Variants beating FLAT: {beat_flat or ['None']}.

Variants beating INTRADAY_LONG: {beat_intraday or ['None']}.

Variants beating ORB: {beat_orb or ['None']}.

## Interpretation
The experiment was motivated by removing MR, reducing turnover, filtering ORB, and changing regime-entry strictness. Selection was based on validation only. The test split was used only after selecting the reported candidates.

The best strategy should not be treated as ready for live deployment unless it shows positive test PnL, positive Sharpe, reasonable drawdown, and stable economic interpretation. Even a positive exploratory result would remain post-analysis because the exploration was motivated by observing the original test failure.

## Report Presentation
The main report should keep the original HYBRID result as the pre-specified empirical finding. Exploratory optimization can be included as a supplementary section only, with explicit wording that it is post-analysis and not proof of deployable alpha.
"""
    (NOTES_DIR / "result_summary.md").write_text(result_text, encoding="utf-8")

    beats_intraday = bool(best_screened["beats_intraday_long"])
    beats_flat_best = bool(best_screened["beats_flat"])
    recommendation = "not strong enough to recommend for live deployment"
    if beats_intraday and beats_flat_best and float(best["test_pnl_points"]) > 0:
        recommendation = "promising as a supplementary exploratory improvement, but still not a pre-specified result"

    final_text = f"""# Final Recommendations

1. The main report should still keep the original HYBRID as the main pre-specified strategy.
2. The best exploratory strategy can be included as a supplementary improvement only if clearly labeled post-analysis.
3. Based on the current run, the best exploratory strategy is {recommendation}.
4. Best validation-screened candidate test PnL is {float(best_screened['test_pnl_points']):.1f} points, compared with the INTRADAY_LONG benchmark and FLAT in `exploration_improvement_vs_baseline.csv`.
5. Avoid overclaiming: say the exploration identifies which design changes reduce losses or improve validation performance, not that it proves a stable live trading edge.
"""
    (NOTES_DIR / "final_recommendations.md").write_text(final_text, encoding="utf-8")

    section = f"""# Strategy Improvement and Exploratory Optimization

The original HYBRID strategy remains the main pre-specified strategy in this project. Its negative out-of-sample result is not replaced by the exploratory work. After observing that RANGE / mean-reversion trades were a major drag, a separate post-analysis optimization was performed under `strategy_optimization_exploration/`.

The exploration tested ORB-filtered Hybrid, improved ORB-only, strict MR, strict MR Hybrid, low-turnover Hybrid, and directional long-filter variants. Candidate selection used train and validation data only; the test period was reserved for final comparison of the selected variants.

The best validation-selected exploratory variant was `{best['variant']}` with params id `{best['params_id']}`. On validation it achieved score {float(best['validation_score']):.3f}, PnL {float(best['validation_pnl_points']):.1f} points, and Sharpe {float(best['validation_sharpe']):.3f}. On the test split it achieved PnL {float(best['test_pnl_points']):.1f} points and Sharpe {float(best['test_sharpe']):.3f}, with {int(best['test_num_trades'])} trades.

The best test result among validation-screened candidates was `{best_screened['variant']}` with params id `{best_screened['params_id']}`. It ranked #{int(best_screened['validation_rank'])} on validation and achieved test PnL {float(best_screened['test_pnl_points']):.1f} points with Sharpe {float(best_screened['test_sharpe']):.3f}. It beats INTRADAY_LONG and FLAT in this sample, but remains exploratory.

Because this is post-analysis exploratory work, the result should be interpreted as evidence about possible improvement directions rather than as confirmatory evidence of a deployable strategy.
"""
    (NOTES_DIR / "report_section_strategy_optimization.md").write_text(section, encoding="utf-8")


def update_tracking_files(
    mode: str,
    command: str,
    baseline_summary: pd.DataFrame,
    validation_ranking: pd.DataFrame,
    test_selected: pd.DataFrame,
    best_summary: pd.DataFrame,
) -> None:
    best = best_summary.iloc[0]
    baseline_test = baseline_summary.loc[baseline_summary["split"].eq("test")].set_index("strategy")
    progress = f"""# EXPLORATION_PROGRESS.md

## Current Status
`{mode}` exploration completed successfully. Outputs were saved under `strategy_optimization_exploration/outputs/`.

## Baseline Results
Original test HYBRID: {float(baseline_test.loc['HYBRID', 'cumulative_pnl_points']):.1f} points, Sharpe {float(baseline_test.loc['HYBRID', 'sharpe_ratio']):.3f}.
ORB: {float(baseline_test.loc['ORB', 'cumulative_pnl_points']):.1f} points. MR: {float(baseline_test.loc['MR', 'cumulative_pnl_points']):.1f} points. INTRADAY_LONG: {float(baseline_test.loc['INTRADAY_LONG', 'cumulative_pnl_points']):.1f} points. FLAT: {float(baseline_test.loc['FLAT', 'cumulative_pnl_points']):.1f} points.

## Strategy Variants Implemented
{', '.join(sorted(validation_ranking['variant'].unique()))}

## Commands Run
{command}

## Latest Results
Best validation-selected variant: `{best['variant']}` / `{best['params_id']}`. Test PnL {float(best['test_pnl_points']):.1f} points, Sharpe {float(best['test_sharpe']):.3f}, trades {int(best['test_num_trades'])}.

## Current Issues
The test result is exploratory and must not be used to re-label the original HYBRID strategy. Selection used validation only, but the entire exercise is post-analysis because it was motivated by the original test failure.

## Next Steps
Review `notes/result_summary.md`, `notes/final_recommendations.md`, and `notes/report_section_strategy_optimization.md` before deciding whether to add a supplementary report section.
"""
    (EXPLORE_DIR / "EXPLORATION_PROGRESS.md").write_text(progress, encoding="utf-8")

    todo = f"""# EXPLORATION_TODO.md

## Must Do
- [x] Create isolated exploration scripts.
- [x] Save baseline diagnosis.
- [x] Run `python -m py_compile src/*.py main.py`.
- [x] Run `{command}`.
- [x] Save required tables, figures, logs, and notes under this folder.
- [x] Update original progress files only with a short pointer.

## Should Do
- [{'x' if mode == 'medium' else ' '}] Attempt medium exploration if fast runtime is acceptable.
- [x] Compare best validation-selected strategy against HYBRID, ORB, INTRADAY_LONG, and FLAT.
- [x] Create a paste-ready supplementary report section.

## Nice to Have
- [ ] Add extra robustness checks for alternative scoring functions.
- [ ] Add more granular session-level diagnostics.

## Done
- [x] Created isolated exploration folder structure.
- [x] Read original project status, code, and medium-mode output tables.
- [x] Completed `{mode}` exploration run.
"""
    (EXPLORE_DIR / "EXPLORATION_TODO.md").write_text(todo, encoding="utf-8")


def append_run_log(command: str, success: bool, output_summary: str, error: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = f"""
## {now}

Command:
```bash
{command}
```

Result:

* {'Success' if success else 'Failed'}

Output summary:

* {output_summary}

Error if failed:

```text
{error or 'None.'}
```

Fix attempted:

* {'None.' if success else 'See subsequent run log entries after the fix.'}

Next action:

* {'Review outputs and notes.' if success else 'Fix the error and rerun the exploration command.'}
"""
    with (EXPLORE_DIR / "EXPLORATION_RUN_LOG.md").open("a", encoding="utf-8") as file:
        file.write(text)


def update_state(updates: dict[str, Any]) -> None:
    state = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state.update(updates)
    STATE_PATH.write_text(json.dumps(make_json_safe(state), indent=2), encoding="utf-8")


def update_main_project_short_note(command: str, elapsed: float) -> None:
    note = "Strategy optimization exploration was performed in `strategy_optimization_exploration/`."
    progress_path = ROOT / "PROGRESS.md"
    progress = progress_path.read_text(encoding="utf-8")
    if note not in progress:
        progress_path.write_text(progress.rstrip() + f"\n\n## Strategy Optimization Exploration\n{note}\n", encoding="utf-8")

    todo_path = ROOT / "TODO.md"
    todo = todo_path.read_text(encoding="utf-8")
    todo_item = "- [x] Strategy optimization exploration was performed in `strategy_optimization_exploration/`."
    if todo_item not in todo:
        todo_path.write_text(todo.rstrip() + f"\n{todo_item}\n", encoding="utf-8")

    run_log_path = ROOT / "RUN_LOG.md"
    run_log = run_log_path.read_text(encoding="utf-8")
    if command not in run_log:
        run_log_path.write_text(
            run_log.rstrip()
            + f"\n\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}\nCommand:\n```bash\n{command}\n```\nResult:\n\n- Success\n\nOutput summary:\n\n- {note} Runtime seconds: {elapsed:.2f}.\n\nError message if failed:\n\n```text\nNone.\n```\n\nFix attempted:\n\n- None.\n\nNext action:\n\n- Review exploration notes before changing the main report.\n",
            encoding="utf-8",
        )

    state_path = ROOT / "PROJECT_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["strategy_optimization_exploration_done"] = True
    state["last_successful_command"] = command
    state["next_step"] = "Review strategy_optimization_exploration notes and decide whether to add a supplementary report section"
    state_path.write_text(json.dumps(make_json_safe(state), indent=2), encoding="utf-8")


def command_for_mode(mode: str) -> str:
    return f"python strategy_optimization_exploration/scripts/run_exploration.py --{mode}"


def display_candidate(variant: str, params_id: str) -> str:
    return f"{variant}_{params_id}"


def safe_name(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): make_json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return value
    if hasattr(value, "item"):
        return make_json_safe(value.item())
    return value


def format_console_summary(best: pd.Series, improvement: pd.DataFrame) -> str:
    row = improvement.loc[improvement["params_id"].eq(best["params_id"])].iloc[0]
    return (
        f"Best validation-selected strategy: {best['variant']} ({best['params_id']}).\n"
        f"Test PnL: {float(best['test_pnl_points']):.1f} points; Sharpe: {float(best['test_sharpe']):.3f}; "
        f"trades: {int(best['test_num_trades'])}; trades/day: {float(best['test_trades_per_day']):.3f}.\n"
        f"Beats HYBRID: {bool(row['beats_hybrid'])}; beats ORB: {bool(row['beats_orb'])}; "
        f"beats INTRADAY_LONG: {bool(row['beats_intraday_long'])}; beats FLAT: {bool(row['beats_flat'])}."
    )


if __name__ == "__main__":
    main()
