# STAT8020 Revised Project Proposal (v2)

## Market-Regime Adaptive Intraday Trading Strategy for Hang Seng Index Futures

**Based on actual dataset inspection of `hi1_20170701_20200609.csv`**

---

# PART 1: Dataset Inspection Summary

## 1.1 Actual Dataset Schema

| Column | Type | Description |
|--------|------|-------------|
| `date` | int | Trading date, format YYYYMMDD (e.g., 20170703) |
| `time` | int | Time, format HMMSS or HHMMSS without leading zero (e.g., 91400 = 09:14:00, 0 = 00:00:00) |
| `hi1_open` | float | 1-minute bar open price |
| `hi1_high` | float | 1-minute bar high price |
| `hi1_low` | float | 1-minute bar low price |
| `hi1_close` | float | 1-minute bar close price |
| `hi1_volume` | float | 1-minute bar volume (number of contracts) |

## 1.2 Key Facts

| Item | Value |
|------|-------|
| Total rows | 582,100 |
| Unique dates | 806 |
| Date range | 2017-07-03 to 2020-06-09 |
| Day session bars per day | ~376 (166 morning + 210 afternoon) |
| OHLC available | Yes, all four |
| Volume available | Yes, reliable (avg 404 contracts/min in day session) |
| Missing values | 0 in all columns |
| Zero volume bars | 30 (negligible) |
| Duplicate timestamps | 4,500 (12 dates in Feb–Mar 2020; same OHLC, slightly different volume) |
| Abnormal intraday returns (>2%/min) | 0 |
| Price range | 20,981 – 33,450 |
| Mean price | ~27,821 |
| Minute return std | 0.000498 (~14 index points at mean price) |
| Full-day high-low range | Median 345, mean 382 points |
| Opening 30-min range (high-low) | Median 169, mean 185 points |

## 1.3 Session Structure (Confirmed from Data)

```
MORNING SESSION:   09:14 – 11:59  (bars 91400 to 115900)  = 166 bars
LUNCH BREAK:       12:00 – 12:57  (no data)               = ~58 min gap
AFTERNOON SESSION: 12:58/13:00 – 16:29  (bars 125800/130000 to 162900) = ~210 bars
NIGHT SESSION:     17:15 – 23:59  (bars 171500 to 235900)
                   00:00 – 02:59  (bars 0 to 25900, on NEXT date, from Sep 2018)
```

**Important findings:**
- The first bar of the day session is at 09:14 (not 09:15) — this is the bar for the first trading minute.
- Lunch break confirmed: last morning bar = 11:59, first afternoon bar = 12:58 or 13:00.
- A few dates (holidays/typhoon days) have extra bars during 12:00–12:30 (rare; ~7 in 2017, ~105 in 2018).
- Night session is 7× less liquid than day session (avg 57 vs 404 contracts/min).
- Night session was extended from 23:45 to 03:00 starting Sep 2018.
- Duplicate timestamps occur only on 12 dates during COVID crash (Feb 28 – Mar 16, 2020). Prices are identical; only volume differs by 1. Solution: keep last row.

## 1.4 Feasibility Assessment

| Original Proposal Element | Feasible? | Notes |
|---------------------------|-----------|-------|
| Opening Range Breakout using High/Low | **Yes** | hi1_high and hi1_low are available per minute |
| VWAP computation | **Yes** | Volume is available and reliable in day session |
| Z-score from rolling price | **Yes** | Close price available |
| Realized volatility from returns | **Yes** | Minute returns computable |
| Trend strength / Efficiency Ratio | **Yes** | Close prices available |
| Long/Short positions | **Yes** | HSI futures allow symmetric trading |
| Forced session-end exit | **Yes** | Session boundaries clearly identifiable |
| Day-session-only focus | **Recommended** | Night session too illiquid; clearer signal logic |
| Stop-loss in index points | **Yes** | Price in index points; typical day range 345 pts |

---

# PART 2: Problems Found in Original Proposal

| # | Problem | Fix |
|---|---------|-----|
| 1 | Breakout buffer as fraction (0.0005–0.0015) too small in points | Use point-based buffer: {0, 5, 10, 20} |
| 2 | Stop-loss as percentage (0.2%–0.8%) is ambiguous | Use point-based: {30, 50, 80, 120} |
| 3 | Assumed volume might not exist | Volume IS available; use real VWAP |
| 4 | Trend strength TS_t = |ΔP|/RV unstable when RV→0 | Replace with Efficiency Ratio |
| 5 | Assumed lunch break might not exist in data | Confirmed: 58-min gap (12:00–12:57) naturally handled |
| 6 | Unclear handling of morning vs afternoon sub-sessions | Define explicit sub-session logic |
| 7 | Column names assumed generic (open, high, low, close) | Actual: hi1_open, hi1_high, hi1_low, hi1_close |
| 8 | Date/time parsing assumed standard format | Time has no leading zeros; needs zero-padding |
| 9 | Full Cartesian grid search infeasible (too many combos) | Use staged optimization |
| 10 | Duplicate rows not addressed | 4,500 duplicates on 12 dates; keep last |
| 11 | Night session complexity underestimated | Exclude night session from main strategy |
| 12 | Parameter selection criterion unclear | Use Sharpe on validation period |

---

# PART 3: Revised Strategy Specification

## 3.1 Trading Session Design

**Decision: Use day session only (09:14–16:29), split into morning and afternoon.**

Rationale:
- Day session has 7× more volume than night session.
- Opening range logic requires a well-defined session start.
- Night session liquidity too low for reliable execution.
- Simpler implementation; avoids cross-date night session complexity.

**Sub-session handling:**
- Morning: 09:14–11:59 (166 bars)
- Afternoon: 13:00–16:29 (210 bars; use 13:00 as start since 12:58/12:59 appear inconsistently)
- Lunch break: Naturally absent from data (no bars 12:00–12:57).

**Position handling across lunch:**
- Allow holding through lunch break. No signals generated during the break.
- Reason: Forcing exit at 11:59 and re-entry at 13:00 would incur unnecessary transaction costs.
- **Lunch-break risk:** Stop-loss and take-profit cannot be executed during the no-data lunch gap (12:00–12:57). These conditions are checked at the first afternoon bar (13:00) when data resumes. A position may experience adverse movement during lunch that exceeds the stop-loss threshold — the realized exit loss will then be larger than the nominal stop-loss parameter.
- This is simple and does not require special code: the backtest loop just skips the absent bars naturally.

**Forced exit (consistent with next-bar execution):**
- At 16:28, generate forced exit signal → execute at 16:29 open.
- If 16:29 open is unavailable (e.g., session ends at 16:28), use the last available bar's close as fallback.
- This ensures forced exit follows the same signal-at-t, execute-at-t+1 logic as all other exits.

## 3.2 Strategy A: Opening Range Breakout (ORB)

### Rationale
The first 30 minutes of the HSI day session absorb overnight news (US/Europe close, China A-shares pre-open). The opening range (median 169 points, mean 185 points) establishes the day's initial contested zone. A breakout from this range signals strong directional conviction.

### Definitions

