# Testing and Improving Regime-Adaptive Intraday Strategies for Hang Seng Index Futures

**Course:** STAT8020 Quantitative Strategies and Algorithmic Trading  
**Group members:** [Insert group member names]  
**Date:** [Insert submission date]  

---

# Abstract

This project develops and evaluates an intraday algorithmic trading framework for the one-month Hang Seng Index futures contract using the minute-level dataset `hi1_20170701_20200609.csv`. The main objective is to test whether a market-regime adaptive strategy can improve risk-adjusted performance relative to simple rule-based intraday strategies after realistic transaction costs, and then to examine whether post-analysis improvements can address the weaknesses found in the original strategy. The project compares an Opening Range Breakout strategy, a VWAP-based intraday mean-reversion strategy, a regime-adaptive Hybrid strategy, and benchmark strategies including Buy-and-Hold, Daily Intraday Long-only, and Always Flat.

The backtesting framework uses day-session data only, parses non-standard time stamps, removes duplicate bars, validates trading sessions, and applies next-bar execution with slippage and commission. Parameters are selected using training and validation periods, while the 2020 period is reserved for out-of-sample evaluation. The final medium-grid run shows that the Hybrid strategy does not generate robust out-of-sample alpha after costs. In the test period, the Hybrid strategy loses 3,577 index points with a Sharpe ratio of -5.133, while the Daily Intraday Long-only benchmark earns 338 points with a Sharpe ratio of 0.152. A supplementary post-analysis long-or-flat filter improves the test result to 991 points with a Sharpe ratio of 0.911, but this result is exploratory and should not be treated as the original pre-specified strategy. The main empirical conclusion is therefore cautious: the original Hybrid is not deployable, while the supplementary result suggests a promising direction for future validation.

---

# 1. Introduction

Hang Seng Index (HSI) futures are among the most actively traded equity index futures products in Hong Kong. They are used by institutional investors, proprietary traders, market makers, and hedgers to express views on Hong Kong equity market direction and volatility. The contract is attractive for intraday algorithmic trading because it offers high notional exposure, regular intraday liquidity, symmetric long and short trading, and clear mark-to-market profit and loss in index points.

Intraday trading is interesting because price dynamics within a trading day are affected by different forces from longer-horizon investing. Overnight information is incorporated near the market open, liquidity varies strongly across the day, and short-lived order imbalances may create temporary deviations from fair value. However, intraday strategies are also difficult to deploy profitably because expected price moves per trade are small relative to bid-ask spreads, slippage, and commission. A strategy that appears reasonable before costs may become unprofitable once realistic execution assumptions are applied.

This project starts from a market-regime hypothesis: a single rule is unlikely to work equally well in all intraday environments. An Opening Range Breakout (ORB) strategy may benefit when early-session price action leads to directional continuation, but it can suffer from false breakouts in range-bound markets. A mean-reversion strategy based on VWAP or rolling fair value may work when price deviations are temporary, but it can lose money during persistent trends. A realized-volatility filter may help avoid trading during extreme market conditions, especially during unstable periods such as the COVID-19 shock in early 2020.

The proposed solution is a regime-adaptive Hybrid strategy. The strategy combines:

- Opening Range Breakout for trend-like conditions.
- VWAP or rolling fair-value deviation for range-like conditions.
- Efficiency Ratio to distinguish trend from range.
- Realized volatility to identify extreme-risk periods.

The main research question is:

**Can regime-adaptive switching improve risk-adjusted intraday performance in HSI futures after realistic slippage and transaction costs?**

Because quantitative strategy development often proceeds through hypothesis testing, failure diagnosis, and controlled improvement, the project also includes a post-analysis exploration stage. This stage does not replace the original Hybrid strategy and is not presented as pre-specified evidence. Instead, it asks whether the empirical weaknesses of the Hybrid strategy suggest a simpler supplementary rule that can improve benchmark-relative performance.

The final empirical answer is cautious. The Hybrid framework is economically motivated and implemented with a realistic backtesting design, but the out-of-sample results do not show superior performance. This negative result is still informative because it demonstrates how hard it is for simple rule-based intraday strategies to overcome costs in liquid futures markets. The supplementary improvement stage then shows that a simpler long-or-flat directional filter is more promising in this sample, although it remains exploratory.

---

# 2. Data Description and Preprocessing

## 2.1 Dataset

The project uses the file `hi1_20170701_20200609.csv`, which contains minute-by-minute OHLCV bars for the one-month Hang Seng Index futures contract. The project proposal reports 582,100 raw rows, 806 unique dates, and an original date range from 2017-07-03 to 2020-06-09.

The actual raw columns are:

| Column | Description |
|---|---|
| `date` | Trading date in `YYYYMMDD` integer format |
| `time` | Bar time as an integer without leading zeros |
| `hi1_open` | One-minute open price |
| `hi1_high` | One-minute high price |
| `hi1_low` | One-minute low price |
| `hi1_close` | One-minute close price |
| `hi1_volume` | One-minute trading volume |

The time field requires special parsing. For example, `91400` means `09:14:00`, while `100` means `00:01:00`. Therefore, the time variable is converted to a six-character string using zero padding before constructing a timestamp.

After preprocessing, the internal schema is:

| Column | Type | Non-null count |
|---|---:|---:|
| `date` | int64 | 269,150 |
| `time` | int64 | 269,150 |
| `open` | float64 | 269,150 |
| `high` | float64 | 269,150 |
| `low` | float64 | 269,150 |
| `close` | float64 | 269,150 |
| `volume` | float64 | 269,150 |
| `datetime` | datetime64 | 269,150 |
| `is_illiquid` | bool | 269,150 |

Full schema details are saved in `outputs/tables/data_schema.csv`.

## 2.2 Day-Session Selection

The main strategy uses day-session data only:

- Morning session: 09:14-11:59.
- Afternoon session: 13:00-16:29.

The night session is excluded for three reasons. First, the project proposal found that night-session liquidity is much lower than day-session liquidity. Second, the night session crosses calendar dates after the extension of night trading hours, which complicates session definition and risk accounting. Third, the ORB design requires a clean and economically meaningful session start. The day session provides a clearer opening range and a more consistent intraday structure.

The 12:58 and 12:59 bars are excluded because they appear inconsistently in the raw data. Holding through lunch is allowed, but no signals are generated during the lunch break because no bars are present. This introduces a realistic lunch-break risk: stop-loss or take-profit conditions cannot be executed during the break and are only checked when data resumes.

## 2.3 Cleaning and Validation

The preprocessing pipeline:

1. Validates required columns.
2. Renames raw OHLCV columns to `open`, `high`, `low`, `close`, and `volume`.
3. Parses the datetime field using zero-padded times.
4. Sorts rows by datetime.
5. Removes duplicate `date` and `time` rows, keeping the last observation.
6. Filters to the day session.
7. Flags zero-volume bars.
8. Drops day sessions with fewer than 300 valid bars.

The cleaning summary is:

| Metric | Value |
|---|---:|
| Rows before cleaning | 582,100 |
| Rows after duplicate removal | 577,600 |
| Duplicate rows removed | 4,500 |
| Rows after day-session filter | 270,511 |
| Rows after final cleaning | 269,150 |
| Sessions before validation | 724 |
| Sessions after validation | 716 |
| Dropped short sessions | 8 |
| Zero-volume rows after day-session cleaning | 0 |

Full cleaning output is saved in `outputs/tables/data_cleaning_summary.csv`, and session bar counts are saved in `outputs/tables/session_counts.csv`.

## 2.4 Time Split

The project uses a chronological split:

| Period | Date range | Cleaned rows | Sessions | Purpose |
|---|---:|---:|---:|---|
| Training | 2017-07-03 to 2019-06-28 | 182,736 | 486 | Parameter estimation |
| Validation | 2019-07-01 to 2019-12-31 | 46,248 | 123 | Parameter selection |
| Test | 2020-01-02 to 2020-06-09 | 40,166 | 107 | Final out-of-sample evaluation |

The test period includes the COVID-19 market shock, making it a demanding out-of-sample stress period. Parameters are not tuned on the test period.

## 2.5 Data Figures

The following figures are generated from the cleaned data:

![Figure 1. HSI futures day-session price series](../outputs/figures/price_series.png)

![Figure 2. Minute return distribution](../outputs/figures/return_distribution.png)

![Figure 3. Average intraday volume pattern](../outputs/figures/intraday_volume_pattern.png)

Additional generated figures are referenced in the empirical results, robustness, and supplementary optimization sections.

---

# 3. Strategy Methodology

## 3.1 Opening Range Breakout Strategy

The Opening Range Breakout strategy is based on the idea that the first part of the trading day incorporates overnight information and establishes the initial high-low range of informed price discovery. If price breaks beyond this range after the opening window, the move may indicate directional continuation.

For a session with opening window length \(N\), define:

\[
OR_{high} = \max_{i=1,\ldots,N} High_i
\]

\[
OR_{low} = \min_{i=1,\ldots,N} Low_i
\]

The breakout levels are:

\[
Upper = OR_{high} + buffer
\]

\[
Lower = OR_{low} - buffer
\]

The entry rule after the opening window is:

\[
Signal_t =
\begin{cases}
1, & Close_t > Upper \text{ and current position is flat} \\
-1, & Close_t < Lower \text{ and current position is flat} \\
0, & \text{otherwise}
\end{cases}
\]

A signal generated at bar \(t\) is executed at the open of bar \(t+1\). The strategy supports both long and short positions. Stop-loss, take-profit, maximum trades per session, and forced session-end exit are applied.

The ORB strategy is suitable for trend-like sessions but can lose money in choppy markets because false breakouts lead to repeated entries and exits.

## 3.2 Intraday Fair-Value Deviation Mean Reversion

The mean-reversion strategy assumes that in range-bound conditions, large intraday deviations from fair value may reverse. The primary fair-value anchor is cumulative VWAP:

\[
VWAP_t = \frac{\sum_{i=1}^{t} Close_i \times Volume_i}{\sum_{i=1}^{t} Volume_i}
\]

If cumulative volume is zero, the implementation falls back to an expanding mean. A rolling mean fair value is also available as a robustness alternative.

The deviation from fair value is standardized using a rolling standard deviation:

\[
Z_t = \frac{Close_t - FairValue_t}{\sigma_t}
\]

