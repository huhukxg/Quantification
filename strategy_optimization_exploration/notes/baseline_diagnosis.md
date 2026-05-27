# Baseline Diagnosis

This note is based on the original medium-mode output tables under `outputs/tables/`. It is a diagnosis of the pre-specified project result, not a replacement for it.

## Original HYBRID Test Result
The original HYBRID strategy loses 3577 index points on the test split, with Sharpe -5.133, 215 trades, profit factor 0.619, and average trade PnL -16.637 points.

## ORB Test Result
ORB loses 1954 points on the test split, with Sharpe -1.687, 164 trades, profit factor 0.822, and average trade PnL -11.915 points.

## MR Test Result
MR loses 3227 points on the test split, with Sharpe -3.558, 229 trades, profit factor 0.692, and average trade PnL -14.092 points.

## INTRADAY_LONG Benchmark Result
INTRADAY_LONG gains 338 points on the test split, with Sharpe 0.152 and 107 trades.

## FLAT Benchmark Result
FLAT has zero PnL, zero trades, and zero drawdown.

## Underperformance Source
The regime breakdown shows that RANGE trades are a major source of underperformance. In test, HYBRID RANGE entries lose 2835 points across 176 trades. TREND entries also lose 742 points across 39 trades in test, but the larger loss and larger turnover come from RANGE.

## Why MR / RANGE Appears Weak
MR has negative train, validation, and test performance. Its average trade PnL is negative in all splits, and its test trades_per_day is higher than ORB. This suggests that the fair-value deviation signal is not strong enough to overcome execution costs and false reversals.

## Why ORB Is Still Most Promising
ORB is positive in train and validation and is less negative than HYBRID and MR in test. It has a better validation Sharpe than INTRADAY_LONG and materially better profit factor than MR. The issue is robustness under the 2020 test regime, not complete absence of signal in earlier periods.

## Costs And Turnover
The backtest charges adverse slippage on entry and exit plus round-trip commission. With many short-horizon trades, small gross edges can be overwhelmed. HYBRID trades more than INTRADAY_LONG and FLAT, so a negative average trade PnL compounds quickly.

## Zero-Slippage Interpretation
The original slippage sensitivity table shows HYBRID remains negative even at zero slippage, with test PnL -2669 points. This suggests the issue is not only transaction costs; the gross signal is weak out of sample.