```
Session start: first bar of day (time = 91400, i.e., 09:14)
Opening window: first N minutes from session start
  N ∈ {15, 30, 45, 60}
  
For N=30: bars from 09:14 to 09:43 (i.e., time 91400 to 94300)

OR_high = max(hi1_high[t] for t in opening window)
OR_low  = min(hi1_low[t] for t in opening window)
OR_mid  = (OR_high + OR_low) / 2

Upper breakout level = OR_high + buffer_points
Lower breakout level = OR_low  - buffer_points

buffer_points ∈ {0, 5, 10, 20}
```

### Signal Logic (after opening window ends)

```
At each minute bar t (after opening window):

  If position == 0 (flat):
    If hi1_close[t] > Upper:
      target_position = +1 (long)
    Elif hi1_close[t] < Lower:
      target_position = -1 (short)
  
  Execute at NEXT bar (t+1): entry_price = hi1_open[t+1]
```

### Exit Conditions

```
1. Stop-loss:
   Long:  exit if hi1_close[t] <= entry_price - stop_loss_points
   Short: exit if hi1_close[t] >= entry_price + stop_loss_points
   Execute at next bar open.

2. Take-profit:
   Long:  exit if hi1_close[t] >= entry_price + take_profit_points
   Short: exit if hi1_close[t] <= entry_price - take_profit_points
   Execute at next bar open.

3. Session end:
   Signal forced exit at 16:28, execute at 16:29 open price.
   Fallback: use 16:28 close if 16:29 bar unavailable.

4. Max trades:
   After max_trades_per_session trades, no new entries.
```

### Parameters

| Parameter | Grid | Unit |
|-----------|------|------|
| opening_window | 15, 30, 45, 60 | minutes |
| buffer_points | 0, 5, 10, 20 | HSI index points |
| stop_loss_points | 30, 50, 80, 120 | HSI index points |
| take_profit_points | 50, 80, 120, 180 | HSI index points |
| max_trades_per_session | 1, 2, 3 | count |

### Why Point-Based Thresholds

HSI futures trade in index points (tick size = 1 point). The contract multiplier is HKD 50 per point. All costs, margins, and PnL are naturally denominated in points. Using percentage thresholds would require conversion and introduce price-level dependency (0.3% of 20,000 ≠ 0.3% of 33,000). Point-based thresholds remain stable across the price range.

---

## 3.3 Strategy B: Intraday Fair-Value Deviation Mean Reversion

### Rationale
In range-bound markets, short-term deviations from fair value tend to revert. Using VWAP (available since volume exists) as the fair value anchor captures the average price weighted by institutional activity. Extreme deviations represent temporary liquidity imbalances.

### Definitions

**VWAP (primary fair-value measure):**
```
VWAP_t = Σ(hi1_close[i] × hi1_volume[i]) / Σ(hi1_volume[i])
         for i from session_start to t (cumulative within session)
```

**Rolling fair-value (alternative, for robustness check):**
```
FairValue_t = mean(hi1_close[t-W+1 : t])   (rolling window of W minutes)
```

**Deviation Z-score:**
```
Rolling_std_t = std(hi1_close[t-W+1 : t])

Z_t = (hi1_close[t] - VWAP_t) / Rolling_std_t
```

**Interpretation:** VWAP is the cumulative intraday fair value (volume-weighted average price from session start to t). Rolling_std is used only to normalize the recent deviation scale — it measures how many "recent standard deviations" the current price is away from fair value. The rolling window W controls the normalization horizon, not the fair-value anchor.

**Robustness check:** As an alternative, replace VWAP with a rolling mean fair value (see `compute_rolling_fair_value`) and compare performance. This tests whether the VWAP anchor or the rolling mean anchor produces more stable signals.

If Rolling_std_t < min_std_threshold (e.g., 5 points), set Z_t = 0 to avoid division by near-zero.

### Signal Logic

```
At each minute bar t (after W bars available):

  If position == 0 (flat):
    If Z_t < -z_entry:
      target_position = +1 (long; price below fair value)
    Elif Z_t > +z_entry:
      target_position = -1 (short; price above fair value)
  
  If position == +1 (long):
    If Z_t >= -z_exit:
      target_position = 0 (exit; price reverted)
  
  If position == -1 (short):
    If Z_t <= +z_exit:
      target_position = 0 (exit; price reverted)

  Execute at NEXT bar (t+1): price = hi1_open[t+1]
```

### Exit Conditions

Same as ORB: stop-loss, take-profit, session-end forced exit.

### Parameters

| Parameter | Grid | Unit |
|-----------|------|------|
| rolling_window (W) | 30, 60, 120 | minutes |
| z_entry | 1.5, 2.0, 2.5 | std deviations |
| z_exit | 0, 0.25, 0.5 | std deviations |
| stop_loss_points | 30, 50, 80 | HSI index points |
| take_profit_points | 50, 80, 120 | HSI index points |
| use_vwap | True, False | (True=VWAP, False=rolling mean) |

---

## 3.4 Strategy C: Regime-Adaptive Hybrid (MAIN STRATEGY)

### Core Innovation

Instead of running ORB and mean-reversion simultaneously or with fixed weights, dynamically classify the current market regime and select the appropriate sub-strategy.

### Regime Features

**Feature 1: Efficiency Ratio (ER)**

```
ER_t = |hi1_close[t] - hi1_close[t-L]| / Σ|hi1_close[i] - hi1_close[i-1]| for i in [t-L+1, t]
```

Where L = er_window.

Properties:
- ER ∈ [0, 1]
- ER → 1: price moved in a straight line (strong trend)
- ER → 0: price moved a lot but ended near the start (range-bound/choppy)
- No division-by-zero risk (denominator is sum of absolute changes; zero only if all prices identical, in which case ER = 0/0 → set to 0)

Edge case: If denominator = 0 (all prices identical), set ER_t = 0.

**Feature 2: Realized Volatility (RV)**

```
r_i = (hi1_close[i] - hi1_close[i-1]) / hi1_close[i-1]

RV_t = sqrt(Σ r_i² for i in [t-V+1, t]) × sqrt(252 × 376)
```

For regime classification, we don't need annualization. Use raw:
```
RV_t = sqrt(Σ r_i² for i in [t-V+1, t])
```

The extreme volatility threshold is computed as a quantile of RV on the training data:
```
extreme_vol_threshold = quantile(RV_training, extreme_vol_quantile)
```

### Regime Classification

```
At each minute t:

If RV_t > extreme_vol_threshold:
    regime = EXTREME  → stay flat (no new positions; close existing)
Elif ER_t > er_threshold:
    regime = TREND    → use ORB signal
Else:
    regime = RANGE    → use Mean Reversion signal
```

### Hybrid Signal Logic

```
1. Compute ER_t and RV_t.
2. Classify regime.
3. If EXTREME:
     [Base version] If position ≠ 0: exit at next bar. No new entries.
     [Robustness version] No new entries; existing positions managed by stop-loss/take-profit only.
4. If TREND:
     Use ORB sub-strategy signal.
     (Only valid after opening window; before that, no ORB signal available → stay flat)
5. If RANGE:
     Use Mean Reversion sub-strategy signal.
```

**EXTREME regime implementation note:** Two versions will be tested:
- **Base version (default):** Close existing positions immediately and block all new entries. Rationale: extreme volatility creates unpredictable whipsaws; immediate exit minimizes tail risk.
- **Robustness version:** Block new entries only; allow existing positions to be managed by their stop-loss/take-profit levels. Rationale: forced exit during a spike may realize losses that a stop-loss would have handled more cheaply. Compare performance of both versions in the optimization stage.

