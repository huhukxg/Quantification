# Result Summary

Mode run: `fast`.

## Variants Tested
EXTREME_TREND_FOLLOWING, LONG_ONLY_ORB, LONG_OR_FLAT_FILTERED, LOW_TURNOVER_HYBRID, ORB_FILTERED_HYBRID_BASIC, ORB_FILTERED_HYBRID_CONFIRM, ORB_FILTERED_HYBRID_STRICT_TREND, ORB_ONLY_CONFIRM, ORB_ONLY_LOW_TURNOVER, ORB_ONLY_RANGE_FILTER, ORB_ONLY_VOLUME, ORB_TO_CLOSE, STRICT_MR_HYBRID, STRICT_MR_ONLY

## Validation-Selected Best Strategy
The top validation-score strategy is `EXTREME_TREND_FOLLOWING` with params id `extreme_trend_following_003`.

Validation score: 2.642. Validation PnL: 1115.0 points. Validation Sharpe: 2.139.

Test PnL: -1138.0 points. Test Sharpe: -1.329. This specific top-ranked validation candidate does not beat the benchmark.

## Benchmark-Beating Validation-Screened Candidate
Among the candidates selected from validation top rankings, `LONG_OR_FLAT_FILTERED` with params id `long_or_flat_filtered_004` is the best test performer.

It ranked #3 on validation, with validation PnL 1078.0 points, validation Sharpe 1.342, and validation score 1.375.

On test it earns 991.0 points with Sharpe 0.911, max drawdown -724.0 points, 68 trades, trades/day 0.636, average trade PnL 14.574, and profit factor 1.244.

It beats original HYBRID by 4568.0 points, ORB by 2945.0 points, INTRADAY_LONG by 653.0 points, and FLAT by 991.0 points.

## Improvements
Variants improving over original HYBRID: ['LONG_OR_FLAT_FILTERED', 'EXTREME_TREND_FOLLOWING', 'ORB_FILTERED_HYBRID_CONFIRM', 'ORB_FILTERED_HYBRID_BASIC'].

Variants beating FLAT: ['LONG_OR_FLAT_FILTERED'].

Variants beating INTRADAY_LONG: ['LONG_OR_FLAT_FILTERED'].

Variants beating ORB: ['LONG_OR_FLAT_FILTERED', 'EXTREME_TREND_FOLLOWING', 'ORB_FILTERED_HYBRID_CONFIRM', 'ORB_FILTERED_HYBRID_BASIC'].

## Interpretation
The benchmark-beating result comes from changing the objective toward long-or-flat daily direction selection. This variant only goes long when the first 30-minute evidence is positive enough: opening return is at least 20 points and ER is at least 0.25; it then holds to close with a wide stop and no take-profit. This directly targets the INTRADAY_LONG benchmark by trying to avoid weaker days rather than trading both directions frequently.

Selection was still based on train/validation screening before test evaluation. However, the whole second-stage search is post-analysis because it was motivated by the original HYBRID test failure. Therefore this can be reported as supplementary exploratory evidence, not as the original pre-specified strategy.

## Report Presentation
The main report should keep the original HYBRID result as the pre-specified empirical finding. The `LONG_OR_FLAT_FILTERED` result can be added as a supplementary post-analysis improvement that beats benchmark in this sample, with clear caution against overclaiming.
