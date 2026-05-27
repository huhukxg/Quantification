"""Generate report-ready outputs for the benchmark-beating long-or-flat variant."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from exploratory_backtester import ExploratoryBacktester
from src.backtester import Backtester
from src.config import BASE_SLIPPAGE, COMMISSION_RT, CONTRACT_MULTIPLIER, DATA_PATH
from src.data_loader import load_and_prepare_data
from src.metrics import (
    compute_all_metrics,
    compute_drawdown,
    compute_equity_curve,
    compute_monthly_pnl,
    compute_regime_performance,
    trades_to_dataframe,
)
from src.preprocessing import get_sessions, preprocess_data, split_by_period
from src.regime import compute_extreme_vol_threshold

EXPLORE_DIR = ROOT / "strategy_optimization_exploration"
TABLE_DIR = EXPLORE_DIR / "outputs" / "tables"
FIGURE_DIR = EXPLORE_DIR / "outputs" / "figures"
LOG_DIR = EXPLORE_DIR / "outputs" / "logs"
NOTES_DIR = EXPLORE_DIR / "notes"

TARGET_PARAMS_ID = "long_or_flat_filtered_004"
TARGET_VARIANT = "LONG_OR_FLAT_FILTERED"
BASELINE_STRATEGIES = ["HYBRID", "ORB", "MR", "INTRADAY_LONG", "FLAT"]
ALL_STRATEGIES = [TARGET_VARIANT, *BASELINE_STRATEGIES]


def main() -> None:
    started = time.perf_counter()
    for path in [TABLE_DIR, FIGURE_DIR, LOG_DIR, NOTES_DIR]:
        path.mkdir(parents=True, exist_ok=True)

    params = load_target_params()
    params_table = pd.DataFrame([{"variant": TARGET_VARIANT, "params_id": TARGET_PARAMS_ID, **params}])
    params_table.to_csv(TABLE_DIR / "long_or_flat_final_selected_params.csv", index=False)

    prepared = load_and_prepare_data(ROOT / DATA_PATH)
    cleaned, _ = preprocess_data(prepared)
    split_sessions = {name: get_sessions(frame) for name, frame in split_by_period(cleaned).items()}
    selected_params = load_selected_params(ROOT / "outputs" / "tables" / "final_selected_params.csv", split_sessions["train"])

    results_by_split = run_all_splits(split_sessions, selected_params, params)
    performance = build_performance_table(results_by_split)
    performance.to_csv(TABLE_DIR / "long_or_flat_final_performance_summary.csv", index=False)
    save_risk_and_trade_tables(performance)
    save_trade_logs(results_by_split)
    save_monthly_and_regime_tables(results_by_split)

    slippage = build_slippage_sensitivity(split_sessions["test"], params)
    slippage.to_csv(TABLE_DIR / "long_or_flat_final_slippage_sensitivity.csv", index=False)

    improvement = build_improvement_table(performance)
    improvement.to_csv(TABLE_DIR / "long_or_flat_final_improvement_vs_baseline.csv", index=False)

    create_figures(results_by_split, performance, slippage)
    write_report_notes(performance, improvement, slippage, params)
    append_log(time.perf_counter() - started)
    print_summary(performance, improvement)


def load_target_params() -> dict[str, Any]:
    ranking_path = TABLE_DIR / "exploration_validation_ranking.csv"
    if not ranking_path.exists():
        raise FileNotFoundError("Run exploration first; missing exploration_validation_ranking.csv.")
    ranking = pd.read_csv(ranking_path)
    row = ranking.loc[ranking["params_id"].eq(TARGET_PARAMS_ID)]
    if row.empty:
        raise ValueError(f"Missing target params_id in validation ranking: {TARGET_PARAMS_ID}")
    return json.loads(str(row.iloc[0]["params_json"]))


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


def run_all_splits(
    split_sessions: dict[str, dict[int, pd.DataFrame]],
    selected_params: dict[str, dict[str, Any]],
    long_params: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    results_by_split: dict[str, dict[str, Any]] = {}
    for split_name, sessions in split_sessions.items():
        split_results: dict[str, Any] = {}
        split_results[TARGET_VARIANT] = ExploratoryBacktester(
            sessions,
            TARGET_VARIANT,
            long_params,
            BASE_SLIPPAGE,
            COMMISSION_RT,
            extreme_vol_threshold=long_params.get("extreme_vol_threshold"),
        ).run()

        for strategy in BASELINE_STRATEGIES:
            params = selected_params.get(strategy, selected_params["HYBRID"])
            threshold = params.get("extreme_vol_threshold") if strategy == "HYBRID" else None
            split_results[strategy] = Backtester(
                sessions,
                strategy,
                params,
                BASE_SLIPPAGE,
                COMMISSION_RT,
                extreme_vol_threshold=threshold,
            ).run()
        results_by_split[split_name] = split_results
    return results_by_split


def build_performance_table(results_by_split: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for split_name, split_results in results_by_split.items():
        for strategy in ALL_STRATEGIES:
            result = split_results[strategy]
            rows.append({"split": split_name, "strategy": strategy, **compute_all_metrics(result.trades, result.daily_pnl)})
    return pd.DataFrame(rows)


def save_risk_and_trade_tables(performance: pd.DataFrame) -> None:
    risk_columns = [
        "split",
        "strategy",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "max_drawdown_points",
        "max_drawdown_duration_days",
        "var_95",
        "var_99",
    ]
    trade_columns = [
        "split",
        "strategy",
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
    ]
    performance[risk_columns].to_csv(TABLE_DIR / "long_or_flat_final_risk_metrics.csv", index=False)
    performance[trade_columns].to_csv(TABLE_DIR / "long_or_flat_final_trade_statistics.csv", index=False)


def save_trade_logs(results_by_split: dict[str, dict[str, Any]]) -> None:
    all_tables = []
    for split_name, split_results in results_by_split.items():
        trades = trades_to_dataframe(split_results[TARGET_VARIANT].trades)
        trades.insert(0, "split", split_name)
        trades.insert(1, "strategy", TARGET_VARIANT)
        all_tables.append(trades)
        trades.to_csv(TABLE_DIR / f"long_or_flat_final_trade_log_{split_name}.csv", index=False)
    pd.concat(all_tables, ignore_index=True).to_csv(TABLE_DIR / "long_or_flat_final_trade_log_all.csv", index=False)


def save_monthly_and_regime_tables(results_by_split: dict[str, dict[str, Any]]) -> None:
    monthly_tables = []
    regime_tables = []
    for split_name, split_results in results_by_split.items():
        result = split_results[TARGET_VARIANT]
        monthly = compute_monthly_pnl(result.daily_pnl)
        monthly.insert(0, "split", split_name)
        monthly.insert(1, "strategy", TARGET_VARIANT)
        monthly_tables.append(monthly)

        trades = trades_to_dataframe(result.trades)
        regime = compute_regime_performance(trades)
        regime.insert(0, "split", split_name)
        regime.insert(1, "strategy", TARGET_VARIANT)
        regime_tables.append(regime)

    pd.concat(monthly_tables, ignore_index=True).to_csv(TABLE_DIR / "long_or_flat_final_monthly_pnl.csv", index=False)
    pd.concat(regime_tables, ignore_index=True).to_csv(TABLE_DIR / "long_or_flat_final_regime_breakdown.csv", index=False)


def build_slippage_sensitivity(test_sessions: dict[int, pd.DataFrame], params: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for slippage in [0, 1, 2, 5, 10]:
        result = ExploratoryBacktester(
            test_sessions,
            TARGET_VARIANT,
            params,
            slippage,
            COMMISSION_RT,
            extreme_vol_threshold=params.get("extreme_vol_threshold"),
        ).run()
        rows.append({"slippage": slippage, **compute_all_metrics(result.trades, result.daily_pnl)})
    return pd.DataFrame(rows)


def build_improvement_table(performance: pd.DataFrame) -> pd.DataFrame:
    test = performance.loc[performance["split"].eq("test")].set_index("strategy")
    target = test.loc[TARGET_VARIANT]
    rows = []
    for baseline in BASELINE_STRATEGIES:
        current = test.loc[baseline]
        rows.append(
            {
                "strategy": TARGET_VARIANT,
                "baseline": baseline,
                "target_test_pnl_points": float(target["cumulative_pnl_points"]),
                "baseline_test_pnl_points": float(current["cumulative_pnl_points"]),
                "delta_pnl_points": float(target["cumulative_pnl_points"] - current["cumulative_pnl_points"]),
                "target_sharpe": float(target["sharpe_ratio"]),
                "baseline_sharpe": float(current["sharpe_ratio"]),
                "delta_sharpe": float(target["sharpe_ratio"] - current["sharpe_ratio"]),
                "target_num_trades": int(target["num_trades"]),
                "baseline_num_trades": int(current["num_trades"]),
                "delta_num_trades": int(target["num_trades"] - current["num_trades"]),
                "beats_baseline": bool(target["cumulative_pnl_points"] > current["cumulative_pnl_points"]),
            }
        )
    return pd.DataFrame(rows)


def create_figures(results_by_split: dict[str, dict[str, Any]], performance: pd.DataFrame, slippage: pd.DataFrame) -> None:
    combined_curves = {}
    test_curves = {}
    for strategy in [TARGET_VARIANT, "HYBRID", "ORB", "INTRADAY_LONG", "FLAT"]:
        combined_daily = {}
        for split_name in ["train", "val", "test"]:
            combined_daily.update(results_by_split[split_name][strategy].daily_pnl)
        combined_curves[strategy] = compute_equity_curve(combined_daily)
        test_curves[strategy] = results_by_split["test"][strategy].equity_curve

    plot_curves(combined_curves, FIGURE_DIR / "long_or_flat_final_cumulative_pnl_comparison.png", "Long-or-Flat Final Cumulative PnL")
    plot_curves(test_curves, FIGURE_DIR / "long_or_flat_final_test_cumulative_pnl_comparison.png", "Long-or-Flat Final Test Cumulative PnL")
    plot_drawdown(test_curves[TARGET_VARIANT], FIGURE_DIR / "long_or_flat_final_drawdown.png")
    plot_trade_distribution(trades_to_dataframe(results_by_split["test"][TARGET_VARIANT].trades), FIGURE_DIR / "long_or_flat_final_trade_distribution.png")
    plot_slippage(slippage, FIGURE_DIR / "long_or_flat_final_slippage_sensitivity.png")
    plot_trade_count(performance, FIGURE_DIR / "long_or_flat_final_trade_count_comparison.png")
    plot_monthly_heatmap(pd.read_csv(TABLE_DIR / "long_or_flat_final_monthly_pnl.csv"), FIGURE_DIR / "long_or_flat_final_monthly_pnl_heatmap.png")


def plot_curves(curves: dict[str, pd.Series], filepath: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for label, curve in curves.items():
        ax.plot(to_dates(curve.index), curve.values, label=label, linewidth=1.2)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(title=title, xlabel="Date", ylabel="Cumulative PnL points")
    ax.legend(fontsize=8)
    save_fig(fig, filepath)


def plot_drawdown(curve: pd.Series, filepath: Path) -> None:
    drawdown, _, _ = compute_drawdown(curve)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(to_dates(drawdown.index), drawdown.values, 0, color="#C44E52", alpha=0.55)
    ax.set(title="Long-or-Flat Test Drawdown", xlabel="Date", ylabel="Drawdown points")
    save_fig(fig, filepath)


def plot_trade_distribution(trades: pd.DataFrame, filepath: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    if not trades.empty:
        ax.hist(trades["pnl_points"], bins=30, color="#4C78A8", alpha=0.85)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set(title="Long-or-Flat Test Trade PnL Distribution", xlabel="PnL points", ylabel="Trades")
    save_fig(fig, filepath)


def plot_slippage(slippage: pd.DataFrame, filepath: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(slippage["slippage"], slippage["cumulative_pnl_points"], marker="o", label="PnL")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(title="Long-or-Flat Slippage Sensitivity", xlabel="Slippage points per side", ylabel="Test PnL points")
    save_fig(fig, filepath)


def plot_trade_count(performance: pd.DataFrame, filepath: Path) -> None:
    test = performance.loc[performance["split"].eq("test")].copy()
    test["strategy"] = pd.Categorical(test["strategy"], categories=ALL_STRATEGIES, ordered=True)
    test = test.sort_values("strategy")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(test["strategy"].astype(str), test["num_trades"], color="#59A14F")
    ax.set(title="Test Trade Count Comparison", ylabel="Trades")
    ax.tick_params(axis="x", labelrotation=30)
    save_fig(fig, filepath)


def plot_monthly_heatmap(monthly: pd.DataFrame, filepath: Path) -> None:
    target = monthly.loc[monthly["strategy"].eq(TARGET_VARIANT)].copy()
    target["period"] = pd.PeriodIndex(target["month"], freq="M")
    target["year"] = target["period"].dt.year
    target["month_num"] = target["period"].dt.month
    pivot = target.pivot_table(index="year", columns="month_num", values="pnl_points", aggfunc="sum", fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn")
    ax.set_xticks(range(len(pivot.columns)), [str(value) for value in pivot.columns])
    ax.set_yticks(range(len(pivot.index)), [str(value) for value in pivot.index])
    ax.set(title="Long-or-Flat Monthly PnL", xlabel="Month", ylabel="Year")
    fig.colorbar(image, ax=ax, shrink=0.85)
    save_fig(fig, filepath)


def write_report_notes(performance: pd.DataFrame, improvement: pd.DataFrame, slippage: pd.DataFrame, params: dict[str, Any]) -> None:
    test = performance.loc[performance["split"].eq("test")].set_index("strategy")
    target = test.loc[TARGET_VARIANT]
    intraday = test.loc["INTRADAY_LONG"]
    flat = test.loc["FLAT"]
    base_slip = slippage.loc[slippage["slippage"].eq(BASE_SLIPPAGE)].iloc[0]
    high_slip = slippage.loc[slippage["slippage"].eq(10)].iloc[0]
    text = f"""# Long-or-Flat Final Supplementary Results