### Parameters (Regime Classifier Only)

| Parameter | Grid | Unit |
|-----------|------|------|
| er_window | 30, 60, 120 | minutes |
| er_threshold | 0.25, 0.35, 0.45, 0.55 | dimensionless [0,1] |
| rv_window | 30, 60, 120 | minutes |
| extreme_vol_quantile | 0.80, 0.90, 0.95 | quantile of training RV |

Sub-strategy parameters (ORB and MR) are fixed from Stage 1–2 optimization.

---

## 3.5 Risk Management Rules

| Rule | Parameter | Logic |
|------|-----------|-------|
| Stop-loss | SL points | Exit if unrealized loss ≥ SL |
| Take-profit | TP points | Exit if unrealized profit ≥ TP |
| Max trades per session | max_trades | No new entry after reaching limit |
| Max daily loss | max_daily_loss_points (e.g., 200) | No new entry if session_realized_pnl ≤ -max_daily_loss_points |
| Session-end exit | 16:28 | Force close all open positions |
| Extreme volatility filter | Via regime classifier | No trading in EXTREME regime |
| Minimum volume filter | vol < 50 → skip bar | Avoid illiquid bars (rare) |

---

# PART 4: Revised Backtesting Methodology

## 4.1 Time Split

| Period | Date Range | Trading Days | Purpose |
|--------|-----------|--------------|---------|
| Training | 2017-07-03 to 2019-06-28 | ~500 | Parameter estimation |
| Validation | 2019-07-01 to 2019-12-31 | ~125 | Parameter selection |
| Out-of-sample | 2020-01-02 to 2020-06-09 | ~105 | Final evaluation (once only) |

**Justification:**
- Training (2 years) covers 2017 bull market, 2018 trade-war correction (-6000 pts), 2019 partial recovery.
- Validation (6 months) in stable 2019H2 tests parameter robustness.
- Out-of-sample includes COVID crash (Feb–Mar 2020) as genuine stress test.
- The split is clean: no parameters are tuned on out-of-sample data.

## 4.2 Execution Model

```
Signal at bar t → Execute at bar t+1

Entry price = hi1_open[t+1]
Exit price  = hi1_open[t+1] (for signal-based exit, stop-loss, take-profit)
            = hi1_open[t+1] for session-end forced exit (signal at 16:28, execute at 16:29 open)
            = hi1_close[t] as fallback only if next bar is unavailable

Slippage is added to entry and exit:
  Actual entry = entry_price + slippage × direction_penalty
  direction_penalty: +1 for buy, -1 for sell (always worse fill)
```

## 4.3 PnL Computation

**Primary metric: Index point PnL**

```
Trade_PnL_points = direction × (exit_price - entry_price) - 2 × slippage_per_side

direction: +1 for long, -1 for short

Daily_PnL = Σ Trade_PnL for all trades closed on that day

HKD_PnL = Point_PnL × 50 (contract multiplier)
```

**Slippage assumptions:**

| Level | Per Side | Per Round-Trip | Scenario |
|-------|----------|----------------|----------|
| 0 | 0 pts | 0 pts | Theoretical |
| 1 | 1 pt | 2 pts | Limit orders, liquid time |
| 2 | 2 pts | 4 pts | Base case (market orders, normal) |
| 5 | 5 pts | 10 pts | Fast market |
| 10 | 10 pts | 20 pts | Extreme conditions |

**Base case for all results:** 2 points per side (4 points round-trip).

**Additional fixed cost:** 2 points per round-trip (commission + exchange fee ≈ HKD 100 ≈ 2 HSI points).

**Total base-case cost per round-trip: 6 points.**

## 4.4 Benchmarks

| # | Benchmark | Definition |
|---|-----------|------------|
| B0 | Full-Period Buy-and-Hold | Buy at first day open, hold until last day close (includes overnight risk) |
| B1 | Daily Intraday Long-only | Long at 09:14 open, close at 16:29 close, every trading day |
| B2 | Always Flat | PnL = 0 (the bar to beat after costs) |
| B3 | Pure ORB | ORB strategy without regime filter |
| B4 | Pure Mean Reversion | MR strategy without regime filter |
| B5 | **Regime-Adaptive Hybrid** | Main proposed strategy |

**Benchmark notes:**
- B0 (Full-Period Buy-and-Hold) is included for consistency with previous STAT8020 projects and provides a familiar reference point. However, it is NOT a fair comparison because it carries overnight and weekend risk that our intraday strategy explicitly avoids.
- B1 (Daily Intraday Long-only) is the **fairer benchmark** for intraday strategies: same universe, same risk exposure horizon (single session), same forced exit. Outperforming B1 demonstrates genuine intraday alpha beyond directional market drift.

## 4.5 Performance Metrics

**Return metrics (in points):**
- Cumulative PnL (points)
- Cumulative PnL (HKD per 1 lot)
- Average daily PnL
- Average PnL per trade

**Risk metrics:**
- Daily PnL standard deviation
- Maximum drawdown (in points)
- Maximum drawdown duration (in days)
- VaR 95% (daily)
- VaR 99% (daily)

**Risk-adjusted metrics:**
- Sharpe ratio = (mean daily PnL / std daily PnL) × √252
- Sortino ratio = (mean daily PnL / downside std) × √252
- Calmar ratio = annualized PnL / max drawdown
- Profit factor = gross profit / gross loss

**Trade statistics:**
- Number of trades
- Average trades per day
- Win rate (% profitable trades)
- Average winner (points)
- Average loser (points)
- Average holding time (minutes)
- Max consecutive wins / losses
- Max single-trade loss

## 4.6 Backtesting Pseudo-Code (Revised)

