"""Stage-oriented command line entry point for the project."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.backtester import Backtester
from src.config import BASE_SLIPPAGE, COMMISSION_RT, DATA_PATH, FORCED_EXIT_TIME
from src.data_loader import load_and_prepare_data
from src.features import compute_session_features
from src.metrics import (
    compute_all_metrics,
    compute_equity_curve,
    compute_monthly_pnl,
    compute_regime_performance,
    trades_to_dataframe,
)
from src.optimization import run_staged_optimization
from src.plots import (
    plot_cumulative_pnl,
    plot_drawdown,
    plot_intraday_pattern_return,
    plot_intraday_pattern_volume,
    plot_monthly_pnl_heatmap,
    plot_param_heatmap,
    plot_price_series,
    plot_return_distribution,
    plot_sharpe_vs_slippage,
    plot_slippage_sensitivity,
    plot_trade_distribution,
)
from src.preprocessing import get_sessions, preprocess_data, split_by_period
from src.regime import classify_regime_series, compute_extreme_vol_threshold
from src.strategies import mr_signal, orb_signal
from src.utils import ensure_dir, save_dict_as_csv

DEFAULT_FEATURE_PARAMS = {
    "opening_window": 30,
    "rolling_window": 60,
    "use_vwap": True,
    "min_std_threshold": 5,
    "er_window": 60,
    "rv_window": 60,
}
DEFAULT_SIGNAL_PARAMS = {
    "buffer_points": 10,
    "z_entry": 2.0,
    "z_exit": 0.25,
}
DEFAULT_REGIME_PARAMS = {
    "er_threshold": 0.35,
    "extreme_vol_quantile": 0.90,
}
DEFAULT_BACKTEST_PARAMS = {
    **DEFAULT_FEATURE_PARAMS,
    **DEFAULT_SIGNAL_PARAMS,
    **DEFAULT_REGIME_PARAMS,
    "stop_loss_points": 80,
    "take_profit_points": 120,
    "max_trades": 3,
    "max_daily_loss": 200,
    "forced_exit_time": FORCED_EXIT_TIME,
}


def save_data_schema(df: pd.DataFrame, filepath: str | Path) -> None:
    """Save a compact schema inspection table."""
    schema = pd.DataFrame(
        {
            "column": df.columns,
            "dtype": [str(dtype) for dtype in df.dtypes],
            "non_null_count": [int(df[column].notna().sum()) for column in df.columns],
        }
    )
    schema.to_csv(filepath, index=False)


def save_session_counts(df: pd.DataFrame, filepath: str | Path) -> pd.DataFrame:
    """Save bar counts per cleaned day session."""
    session_counts = df.groupby("date", sort=True).size().rename("bar_count").reset_index()
    session_counts.to_csv(filepath, index=False)
    return session_counts


def run_data_stage() -> None:
    """Run Stage 1 data loading, preprocessing, and inspection outputs."""
    output_dir = ensure_dir(Path("outputs") / "tables")
    prepared = load_and_prepare_data(DATA_PATH)
    cleaned, summary = preprocess_data(prepared)
    splits = split_by_period(cleaned)

    save_data_schema(cleaned, output_dir / "data_schema.csv")
    session_counts = save_session_counts(cleaned, output_dir / "session_counts.csv")
    sessions = get_sessions(cleaned)

    date_start = cleaned["datetime"].min().date()
    date_end = cleaned["datetime"].max().date()
    print("Stage 1 data preprocessing complete.")
    print(f"Rows before cleaning: {summary['rows_before_cleaning']:,}")
    print(f"Rows after cleaning: {summary['rows_after_cleaning']:,}")
    print(f"Date range: {date_start} to {date_end}")
    print(f"Number of sessions: {len(sessions):,}")
    print(f"Train rows: {len(splits['train']):,}")
    print(f"Validation rows: {len(splits['val']):,}")
    print(f"Test rows: {len(splits['test']):,}")
    print(f"Duplicate count removed: {summary['duplicate_count_removed']:,}")
    print(f"Zero-volume count: {summary['zero_volume_count']:,}")
    print(f"Dropped short sessions: {summary['dropped_short_sessions']:,}")
    print(f"Session counts saved: {len(session_counts):,} rows")


def summarize_series(series: pd.Series) -> str:
    """Format compact summary statistics for terminal sanity output."""
    return (
        f"min={series.min():.6f}, median={series.median():.6f}, "
        f"mean={series.mean():.6f}, max={series.max():.6f}"
    )


def find_first_signal(feature_df: pd.DataFrame, signal_name: str) -> int:
    """Exercise one pure signal function and return its first non-flat output."""
    if signal_name == "orb":
        signals = [
            orb_signal(
                row.close,
                feature_df.attrs["OR_high"],
                feature_df.attrs["OR_low"],
                DEFAULT_SIGNAL_PARAMS["buffer_points"],
                0,
            )
            for row in feature_df.iloc[DEFAULT_FEATURE_PARAMS["opening_window"] :].itertuples()
        ]
    elif signal_name == "mr":
        signals = [
            mr_signal(row.z_score, DEFAULT_SIGNAL_PARAMS["z_entry"], DEFAULT_SIGNAL_PARAMS["z_exit"], 0)
            for row in feature_df.itertuples()
        ]
    else:
        raise ValueError(f"Unknown signal name: {signal_name}")
    return next((signal for signal in signals if signal != 0), 0)


def run_feature_stage() -> None:
    """Run Stage 2 feature and signal sanity checks on one training session."""
    output_dir = ensure_dir(Path("outputs") / "tables")
    prepared = load_and_prepare_data(DATA_PATH)
    cleaned, _ = preprocess_data(prepared)
    splits = split_by_period(cleaned)
    train_sessions = get_sessions(splits["train"])
    sample_date, sample_session = next(iter(train_sessions.items()))

    feature_df = compute_session_features(sample_session, DEFAULT_FEATURE_PARAMS)
    extreme_threshold = compute_extreme_vol_threshold(
        train_sessions,
        DEFAULT_FEATURE_PARAMS["rv_window"],
        DEFAULT_REGIME_PARAMS["extreme_vol_quantile"],
    )
    regimes = classify_regime_series(
        feature_df["ER"],
        feature_df["RV"],
        DEFAULT_REGIME_PARAMS["er_threshold"],
        extreme_threshold,
    )
    regime_counts = regimes.value_counts().sort_index()
    first_vwap_values = feature_df["vwap"].dropna().head(5).round(4).tolist()
    orb_test_signal = find_first_signal(feature_df, "orb")
    mr_test_signal = find_first_signal(feature_df, "mr")

    summary = {
        "sample_session_date": sample_date,
        "sample_session_rows": len(feature_df),
        "OR_high": feature_df.attrs["OR_high"],
        "OR_low": feature_df.attrs["OR_low"],
        "first_vwap_values": "; ".join(str(value) for value in first_vwap_values),
        "z_score_nonzero_count": int(feature_df["z_score"].ne(0).sum()),
        "z_score_min": float(feature_df["z_score"].min()),
        "z_score_max": float(feature_df["z_score"].max()),
        "ER_max": float(feature_df["ER"].max()),
        "RV_max": float(feature_df["RV"].max()),
        "extreme_vol_threshold": extreme_threshold,
        "regime_EXTREME_count": int(regime_counts.get("EXTREME", 0)),
        "regime_RANGE_count": int(regime_counts.get("RANGE", 0)),
        "regime_TREND_count": int(regime_counts.get("TREND", 0)),
        "orb_test_signal": orb_test_signal,
        "mr_test_signal": mr_test_signal,
    }
    save_dict_as_csv(summary, output_dir / "feature_sanity_summary.csv")

    print("Stage 2 feature sanity check complete.")
    print(f"Sample training session: {sample_date} ({len(feature_df):,} rows)")
    print(f"OR_high / OR_low: {feature_df.attrs['OR_high']:.2f} / {feature_df.attrs['OR_low']:.2f}")
    print(f"First VWAP values: {first_vwap_values}")
    print(f"Z-score summary: {summarize_series(feature_df['z_score'])}")
    print(f"ER summary: {summarize_series(feature_df['ER'])}")
    print(f"RV summary: {summarize_series(feature_df['RV'])}")
    print(f"Extreme RV threshold: {extreme_threshold:.6f}")
    print(f"Sample regime counts: {regime_counts.to_dict()}")
    print(f"ORB signal sanity output: {orb_test_signal}")
    print(f"MR signal sanity output: {mr_test_signal}")


def run_backtest_stage() -> None:
    """Run a small Stage 3 backtest sanity pass on training sessions."""
    table_dir = ensure_dir(Path("outputs") / "tables")
    log_dir = ensure_dir(Path("outputs") / "logs")
    prepared = load_and_prepare_data(DATA_PATH)
    cleaned, _ = preprocess_data(prepared)
    train_sessions = get_sessions(split_by_period(cleaned)["train"])
    small_sessions = dict(list(train_sessions.items())[:20])
    extreme_threshold = compute_extreme_vol_threshold(
        train_sessions,
        DEFAULT_BACKTEST_PARAMS["rv_window"],
        DEFAULT_BACKTEST_PARAMS["extreme_vol_quantile"],
    )

    results = {}
    for strategy in ["ORB", "MR", "HYBRID", "FLAT", "INTRADAY_LONG"]:
        results[strategy] = Backtester(
            small_sessions,
            strategy,
            DEFAULT_BACKTEST_PARAMS,
            BASE_SLIPPAGE,
            COMMISSION_RT,
            extreme_vol_threshold=extreme_threshold,
        ).run()

    metrics_rows = []
    for strategy, result in results.items():
        metrics_rows.append({"strategy": strategy, **compute_all_metrics(result.trades, result.daily_pnl)})
    metrics_df = pd.DataFrame(metrics_rows)
    metrics_df.to_csv(table_dir / "stage3_backtest_metrics.csv", index=False)
    for strategy in ["ORB", "MR", "HYBRID"]:
        trades_to_dataframe(results[strategy].trades).to_csv(
            log_dir / f"stage3_trades_{strategy.lower()}.csv",
            index=False,
        )

    print("Stage 3 small backtest complete.")
    print(f"Sessions tested: {len(small_sessions)}")
    print(f"Extreme RV threshold: {extreme_threshold:.6f}")
    summary_columns = ["strategy", "num_trades", "cumulative_pnl_points", "win_rate", "sharpe_ratio"]
    print(metrics_df.loc[metrics_df["strategy"].isin(["ORB", "MR", "HYBRID"]), summary_columns].to_string(index=False))
    print("Saved Stage 3 metrics and ORB/MR/HYBRID trade logs.")


def run_fast_mode() -> None:
    """Run the reduced-grid end-to-end pipeline."""
    run_pipeline("fast")


def run_medium_mode() -> None:
    """Run the medium-grid final-output pipeline."""
    run_pipeline("medium")


def run_supplementary_mode() -> None:
    """Run post-analysis ORB-filtered Hybrid variants without changing original outputs."""
    started = time.perf_counter()
    table_dir = ensure_dir(Path("outputs") / "tables")
    figure_dir = ensure_dir(Path("outputs") / "figures")

    prepared = load_and_prepare_data(DATA_PATH)
    cleaned, _ = preprocess_data(prepared)
    split_frames = split_by_period(cleaned)
    split_sessions = {name: get_sessions(frame) for name, frame in split_frames.items()}
    selected_params = load_selected_params(table_dir / "final_selected_params.csv", split_sessions["train"])

    hybrid_params = dict(selected_params["HYBRID"])
    basic_params = {
        **hybrid_params,
        "use_volume_filter": False,
        "use_or_width_filter": False,
        "use_two_bar_confirmation": False,
    }
    filtered_params = {
        **hybrid_params,
        "use_volume_filter": True,
        "volume_window": 30,
        "volume_multiplier": 1.0,
        "use_two_bar_confirmation": True,
        "use_or_width_filter": True,
        "max_or_width_quantile": 0.80,
    }
    filtered_params["max_or_width_points"] = compute_opening_range_width_threshold(
        split_sessions["train"],
        int(filtered_params.get("opening_window", 30)),
        float(filtered_params["max_or_width_quantile"]),
    )

    strategy_specs = {
        "HYBRID_ORIGINAL": ("HYBRID", hybrid_params),
        "ORB_FILTERED_HYBRID_BASIC": ("ORB_FILTERED_HYBRID", basic_params),
        "ORB_FILTERED_HYBRID_FILTERED": ("ORB_FILTERED_HYBRID", filtered_params),
        "ORB": ("ORB", selected_params["ORB"]),
        "MR": ("MR", selected_params["MR"]),
        "INTRADAY_LONG": ("INTRADAY_LONG", hybrid_params),
        "FLAT": ("FLAT", hybrid_params),
    }

    results_by_split: dict[str, dict[str, object]] = {}
    metric_rows: list[dict[str, object]] = []
    trade_tables: dict[str, list[pd.DataFrame]] = {
        "ORB_FILTERED_HYBRID_BASIC": [],
        "ORB_FILTERED_HYBRID_FILTERED": [],
    }
    regime_rows: list[dict[str, object]] = []

    for split_name, sessions in split_sessions.items():
        split_results = {}
        for label, (engine_strategy, params) in strategy_specs.items():
            threshold = params.get("extreme_vol_threshold") if engine_strategy in {"HYBRID", "ORB_FILTERED_HYBRID"} else None
            result = Backtester(
                sessions,
                engine_strategy,
                params,
                BASE_SLIPPAGE,
                COMMISSION_RT,
                extreme_vol_threshold=threshold,
            ).run()
            split_results[label] = result
            metrics = compute_all_metrics(result.trades, result.daily_pnl)
            metric_rows.append({"split": split_name, "strategy": label, **_select_supplementary_metrics(metrics)})

            trades_df = trades_to_dataframe(result.trades)
            if not trades_df.empty:
                trades_df.insert(0, "strategy", label)
                trades_df.insert(0, "split", split_name)
            if label in trade_tables:
                trade_tables[label].append(trades_df)
            regime_rows.extend(build_regime_breakdown_rows(split_name, label, trades_df))
        results_by_split[split_name] = split_results

    comparison = pd.DataFrame(metric_rows)
    comparison.to_csv(table_dir / "supplementary_strategy_comparison.csv", index=False)
    pd.DataFrame(regime_rows).to_csv(table_dir / "supplementary_regime_trade_breakdown.csv", index=False)

    for label, tables in trade_tables.items():
        combined = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
        suffix = "basic" if label.endswith("BASIC") else "filtered"
        combined.to_csv(table_dir / f"supplementary_orb_filtered_hybrid_{suffix}_trades.csv", index=False)

    improvement = build_supplementary_improvement_summary(comparison)
    improvement.to_csv(table_dir / "supplementary_improvement_summary.csv", index=False)

    comparison_labels = [
        "HYBRID_ORIGINAL",
        "ORB_FILTERED_HYBRID_BASIC",
        "ORB_FILTERED_HYBRID_FILTERED",
        "INTRADAY_LONG",
        "FLAT",
    ]
    combined_curves = {}
    test_curves = {}
    for label in comparison_labels:
        combined_daily = {}
        for split_name in ["train", "val", "test"]:
            combined_daily.update(results_by_split[split_name][label].daily_pnl)
        combined_curves[label] = compute_equity_curve(combined_daily)
        test_curves[label] = results_by_split["test"][label].equity_curve

    plot_cumulative_pnl(
        combined_curves,
        figure_dir / "supplementary_cumulative_pnl_comparison.png",
        "Supplementary Cumulative PnL Comparison",
    )
    plot_cumulative_pnl(
        test_curves,
        figure_dir / "supplementary_test_cumulative_pnl_comparison.png",
        "Supplementary Test Cumulative PnL Comparison",
    )
    plot_supplementary_trade_counts(
        comparison,
        figure_dir / "supplementary_trade_count_comparison.png",
    )
    update_report_with_supplementary_results(comparison, improvement)

    runtime = time.perf_counter() - started
    test_summary = comparison.loc[
        comparison["split"].eq("test")
        & comparison["strategy"].isin(
            [
                "HYBRID_ORIGINAL",
                "ORB_FILTERED_HYBRID_BASIC",
                "ORB_FILTERED_HYBRID_FILTERED",
                "INTRADAY_LONG",
                "FLAT",
            ]
        )
    ]
    print("Supplementary strategy run complete.")
    print(f"Runtime seconds: {runtime:.2f}")
    print(f"Filtered OR width threshold: {filtered_params['max_or_width_points']:.2f}")
    print("Test comparison:")
    print(test_summary.to_string(index=False))
    print("Saved supplementary tables and figures under outputs/.")


def run_improvement_mode() -> None:
    """Run a conservative structural improvement experiment separately."""
    started = time.perf_counter()
    table_dir = ensure_dir(Path("outputs") / "tables")
    figure_dir = ensure_dir(Path("outputs") / "figures")

    prepared = load_and_prepare_data(DATA_PATH)
    cleaned, _ = preprocess_data(prepared)
    split_sessions = {name: get_sessions(frame) for name, frame in split_by_period(cleaned).items()}
    selected_params = load_selected_params(table_dir / "final_selected_params.csv", split_sessions["train"])
    hybrid_params = dict(selected_params["HYBRID"])

    balanced_params = {
        **hybrid_params,
        "max_trades": 1,
        "er_margin": 0.00,
        "use_volume_filter": True,
        "volume_window": 30,
        "volume_multiplier": 1.0,
        "use_two_bar_confirmation": True,
        "use_or_width_filter": True,
        "max_or_width_quantile": 0.80,
        "use_vwap_direction_filter": True,
    }
    balanced_params["max_or_width_points"] = compute_opening_range_width_threshold(
        split_sessions["train"],
        int(balanced_params.get("opening_window", 30)),
        float(balanced_params["max_or_width_quantile"]),
    )
    strict_params = {
        **hybrid_params,
        "max_trades": 1,
        "er_margin": 0.10,
        "use_volume_filter": True,
        "volume_window": 30,
        "volume_multiplier": 1.2,
        "use_two_bar_confirmation": True,
        "use_or_width_filter": True,
        "max_or_width_quantile": 0.80,
        "use_vwap_direction_filter": True,
        "latest_entry_time": 113000,
    }
    strict_params["max_or_width_points"] = compute_opening_range_width_threshold(
        split_sessions["train"],
        int(strict_params.get("opening_window", 30)),
        float(strict_params["max_or_width_quantile"]),
    )

    comparison_specs = {
        "HYBRID_ORIGINAL": ("HYBRID", hybrid_params),
        "ORB_FILTERED_HYBRID_FILTERED": (
            "ORB_FILTERED_HYBRID",
            {
                **hybrid_params,
                "use_volume_filter": True,
                "volume_window": 30,
                "volume_multiplier": 1.0,
                "use_two_bar_confirmation": True,
                "use_or_width_filter": True,
                "max_or_width_quantile": 0.80,
                "max_or_width_points": balanced_params["max_or_width_points"],
            },
        ),
        "ORB_CONFIRMED_HYBRID_BALANCED": ("ORB_CONFIRMED_HYBRID", balanced_params),
        "ORB_CONFIRMED_HYBRID_STRICT": ("ORB_CONFIRMED_HYBRID", strict_params),
        "INTRADAY_LONG": ("INTRADAY_LONG", hybrid_params),
        "FLAT": ("FLAT", hybrid_params),
    }

    results_by_split: dict[str, dict[str, object]] = {}
    metric_rows: list[dict[str, object]] = []
    regime_rows: list[dict[str, object]] = []
    confirmed_trade_tables: list[pd.DataFrame] = []

    for split_name, sessions in split_sessions.items():
        split_results = {}
        for label, (engine_strategy, params) in comparison_specs.items():
            threshold = params.get("extreme_vol_threshold") if engine_strategy in {"HYBRID", "ORB_FILTERED_HYBRID", "ORB_CONFIRMED_HYBRID"} else None
            result = Backtester(
                sessions,
                engine_strategy,
                params,
                BASE_SLIPPAGE,
                COMMISSION_RT,
                extreme_vol_threshold=threshold,
            ).run()
            split_results[label] = result
            metric_rows.append({"split": split_name, "strategy": label, **_select_supplementary_metrics(compute_all_metrics(result.trades, result.daily_pnl))})
            trades_df = trades_to_dataframe(result.trades)
            if not trades_df.empty:
                trades_df.insert(0, "strategy", label)
                trades_df.insert(0, "split", split_name)
            regime_rows.extend(build_regime_breakdown_rows(split_name, label, trades_df))
            if label.startswith("ORB_CONFIRMED_HYBRID"):
                confirmed_trade_tables.append(trades_df)
        results_by_split[split_name] = split_results

    comparison = pd.DataFrame(metric_rows)
    comparison.to_csv(table_dir / "improved_strategy_comparison.csv", index=False)
    pd.DataFrame(regime_rows).to_csv(table_dir / "improved_regime_trade_breakdown.csv", index=False)
    non_empty_confirmed = [table for table in confirmed_trade_tables if not table.empty]
    confirmed_trades = pd.concat(non_empty_confirmed, ignore_index=True) if non_empty_confirmed else pd.DataFrame()
    confirmed_trades.to_csv(
        table_dir / "improved_orb_confirmed_hybrid_trades.csv",
        index=False,
    )
    improvement = build_improved_strategy_summary(comparison)
    improvement.to_csv(table_dir / "improved_strategy_summary.csv", index=False)

    comparison_labels = [
        "HYBRID_ORIGINAL",
        "ORB_FILTERED_HYBRID_FILTERED",
        "ORB_CONFIRMED_HYBRID_BALANCED",
        "ORB_CONFIRMED_HYBRID_STRICT",
        "INTRADAY_LONG",
        "FLAT",
    ]
    combined_curves = {}
    test_curves = {}
    for label in comparison_labels:
        combined_daily = {}
        for split_name in ["train", "val", "test"]:
            combined_daily.update(results_by_split[split_name][label].daily_pnl)
        combined_curves[label] = compute_equity_curve(combined_daily)
        test_curves[label] = results_by_split["test"][label].equity_curve

    plot_cumulative_pnl(
        combined_curves,
        figure_dir / "improved_cumulative_pnl_comparison.png",
        "Improved Strategy Cumulative PnL Comparison",
    )
    plot_cumulative_pnl(
        test_curves,
        figure_dir / "improved_test_cumulative_pnl_comparison.png",
        "Improved Strategy Test Cumulative PnL Comparison",
    )
    plot_supplementary_trade_counts(
        comparison,
        figure_dir / "improved_trade_count_comparison.png",
    )

    runtime = time.perf_counter() - started
    test_summary = comparison.loc[comparison["split"].eq("test")]
    print("Improvement experiment complete.")
    print(f"Runtime seconds: {runtime:.2f}")
    print(f"Confirmed OR width threshold: {balanced_params['max_or_width_points']:.2f}")
    print("ORB_CONFIRMED_HYBRID_BALANCED parameters:")
    print(pd.Series(balanced_params).sort_index().to_string())
    print("ORB_CONFIRMED_HYBRID_STRICT parameters:")
    print(pd.Series(strict_params).sort_index().to_string())
    print("Test comparison:")
    print(test_summary.to_string(index=False))
    print("Saved improved strategy tables and figures under outputs/.")


def run_pipeline(mode: str) -> None:
    """Run optimization, final evaluation, tables, logs, and figures."""
    started = time.perf_counter()
    table_dir = ensure_dir(Path("outputs") / "tables")
    log_dir = ensure_dir(Path("outputs") / "logs")
    figure_dir = ensure_dir(Path("outputs") / "figures")
    fast = mode == "fast"
    medium = mode == "medium"

    prepared = load_and_prepare_data(DATA_PATH)
    cleaned, _ = preprocess_data(prepared)
    split_frames = split_by_period(cleaned)
    split_sessions = {name: get_sessions(frame) for name, frame in split_frames.items()}

    plot_price_series(cleaned, figure_dir / "price_series.png")
    plot_return_distribution(cleaned.groupby("date")["close"].pct_change().fillna(0), figure_dir / "return_distribution.png")
    plot_intraday_pattern_return(cleaned, figure_dir / "intraday_return_pattern.png")
    plot_intraday_pattern_volume(cleaned, figure_dir / "intraday_volume_pattern.png")

    optimization = run_staged_optimization(
        split_sessions["train"],
        split_sessions["val"],
        fast=fast,
        medium=medium,
        slippage=BASE_SLIPPAGE,
        commission_rt=COMMISSION_RT,
    )
    selected_params = {
        "ORB": optimization["orb_params"],
        "MR": optimization["mr_params"],
        "HYBRID": optimization["hybrid_params"],
    }

    results_by_split: dict[str, dict[str, object]] = {}
    metric_rows: list[dict[str, object]] = []
    strategy_order = ["BUY_AND_HOLD", "INTRADAY_LONG", "FLAT", "ORB", "MR", "HYBRID"]
    for split_name, sessions in split_sessions.items():
        split_results = {}
        for strategy in strategy_order:
            params = selected_params.get(strategy, selected_params["HYBRID"])
            threshold = params.get("extreme_vol_threshold") if strategy == "HYBRID" else None
            result = Backtester(
                sessions,
                strategy,
                params,
                BASE_SLIPPAGE,
                COMMISSION_RT,
                extreme_vol_threshold=threshold,
            ).run()
            split_results[strategy] = result
            metric_rows.append({"split": split_name, "strategy": strategy, **compute_all_metrics(result.trades, result.daily_pnl)})
        results_by_split[split_name] = split_results

    performance = pd.DataFrame(metric_rows)
    performance.to_csv(table_dir / "performance_summary.csv", index=False)
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
    performance[risk_columns].to_csv(table_dir / "risk_metrics.csv", index=False)
    performance[trade_columns].to_csv(table_dir / "trade_statistics.csv", index=False)

    hybrid_trade_tables = []
    monthly_tables = []
    regime_tables = []
    for split_name, split_results in results_by_split.items():
        hybrid_result = split_results["HYBRID"]
        trades_df = trades_to_dataframe(hybrid_result.trades)
        trades_df.insert(0, "split", split_name)
        hybrid_trade_tables.append(trades_df)
        monthly = compute_monthly_pnl(hybrid_result.daily_pnl)
        monthly.insert(0, "split", split_name)
        monthly.insert(1, "strategy", "HYBRID")
        monthly_tables.append(monthly)
        regime = compute_regime_performance(trades_df)
        regime.insert(0, "split", split_name)
        regime_tables.append(regime)

    all_hybrid_trades = pd.concat(hybrid_trade_tables, ignore_index=True)
    all_hybrid_trades.to_csv(log_dir / "all_trades_hybrid.csv", index=False)
    monthly_pnl = pd.concat(monthly_tables, ignore_index=True)
    monthly_pnl.to_csv(table_dir / "monthly_pnl.csv", index=False)
    pd.concat(regime_tables, ignore_index=True).to_csv(table_dir / "regime_performance.csv", index=False)

    slippage_rows = []
    test_hybrid_params = selected_params["HYBRID"]
    for slippage in [0, 1, 2, 5, 10]:
        result = Backtester(
            split_sessions["test"],
            "HYBRID",
            test_hybrid_params,
            slippage,
            COMMISSION_RT,
            extreme_vol_threshold=test_hybrid_params.get("extreme_vol_threshold"),
        ).run()
        slippage_rows.append({"slippage": slippage, **compute_all_metrics(result.trades, result.daily_pnl)})
    slippage_sensitivity = pd.DataFrame(slippage_rows)
    slippage_sensitivity.to_csv(table_dir / "slippage_sensitivity.csv", index=False)

    combined_curves = {}
    for strategy in strategy_order:
        combined_daily = {}
        for split_name in ["train", "val", "test"]:
            combined_daily.update(results_by_split[split_name][strategy].daily_pnl)
        combined_curves[strategy] = compute_equity_curve(combined_daily)
    test_curves = {strategy: results_by_split["test"][strategy].equity_curve for strategy in strategy_order}
    test_hybrid_trades = trades_to_dataframe(results_by_split["test"]["HYBRID"].trades)
    test_monthly = monthly_pnl.loc[monthly_pnl["split"].eq("test")]

    plot_cumulative_pnl(combined_curves, figure_dir / "cumulative_pnl_comparison.png", "Cumulative PnL Comparison")
    plot_cumulative_pnl(test_curves, figure_dir / "out_of_sample_cumulative_pnl.png", "Out-of-Sample Cumulative PnL")
    plot_drawdown(results_by_split["test"]["HYBRID"].equity_curve, figure_dir / "hybrid_drawdown.png")
    plot_trade_distribution(test_hybrid_trades, figure_dir / "hybrid_trade_distribution.png")
    plot_param_heatmap(optimization["orb_train_grid"], "opening_window", "buffer_points", figure_dir / "orb_param_heatmap.png")
    plot_param_heatmap(optimization["mr_train_grid"], "rolling_window", "z_entry", figure_dir / "mr_param_heatmap.png")
    plot_param_heatmap(optimization["regime_train_grid"], "er_threshold", "rv_window", figure_dir / "regime_param_heatmap.png")
    plot_slippage_sensitivity(slippage_sensitivity, figure_dir / "slippage_sensitivity.png")
    plot_sharpe_vs_slippage(slippage_sensitivity, figure_dir / "sharpe_vs_slippage.png")
    plot_monthly_pnl_heatmap(test_monthly, figure_dir / "monthly_pnl_heatmap.png")
    write_report_summary(
        table_dir / "report_summary.md",
        mode,
        selected_params,
        performance,
        slippage_sensitivity,
    )

    runtime = time.perf_counter() - started
    test_summary = performance.loc[
        performance["split"].eq("test") & performance["strategy"].isin(["ORB", "MR", "HYBRID"]),
        ["strategy", "num_trades", "cumulative_pnl_points", "sharpe_ratio", "max_drawdown_points"],
    ]
    print(f"{mode.capitalize()} mode complete.")
    print(f"Runtime seconds: {runtime:.2f}")
    print("Selected HYBRID parameters:")
    print(pd.Series(selected_params["HYBRID"]).sort_index().to_string())
    print("Test performance:")
    print(test_summary.to_string(index=False))
    print("Saved tables, logs, and figures under outputs/.")


def write_report_summary(
    filepath: str | Path,
    mode: str,
    selected_params: dict[str, dict],
    performance: pd.DataFrame,
    slippage_sensitivity: pd.DataFrame,
) -> None:
    """Create a compact report-ready markdown summary."""
    path = Path(filepath)
    ensure_dir(path.parent)
    test = performance.loc[performance["split"].eq("test")].copy()
    test_ranked = test.sort_values("sharpe_ratio", ascending=False)
    best_test = test_ranked.iloc[0]
    hybrid_test = test.loc[test["strategy"].eq("HYBRID")].iloc[0]
    orb_test = test.loc[test["strategy"].eq("ORB")].iloc[0]
    mr_test = test.loc[test["strategy"].eq("MR")].iloc[0]
    benchmark_best = test.loc[test["strategy"].isin(["BUY_AND_HOLD", "INTRADAY_LONG", "FLAT"])].sort_values(
        "sharpe_ratio",
        ascending=False,
    ).iloc[0]
    hybrid_beats_orb_mr = (
        hybrid_test["sharpe_ratio"] > orb_test["sharpe_ratio"]
        and hybrid_test["sharpe_ratio"] > mr_test["sharpe_ratio"]
    )
    hybrid_beats_benchmark = hybrid_test["sharpe_ratio"] > benchmark_best["sharpe_ratio"]
    base_slippage_row = slippage_sensitivity.loc[slippage_sensitivity["slippage"].eq(BASE_SLIPPAGE)]
    high_slippage_row = slippage_sensitivity.loc[slippage_sensitivity["slippage"].eq(10)]
    base_pnl = float(base_slippage_row["cumulative_pnl_points"].iloc[0]) if not base_slippage_row.empty else float("nan")
    high_pnl = float(high_slippage_row["cumulative_pnl_points"].iloc[0]) if not high_slippage_row.empty else float("nan")
    robust_text = (
        "HYBRID remains profitable under the tested slippage range."
        if (slippage_sensitivity["cumulative_pnl_points"] > 0).all()
        else "HYBRID is not slippage robust under the tested range."
    )

    with path.open("w", encoding="utf-8") as file:
        file.write("# Report Summary\n\n")
        file.write(f"Mode used: `{mode}`\n\n")
        file.write("## Final Selected Parameters\n\n")
        for strategy, params in selected_params.items():
            file.write(f"### {strategy}\n\n")
            for key, value in sorted(params.items()):
                file.write(f"- `{key}`: `{value}`\n")
            file.write("\n")

        file.write("## Train / Validation / Test Performance\n\n")
        summary = performance[
            [
                "split",
                "strategy",
                "num_trades",
                "cumulative_pnl_points",
                "sharpe_ratio",
                "max_drawdown_points",
                "profit_factor",
            ]
        ]
        file.write(dataframe_to_markdown(summary))
        file.write("\n\n")

        file.write("## Out-of-Sample Winner\n\n")
        file.write(
            f"Best test strategy by Sharpe is `{best_test['strategy']}` "
            f"with Sharpe `{best_test['sharpe_ratio']:.3f}` and "
            f"PnL `{best_test['cumulative_pnl_points']:.1f}` points.\n\n"
        )

        file.write("## Hybrid Comparison\n\n")
        file.write(f"- HYBRID beats ORB and MR on test Sharpe: `{hybrid_beats_orb_mr}`\n")
        file.write(f"- HYBRID beats the best benchmark on test Sharpe: `{hybrid_beats_benchmark}`\n")
        file.write(f"- Best benchmark by test Sharpe: `{benchmark_best['strategy']}`\n\n")

        file.write("## Slippage Robustness\n\n")
        file.write(f"- Base slippage `{BASE_SLIPPAGE}` point HYBRID PnL: `{base_pnl:.1f}` points\n")
        file.write(f"- 10-point slippage HYBRID PnL: `{high_pnl:.1f}` points\n")
        file.write(f"- Interpretation: {robust_text}\n\n")

        file.write("## Key Interpretation\n\n")
        if hybrid_beats_orb_mr and hybrid_beats_benchmark:
            file.write(
                "The regime-adaptive framework is the strongest tested configuration in this run. "
                "Report this as supportive evidence, while still noting parameter-selection and cost assumptions.\n"
            )
        else:
            file.write(
                "The current selected HYBRID strategy does not dominate the alternatives out of sample. "
                "This should be reported as an important empirical finding rather than tuned away on the test set.\n"
            )


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    """Render a small DataFrame as a markdown table without optional dependencies."""
    columns = list(df.columns)
    lines = [
        "| " + " | ".join(str(column) for column in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in df.iterrows():
        values = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def load_selected_params(filepath: str | Path, train_sessions: dict[int, pd.DataFrame]) -> dict[str, dict]:
    """Load medium-mode selected parameters and fill any missing HYBRID threshold from training only."""
    selected = pd.read_csv(filepath)
    params_by_strategy: dict[str, dict] = {}
    for _, row in selected.iterrows():
        strategy = str(row["selection"])
        params = {
            key: value.item() if hasattr(value, "item") else value
            for key, value in row.items()
            if key != "selection" and pd.notna(value)
        }
        params_by_strategy[strategy] = params

    hybrid = params_by_strategy.get("HYBRID")
    if hybrid is None:
        raise ValueError("final_selected_params.csv must contain a HYBRID row.")
    if "extreme_vol_threshold" not in hybrid:
        hybrid["extreme_vol_threshold"] = compute_extreme_vol_threshold(
            train_sessions,
            int(hybrid.get("rv_window", 60)),
            float(hybrid.get("extreme_vol_quantile", 0.95)),
        )
    params_by_strategy.setdefault("ORB", dict(hybrid))
    params_by_strategy.setdefault("MR", dict(hybrid))
    return params_by_strategy


def compute_opening_range_width_threshold(
    train_sessions: dict[int, pd.DataFrame],
    opening_window: int,
    quantile: float,
) -> float:
    """Compute an opening-range width cutoff from training sessions only."""
    widths = []
    for session in train_sessions.values():
        ordered = session.sort_values("datetime").reset_index(drop=True)
        if len(ordered) < opening_window:
            continue
        opening = ordered.iloc[:opening_window]
        widths.append(float(opening["high"].max() - opening["low"].min()))
    if not widths:
        raise ValueError("No training sessions are available to compute OR width threshold.")
    return float(pd.Series(widths).quantile(quantile))


def _select_supplementary_metrics(metrics: dict[str, object]) -> dict[str, object]:
    """Keep the requested compact metric set for supplementary outputs."""
    wanted = [
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
    return {key: metrics[key] for key in wanted}


def build_regime_breakdown_rows(split_name: str, strategy: str, trades_df: pd.DataFrame) -> list[dict[str, object]]:
    """Build per-regime trade-count and PnL rows for supplementary diagnosis."""
    rows = []
    if trades_df.empty:
        for regime in ["TREND", "RANGE", "EXTREME"]:
            rows.append(
                {
                    "split": split_name,
                    "strategy": strategy,
                    "regime_at_entry": regime,
                    "num_entries": 0,
                    "pnl_points": 0.0,
                    "extreme_exits": 0,
                }
            )
        return rows

    for regime in ["TREND", "RANGE", "EXTREME"]:
        subset = trades_df.loc[trades_df["regime_at_entry"].eq(regime)]
        rows.append(
            {
                "split": split_name,
                "strategy": strategy,
                "regime_at_entry": regime,
                "num_entries": int(len(subset)),
                "pnl_points": float(subset["pnl_points"].sum()) if not subset.empty else 0.0,
                "extreme_exits": int(subset["exit_reason"].eq("regime_extreme").sum()) if not subset.empty else 0,
            }
        )
    return rows


def build_supplementary_improvement_summary(comparison: pd.DataFrame) -> pd.DataFrame:
    """Compare supplementary test variants against the original HYBRID."""
    test = comparison.loc[comparison["split"].eq("test")].set_index("strategy")
    original = test.loc["HYBRID_ORIGINAL"]
    rows = []
    for strategy in ["ORB_FILTERED_HYBRID_BASIC", "ORB_FILTERED_HYBRID_FILTERED"]:
        current = test.loc[strategy]
        pnl_change = float(current["cumulative_pnl_points"] - original["cumulative_pnl_points"])
        sharpe_change = float(current["sharpe_ratio"] - original["sharpe_ratio"])
        trade_change = int(current["num_trades"] - original["num_trades"])
        profit_factor_change = float(current["profit_factor"] - original["profit_factor"])
        if pnl_change > 0 and float(current["cumulative_pnl_points"]) < 0:
            interpretation = "Improves loss versus original HYBRID but remains negative."
        elif pnl_change > 0:
            interpretation = "Improves versus original HYBRID."
        else:
            interpretation = "Does not improve versus original HYBRID."
        rows.append(
            {
                "strategy": strategy,
                "original_hybrid_test_pnl": float(original["cumulative_pnl_points"]),
                "supplementary_test_pnl": float(current["cumulative_pnl_points"]),
                "change_in_pnl_vs_original": pnl_change,
                "original_hybrid_sharpe": float(original["sharpe_ratio"]),
                "supplementary_sharpe": float(current["sharpe_ratio"]),
                "change_in_sharpe_vs_original": sharpe_change,
                "original_hybrid_num_trades": int(original["num_trades"]),
                "supplementary_num_trades": int(current["num_trades"]),
                "change_in_num_trades": trade_change,
                "original_hybrid_profit_factor": float(original["profit_factor"]),
                "supplementary_profit_factor": float(current["profit_factor"]),
                "change_in_profit_factor": profit_factor_change,
                "interpretation": interpretation,
            }
        )
    return pd.DataFrame(rows)


def build_improved_strategy_summary(comparison: pd.DataFrame) -> pd.DataFrame:
    """Summarize the confirmed improvement versus original and prior filtered variant."""
    test = comparison.loc[comparison["split"].eq("test")].set_index("strategy")
    original = test.loc["HYBRID_ORIGINAL"]
    filtered = test.loc["ORB_FILTERED_HYBRID_FILTERED"]
    rows = []
    for strategy in ["ORB_CONFIRMED_HYBRID_BALANCED", "ORB_CONFIRMED_HYBRID_STRICT"]:
        confirmed = test.loc[strategy]
        for baseline_name, baseline in [("HYBRID_ORIGINAL", original), ("ORB_FILTERED_HYBRID_FILTERED", filtered)]:
            pnl_change = float(confirmed["cumulative_pnl_points"] - baseline["cumulative_pnl_points"])
            sharpe_change = float(confirmed["sharpe_ratio"] - baseline["sharpe_ratio"])
            trade_change = int(confirmed["num_trades"] - baseline["num_trades"])
            if pnl_change > 0 and float(confirmed["cumulative_pnl_points"]) < 0:
                interpretation = "Improves versus baseline but remains negative."
            elif pnl_change > 0:
                interpretation = "Improves versus baseline."
            else:
                interpretation = "Does not improve versus baseline."
            rows.append(
                {
                    "strategy": strategy,
                    "baseline": baseline_name,
                    "baseline_test_pnl": float(baseline["cumulative_pnl_points"]),
                    "confirmed_test_pnl": float(confirmed["cumulative_pnl_points"]),
                    "change_in_pnl": pnl_change,
                    "baseline_sharpe": float(baseline["sharpe_ratio"]),
                    "confirmed_sharpe": float(confirmed["sharpe_ratio"]),
                    "change_in_sharpe": sharpe_change,
                    "baseline_num_trades": int(baseline["num_trades"]),
                    "confirmed_num_trades": int(confirmed["num_trades"]),
                    "change_in_num_trades": trade_change,
                    "baseline_profit_factor": float(baseline["profit_factor"]),
                    "confirmed_profit_factor": float(confirmed["profit_factor"]),
                    "change_in_profit_factor": float(confirmed["profit_factor"] - baseline["profit_factor"]),
                    "interpretation": interpretation,
                }
            )
    return pd.DataFrame(rows)


def plot_supplementary_trade_counts(comparison: pd.DataFrame, filepath: str | Path) -> None:
    """Plot test-period trade count comparison for supplementary strategies."""
    test = comparison.loc[comparison["split"].eq("test")].copy()
    order = [
        "HYBRID_ORIGINAL",
        "ORB_FILTERED_HYBRID_BASIC",
        "ORB_FILTERED_HYBRID_FILTERED",
        "ORB",
        "MR",
        "INTRADAY_LONG",
        "FLAT",
    ]
    test["strategy"] = pd.Categorical(test["strategy"], categories=order, ordered=True)
    test = test.sort_values("strategy")
    path = Path(filepath)
    ensure_dir(path.parent)
    plt.figure(figsize=(10, 5))
    plt.bar(test["strategy"].astype(str), test["num_trades"], color="#4C78A8")
    plt.xticks(rotation=35, ha="right")
    plt.ylabel("Number of trades")
    plt.title("Supplementary Test Trade Count Comparison")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def update_report_with_supplementary_results(comparison: pd.DataFrame, improvement: pd.DataFrame) -> None:
    """Insert or replace the supplementary-report section before the conclusion."""
    report_path = Path("report") / "STAT8020_Project_Report_Draft.md"
    if not report_path.exists():
        return

    marker_start = "# Strategy Improvement and Supplementary Experiment"
    marker_end = "# 11. Conclusion"
    text = report_path.read_text(encoding="utf-8")
    section = build_supplementary_report_section(comparison, improvement)
    if marker_start in text:
        before = text.split(marker_start, 1)[0].rstrip()
        rest = text.split(marker_start, 1)[1]
        after = rest.split(marker_end, 1)[1]
        text = f"{before}\n\n{section}\n\n{marker_end}{after}"
    elif marker_end in text:
        text = text.replace(marker_end, f"{section}\n\n{marker_end}", 1)
    else:
        text = text.rstrip() + "\n\n" + section + "\n"
    report_path.write_text(text, encoding="utf-8")


def build_supplementary_report_section(comparison: pd.DataFrame, improvement: pd.DataFrame) -> str:
    """Return the Markdown supplementary experiment section."""
    test = comparison.loc[
        comparison["split"].eq("test")
        & comparison["strategy"].isin(
            [
                "HYBRID_ORIGINAL",
                "ORB_FILTERED_HYBRID_BASIC",
                "ORB_FILTERED_HYBRID_FILTERED",
                "INTRADAY_LONG",
                "FLAT",
            ]
        )
    ][
        [
            "strategy",
            "num_trades",
            "cumulative_pnl_points",
            "sharpe_ratio",
            "max_drawdown_points",
            "profit_factor",
            "avg_pnl_per_trade",
        ]
    ]
    basic_row = improvement.loc[improvement["strategy"].eq("ORB_FILTERED_HYBRID_BASIC")].iloc[0]
    filtered_row = improvement.loc[improvement["strategy"].eq("ORB_FILTERED_HYBRID_FILTERED")].iloc[0]
    basic_text = (
        f"The BASIC variant changes test PnL by {basic_row['change_in_pnl_vs_original']:.1f} points "
        f"and trade count by {basic_row['change_in_num_trades']:.0f} relative to the original Hybrid."
    )
    filtered_text = (
        f"The FILTERED variant changes test PnL by {filtered_row['change_in_pnl_vs_original']:.1f} points "
        f"and trade count by {filtered_row['change_in_num_trades']:.0f} relative to the original Hybrid."
    )
    return f"""# Strategy Improvement and Supplementary Experiment