This note reports the final, report-ready output pass for `LONG_OR_FLAT_FILTERED` / `{TARGET_PARAMS_ID}`.

## Strategy Logic
The strategy enters at most one long trade per day after the opening window when early-session evidence is favorable. For the selected variant:

- opening window: {int(params.get('opening_window', 30))} bars
- minimum opening return: {float(params.get('min_opening_return_points', 0)):.1f} points
- minimum ER: {float(params.get('min_er', 0)):.2f}
- hold to close: {bool(params.get('hold_to_close', False))}
- stop loss: {float(params.get('stop_loss_points', 0)):.1f} points
- take profit disabled: {bool(params.get('disable_take_profit', False))}

## Test Result
`LONG_OR_FLAT_FILTERED` test PnL is {float(target['cumulative_pnl_points']):.1f} points, Sharpe {float(target['sharpe_ratio']):.3f}, max drawdown {float(target['max_drawdown_points']):.1f} points, trades {int(target['num_trades'])}, trades/day {float(target['trades_per_day']):.3f}, average trade PnL {float(target['avg_pnl_per_trade']):.3f}, and profit factor {float(target['profit_factor']):.3f}.

It beats INTRADAY_LONG by {float(target['cumulative_pnl_points'] - intraday['cumulative_pnl_points']):.1f} points and FLAT by {float(target['cumulative_pnl_points'] - flat['cumulative_pnl_points']):.1f} points.

