# Strategy Improvement and Exploratory Optimization

The original HYBRID strategy remains the main pre-specified strategy in this project. Its negative out-of-sample result is not replaced by the exploratory work. After observing that RANGE / mean-reversion trades were a major drag, a separate post-analysis optimization was performed under `strategy_optimization_exploration/`.

The second-stage exploration added directionally filtered variants designed to compete directly with the INTRADAY_LONG benchmark. These include `LONG_OR_FLAT_FILTERED`, `LONG_ONLY_ORB`, `ORB_TO_CLOSE`, and `EXTREME_TREND_FOLLOWING`, in addition to the previous ORB-filtered Hybrid and low-turnover variants. Candidate selection used train and validation data only; the test period was reserved for final comparison of validation-screened candidates.

The highest validation-score candidate was `EXTREME_TREND_FOLLOWING` with params id `extreme_trend_following_003`. It had validation Sharpe 2.139, but did not generalize to test, where it lost -1138.0 points. This shows that validation strength alone was not fully robust.

The best test result among validation-screened candidates was `LONG_OR_FLAT_FILTERED` with params id `long_or_flat_filtered_004`. It ranked #3 on validation, with validation PnL 1078.0 points and validation Sharpe 1.342. On the test split it achieved PnL 991.0 points and Sharpe 0.911, with 68 trades. This beats the original HYBRID, ORB, INTRADAY_LONG, and FLAT benchmarks in the test sample.

The economic interpretation is that a long-or-flat filter is more suitable than the original regime-switching HYBRID in this dataset. Instead of trying to profit from both trend and range regimes, it only takes long exposure when early-session evidence is favorable and otherwise remains flat. This reduces harmful short/MR exposure while preserving part of the positive long-only benchmark behavior.

Robustness checks are mixed. The strategy remains profitable at 5 points of slippage per side but becomes negative at 10 points. Its test profit is also concentrated in March 2020. Because this is post-analysis exploratory work, the benchmark-beating result should be interpreted as a promising supplementary improvement rather than confirmatory evidence of a deployable strategy. A fresh holdout period or walk-forward validation would be needed before making stronger claims.
