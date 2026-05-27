# Report Summary

Mode used: `medium`

## Final Selected Parameters

### ORB

- `buffer_points`: `20`
- `er_threshold`: `0.35`
- `er_window`: `60`
- `extreme_action`: `close`
- `extreme_vol_quantile`: `0.9`
- `forced_exit_time`: `162800`
- `max_daily_loss`: `200`
- `max_trades`: `2`
- `min_std_threshold`: `5`
- `opening_window`: `30`
- `rolling_window`: `60`
- `rv_window`: `60`
- `stop_loss_points`: `120`
- `take_profit_points`: `180`
- `use_vwap`: `True`
- `z_entry`: `2.0`
- `z_exit`: `0.25`

### MR

- `buffer_points`: `10`
- `er_threshold`: `0.35`
- `er_window`: `60`
- `extreme_action`: `close`
- `extreme_vol_quantile`: `0.9`
- `forced_exit_time`: `162800`
- `max_daily_loss`: `200`
- `max_trades`: `3`
- `min_std_threshold`: `5`
- `opening_window`: `30`
- `rolling_window`: `120`
- `rv_window`: `60`
- `stop_loss_points`: `80`
- `take_profit_points`: `120`
- `use_vwap`: `True`
- `z_entry`: `2.5`
- `z_exit`: `0.25`

### HYBRID

- `buffer_points`: `10`
- `er_threshold`: `0.35`
- `er_window`: `60`
- `extreme_action`: `close`
- `extreme_vol_quantile`: `0.95`
- `extreme_vol_threshold`: `0.00545138283487605`
- `forced_exit_time`: `162800`
- `max_daily_loss`: `200`
- `max_trades`: `3`
- `min_std_threshold`: `5`
- `opening_window`: `30`
- `rolling_window`: `120`
- `rv_window`: `60`
- `stop_loss_points`: `80`
- `take_profit_points`: `120`
- `use_vwap`: `True`
- `z_entry`: `2.5`
- `z_exit`: `0.25`

## Train / Validation / Test Performance

| split | strategy | num_trades | cumulative_pnl_points | sharpe_ratio | max_drawdown_points | profit_factor |
| --- | --- | --- | --- | --- | --- | --- |
| train | BUY_AND_HOLD | 1 | 2975.0000 | 0.7201 | 0.0000 | inf |
| train | INTRADAY_LONG | 486 | -5313.0000 | -0.6986 | -9792.0000 | 0.8901 |
| train | FLAT | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| train | ORB | 701 | 3193.0000 | 0.6730 | -1430.0000 | 1.0838 |
| train | MR | 906 | -11323.0000 | -3.4372 | -11626.0000 | 0.6932 |
| train | HYBRID | 934 | -6622.0000 | -2.0473 | -7837.0000 | 0.8137 |
| val | BUY_AND_HOLD | 1 | -491.0000 | -1.4314 | -491.0000 | 0.0000 |
| val | INTRADAY_LONG | 123 | 2117.0000 | 1.1499 | -1639.0000 | 1.2149 |
| val | FLAT | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| val | ORB | 153 | 1295.0000 | 1.2532 | -1041.0000 | 1.1878 |
| val | MR | 213 | -2639.0000 | -3.8271 | -2892.0000 | 0.6333 |
| val | HYBRID | 214 | -1179.0000 | -2.0011 | -1665.0000 | 0.8246 |
| test | BUY_AND_HOLD | 1 | -3502.0000 | -1.5346 | -3502.0000 | 0.0000 |
| test | INTRADAY_LONG | 107 | 338.0000 | 0.1516 | -2647.0000 | 1.0254 |
| test | FLAT | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| test | ORB | 164 | -1954.0000 | -1.6867 | -3187.0000 | 0.8217 |
| test | MR | 229 | -3227.0000 | -3.5583 | -3276.0000 | 0.6919 |
| test | HYBRID | 215 | -3577.0000 | -5.1328 | -3689.0000 | 0.6186 |

## Out-of-Sample Winner

Best test strategy by Sharpe is `INTRADAY_LONG` with Sharpe `0.152` and PnL `338.0` points.

## Hybrid Comparison

- HYBRID beats ORB and MR on test Sharpe: `False`
- HYBRID beats the best benchmark on test Sharpe: `False`
- Best benchmark by test Sharpe: `INTRADAY_LONG`

## Slippage Robustness

- Base slippage `2` point HYBRID PnL: `-3577.0` points
- 10-point slippage HYBRID PnL: `-7127.0` points
- Interpretation: HYBRID is not slippage robust under the tested range.

## Key Interpretation

The current selected HYBRID strategy does not dominate the alternatives out of sample. This should be reported as an important empirical finding rather than tuned away on the test set.