```python
def backtest(day_session_data, params):
    """
    day_session_data: dict of {date: DataFrame} where each DataFrame has bars 91400-162900
    """
    all_trades = []
    daily_pnl = {}
    
    for date, session_df in day_session_data.items():
        
        position = 0          # -1, 0, +1
        entry_price = None
        entry_time = None
        session_trades = []
        session_trade_count = 0
        session_realized_pnl = 0
        
        # === Compute session features ===
        bars = session_df.values  # each row: [time, open, high, low, close, volume]
        N = params['opening_window']
        
        # Opening range from first N bars
        opening_bars = bars[:N]
        OR_high = max(row[HIGH] for row in opening_bars)
        OR_low  = min(row[LOW] for row in opening_bars)
        Upper = OR_high + params['buffer_points']
        Lower = OR_low  - params['buffer_points']
        
        # Precompute VWAP, Z-score, ER, RV for each bar
        features = compute_all_features(session_df, params)
        
        # === Main trading loop ===
        for i in range(N, len(bars) - 1):  # -1 because we execute at i+1
            
            t = bars[i]
            t_next = bars[i + 1]
            close_t = t[CLOSE]
            
            # Get regime
            er_t = features['ER'][i]
            rv_t = features['RV'][i]
            regime = classify_regime(er_t, rv_t, params)
            
            # === Check exit conditions (if in position) ===
            if position != 0:
                unrealized_pnl = position * (close_t - entry_price)
                
                # Stop-loss
                if unrealized_pnl <= -params['stop_loss_points']:
                    exit_price = t_next[OPEN] + slippage_exit
                    record_trade(...)
                    position = 0
                    continue
                
                # Take-profit
                if unrealized_pnl >= params['take_profit_points']:
                    exit_price = t_next[OPEN] - slippage_exit_direction
                    record_trade(...)
                    position = 0
                    continue
                
                # Forced exit: signal at 16:28 (i == len(bars)-2), execute at 16:29 open
                if i >= len(bars) - 2:
                    exit_price = t_next[OPEN] if (i + 1 < len(bars)) else close_t
                    record_trade(...)
                    position = 0
                    continue
                
                # EXTREME regime: exit
                if regime == 'EXTREME':
                    exit_price = t_next[OPEN]
                    record_trade(...)
                    position = 0
                    continue
                
                # Mean-reversion exit signal
                if position != 0 and current_strategy == 'MR':
                    z_t = features['Z'][i]
                    if should_exit_mr(position, z_t, params):
                        exit_price = t_next[OPEN]
                        record_trade(...)
                        position = 0
                        continue
            
            # === Check entry conditions (if flat) ===
            if position == 0:
                # Risk checks
                if session_trade_count >= params['max_trades']:
                    continue
                if session_realized_pnl <= -params['max_daily_loss_points']:
                    continue
                if regime == 'EXTREME':
                    continue
                
                signal = 0
                
                if regime == 'TREND':
                    # ORB signal
                    if close_t > Upper:
                        signal = +1
                    elif close_t < Lower:
                        signal = -1
                
                elif regime == 'RANGE':
                    # MR signal
                    z_t = features['Z'][i]
                    if z_t < -params['z_entry']:
                        signal = +1
                    elif z_t > params['z_entry']:
                        signal = -1
                
                if signal != 0:
                    entry_price = t_next[OPEN] + slippage * signal
                    entry_time = t_next[TIME]
                    position = signal
                    session_trade_count += 1
        
        # Force close if still in position at session end
        if position != 0:
            exit_price = bars[-1][CLOSE]
            record_trade(...)
        
        daily_pnl[date] = sum(trade.pnl for trade in session_trades)
        all_trades.extend(session_trades)
    
    return all_trades, daily_pnl
```

---

# PART 5: Revised Parameter Optimization

## 5.1 Staged Optimization

**Stage 1: Tune ORB sub-strategy (on training data)**

Run ORB alone (no regime filter) across parameter grid:
- 4 × 4 × 4 × 4 × 3 = 768 combinations
- Evaluate on training data
- Rank by Sharpe ratio
- Select top-5 parameter sets

**Stage 2: Tune Mean Reversion sub-strategy (on training data)**

Run MR alone (no regime filter) across parameter grid:
- 3 × 3 × 3 × 3 × 3 × 2 = 486 combinations
- Evaluate on training data
- Rank by Sharpe ratio
- Select top-5 parameter sets

**Stage 3: Validate ORB and MR (on validation data)**

Run top-5 ORB and top-5 MR sets on validation data.
Select 1 best ORB parameter set and 1 best MR parameter set based on validation Sharpe.

**Stage 4: Tune regime classifier (on training data, with fixed ORB/MR params)**

Run Hybrid with fixed ORB and MR params, varying regime parameters:
- 3 × 4 × 3 × 3 = 108 combinations
- Rank by Sharpe ratio on training data
- Validate top-5 on validation data
- Select best regime parameter set

**Stage 5: Final out-of-sample test (once)**

Run the full Hybrid strategy with all fixed parameters on the out-of-sample period.
Report results. Do NOT adjust.

**Total backtest runs:** ~768 + 486 + 10 + 108 + 5 + 1 ≈ 1,378 (very feasible computationally)

## 5.2 Anti-Overfitting Rules

1. **Flat-optimum preference:** If top-5 training sets all have similar Sharpe on validation, pick the one closest to the center of the parameter grid.
2. **Penalize high frequency:** If two sets have similar Sharpe but one trades 2×/day and the other 5×/day, prefer the lower-frequency one (more robust to slippage).
3. **Stability check:** The selected parameters must produce positive Sharpe on at least 60% of individual months in the training period.
4. **No test-set snooping:** Out-of-sample results are reported once; never used for parameter selection.

---

# PART 6: Revised Report Outline

## Section 1: Introduction (1–1.5 pages)

**Content:**
- HSI futures market background (contract specs, trading hours, participants)
- Motivation: why intraday algorithmic trading
- Market regime hypothesis: single strategies fail under regime mismatch
- Project contribution: regime-adaptive framework combining ORB and fair-value mean reversion

**Tables:** None
**Figures:** None

---

## Section 2: Data Description and Preprocessing (1.5–2 pages)

**Content:**
- Dataset schema (columns, types, format)
- Trading session definition (morning 09:14–11:59, afternoon 13:00–16:29)
- Decision to use day session only (justification: liquidity, clarity)
- Lunch break handling (hold through, no signals during gap)
- Data cleaning: duplicates (keep last), zero-volume bars (flag), session validation
- Summary statistics of price and returns

**Tables:**
- Table 1: Dataset schema and column description
- Table 2: Summary statistics (mean, std, percentiles of returns; daily range stats)
- Table 3: Data cleaning summary (rows removed, duplicates handled)

**Figures:**
- Figure 1: HSI futures price series (full period, day session close)
- Figure 2: Minute return distribution (histogram with normal overlay)
- Figure 3: Average intraday pattern (mean return by minute-of-session)
- Figure 4: Daily volume pattern (average volume by minute-of-session)

---

## Section 3: Trading Algorithm and Rationale (3–4 pages)

**Content:**
- Strategy A: Opening Range Breakout — full description, formulas, rationale
- Strategy B: Fair-Value Deviation Mean Reversion — full description, formulas, rationale
- Strategy C: Regime-Adaptive Hybrid — regime classification, switching logic
- All formulas clearly stated
- Execution model (next-bar execution, no look-ahead)
- Position sizing (1 lot, no scaling in base case)

**Tables:**
- Table 4: Parameter definitions and grids for all three strategies
- Table 5: Regime classification rules

**Figures:**
- Figure 5: Example ORB day (price chart with OR levels, entry/exit markers)
- Figure 6: Example MR day (price chart with VWAP, Z-score, entry/exit markers)
- Figure 7: Example regime classification (ER and RV over a trading day, regime bands)

---

## Section 4: In-Sample, Validation, and Out-Sample Design (1 page)

**Content:**
- Time split rationale
- Market conditions in each period
- Overfitting discussion

**Tables:**
- Table 6: Time split specification (dates, trading days, market context)

**Figures:** None

---

## Section 5: Backtesting Methodology (1–1.5 pages)

**Content:**
- Execution assumptions (next-bar open)
- Transaction cost and slippage model
- Forced session-end exit
- Risk management rules
- Benchmark definitions

**Tables:**
- Table 7: Transaction cost and slippage assumptions
- Table 8: Risk management parameters

**Figures:** None

---

## Section 6: Parameter Optimization (2–3 pages)

**Content:**
- Staged optimization procedure
- Training results for ORB and MR
- Validation results for top parameter sets
- Regime classifier tuning
- Selected final parameters
- Anti-overfitting measures

**Tables:**
- Table 9: Top-5 ORB parameter sets (training + validation Sharpe)
- Table 10: Top-5 MR parameter sets (training + validation Sharpe)
- Table 11: Regime classifier tuning results
- Table 12: Final selected parameters for all strategies

