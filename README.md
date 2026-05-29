# STAT8020 Project: HSI Futures Intraday Strategy Research

This repository contains the code and report materials for the STAT8020 project:

**Testing and Improving Regime-Adaptive Intraday Strategies for Hang Seng Index Futures**

Code repository: [huhukxg/Quantification](https://github.com/huhukxg/Quantification)

## Project Overview

The project evaluates intraday trading strategies on one-minute Hang Seng Index futures data. The original research question is whether a regime-adaptive Hybrid strategy can outperform simpler rule-based strategies and benchmarks after realistic transaction costs.

The workflow covers data cleaning, session validation, feature construction, strategy implementation, staged parameter selection, out-of-sample testing, trade-level diagnosis, and a supplementary post-analysis improvement experiment.

The main conclusion is deliberately cautious:

- The original pre-specified Hybrid strategy does not outperform the benchmarks in the 2020 test period.
- The Hybrid strategy loses 3,577 index points with a Sharpe ratio of -5.133.
- The Daily Intraday Long-only benchmark earns 338 points with a Sharpe ratio of 0.152.
- A supplementary post-analysis Long-or-Flat filter improves the test result to 991 points with a Sharpe ratio of 0.911.
- The Long-or-Flat result is exploratory and should not be treated as the original pre-specified strategy.

## Repository Structure

```text
.
|-- main.py
|-- requirements.txt
|-- hi1_20170701_20200609.csv
|-- src/
|   |-- backtester.py
|   |-- config.py
|   |-- data_loader.py
|   |-- features.py
|   |-- metrics.py
|   |-- optimization.py
|   |-- plots.py
|   |-- preprocessing.py
|   |-- regime.py
|   |-- risk_manager.py
|   |-- strategies.py
|   `-- utils.py
|-- outputs/
|   |-- figures/
|   |-- logs/
|   `-- tables/
|-- strategy_optimization_exploration/
|   |-- scripts/
|   |-- outputs/
|   `-- notes/
|-- report/
|   |-- STAT8020_Project_Report_Draft.md
|   `-- report_final_logic.md
`-- 8020_report (30.5.2026)/
    |-- report.tex
    |-- report.pdf
    |-- hku_logo.png
    `-- figures/
```

## Environment Setup

Use Python 3.10 or later.

```bash
python -m pip install -r requirements.txt
```

Main Python dependencies include:

```text
pandas
numpy
matplotlib
seaborn
scipy
tqdm
```

Optional syntax checks:

```bash
python -m py_compile src/*.py main.py
python -m py_compile strategy_optimization_exploration/scripts/*.py
```

## Reproducing the Main Results

Run the medium-mode pipeline from the repository root:

```bash
python main.py --medium
```

This regenerates the original ORB, MR, Hybrid, and benchmark outputs used in the main report.

Important outputs:

```text
outputs/tables/final_selected_params.csv
outputs/tables/performance_summary.csv
outputs/tables/risk_metrics.csv
outputs/tables/trade_statistics.csv
outputs/tables/monthly_pnl.csv
outputs/tables/regime_performance.csv
outputs/tables/slippage_sensitivity.csv
outputs/tables/report_summary.md
outputs/figures/
outputs/logs/
```

## Supplementary Post-Analysis Experiments

The first supplementary experiment can be reproduced with:

```bash
python main.py --supplementary
```

The second-stage exploratory search is isolated under `strategy_optimization_exploration/`:

```bash
python strategy_optimization_exploration/scripts/run_exploration.py --fast
```

The final Long-or-Flat output pass can be reproduced with:

```bash
python strategy_optimization_exploration/scripts/run_long_or_flat_final.py
```

These supplementary outputs are intentionally separated from the original pre-specified strategy outputs.

## Final Report

The final LaTeX report is located at:

```text
8020_report (30.5.2026)/report.tex
```

The compiled PDF is:

```text
8020_report (30.5.2026)/report.pdf
```

To rebuild the PDF locally with TinyTeX:

```bash
cd "8020_report (30.5.2026)"
env PATH="/Users/xuwantong/Library/TinyTeX/bin/universal-darwin:$PATH" latexmk -xelatex -interaction=nonstopmode -halt-on-error report.tex
```

If another TeX distribution is installed and already on `PATH`, the shorter command should also work:

```bash
latexmk -xelatex -interaction=nonstopmode -halt-on-error report.tex
```

## Result Summary

Original test-period performance:

| Strategy | Test PnL points | Sharpe | Trades |
|---|---:|---:|---:|
| HYBRID | -3,577 | -5.133 | 215 |
| ORB | -1,954 | -1.687 | 164 |
| MR | -3,227 | -3.558 | 229 |
| INTRADAY_LONG | 338 | 0.152 | 107 |
| FLAT | 0 | 0.000 | 0 |

Final supplementary Long-or-Flat comparison:

| Strategy | Test PnL points | Sharpe | Max drawdown | Trades | Profit factor |
|---|---:|---:|---:|---:|---:|
| LONG_OR_FLAT_FILTERED | 991 | 0.911 | -724 | 68 | 1.244 |
| HYBRID | -3,577 | -5.133 | -3,689 | 215 | 0.619 |
| ORB | -1,954 | -1.687 | -3,187 | 164 | 0.822 |
| MR | -3,227 | -3.558 | -3,276 | 229 | 0.692 |
| INTRADAY_LONG | 338 | 0.152 | -2,647 | 107 | 1.025 |
| FLAT | 0 | 0.000 | 0 | 0 | 0.000 |

## Interpretation Notes

The original Hybrid strategy remains the main pre-specified empirical test, and it fails out of sample. The Long-or-Flat filter is reported as a supplementary post-analysis result motivated by the observed Hybrid failure and trade-level diagnosis.

The supplementary result should be interpreted with care because:

- it was developed after observing the original test-period weakness;
- its positive test PnL is concentrated in March 2020;
- it turns negative under a 10-point slippage-per-side stress test;
- it requires fresh holdout or walk-forward validation before any deployment claim.

## Key Design Choices

- Data are restricted to the day session.
- Entries use next-bar execution.
- Slippage and round-trip commission are included.
- Parameters are selected on train and validation periods before test evaluation.
- Post-analysis experiments are isolated from the original pipeline.
- Output tables, figures, and trade logs are saved as files for auditability.

