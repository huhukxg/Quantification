# Final Recommendations

1. The main report should still keep the original HYBRID as the main pre-specified strategy.
2. A supplementary improvement section is now worthwhile, because one validation-screened exploratory candidate beats both INTRADAY_LONG and FLAT on test.
3. The benchmark-beating candidate is `LONG_OR_FLAT_FILTERED` / `long_or_flat_filtered_004`. It ranked #3 on validation, so it was not chosen by looking at test alone.
4. Test result: 991.0 points, Sharpe 0.911, 68 trades, profit factor 1.244. This beats INTRADAY_LONG by 653.0 points and FLAT by 991.0 points.
5. Robustness caveats: test profit is concentrated in March 2020, and the strategy becomes negative under 10-point slippage per side.
6. The strategy is promising as a supplementary exploratory improvement, but not strong enough to present as confirmed live alpha. It was designed after seeing the original HYBRID failure.
7. Careful wording: say the original HYBRID failed; a post-analysis long-or-flat filter improved performance and beat the benchmarks in this sample; further walk-forward or truly fresh out-of-sample testing would be needed.