## Slippage Robustness
At base slippage {BASE_SLIPPAGE} points per side, test PnL is {float(base_slip['cumulative_pnl_points']):.1f} points. At 10 points per side, test PnL is {float(high_slip['cumulative_pnl_points']):.1f} points.

## Interpretation
This is a post-analysis supplementary strategy, not the original pre-specified HYBRID strategy. It is useful because it demonstrates that the empirical diagnosis points toward long-or-flat directional filtering rather than mean-reversion or high-turnover regime switching. It should be reported with caution and framed as exploratory evidence requiring additional validation.
"""
    (NOTES_DIR / "long_or_flat_final_result_summary.md").write_text(text, encoding="utf-8")


def append_log(elapsed: float) -> None:
    with (EXPLORE_DIR / "EXPLORATION_RUN_LOG.md").open("a", encoding="utf-8") as file:
        file.write(
            f"""
## {datetime.now().strftime('%Y-%m-%d %H:%M')}

Command:
```bash
python strategy_optimization_exploration/scripts/run_long_or_flat_final.py
```

Result:

* Success

Output summary:

* Generated report-ready final supplementary outputs for `LONG_OR_FLAT_FILTERED` under `strategy_optimization_exploration/outputs/`.
* Runtime seconds: {elapsed:.2f}.

Error if failed:

```text
None.
```

Fix attempted:

* None.

Next action:

* Use `notes/long_or_flat_final_result_summary.md` and `notes/report_section_strategy_optimization.md` for the supplementary report section.
"""
        )


def print_summary(performance: pd.DataFrame, improvement: pd.DataFrame) -> None:
    test = performance.loc[performance["split"].eq("test") & performance["strategy"].isin([TARGET_VARIANT, "INTRADAY_LONG", "FLAT", "HYBRID", "ORB"])]
    print("Long-or-flat final supplementary run complete.")
    print(test[["strategy", "cumulative_pnl_points", "sharpe_ratio", "max_drawdown_points", "num_trades", "profit_factor"]].to_string(index=False))
    print("Improvement vs baselines:")
    print(improvement[["baseline", "delta_pnl_points", "delta_sharpe", "delta_num_trades", "beats_baseline"]].to_string(index=False))


def to_dates(index: pd.Index) -> pd.DatetimeIndex:
    return pd.to_datetime(index.astype(str), format="%Y%m%d")


def save_fig(fig: plt.Figure, filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(filepath, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()

