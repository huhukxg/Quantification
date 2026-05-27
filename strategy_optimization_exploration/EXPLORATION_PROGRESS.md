# EXPLORATION_PROGRESS.md

## Current Status
`fast` exploration completed successfully. Outputs were saved under `strategy_optimization_exploration/outputs/`.

## Baseline Results
Original test HYBRID: -3577.0 points, Sharpe -5.133.
ORB: -1954.0 points. MR: -3227.0 points. INTRADAY_LONG: 338.0 points. FLAT: 0.0 points.

## Strategy Variants Implemented
EXTREME_TREND_FOLLOWING, LONG_ONLY_ORB, LONG_OR_FLAT_FILTERED, LOW_TURNOVER_HYBRID, ORB_FILTERED_HYBRID_BASIC, ORB_FILTERED_HYBRID_CONFIRM, ORB_FILTERED_HYBRID_STRICT_TREND, ORB_ONLY_CONFIRM, ORB_ONLY_LOW_TURNOVER, ORB_ONLY_RANGE_FILTER, ORB_ONLY_VOLUME, ORB_TO_CLOSE, STRICT_MR_HYBRID, STRICT_MR_ONLY

## Commands Run
python strategy_optimization_exploration/scripts/run_exploration.py --fast

## Latest Results
Top validation-score variant: `EXTREME_TREND_FOLLOWING` / `extreme_trend_following_003`. Test PnL -1138.0 points, Sharpe -1.329, trades 32.

Best benchmark-beating validation-screened candidate: `LONG_OR_FLAT_FILTERED` / `long_or_flat_filtered_004`. It ranked #3 on validation, with validation PnL 1078.0 points and validation Sharpe 1.342. On test it earns 991.0 points, Sharpe 0.911, 68 trades, and profit factor 1.244. It beats original HYBRID, ORB, INTRADAY_LONG, and FLAT in the test sample.

Final report-ready output pass for `LONG_OR_FLAT_FILTERED` completed. Tables, figures, trade logs, slippage sensitivity, monthly PnL, and final notes are saved with the `long_or_flat_final_` prefix.

## Current Issues
The benchmark-beating result is exploratory and must not be used to re-label the original HYBRID strategy. The `LONG_OR_FLAT_FILTERED` candidate was validation-screened before test evaluation, but the entire second-stage search is post-analysis because it was motivated by the original test failure.

## Next Steps
Review `notes/result_summary.md`, `notes/final_recommendations.md`, and `notes/report_section_strategy_optimization.md` before deciding whether to add a supplementary report section.