**Figures:**
- Figure 8: ORB parameter sensitivity heatmap (opening_window × buffer → Sharpe)
- Figure 9: MR parameter sensitivity heatmap (z_entry × rolling_window → Sharpe)
- Figure 10: Regime ER threshold sensitivity (Sharpe vs. er_threshold)

---

## Section 7: Backtesting Results and Performance Characteristics (3–4 pages)

**Content:**
- Performance comparison across all strategies and periods
- Cumulative PnL curves
- Drawdown analysis
- Trade statistics
- Discussion of results

**Tables:**
- Table 13: Performance summary (all strategies × all periods)
- Table 14: Risk metrics comparison
- Table 15: Trade statistics (trades, win rate, avg winner/loser, holding time)

**Figures:**
- Figure 11: Cumulative PnL — training period (all strategies)
- Figure 12: Cumulative PnL — out-of-sample period (all strategies)
- Figure 13: Drawdown curve (Hybrid strategy)
- Figure 14: Trade PnL distribution (histogram of individual trade PnL)
- Figure 15: Position timeline for a sample week

---

## Section 8: Slippage and Transaction Cost Analysis (1.5–2 pages)

**Content:**
- Slippage sensitivity analysis
- Break-even slippage computation
- Discussion of realistic execution costs for HSI futures
- Conclusion on robustness to costs

**Tables:**
- Table 16: Slippage sensitivity table (metrics at 0, 1, 2, 5, 10 pts)

**Figures:**
- Figure 16: Cumulative PnL under different slippage levels
- Figure 17: Sharpe ratio vs. slippage level (bar chart)

---

## Section 9: Risk Management Features (1 page)

**Content:**
- Stop-loss and take-profit rationale
- Max daily loss and max trades limits
- Extreme volatility filter (via regime classifier)
- Forced session-end exit
- How each rule protects capital

**Tables:**
- Table 17: Risk management rule summary

**Figures:** None

---

## Section 10: Implementation Difficulty and Real-Time Trading (1.5 pages)

**Content:**
- Real-time data feed requirements
- Order execution: market vs limit orders
- Slippage in fast markets (especially during COVID period)
- Futures margin requirements (initial ~HKD 100,000 per lot)
- Night session exclusion rationale
- Contract rollover procedure
- Parameter recalibration frequency
- System failure handling
- Difference between backtest and live trading

**Tables:**
- Table 18: Implementation risk register

**Figures:** None

---

## Section 11: Discussion and Market Observations (1.5 pages)

**Content:**
- Why regime-adaptive approach improves over single strategies
- Market conditions when strategy performs well vs. poorly
- Observations about HSI futures microstructure
- Limitations of the approach
- Possible improvements (ML-based regime classifier, adaptive parameters, multi-timeframe)
- Comparison with previous project approaches

**Tables:** None
**Figures:** None

---

## Section 12: Conclusion (0.5–1 page)

**Content:**
- Final recommended algorithm and exact parameters
- Key findings
- Practical deployment recommendation

**Tables:**
- Table 19: Final recommended strategy specification

---

## Section 13: References (0.5 page)

## Section 14: Appendix (2–3 pages)

- Full parameter grid results (top-20 for each sub-strategy)
- Additional monthly return details
- Code structure description
- Pseudo-code for backtesting loop

---

# PART 7: Revised Expected Figures (15 total)

| # | Figure | Section |
|---|--------|---------|
| 1 | HSI futures day-session close price (full period) | Data |
| 2 | Minute return distribution (histogram + normal QQ) | Data |
| 3 | Intraday pattern: mean return by minute | Data |
| 4 | Intraday pattern: mean volume by minute | Data |
| 5 | Example ORB trading day | Strategy |
| 6 | Example MR trading day with VWAP and Z-score | Strategy |
| 7 | Example regime classification day (ER + RV + regime bands) | Strategy |
| 8 | ORB parameter heatmap (training Sharpe) | Optimization |
| 9 | MR parameter heatmap (training Sharpe) | Optimization |
| 10 | ER threshold sensitivity plot | Optimization |
| 11 | Cumulative PnL — training period (all strategies) | Results |
| 12 | Cumulative PnL — out-of-sample (all strategies) | Results |
| 13 | Drawdown curve (Hybrid) | Results |
| 14 | Trade PnL distribution | Results |
| 15 | Position timeline (sample week) | Results |
| 16 | Slippage sensitivity: cumulative PnL curves | Robustness |
| 17 | Sharpe ratio vs. slippage bar chart | Robustness |

# PART 7 (cont.): Revised Expected Tables (19 total)

| # | Table | Section |
|---|-------|---------|
| 1 | Dataset schema | Data |
| 2 | Return / range summary statistics | Data |
| 3 | Data cleaning summary | Data |
| 4 | Strategy parameter definitions and grids | Strategy |
| 5 | Regime classification rules | Strategy |
| 6 | Time split specification | Design |
| 7 | Cost / slippage assumptions | Backtest |
| 8 | Risk management parameters | Backtest |
| 9 | Top-5 ORB params (train + validation) | Optimization |
| 10 | Top-5 MR params (train + validation) | Optimization |
| 11 | Regime classifier results | Optimization |
| 12 | Final selected parameters | Optimization |
| 13 | Performance summary (all strategies × periods) | Results |
| 14 | Risk metrics comparison | Results |
| 15 | Trade statistics | Results |
| 16 | Slippage sensitivity table | Robustness |
| 17 | Risk management rule summary | Risk |
| 18 | Implementation risk register | Implementation |
| 19 | Final recommended strategy specification | Conclusion |

---

# PART 8: Revised Codex Implementation Plan

## Project Structure

```
financial8020/
├── hi1_20170701_20200609.csv          # Raw data (already present)
├── PROJECT_PROPOSAL_v2.md             # This document
├── data/                              # (optional symlink or copy)
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── data_loader.py
│   ├── preprocessing.py
│   ├── features.py
│   ├── strategies.py
│   ├── regime.py
│   ├── risk_manager.py
│   ├── backtester.py
│   ├── metrics.py
│   ├── optimization.py
│   ├── plots.py
│   └── utils.py
├── outputs/
│   ├── figures/
│   ├── tables/
│   └── logs/
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_strategy_development.ipynb
│   └── 03_backtest_results.ipynb
├── main.py
├── requirements.txt
└── README.md
```

## File-by-File Specification

### `src/config.py`

