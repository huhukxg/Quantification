# Final Report Logic

## Core Story
The report should not be framed as "we found a profitable HYBRID strategy." The stronger and more honest story is:

1. The project proposed a market-regime adaptive HYBRID strategy.
2. The full data pipeline, feature engineering, backtester, cost model, train/validation/test split, and benchmark comparison were implemented.
3. The original pre-specified HYBRID failed out of sample.
4. Trade-level diagnosis showed that RANGE / MR trades and high turnover were major problems.
5. A post-analysis supplementary exploration tested lower-turnover and directional filters.
6. The best validation-screened supplementary strategy, `LONG_OR_FLAT_FILTERED`, beat INTRADAY_LONG and FLAT on the test sample.
7. Because this strategy was designed after observing the original failure, it is exploratory and requires further validation.

## Recommended Emphasis
Main result:

> The original HYBRID strategy does not outperform the benchmark and is not recommended for live deployment.

Supplementary result:

> A post-analysis long-or-flat filter outperforms the benchmark in this sample, suggesting that directional filtering is more promising than regime-switching with mean reversion.

Important caveats:

- The result is post-analysis.
- Test profit is concentrated in March 2020.
- Performance becomes negative under 10-point slippage.
- More validation is required before claiming live-trading alpha.

## Suggested Presentation Order
1. Introduction and original research question.
2. Data and preprocessing.
3. Original ORB, MR, and HYBRID methodology.
4. Backtesting and parameter optimization protocol.
5. Original empirical results: HYBRID fails.
6. Diagnosis: MR / RANGE and turnover are the drag.
7. Supplementary optimization: `LONG_OR_FLAT_FILTERED`.
8. Robustness caveats.
9. Conclusion: original strategy fails; supplementary direction is promising but exploratory.
