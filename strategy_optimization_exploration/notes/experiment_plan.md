# Experiment Plan

1. Load original cleaned data using existing project loaders.
2. Split data chronologically into train, validation, and test using the original project split.
3. Load original medium-mode baseline results from `outputs/tables/performance_summary.csv`.
4. Generate exploratory variants with conservative grids.
5. Evaluate all candidates on train and validation.
6. Select candidates using validation score only.
7. Evaluate selected candidates on test once.
8. Save all exploratory outputs under `strategy_optimization_exploration/outputs/`.
9. Report results honestly as post-analysis exploratory improvements.

