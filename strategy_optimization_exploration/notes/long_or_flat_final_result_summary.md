# Long-or-Flat Final Supplementary Results

This note reports the final, report-ready output pass for `LONG_OR_FLAT_FILTERED` / `long_or_flat_filtered_004`.

## Strategy Logic
The strategy enters at most one long trade per day after the opening window when early-session evidence is favorable. For the selected variant:

- opening window: 30 bars
- minimum opening return: 20.0 points
- minimum ER: 0.25
- hold to close: True
- stop loss: 160.0 points
- take profit disabled: True

## Test Result
`LONG_OR_FLAT_FILTERED` test PnL is 991.0 points, Sharpe 0.911, max drawdown -724.0 points, trades 68, trades/day 0.636, average trade PnL 14.574, and profit factor 1.244.

It beats INTRADAY_LONG by 653.0 points and FLAT by 991.0 points.

## Slippage Robustness
At base slippage 2 points per side, test PnL is 991.0 points. At 10 points per side, test PnL is -1202.0 points.

## Monthly Concentration
Test monthly PnL is not evenly distributed: January -270 points, February -138, March +1455, April +58, May -356, and June +242. The positive test result is therefore strongly helped by March 2020. This should be reported as a robustness caveat.

## Interpretation
This is a post-analysis supplementary strategy, not the original pre-specified HYBRID strategy. It is useful because it demonstrates that the empirical diagnosis points toward long-or-flat directional filtering rather than mean-reversion or high-turnover regime switching. It should be reported with caution and framed as exploratory evidence requiring additional validation.
