# EXPLORATION_RUN_LOG.md

## 2026-05-24 00:00

Command:
```bash
mkdir -p strategy_optimization_exploration/scripts strategy_optimization_exploration/outputs/tables strategy_optimization_exploration/outputs/figures strategy_optimization_exploration/outputs/logs strategy_optimization_exploration/notes
```

Result:

* Success

Output summary:

* Created the isolated exploration directory structure.

Error if failed:

```text
None.
```

Fix attempted:

* None.

Next action:

* Create exploratory scripts and notes, then run compile and fast exploration.

## 2026-05-24 00:00

Command:
```bash
python -m py_compile src/*.py main.py
python -m py_compile strategy_optimization_exploration/scripts/*.py
```

Result:

* Success

Output summary:

* Original source files, `main.py`, and exploratory scripts compiled without syntax errors.

Error if failed:

```text
None.
```

Fix attempted:

* None.

Next action:

* Run fast exploration.


## 2026-05-25 00:09

Command:
```bash
python strategy_optimization_exploration/scripts/run_exploration.py --fast
```

Result:

* Success

Output summary:

* Exploration completed in 225.74 seconds.

Error if failed:

```text
None.
```

Fix attempted:

* None.

Next action:

* Review outputs and notes.

## 2026-05-24 00:00

Command:
```bash
find strategy_optimization_exploration -maxdepth 3 -type f | sort
python - <<'PY'
import pandas as pd
for f in ['baseline_summary','exploration_validation_ranking','exploration_test_selected_results','exploration_improvement_vs_baseline','exploration_best_strategy_summary','exploration_regime_breakdown']:
    p=f'strategy_optimization_exploration/outputs/tables/{f}.csv'
    df=pd.read_csv(p)
    print(p, df.shape)
PY
find strategy_optimization_exploration/outputs/figures -maxdepth 1 -type f -name '*.png' -print | sort | wc -l
find strategy_optimization_exploration/outputs/tables -maxdepth 1 -type f -name '*.csv' -print | sort | wc -l
```

Result:

* Success

Output summary:

* Verified required exploration tables and figures were created. The fast run produced 12 CSV tables/log tables and 7 PNG figures.
* `exploration_all_results.csv` contains 20 train rows, 20 validation rows, and 5 test rows for validation-selected candidates.

Error if failed:

```text
None.
```

Fix attempted:

* None.

Next action:

* Report final exploration outcome.

## 2026-05-25 00:39

Command:
```bash
python strategy_optimization_exploration/scripts/run_exploration.py --fast
```

Result:

* Success

Output summary:

* Exploration completed in 408.81 seconds.

Error if failed:

```text
None.
```

Fix attempted:

* None.

Next action:

* Review outputs and notes.

## 2026-05-25 00:39

Command:
```bash
python -m py_compile src/*.py main.py
python -m py_compile strategy_optimization_exploration/scripts/*.py
```

Result:

* Success

Output summary:

* Original source files, `main.py`, and updated directional exploration scripts compiled without syntax errors before the second-stage run.

Error if failed:

```text
None.
```

Fix attempted:

* None.

Next action:

* Review second-stage directional exploration results.

## 2026-05-25 00:40

Command:
```bash
python - <<'PY'
import pandas as pd
val=pd.read_csv('strategy_optimization_exploration/outputs/tables/exploration_validation_ranking.csv')
test=pd.read_csv('strategy_optimization_exploration/outputs/tables/exploration_test_selected_results.csv')
imp=pd.read_csv('strategy_optimization_exploration/outputs/tables/exploration_improvement_vs_baseline.csv')
print(val.head(12))
print(test)
print(imp)
PY
```

Result:

* Success

Output summary:

* Confirmed 36 train candidates, 36 validation candidates, and 5 test evaluations for validation-screened candidates.
* `LONG_OR_FLAT_FILTERED` / `long_or_flat_filtered_004` ranked #3 on validation and achieved test PnL 991.0 points, Sharpe 0.911, 68 trades, and profit factor 1.244.
* This candidate beats original HYBRID, ORB, INTRADAY_LONG, and FLAT on the test split.

Error if failed:

```text
None.
```

Fix attempted:

* None.

Next action:

* Update result summary, final recommendations, and report-section draft with benchmark-beating but post-analysis wording.

## 2026-05-25 00:40

Command:
```bash
python -m py_compile strategy_optimization_exploration/scripts/*.py
```

Result:

* Success

Output summary:

* Recompiled updated exploration scripts after improving summary handling for the top validation strategy and the benchmark-beating validation-screened candidate.

Error if failed:

```text
None.
```

Fix attempted:

* None.

Next action:

* Report benchmark-beating exploratory result with appropriate caveats.

## 2026-05-25 00:59

Command:
```bash
python strategy_optimization_exploration/scripts/run_long_or_flat_final.py
```

Result:

* Success

Output summary:

* Generated report-ready final supplementary outputs for `LONG_OR_FLAT_FILTERED` under `strategy_optimization_exploration/outputs/`.
* Runtime seconds: 72.06.

Error if failed:

```text
None.
```

Fix attempted:

* None.

Next action:

* Use `notes/long_or_flat_final_result_summary.md` and `notes/report_section_strategy_optimization.md` for the supplementary report section.