```python
# Purpose: Central configuration for all parameters and paths

DATA_PATH = '../hi1_20170701_20200609.csv'  # or absolute path

# Column mapping (ACTUAL dataset columns)
COL_DATE = 'date'
COL_TIME = 'time'
COL_OPEN = 'hi1_open'
COL_HIGH = 'hi1_high'
COL_LOW = 'hi1_low'
COL_CLOSE = 'hi1_close'
COL_VOLUME = 'hi1_volume'

# Session times (as integer HMMSS format matching the data)
MORNING_START = 91400    # 09:14
MORNING_END = 115900     # 11:59
AFTERNOON_START = 130000 # 13:00
AFTERNOON_END = 162900   # 16:29
FORCED_EXIT_TIME = 162800  # 16:28 (exit one bar before end)

# Time split dates (YYYYMMDD integers)
TRAIN_START = 20170703
TRAIN_END = 20190628
VAL_START = 20190701
VAL_END = 20191231
TEST_START = 20200102
TEST_END = 20200609

# Contract specifications
TICK_SIZE = 1            # HSI futures: 1 index point
CONTRACT_MULTIPLIER = 50 # HKD per point

# Cost assumptions
BASE_SLIPPAGE = 2        # points per side
COMMISSION_RT = 2        # points per round-trip (fixed costs)

# Default strategy parameters (placeholders; tuned in optimization)
DEFAULT_ORB_PARAMS = {
    'opening_window': 30,
    'buffer_points': 10,
    'stop_loss_points': 80,
    'take_profit_points': 120,
    'max_trades': 2,
}

DEFAULT_MR_PARAMS = {
    'rolling_window': 60,
    'z_entry': 2.0,
    'z_exit': 0.25,
    'stop_loss_points': 50,
    'take_profit_points': 80,
    'use_vwap': True,
}

DEFAULT_REGIME_PARAMS = {
    'er_window': 60,
    'er_threshold': 0.35,
    'rv_window': 60,
    'extreme_vol_quantile': 0.90,
}

DEFAULT_RISK_PARAMS = {
    'max_trades_per_session': 3,
    'max_daily_loss_points': 200,
}
```

### `src/data_loader.py`

```python
# Purpose: Load CSV, parse datetime, return clean DataFrame

def load_raw_data(filepath: str) -> DataFrame:
    """
    Read hi1_20170701_20200609.csv
    Returns DataFrame with columns:
      date (int), time (int), open, high, low, close, volume
    Renames hi1_* columns to generic names.
    """
    # Read CSV
    # Rename columns: hi1_open -> open, hi1_high -> high, etc.
    # Ensure types: date=int, time=int, prices=float, volume=float
    # Return df

def parse_datetime(df: DataFrame) -> DataFrame:
    """
    Add 'datetime' column from date and time.
    Format time with zero-padding: time=91400 -> '091400'
    Combine: datetime = pd.to_datetime(str(date) + str(time).zfill(6), format='%Y%m%d%H%M%S')
    """
    # Edge case: time=0 should become '000000', time=100 -> '000100'
    pass
```

### `src/preprocessing.py`

```python
# Purpose: Clean data, define sessions, split periods

def remove_duplicates(df: DataFrame) -> DataFrame:
    """
    Remove duplicate (date, time) rows. Keep LAST row (slightly higher volume).
    Affected dates: 12 dates in Feb-Mar 2020.
    Expected: removes ~4500 rows.
    """

def filter_day_session(df: DataFrame) -> DataFrame:
    """
    Keep only rows where:
      (MORNING_START <= time <= MORNING_END) OR (AFTERNOON_START <= time <= AFTERNOON_END)
    
    Note: Include 130000 as afternoon start (some dates have 125800/125900 but inconsistent).
    Conservative choice: use >= 130000 for afternoon to be consistent.
    
    Result: ~376 bars per day × 724 days ≈ 272,000 rows
    """

def validate_sessions(df: DataFrame) -> DataFrame:
    """
    For each date, count bars. Remove dates with < 300 bars (abnormal short days).
    Report removed dates.
    """

def flag_zero_volume(df: DataFrame) -> DataFrame:
    """
    Add column 'is_illiquid' = True if volume == 0.
    Only 30 bars affected; do not remove, just flag.
    """

def split_by_period(df, train_start, train_end, val_start, val_end, test_start, test_end):
    """
    Return (df_train, df_val, df_test) based on date ranges.
    """

def get_sessions(df: DataFrame) -> dict:
    """
    Group df by date. Return dict {date_int: DataFrame_for_that_date}.
    Each session DataFrame is indexed from 0 to N_bars-1.
    """
```

### `src/features.py`

```python
# Purpose: Compute all derived features for a single session

def compute_returns(session_df: DataFrame) -> Series:
    """
    r[i] = close[i] / close[i-1] - 1
    r[0] = 0 (first bar has no prior)
    """

def compute_opening_range(session_df: DataFrame, opening_window: int) -> tuple:
    """
    OR_high = max(high[0:opening_window])
    OR_low  = min(low[0:opening_window])
    Returns (OR_high, OR_low)
    
    Edge case: if session has fewer than opening_window bars, return (None, None)
    """

def compute_vwap(session_df: DataFrame) -> Series:
    """
    Cumulative intraday VWAP:
    VWAP[i] = sum(close[0:i+1] * volume[0:i+1]) / sum(volume[0:i+1])
    
    Edge case: if cumulative volume == 0, use simple mean.
    """

def compute_rolling_fair_value(session_df: DataFrame, window: int) -> Series:
    """
    Rolling mean of close price over window bars.
    First window-1 bars: use expanding mean.
    """

def compute_zscore(close: Series, fair_value: Series, window: int) -> Series:
    """
    rolling_std = close.rolling(window).std()
    z = (close - fair_value) / rolling_std
    
    Edge case: if rolling_std < 5 (points), set z = 0.
    First window-1 bars: z = 0.
    """

def compute_efficiency_ratio(close: Series, window: int) -> Series:
    """
    ER[i] = |close[i] - close[i-window]| / sum(|close[j] - close[j-1]| for j in [i-window+1, i])
    
    Edge case: if denominator == 0, ER = 0.
    First window bars: ER = 0.
    """

def compute_realized_volatility(returns: Series, window: int) -> Series:
    """
    RV[i] = sqrt(sum(r[j]^2 for j in [i-window+1, i]))
    
    First window-1 bars: use expanding.
    """

def compute_session_features(session_df: DataFrame, params: dict) -> dict:
    """
    Compute and return all features for one session.
    Returns dict with keys: 'returns', 'OR_high', 'OR_low', 'vwap', 'z_score', 'ER', 'RV'
    """
```

### `src/regime.py`

```python
# Purpose: Regime classification

def compute_extreme_vol_threshold(rv_train_all: array, quantile: float) -> float:
    """
    Compute the quantile of all RV values from training period.
    This is computed ONCE and used as a fixed threshold.
    """

def classify_regime(er_t: float, rv_t: float, er_threshold: float, extreme_vol_threshold: float) -> str:
    """
    Returns 'EXTREME', 'TREND', or 'RANGE'.
    
    If rv_t > extreme_vol_threshold: return 'EXTREME'
    If er_t > er_threshold: return 'TREND'
    Else: return 'RANGE'
    """
```

### `src/strategies.py`

```python
# Purpose: Signal generation for each sub-strategy

def orb_signal(close_t: float, or_high: float, or_low: float, 
               buffer_points: float, current_position: int) -> int:
    """
    If current_position != 0: return current_position (no new entry while in position)
    If close_t > or_high + buffer_points: return +1
    If close_t < or_low - buffer_points: return -1
    Else: return 0
    """

def mr_signal(z_t: float, z_entry: float, z_exit: float, current_position: int) -> int:
    """
    If current_position == 0:
        If z_t < -z_entry: return +1 (long; price below fair value)
        If z_t > z_entry: return -1 (short; price above fair value)
        Else: return 0
    If current_position == +1:
        If z_t >= -z_exit: return 0 (exit long)
        Else: return +1 (hold)
    If current_position == -1:
        If z_t <= z_exit: return 0 (exit short)
        Else: return -1 (hold)
    """

def hybrid_signal(regime: str, close_t: float, z_t: float,
                  or_high: float, or_low: float, buffer_points: float,
                  z_entry: float, z_exit: float, current_position: int,
                  opening_window_passed: bool) -> int:
    """
    If regime == 'EXTREME': return 0 (force flat)
    If regime == 'TREND' and opening_window_passed: return orb_signal(...)
    If regime == 'RANGE': return mr_signal(...)
    If regime == 'TREND' and not opening_window_passed: return 0
    """
```

