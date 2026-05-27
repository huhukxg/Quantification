# Strategy Ideas

All variants in this folder are post-analysis exploratory improvements. The original HYBRID strategy remains the pre-specified main result.

## A. ORB_FILTERED_HYBRID
Motivation: MR / RANGE trades are weak.

Variants:
- A1 `ORB_FILTERED_HYBRID_BASIC`: TREND maps to ORB; RANGE and EXTREME stay flat or close.
- A2 `ORB_FILTERED_HYBRID_CONFIRM`: A1 plus two-bar breakout and/or volume confirmation.
- A3 `ORB_FILTERED_HYBRID_STRICT_TREND`: A1 plus an ER no-trade margin near the trend threshold.

## B. ORB_ONLY_IMPROVED
Motivation: ORB has the strongest train/validation profile among the original active strategies.

Variants:
- B1 `ORB_ONLY_CONFIRM`: pure ORB with two-bar confirmation.
- B2 `ORB_ONLY_VOLUME`: pure ORB with volume confirmation.
- B3 `ORB_ONLY_RANGE_FILTER`: pure ORB with opening-range width filter.
- B4 `ORB_ONLY_LOW_TURNOVER`: pure ORB with one trade per session, cooldown, and no re-entry after stop-loss.

## C. STRICT_MR_ONLY / STRICT_MR_HYBRID
Motivation: MR is weak overall but may be less harmful under stricter range and reversal conditions.

Variants:
- C1 `STRICT_MR_ONLY`: MR only with very low ER, low RV, and reversal confirmation.
- C2 `STRICT_MR_HYBRID`: TREND maps to ORB; RANGE maps to strict MR only when the strict conditions hold.

## D. LOW_TURNOVER_HYBRID
Motivation: The original HYBRID trades often and has negative average trade PnL.

Variants:
- D1 `LOW_TURNOVER_HYBRID_1TRADE`: max one trade per session.
- D2 `LOW_TURNOVER_HYBRID_COOLDOWN`: wait after stop-loss before allowing new entries.
- D3 `LOW_TURNOVER_HYBRID_NO_BOUNDARY`: stay flat when ER is close to the regime threshold.

## E. COST_AWARE_SELECTION
Selection uses train and validation only. Validation score is:

```text
score = Sharpe - 0.25 * abs(max_drawdown_points / 1000) - 0.25 * trades_per_day + 0.25 * min(profit_factor, 3)
```

The test split is reserved for final comparison of validation-selected variants.

## F. DIRECTIONAL_LONG_FILTERS
Motivation: INTRADAY_LONG is the strongest original test benchmark, so a more direct improvement is to keep long exposure only on days with favorable early-session evidence and stay flat otherwise.

Variants:
- `LONG_OR_FLAT_FILTERED`: enter one long trade only when opening-window evidence is positive; otherwise stay flat.
- `LONG_ONLY_ORB`: trade only upward ORB breakouts and ignore short breakouts.
- `ORB_TO_CLOSE`: enter on upward ORB breakout and hold to close, using a wide stop and no take-profit.
- `EXTREME_TREND_FOLLOWING`: allow long trend-following entries during extreme volatility only when early evidence is positive.

The strongest second-stage validation-screened candidate was `LONG_OR_FLAT_FILTERED`, which ranked #3 on validation and beat INTRADAY_LONG and FLAT on test. This remains post-analysis exploratory evidence.