After the original Hybrid strategy was evaluated, the trade-level diagnosis showed that RANGE/mean-reversion trades were consistently negative and were a major drag on performance. This motivates a supplementary post-analysis experiment called `ORB_FILTERED_HYBRID`. The purpose is not to rewrite the original pre-specified main strategy, and it is not used to tune the test set. Instead, it is used to learn from the empirical diagnosis.

The supplementary strategy keeps the same regime classifier but changes the action mapping:

| Regime | Original Hybrid | ORB-filtered Hybrid |
|---|---|---|
| TREND | ORB | ORB |
| RANGE | Mean Reversion | Flat; no new entries |
| EXTREME | Flat / close | Flat / close |

Two variants are tested:

- `ORB_FILTERED_HYBRID_BASIC`: removes RANGE/MR entries with no additional ORB filters.
- `ORB_FILTERED_HYBRID_FILTERED`: additionally applies volume confirmation, two-bar breakout confirmation, and a training-only opening-range-width filter.

The test-period comparison is:

{dataframe_to_markdown(test)}

Full supplementary results are saved in `outputs/tables/supplementary_strategy_comparison.csv`.

{basic_text} {filtered_text}

If either supplementary variant improves but remains negative, the interpretation is that removing mean reversion helps reduce part of the loss but is not sufficient for live deployment. If a variant fails to improve, then the weakness is not only caused by the mean-reversion component; the ORB signals and regime stability are also insufficient.

