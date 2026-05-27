# STAT8020 Strategy Optimization Exploration

This folder contains post-analysis exploratory strategy improvement work for the HSI futures intraday project.

The original project results are not overwritten. All exploratory code, tables, figures, logs, and notes are kept under this folder.

The exploration is motivated by the original empirical finding that the pre-specified HYBRID strategy underperformed out of sample, especially because RANGE / mean-reversion trades were weak. These variants are exploratory and should not be described as the original pre-specified strategy.

Main command:

```bash
python strategy_optimization_exploration/scripts/run_exploration.py --fast
```

Optional larger run:

```bash
python strategy_optimization_exploration/scripts/run_exploration.py --medium
```