where \(\sigma_t\) is the rolling standard deviation over the selected window. If \(\sigma_t\) is missing or below a minimum threshold, \(Z_t\) is set to zero to avoid unstable signals.

The entry rule is:

\[
Signal_t =
\begin{cases}
1, & Z_t < -z_{entry} \\
-1, & Z_t > z_{entry} \\
0, & \text{otherwise}
\end{cases}
\]

For existing long positions, the strategy exits when:

\[
Z_t \geq -z_{exit}
\]

For existing short positions, it exits when:

\[
Z_t \leq z_{exit}
\]

Stop-loss, take-profit, and forced session-end exits are also applied.

## 3.3 Regime-Adaptive Hybrid Strategy

The Hybrid strategy attempts to use ORB only when the market appears trend-like and mean reversion when the market appears range-bound. The regime classifier uses Efficiency Ratio and realized volatility.

The Efficiency Ratio is:

\[
ER_t =
\frac{|Close_t - Close_{t-L}|}
{\sum_{i=t-L+1}^{t} |Close_i - Close_{i-1}|}
\]

where \(L\) is the ER window. An ER near 1 indicates directional movement, while an ER near 0 indicates noisy or range-bound movement.

Realized volatility is:

\[
RV_t = \sqrt{\sum_{i=t-V+1}^{t} r_i^2}
\]

where:

\[
r_i = \frac{Close_i - Close_{i-1}}{Close_{i-1}}
\]

The extreme-volatility threshold is estimated from training sessions:

\[
RV^* = Quantile(RV_{train}, q)
\]

The regime classification rule is:

\[
Regime_t =
\begin{cases}
EXTREME, & RV_t > RV^* \\
TREND, & ER_t > ER_{threshold} \\
RANGE, & \text{otherwise}
\end{cases}
\]

The Hybrid switching logic is:

| Regime | Action |
|---|---|
| `TREND` | Use ORB signal after the opening window |
| `RANGE` | Use mean-reversion signal |
| `EXTREME` | Close or block trades according to the extreme-action setting |

The final selected Hybrid configuration uses `extreme_action = close`, meaning existing positions are closed when an extreme-volatility regime is detected.

## 3.4 Risk Management

The implemented risk management rules are:

| Rule | Description |
|---|---|
| Stop-loss | Exit when unrealized loss exceeds the point threshold |
| Take-profit | Exit when unrealized gain exceeds the point threshold |
| Maximum trades per session | Prevents excessive turnover in noisy sessions |
| Maximum daily loss | Blocks new entries after daily realized loss exceeds the limit |
| Minimum volume / illiquidity flag | Identifies illiquid bars |
| Forced session-end exit | Closes positions before the day session ends |
| No overnight position | Avoids overnight gap risk |
| Lunch-break handling | Allows holding through lunch, but no stops can be executed while the market is closed |

All strategies use one contract and do not scale positions.

## 3.5 Supplementary Long-or-Flat Filter

The original pre-specified strategy is the regime-adaptive Hybrid described above. After the original Hybrid result was evaluated, a supplementary post-analysis strategy was added to study whether the empirical diagnosis points toward a simpler improvement. This strategy is called `LONG_OR_FLAT_FILTERED`.

The motivation is that the original test results show two important patterns. First, the Daily Intraday Long-only benchmark is stronger than the active ORB, MR, and Hybrid strategies in the test period. Second, MR / RANGE trades and high turnover are major sources of loss. Therefore, the supplementary rule does not try to switch between long, short, and mean-reversion trades. It instead tries to filter the simple long-only benchmark:

\[
Signal_t =
\begin{cases}
1, & OpenRet_t \geq 20 \text{ points and } ER_t \geq 0.25 \\
0, & \text{otherwise}
\end{cases}
\]

where \(OpenRet_t\) is the price change from the first session open to the post-opening-window decision bar. The selected variant uses:

| Parameter | Value |
|---|---:|
| Opening window | 30 bars |
| Minimum opening return | 20 points |
| Minimum ER | 0.25 |
| Maximum trades per day | 1 |
| Stop-loss | 160 points |
| Take-profit | Disabled |
| Holding rule | Hold toward session close |

This rule is deliberately simpler than the original Hybrid. Its purpose is not to replace the original research hypothesis, but to test whether the failure diagnosis suggests a more robust benchmark-oriented improvement.

---

# 4. Backtesting Design

The backtest is event-driven at the one-minute bar level. Signals are generated using information available at bar \(t\), and trades are executed at the open of bar \(t+1\). This design avoids look-ahead bias because the execution price is not known at the time the signal is generated.

The strategy can be long, short, or flat. Entry and exit slippage are applied in the unfavorable direction:

- Long entry: next open plus slippage.
- Short entry: next open minus slippage.
- Long exit: next open minus slippage.
- Short exit: next open plus slippage.

The HSI futures contract multiplier is HKD 50 per point. The base case uses 2 points of slippage per side and 2 points of round-trip commission.

Trade PnL in points is:

\[
PnL_{points} = Direction \times (ExitPrice - EntryPrice) - Commission_{RT}
\]

where `Direction = 1` for long trades and `Direction = -1` for short trades. HKD PnL is:

\[
PnL_{HKD} = PnL_{points} \times 50
\]

Daily PnL is computed as the sum of all trade PnL closed on that day:

\[
DailyPnL_d = \sum_{j \in d} PnL_j
\]

The Sharpe ratio is annualized using 252 trading days:

\[
Sharpe =
\frac{Mean(DailyPnL)}
{Std(DailyPnL)}
\times \sqrt{252}
\]

Maximum drawdown is computed from the cumulative daily PnL curve:

\[
Drawdown_t = Equity_t - \max_{s \leq t} Equity_s
\]

The test period is used once for final evaluation and is not used for parameter tuning.

---

# 5. Parameter Optimization

The project uses staged optimization to reduce overfitting and computational burden.

1. Tune ORB parameters on the training period.
2. Tune mean-reversion parameters on the training period.
3. Validate top parameter sets on the validation period.
4. Fix ORB and MR parameters, then tune the regime classifier.
5. Evaluate the final selected parameters once on the test period.

The final run uses the medium grid rather than the full grid. Medium mode completed successfully in 1,550.41 seconds and provides a more reliable search than the initial fast mode. Full mode is not used because the current implementation recomputes features repeatedly, making larger grids inefficient without feature caching.

## 5.1 Final Selected Parameters

Full parameter output is saved in `outputs/tables/final_selected_params.csv`.

| Strategy | Key selected parameters |
|---|---|
| ORB | `opening_window=30`, `buffer_points=20`, `stop_loss_points=120`, `take_profit_points=180`, `max_trades=2` |
| MR | `rolling_window=120`, `z_entry=2.5`, `z_exit=0.25`, `stop_loss_points=80`, `take_profit_points=120`, `use_vwap=True` |
| HYBRID | `opening_window=30`, `buffer_points=10`, `rolling_window=120`, `z_entry=2.5`, `er_window=60`, `er_threshold=0.35`, `rv_window=60`, `extreme_vol_quantile=0.95`, `stop_loss_points=80`, `take_profit_points=120`, `max_trades=3` |

The selected Hybrid extreme-volatility threshold is 0.005451.

## 5.2 Validation Results

The top validation results show that ORB had positive validation performance, but MR and Hybrid did not. This is already a warning sign before the test period.

| Strategy | Best validation PnL | Best validation Sharpe | Trades | Profit factor |
|---|---:|---:|---:|---:|
| ORB | 1,295 | 1.253 | 153 | 1.188 |
| MR | -2,639 | -3.827 | 213 | 0.633 |
| HYBRID | -1,179 | -2.001 | 214 | 0.825 |

Top-five validation tables are saved in:

- `outputs/tables/orb_validation_top5.csv`
- `outputs/tables/mr_validation_top5.csv`
- `outputs/tables/regime_validation_top5.csv`

The parameter heatmaps are:

![Figure 4. ORB parameter heatmap](../outputs/figures/orb_param_heatmap.png)

![Figure 5. Mean-reversion parameter heatmap](../outputs/figures/mr_param_heatmap.png)

![Figure 6. Regime parameter heatmap](../outputs/figures/regime_param_heatmap.png)

## 5.3 Supplementary Exploration Protocol

The supplementary optimization is stored separately under `strategy_optimization_exploration/` so that exploratory outputs do not overwrite the original project results. The exploration is explicitly post-analysis because it was motivated by the original Hybrid test failure.

The supplementary search follows a restrained protocol:

1. Use the original train / validation / test split.
2. Use train and validation to screen candidate improvement variants.
3. Reserve the test split for final comparison of validation-screened candidates.
4. Save all exploratory scripts, tables, figures, logs, and notes separately.
5. Report the result as exploratory rather than as the original pre-specified strategy.

The candidate families include ORB-filtered Hybrid variants, low-turnover Hybrid variants, long-only ORB variants, ORB-to-close variants, extreme-trend-following variants, and long-or-flat directional filters. The benchmark-beating candidate, `LONG_OR_FLAT_FILTERED` with params id `long_or_flat_filtered_004`, ranked third by validation score before test evaluation. Its final report-ready outputs use the prefix `long_or_flat_final_` under `strategy_optimization_exploration/outputs/`.

---

# 6. Empirical Results

The final evaluation compares six strategies:

1. Full-period Buy-and-Hold.
2. Daily Intraday Long-only.
3. Always Flat.
4. Pure ORB.
5. Pure Mean Reversion.
6. Regime-Adaptive Hybrid.

Full results are available in:

- `outputs/tables/performance_summary.csv`
- `outputs/tables/risk_metrics.csv`
- `outputs/tables/trade_statistics.csv`

## 6.1 Training and Validation Performance

In training, ORB performs best among the active rule-based strategies, earning 3,193 points with a Sharpe ratio of 0.673. However, MR loses 11,323 points and Hybrid loses 6,622 points. In validation, ORB remains positive, earning 1,295 points with a Sharpe ratio of 1.253, while MR and Hybrid remain negative.

This suggests that the ORB component has some in-sample and validation strength, but the mean-reversion and regime-switching components do not add reliable value in the current specification.

## 6.2 Out-of-Sample Test Results

The out-of-sample results are:

| Strategy | Trades | PnL points | PnL HKD | Sharpe | Max drawdown | Win rate | Profit factor |
|---|---:|---:|---:|---:|---:|---:|---:|
| Buy-and-Hold | 1 | -3,502 | -175,100 | -1.535 | -3,502 | 0.000 | 0.000 |
| Intraday Long-only | 107 | 338 | 16,900 | 0.152 | -2,647 | 0.523 | 1.025 |
| Flat | 0 | 0 | 0 | 0.000 | 0 | 0.000 | 0.000 |
| ORB | 164 | -1,954 | -97,700 | -1.687 | -3,187 | 0.427 | 0.822 |
| MR | 229 | -3,227 | -161,350 | -3.558 | -3,276 | 0.424 | 0.692 |
| HYBRID | 215 | -3,577 | -178,850 | -5.133 | -3,689 | 0.405 | 0.619 |

The Daily Intraday Long-only benchmark is the best test strategy by Sharpe ratio and cumulative PnL, although its Sharpe ratio of 0.152 is weak. The Flat benchmark also beats the active rule-based strategies because ORB, MR, and Hybrid all lose money after costs.

The Hybrid strategy does not beat ORB or MR in the test period. It also does not beat the Intraday Long-only benchmark. Therefore, the final empirical evidence does not support deploying the current Hybrid strategy in live trading.

![Figure 7. Cumulative PnL comparison](../outputs/figures/cumulative_pnl_comparison.png)

![Figure 8. Out-of-sample cumulative PnL comparison](../outputs/figures/out_of_sample_cumulative_pnl.png)

![Figure 9. Hybrid drawdown curve](../outputs/figures/hybrid_drawdown.png)

![Figure 10. Hybrid trade PnL distribution](../outputs/figures/hybrid_trade_distribution.png)

## 6.3 Trade Characteristics

The Hybrid strategy makes 215 trades in the test period, or approximately 2.01 trades per day. Its average trade PnL is -16.64 points, with an average winner of 66.68 points and an average loser of -73.27 points. The win rate is 40.47%, and the profit factor is 0.619.

This means the strategy loses because both the win rate and payoff ratio are insufficient after costs. The stop-loss and take-profit system controls single-trade losses, with a maximum single-trade loss of -128 points for the test Hybrid results, but the repeated small negative expectancy accumulates into a large drawdown.

The main Hybrid exit reasons in the test period are:

| Exit reason | Number of exits |
|---|---:|
| Stop-loss | 88 |
| Session end | 55 |
| Mean-reversion exit | 42 |
| Take-profit | 17 |
| Regime extreme | 13 |

The high number of stop-loss exits relative to take-profit exits indicates that the selected Hybrid rules were not able to identify enough favorable intraday opportunities during the test period.

## 6.4 Interpretation of Negative Out-of-Sample Results

The negative result should not be interpreted as a failure of the project. It is an empirical finding: the current rule-based regime-switching strategy does not produce robust out-of-sample alpha after realistic costs.

Several explanations are plausible:

1. **Transaction costs and slippage are large relative to intraday alpha.** The strategy trades frequently, and the average edge per signal is not enough to overcome execution costs.
2. **The regime classifier is simple.** ER and realized volatility may not fully distinguish profitable trend and range regimes.
3. **The COVID-19 test period is difficult.** The out-of-sample period contains abrupt transitions and unusually high volatility, which can hurt both breakout and mean-reversion rules.
4. **ORB and MR can both fail in fast-changing markets.** Breakout entries may become false breakouts, while mean-reversion entries may be overwhelmed by persistent directional movement.
5. **The Intraday Long-only benchmark may benefit from market drift.** Even a weak positive drift can outperform more complex strategies when the latter have high turnover.
6. **Medium-grid optimization is broader than fast mode but not exhaustive.** Larger grids or walk-forward optimization may produce different results, but test-set tuning should be avoided.

The empirical results do not support immediate live deployment of the current Hybrid strategy. However, the result is useful because it demonstrates the practical difficulty of converting intuitive intraday trading logic into a robust after-cost strategy.

---

# 7. Slippage and Transaction Cost Analysis

The base case uses 2 points of slippage per side and 2 points of round-trip commission. Slippage sensitivity is tested at 0, 1, 2, 5, and 10 points per side using the final Hybrid parameters.

The results are:

| Slippage per side | Hybrid PnL points | Hybrid PnL HKD | Sharpe | Trades | Profit factor |
|---:|---:|---:|---:|---:|---:|
| 0 | -2,669 | -133,450 | -4.002 | 214 | 0.698 |
| 1 | -3,143 | -157,150 | -4.553 | 214 | 0.656 |
| 2 | -3,577 | -178,850 | -5.133 | 215 | 0.619 |
| 5 | -4,601 | -230,050 | -6.604 | 214 | 0.533 |
| 10 | -7,127 | -356,350 | -9.785 | 219 | 0.376 |

The strategy is negative even at zero slippage, which suggests the gross signal itself is weak in the test period. Performance deteriorates further as slippage rises. This means the current signals are too small relative to execution costs. Since minute-level strategies often target short holding periods and small price moves, this cost sensitivity is economically important.

![Figure 11. Slippage sensitivity](../outputs/figures/slippage_sensitivity.png)