The supplementary figures are:

![Supplementary cumulative PnL comparison](../outputs/figures/supplementary_cumulative_pnl_comparison.png)

![Supplementary test cumulative PnL comparison](../outputs/figures/supplementary_test_cumulative_pnl_comparison.png)

![Supplementary trade count comparison](../outputs/figures/supplementary_trade_count_comparison.png)

Future improvements should consider stronger volume confirmation, a more conservative no-trade zone near the ER threshold, an explicit turnover penalty during optimization, walk-forward validation, and spread-aware execution modeling.
"""


def parse_args() -> argparse.Namespace:
    """Parse the stage selection for the command line entry point."""
    parser = argparse.ArgumentParser(description="STAT8020 HSI futures project runner")
    parser.add_argument("--stage", choices=["data", "features", "backtest"], help="Project stage to run")
    parser.add_argument("--fast", action="store_true", help="Run the reduced-grid end-to-end pipeline")
    parser.add_argument("--medium", action="store_true", help="Run the medium-grid final-output pipeline")
    parser.add_argument("--supplementary", action="store_true", help="Run supplementary ORB-filtered Hybrid experiments")
    parser.add_argument("--improvement", action="store_true", help="Run conservative ORB-confirmed improvement experiment")
    return parser.parse_args()


def main() -> None:
    """Dispatch the requested project stage."""
    args = parse_args()
    if args.fast:
        run_fast_mode()
        return
    if args.medium:
        run_medium_mode()
        return
    if args.supplementary:
        run_supplementary_mode()
        return
    if args.improvement:
        run_improvement_mode()
        return
    if args.stage == "data":
        run_data_stage()
    if args.stage == "features":
        run_feature_stage()
    if args.stage == "backtest":
        run_backtest_stage()
    if not args.stage:
        raise SystemExit("Choose a stage with --stage or run the fast pipeline with --fast.")


if __name__ == "__main__":
    main()