### `src/risk_manager.py`

```python
# Purpose: Risk checks

class RiskManager:
    def __init__(self, stop_loss_points, take_profit_points, 
                 max_trades, max_daily_loss, forced_exit_time):
        pass
    
    def check_stop_loss(self, entry_price, current_close, direction) -> bool:
        """True if stop-loss triggered."""
        unrealized = direction * (current_close - entry_price)
        return unrealized <= -self.stop_loss_points
    
    def check_take_profit(self, entry_price, current_close, direction) -> bool:
        """True if take-profit triggered."""
        unrealized = direction * (current_close - entry_price)
        return unrealized >= self.take_profit_points
    
    def check_session_end(self, current_time) -> bool:
        """True if we must exit (time >= forced_exit_time)."""
        return current_time >= self.forced_exit_time
    
    def can_trade(self, session_trade_count, session_realized_pnl) -> bool:
        """True if allowed to enter new position."""
        if session_trade_count >= self.max_trades:
            return False
        if session_realized_pnl <= -self.max_daily_loss:
            return False
        return True
```

### `src/backtester.py`

```python
# Purpose: Main backtesting engine

class Trade:
    """Stores one complete round-trip trade."""
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    direction: int  # +1 or -1
    pnl_points: float
    holding_bars: int
    exit_reason: str  # 'signal', 'stop_loss', 'take_profit', 'session_end', 'regime_change'
    regime_at_entry: str

class BacktestResult:
    """Container for backtest outputs."""
    trades: list[Trade]
    daily_pnl: dict  # {date: float}
    positions: list   # position at each bar

class Backtester:
    def __init__(self, sessions: dict, strategy: str, params: dict, 
                 slippage: float, commission_rt: float):
        """
        sessions: dict of {date: DataFrame}
        strategy: 'ORB', 'MR', or 'HYBRID'
        params: combined dict with all relevant parameters
        """
    
    def run(self) -> BacktestResult:
        """
        Main loop: iterate over sessions, generate signals, execute trades.
        See pseudo-code in Section 4.6.
        """
    
    def _run_session(self, date, session_df) -> list[Trade]:
        """
        Process one trading session.
        """
```

### `src/metrics.py`

```python
# Purpose: Compute all performance metrics

def compute_all_metrics(trades: list, daily_pnl: dict) -> dict:
    """
    Returns dict with all metrics:
    - cumulative_pnl_points
    - cumulative_pnl_hkd
    - avg_daily_pnl
    - sharpe_ratio
    - sortino_ratio
    - calmar_ratio
    - max_drawdown_points
    - max_drawdown_duration_days
    - var_95, var_99
    - num_trades, win_rate, avg_winner, avg_loser
    - profit_factor
    - avg_holding_bars
    - max_consecutive_losses
    """

def compute_monthly_pnl(daily_pnl: dict) -> DataFrame:
    """Group daily PnL by year-month, return table."""

def compute_regime_performance(trades: list) -> dict:
    """Group trades by regime_at_entry, compute metrics per regime."""
```

### `src/optimization.py`

```python
# Purpose: Parameter grid search

def generate_orb_grid() -> list[dict]:
    """Return list of all ORB parameter combinations."""

def generate_mr_grid() -> list[dict]:
    """Return list of all MR parameter combinations."""

def generate_regime_grid() -> list[dict]:
    """Return list of all regime parameter combinations."""

def run_grid_search(sessions: dict, strategy: str, param_grid: list, 
                    slippage: float) -> DataFrame:
    """
    For each param set in grid:
      Run backtester
      Collect metrics
    Return DataFrame with params + metrics columns, sorted by Sharpe.
    Use multiprocessing or simple loop.
    """

def select_best_params(train_results: DataFrame, val_results: DataFrame, 
                       top_n: int = 5) -> dict:
    """
    From train_results, take top_n by Sharpe.
    Evaluate on validation.
    Return the params with best validation Sharpe.
    """
```

### `src/plots.py`

```python
# Purpose: Generate all figures

# Each function takes data and saves to outputs/figures/

def plot_price_series(df, filepath): ...
def plot_return_distribution(returns, filepath): ...
def plot_intraday_pattern_return(df, filepath): ...
def plot_intraday_pattern_volume(df, filepath): ...
def plot_orb_example(session_df, or_high, or_low, trades, filepath): ...
def plot_mr_example(session_df, vwap, z_score, trades, filepath): ...
def plot_regime_example(session_df, er, rv, regime, filepath): ...
def plot_param_heatmap(results_df, param_x, param_y, metric, filepath): ...
def plot_er_sensitivity(results_df, filepath): ...
def plot_cumulative_pnl(pnl_dict_of_strategies, filepath): ...
def plot_drawdown(daily_pnl, filepath): ...
def plot_trade_distribution(trades, filepath): ...
def plot_position_timeline(positions, dates, filepath): ...
def plot_slippage_sensitivity(slippage_results, filepath): ...
def plot_sharpe_vs_slippage(slippage_results, filepath): ...
```

### `src/utils.py`

```python
# Purpose: Helper functions

def time_to_minutes(time_int: int) -> int:
    """Convert HMMSS int to minutes since midnight. E.g., 91400 -> 554"""
    h = time_int // 10000
    m = (time_int % 10000) // 100
    return h * 60 + m

def is_in_session(time_int: int) -> bool:
    """Check if time_int is within day session (morning or afternoon)."""

def bars_between(time1: int, time2: int) -> int:
    """Approximate number of 1-min bars between two session times."""
```

### `main.py`

```python
# Purpose: Run the full pipeline end-to-end

# 1. Load and preprocess data
# 2. Split into train/val/test
# 3. Stage 1: ORB grid search (training)
# 4. Stage 2: MR grid search (training)
# 5. Stage 3: Validate ORB and MR (validation)
# 6. Stage 4: Regime grid search (training, fixed ORB+MR)
# 7. Stage 5: Validate regime (validation)
# 8. Final: Run all strategies on test
# 9. Run benchmarks
# 10. Generate all metrics, figures, tables
# 11. Save outputs
```

### `requirements.txt`

```
pandas>=1.5
numpy>=1.21
matplotlib>=3.5
seaborn>=0.11
scipy>=1.7
tqdm>=4.60
```

---

# PART 9: Codex Task List (Directly Usable)

Below is the ordered task list for code generation.

### Task 1: Create project structure
```
Create all directories: src/, outputs/figures/, outputs/tables/, outputs/logs/, notebooks/
Create src/__init__.py (empty)
Create requirements.txt
```

### Task 2: Implement config.py
```
All constants, paths, column names, session times, default parameters as specified above.
Use the ACTUAL column names from the dataset: 'date', 'time', 'hi1_open', 'hi1_high', 'hi1_low', 'hi1_close', 'hi1_volume'.
Time format is integer without leading zeros (91400 means 09:14:00).
```

### Task 3: Implement data_loader.py
```
load_raw_data(): Read CSV with pandas, rename columns (hi1_open->open, etc.), ensure correct dtypes.
parse_datetime(): Add datetime column. Handle time=0 (midnight), time=100 (00:01:00), etc.
  Key: str(time).zfill(6) converts 91400 -> '091400', 0 -> '000000', 100 -> '000100'.
```