![Figure 12. Sharpe ratio versus slippage](../outputs/figures/sharpe_vs_slippage.png)

The slippage analysis supports a conservative conclusion: the strategy is not robust enough for live deployment without substantial improvement to signal quality, trade filtering, or execution design.

---

# 8. Robustness and Market Regime Analysis

## 8.1 Monthly Stability

Monthly Hybrid PnL is saved in `outputs/tables/monthly_pnl.csv`. In the test period, monthly Hybrid PnL is:

| Month | PnL points | PnL HKD |
|---|---:|---:|
| 2020-01 | -1,277 | -63,850 |
| 2020-02 | 9 | 450 |
| 2020-03 | -250 | -12,500 |
| 2020-04 | -919 | -45,950 |
| 2020-05 | -791 | -39,550 |
| 2020-06 | -349 | -17,450 |

Losses are not concentrated in only one month. The strategy is slightly positive in February 2020, but it loses in January, March, April, May, and June. This indicates a lack of stability across the out-of-sample months.

![Figure 13. Monthly PnL heatmap](../outputs/figures/monthly_pnl_heatmap.png)

## 8.2 Regime Performance

Regime performance is saved in `outputs/tables/regime_performance.csv`.

| Split | Regime | Trades | PnL points | Win rate | Average trade PnL |
|---|---|---:|---:|---:|---:|
| Train | RANGE | 776 | -8,690 | 0.477 | -11.20 |
| Train | TREND | 158 | 2,068 | 0.506 | 13.09 |
| Validation | RANGE | 175 | -1,712 | 0.491 | -9.78 |
| Validation | TREND | 39 | 533 | 0.487 | 13.67 |
| Test | RANGE | 176 | -2,835 | 0.420 | -16.11 |
| Test | TREND | 39 | -742 | 0.333 | -19.03 |

The regime analysis is informative. In training and validation, TREND entries are profitable on average, while RANGE entries are negative. In the test period, both RANGE and TREND entries are negative. This suggests that the current ER/RV classifier may not be sufficient to identify robust profitable trading regimes in the COVID-era out-of-sample period.

The result also suggests that the Hybrid strategy did not stabilize performance relative to the pure strategies. Although regime switching is a reasonable design, the implemented classifier and signal rules do not create a reliable edge in the final test.

---

# 9. Implementation Difficulty and Real-Time Trading Issues

Even if a backtest were profitable, real-time deployment of an HSI futures intraday strategy would introduce several additional challenges.

First, data quality and latency are critical. The strategy uses one-minute bars and assumes signals can be computed immediately at the end of each bar. In live trading, delayed data, missing bars, or incorrect timestamps could lead to wrong signals.

Second, execution prices in the backtest are based on next-bar open plus slippage. Actual execution depends on market depth, bid-ask spreads, queue position, and order type. Market orders may suffer larger slippage during volatile periods. Limit orders may reduce slippage but increase non-fill risk.

Third, lunch-break risk is important for HSI futures. The project allows holding through lunch, but stop-loss and take-profit orders cannot be evaluated from minute bars during the no-data lunch gap. A large price move during the break may result in a realized loss larger than the nominal stop-loss.

Fourth, HSI futures require sufficient capital and margin. One index point is HKD 50 per contract, so drawdowns of several thousand points correspond to large HKD fluctuations. Risk limits must be set relative to account capital and exchange margin requirements.

Fifth, contract rollover must be handled carefully. The dataset uses the one-month futures contract, but live implementation requires rules for rolling exposure before expiry and handling potential liquidity migration from the front contract to the next contract.

Sixth, system failure is a practical risk. A production system would need monitoring, fail-safe order cancellation, position reconciliation, and emergency flat-position controls.

Finally, parameter instability is a major concern. The strategy parameters selected from 2017-2019 do not perform well in 2020. A live strategy would require walk-forward monitoring, retraining rules, and conservative shutdown criteria when live performance deviates from historical expectations.

---

# 10. Discussion

This project shows that a complete quantitative trading workflow can be built around an economically motivated idea, even when the final trading result is negative. The Hybrid strategy is appealing because it tries to avoid the weakness of single-rule strategies: ORB is intended for directional markets, mean reversion is intended for range-bound markets, and realized volatility is intended to reduce exposure during extreme conditions.

The empirical results do not support the original hypothesis that this particular regime-adaptive switching rule improves out-of-sample performance. ORB alone has positive training and validation performance but fails in the test period. MR is weak in training, validation, and test. Hybrid reduces some losses relative to MR in validation but does not preserve performance in the test period.

The strengths of the project are:

- A complete data pipeline with explicit time parsing and session validation.
- A realistic execution model using signal-at-\(t\), execute-at-\(t+1\).
- Long and short trading with point-based HSI futures PnL.
- Transaction cost and slippage modeling.
- Separate training, validation, and test periods.
- Benchmark comparison against Buy-and-Hold, Intraday Long-only, and Flat.
- Slippage sensitivity, risk metrics, trade statistics, and regime analysis.

The main limitations are:

- The regime classifier is rule-based and uses only ER and realized volatility.
- No bid-ask spread, order book, or queue-position data are available.
- The strategy uses one instrument only.
- The medium grid is broader than fast mode but still not the full proposal grid.
- Feature caching is not implemented, making full-grid optimization slow.
- Buy-and-Hold risk metrics are less comparable because the implementation records it as one holding-period trade rather than a fully marked daily strategy.
- The test period is stressful and includes COVID-era volatility, which may not represent normal market conditions.

Future improvements include reducing turnover, adding a no-trade zone, using adaptive thresholds, applying walk-forward re-optimization, adding spread-aware execution assumptions, incorporating additional market state features, and testing alternative regime classifiers.

---

# 11. Strategy Improvement and Exploratory Optimization

The original HYBRID strategy remains the main pre-specified strategy in this project. Its negative out-of-sample result is not replaced by the exploratory work. After observing that RANGE / mean-reversion trades were a major drag, a separate post-analysis optimization was performed under `strategy_optimization_exploration/`.

The first improvement direction removed RANGE / MR trades and reduced turnover. It kept the regime classifier but changed the action mapping so that TREND still used ORB, while RANGE stayed flat instead of using mean reversion. A filtered version also added two-bar breakout confirmation, volume confirmation, and a training-only opening-range-width filter.

The first-stage supplementary results are:

| Strategy | Trades | PnL points | Sharpe | Max drawdown | Profit factor | Avg trade PnL |
|---|---:|---:|---:|---:|---:|---:|
| HYBRID original | 215 | -3,577 | -5.133 | -3,689 | 0.619 | -16.637 |
| ORB-filtered Hybrid basic | 60 | -335 | -0.984 | -702 | 0.854 | -5.583 |
| ORB-filtered Hybrid filtered | 35 | -142 | -0.523 | -425 | 0.904 | -4.057 |
| Intraday Long-only | 107 | 338 | 0.152 | -2,647 | 1.025 | 3.159 |
| Flat | 0 | 0 | 0.000 | 0 | 0.000 | 0.000 |

This first stage is important because it validates the diagnosis: removing RANGE / MR trades and reducing turnover substantially reduces losses. However, both ORB-filtered variants remain negative and still fail to beat the Flat or Intraday Long-only benchmarks. The second-stage exploration therefore changed the objective more directly: instead of trying to trade both trend and range regimes, it tested directionally filtered long-only variants designed to compete with the Intraday Long-only benchmark. These variants included `LONG_OR_FLAT_FILTERED`, `LONG_ONLY_ORB`, `ORB_TO_CLOSE`, and `EXTREME_TREND_FOLLOWING`, in addition to the earlier ORB-filtered Hybrid and low-turnover variants.

Candidate selection still used train and validation data before test evaluation. The highest validation-score candidate was `EXTREME_TREND_FOLLOWING`, with validation Sharpe 2.139, but it did not generalize to test and lost 1,138 points. This shows that validation performance alone was not fully robust.

Among the validation-screened candidates, the strongest test result came from `LONG_OR_FLAT_FILTERED` with params id `long_or_flat_filtered_004`. It ranked third on validation, with validation PnL 1,078 points and validation Sharpe 1.342. Its rule is simple: after the opening window, enter at most one long trade only if early-session evidence is favorable; otherwise remain flat. For the selected variant, the opening return must be at least 20 points and the Efficiency Ratio must be at least 0.25. The trade is then held toward the close with a 160-point stop-loss and no take-profit.

The test-period comparison is:

| Strategy | Trades | PnL points | Sharpe | Max drawdown | Profit factor | Avg trade PnL |
|---|---:|---:|---:|---:|---:|---:|
| `LONG_OR_FLAT_FILTERED` | 68 | 991 | 0.911 | -724 | 1.244 | 14.574 |
| HYBRID | 215 | -3,577 | -5.133 | -3,689 | 0.619 | -16.637 |
| ORB | 164 | -1,954 | -1.687 | -3,187 | 0.822 | -11.915 |
| MR | 229 | -3,227 | -3.558 | -3,276 | 0.692 | -14.092 |
| Intraday Long-only | 107 | 338 | 0.152 | -2,647 | 1.025 | 3.159 |
| Flat | 0 | 0 | 0.000 | 0 | 0.000 | 0.000 |

The supplementary strategy therefore improves test PnL by 4,568 points relative to the original HYBRID, 2,945 points relative to ORB, 653 points relative to Intraday Long-only, and 991 points relative to Flat. It also reduces turnover relative to the original HYBRID, from 215 test trades to 68 test trades.

The economic interpretation is that a long-or-flat filter is more suitable than the original regime-switching HYBRID in this sample. Instead of trying to profit from both trend and range regimes, it only takes long exposure when early-session direction is favorable and otherwise stays flat. This removes harmful short / MR exposure while preserving part of the positive long-only benchmark behavior.

The robustness evidence is mixed. At the base slippage assumption of 2 points per side, the strategy earns 991 points. It remains positive at 5 points per side, with 480 points of test PnL, but becomes negative at 10 points per side, with -1,202 points. Monthly results are also concentrated: test PnL is -270 points in January 2020, -138 in February, +1,455 in March, +58 in April, -356 in May, and +242 in June. The positive test result is therefore strongly helped by March 2020.