### Task 4: Implement preprocessing.py
```
remove_duplicates(): df.drop_duplicates(subset=['date','time'], keep='last')
filter_day_session(): Keep rows where (91400<=time<=115900) OR (130000<=time<=162900)
validate_sessions(): Group by date, count bars, drop dates with < 300 bars. Print removed.
flag_zero_volume(): Add boolean column.
split_by_period(): Filter by date ranges.
get_sessions(): groupby('date') -> dict
```

### Task 5: Implement features.py
```
All functions as specified. Key edge cases:
- compute_vwap: handle cumulative_volume==0 by using expanding mean
- compute_zscore: set z=0 when rolling_std < 5
- compute_efficiency_ratio: set ER=0 when denominator==0
- All rolling features: first window-1 values = NaN or 0, handle gracefully
```

### Task 6: Implement regime.py
```
compute_extreme_vol_threshold(): Simple quantile calculation on training RV values.
classify_regime(): Three-way classification as specified.
```

### Task 7: Implement strategies.py
```
orb_signal(), mr_signal(), hybrid_signal() as specified.
Pure functions, no side effects.
```

### Task 8: Implement risk_manager.py
```
RiskManager class with check methods as specified.
All comparisons in index points.
```

### Task 9: Implement backtester.py
```
Trade dataclass, BacktestResult class, Backtester class.
Key logic:
- Loop through bars within session
- Skip first opening_window bars (for ORB)
- At each bar: check exits first, then entries
- Apply slippage to entry_price and exit_price
- Record each trade with all fields
- Force close at session end

CRITICAL: signal at bar i → execute at bar i+1 (use i+1 OPEN as execution price)
CRITICAL: last bar in session = index len-1; forced exit uses close of second-to-last bar
```

### Task 10: Implement metrics.py
```
compute_all_metrics(): From trades list and daily PnL dict.
Sharpe = mean(daily_pnl) / std(daily_pnl) * sqrt(252)
Handle edge case: if std==0 or no trades, return NaN.
```

### Task 11: Implement optimization.py
```
Grid generation functions: return lists of parameter dicts.
run_grid_search(): Loop (or parallel) over param sets, run backtester, collect metrics.
  For ~800 combinations × ~500 days × 376 bars ≈ manageable in <10 min.
select_best_params(): Take top-N from training, evaluate on validation, return best.
```

### Task 12: Implement plots.py
```
All plotting functions. Use matplotlib for main figures, seaborn for heatmaps.
Save to outputs/figures/ as PNG 300dpi.
```

### Task 13: Implement utils.py
```
Helper functions: time conversion, session checks, formatting.
```

### Task 14: Implement main.py
```
Full pipeline orchestration as specified. Print progress.
At end: print summary table of all results.
```

### Task 15: Generate README.md
```
Project overview, how to run, dependencies, results location.
```

---

# PART 10: Final Recommended Strategy

## Regime-Adaptive Hybrid Intraday Trading Strategy

**Recommended parameters (to be confirmed by optimization):**

| Component | Parameter | Expected Value | Rationale |
|-----------|-----------|---------------|-----------|
| ORB | opening_window | 30 min | Balance between noise and missed signals |
| ORB | buffer_points | 10 pts | ~5% of median OR width (169 pts) |
| ORB | stop_loss | 80 pts | ~0.3% of price; ~half of typical OR width |
| ORB | take_profit | 120 pts | 1.5× stop-loss; positive expectancy |
| MR | rolling_window | 60 min | 1-hour fair value |
| MR | z_entry | 2.0 | Standard statistical threshold |
| MR | z_exit | 0.25 | Close to fair value |
| MR | stop_loss | 50 pts | Tighter than ORB (smaller expected move) |
| MR | take_profit | 80 pts | 1.6× stop-loss |
| Regime | er_window | 60 min | 1-hour trend measurement |
| Regime | er_threshold | 0.35 | Calibrate on training data |
| Regime | rv_window | 60 min | 1-hour volatility measurement |
| Regime | extreme_vol_q | 0.90 | Top 10% volatility → stay flat |
| Risk | max_trades | 3 per session | Prevent over-trading |
| Risk | max_daily_loss | 200 pts | Capital preservation |
| Cost | slippage | 2 pts/side | Realistic base case |
| Cost | commission | 2 pts RT | Includes exchange fees |

**Expected characteristics (rough estimates; final judgement will depend on actual backtest results):**
- Trades: ~1–2 per day on average
- Win rate: 45–55%
- Average winner: 80–150 points
- Average loser: 50–80 points
- Break-even slippage: targeting > 5 points per side for robustness

**Performance evaluation criteria:** Rather than pre-specifying Sharpe ratio targets, strategy quality will be judged by: (1) out-of-sample stability relative to in-sample, (2) drawdown magnitude and duration, (3) slippage robustness (whether the strategy remains profitable under realistic costs), and (4) regime-adaptive hybrid outperforming both pure sub-strategies.

---

# PART 11: Why This Project Scores High

## Satisfies STAT8020 Requirements

| Requirement | How Addressed |
|-------------|---------------|
| 1. Introduction | Clear market background, motivation, contribution |
| 2. Algorithm description + rationale | Three strategies with full formulas and market logic |
| 3. In-sample / out-sample | Rigorous 3-way split with justification |
| 4. Backtesting results | Comprehensive metrics, multiple benchmarks |
| 5. Parameter optimization | Staged approach with anti-overfitting |
| 6. Slippage | Full sensitivity analysis with break-even |
| 7. Implementation difficulty | HSI-specific issues, execution, margin |
| 8. Risk management | Multi-layer protection |
| 9. Additional observations | Market regime analysis, COVID stress test |
| 10. References | Academic + practitioner sources |
| 11. Conclusion | Clear final recommendation |

## Grading Criteria Alignment

| Criterion | How Met |
|-----------|---------|
| **Presentation** | Professional structure, 17 figures, 19 tables, clean code |
| **Innovation** | Regime-adaptive switching (novel for this course); efficiency ratio |
| **Sound reasoning** | Each component motivated by market microstructure |
| **Comprehensiveness** | Covers all 11 required sections in depth |
| **Market understanding** | HSI-specific details (sessions, liquidity, night vs day, COVID) |
| **Clever observations** | Regime mismatch insight; VWAP + ER combination; forced intraday exit |

## Different from Previous Projects

| Previous Approach | Why This Is Different |
|-------------------|---------------------|
| VIX contrarian (daily) | Intraday; endogenous regime features; no external indicator |
| EWMA + Z-score (daily stock) | Minute-level futures; opening range (not EWMA); VWAP (not daily Z); regime switching (not averaging) |
| Bollinger Band | Session-specific opening range; adaptive threshold via regime |
| Filter rule | Dynamic regime classification vs. fixed filter |
| Kelly sizing | Point-based risk control; more practical for futures |

## Feasibility

- Dataset fully supports all required computations (OHLCV available)
- ~1,400 total backtests needed → runs in < 30 minutes on a modern laptop
- No external data required
- Standard Python libraries only (pandas, numpy, matplotlib)
- No ML model training (simple rule-based; deterministic and reproducible)

---

*End of Revised Project Proposal v2*