The supplementary figures and tables are saved under `strategy_optimization_exploration/outputs/`. Key files include `long_or_flat_final_performance_summary.csv`, `long_or_flat_final_trade_statistics.csv`, `long_or_flat_final_monthly_pnl.csv`, `long_or_flat_final_slippage_sensitivity.csv`, and the final cumulative PnL and drawdown figures.

Because this is post-analysis exploratory work, the benchmark-beating result should be interpreted as a promising supplementary improvement rather than confirmatory evidence of a deployable strategy. A fresh holdout period, walk-forward validation, or additional years of data would be required before making stronger claims.


# 12. Conclusion

The final empirical evidence does not support deploying the original Hybrid strategy directly in live trading. Although the strategy is economically motivated and carefully backtested, its out-of-sample performance does not exceed the intraday benchmark after realistic transaction costs. In the test period, the Hybrid strategy loses 3,577 points with a Sharpe ratio of -5.133, while the Daily Intraday Long-only benchmark earns 338 points with a Sharpe ratio of 0.152.

A supplementary post-analysis strategy, `LONG_OR_FLAT_FILTERED`, improves the test result and earns 991 points with a Sharpe ratio of 0.911. It beats both the Intraday Long-only and Flat benchmarks in this sample. However, this result was developed after diagnosing the original Hybrid failure, and it is sensitive to higher slippage and concentrated in March 2020. It should therefore be treated as exploratory evidence rather than confirmed live-trading alpha.

The recommended conclusion is therefore two-part. First, the original pre-specified Hybrid does not work out of sample and should not be recommended for live deployment. Second, the research framework is valuable because it identifies why the original strategy failed and points toward a more promising long-or-flat filtering direction. Future research should focus on walk-forward validation, fresh out-of-sample testing, more realistic spread and execution modeling, and additional market-state features before any real deployment.

---

# References

The following references are based on the project proposal and course project context. The group should verify exact bibliographic formatting before final submission.

- Andersen, T. G., and Bollerslev, T. Realized volatility research on high-frequency financial data.
- Chan, E. P. Quantitative trading and algorithmic trading references used for trading-system design.
- Crabel, T. Opening range breakout trading concept.
- De Bondt, W. F. M., and Thaler, R. Research on overreaction and return reversal.
- Hong Kong Exchanges and Clearing Limited (HKEX). HSI futures contract specifications and trading-hour information.
- Jegadeesh, N., and Titman, S. Momentum and return continuation literature.

---

# Appendix A. Parameter Grids

## A.1 Medium-Mode Grids Used for Final Output

ORB medium grid:

- `opening_window`: 30, 60
- `buffer_points`: 5, 10, 20
- `stop_loss_points`: 50, 80, 120
- `take_profit_points`: 80, 120, 180
- `max_trades`: 2, 3

MR medium grid:

- `rolling_window`: 30, 60, 120
- `z_entry`: 1.5, 2.0, 2.5
- `z_exit`: 0.25
- `stop_loss_points`: 50, 80
- `take_profit_points`: 80, 120
- `use_vwap`: True

Regime medium grid:

- `er_window`: 60, 120
- `er_threshold`: 0.35, 0.45
- `rv_window`: 60, 120
- `extreme_vol_quantile`: 0.90, 0.95
- `extreme_action`: close, block_only

The generated grid files contain 108 ORB candidates, 36 MR candidates, and 32 regime candidates:

- `outputs/tables/orb_train_grid.csv`
- `outputs/tables/mr_train_grid.csv`
- `outputs/tables/regime_train_grid.csv`

## A.2 Full Proposal Grid Not Used for Final Run

The full grid is larger and was not used for final output because the current implementation recomputes session features repeatedly. A future version should add feature caching before running the full grid.

---

# Appendix B. Backtesting Pseudo-Code

```python
for date, session in sessions:
    compute features for session
    position = 0
    for each bar t:
        classify regime using ER and RV
        if position != 0:
            check stop-loss, take-profit, session-end, regime-extreme, and MR exit
            execute exit at next bar open when triggered
        if position == 0:
            check max trades and max daily loss
            generate ORB, MR, or Hybrid signal
            execute entry at next bar open
    force close remaining position at the final available bar
```

---

# Appendix C. Reproducibility Note

The project can be reproduced from the repository root with:

```bash
python -m py_compile src/*.py main.py
python main.py --medium
```

The latest successful medium run completed in 1,550.41 seconds and regenerated the final output tables, logs, figures, and report summary.

The supplementary exploration can be reproduced with:

```bash
python -m py_compile strategy_optimization_exploration/scripts/*.py
python strategy_optimization_exploration/scripts/run_exploration.py --fast
python strategy_optimization_exploration/scripts/run_long_or_flat_final.py
```

The original pre-specified project code is under `src/` and `main.py`. The post-analysis exploratory code is isolated under `strategy_optimization_exploration/scripts/`.

Key output locations:

- Tables: `outputs/tables/`
- Figures: `outputs/figures/`
- Trade logs: `outputs/logs/`
- Report summary: `outputs/tables/report_summary.md`
- Supplementary exploration tables: `strategy_optimization_exploration/outputs/tables/`
- Supplementary exploration figures: `strategy_optimization_exploration/outputs/figures/`
- Supplementary notes: `strategy_optimization_exploration/notes/`
