# STAT8020 HSI Futures Project Group Writing Guide

项目题目：

**Testing and Improving Regime-Adaptive Intraday Strategies for Hang Seng Index Futures**

用途：这份 guide 是给四位组员分工写最终 report 用的。它说明：

- 项目完整逻辑是什么；
- 四位组员分别负责哪些 report 部分；
- 每个人需要看哪些代码、表格、图像和 notes；
- 写作时必须保持哪些统一口径；
- 如何把 `report/STAT8020_Project_Report_Draft.md` 改成最终提交版本。

主报告参考文件：

```text
report/STAT8020_Project_Report_Draft.md
```

最终逻辑参考：

```text
report/report_final_logic.md
```

---

## 1. 项目一句话逻辑

本项目不是简单寻找一个赚钱规则，而是完成一个完整的量化研究流程：

```text
提出 regime-adaptive HYBRID 假设
-> 实现数据清洗、特征、信号、回测、参数优化
-> 用 train / validation / test 严格检验原始 HYBRID
-> 发现 HYBRID 样本外失败
-> 诊断 MR / RANGE 和 high turnover 是主要拖累
-> 做 post-analysis supplementary optimization
-> 发现 LONG_OR_FLAT_FILTERED 在 test 中超过 benchmark
-> 谨慎报告：原 HYBRID 失败；long-or-flat 是探索性改进，需要进一步验证
```

最终 report 的核心不是“HYBRID 成功”，而是：

> The original pre-specified HYBRID strategy failed out of sample, but the diagnosis led to a post-analysis long-or-flat supplementary strategy that outperformed the benchmarks in this sample.

---

## 2. 最终结果口径

### 2.1 原始 HYBRID 结果

原始主策略：

```text
TREND   -> ORB
RANGE   -> MR
EXTREME -> flat / close
```

Test 结果：

| Strategy | Test PnL | Sharpe | Trades |
|---|---:|---:|---:|
| HYBRID | -3577 | -5.133 | 215 |
| ORB | -1954 | -1.687 | 164 |
| MR | -3227 | -3.558 | 229 |
| INTRADAY_LONG | 338 | 0.152 | 107 |
| FLAT | 0 | 0.000 | 0 |

结论：

- 原始 HYBRID 没有 outperform benchmark。
- 原始 HYBRID 不建议 live deployment。
- 负结果是主要 empirical finding，不要在报告中把它“改写成功”。

### 2.2 第一阶段补充优化

第一阶段：

```text
ORB_FILTERED_HYBRID
TREND -> ORB
RANGE -> flat
EXTREME -> flat / close
```

Test 结果：

| Strategy | Test PnL | Sharpe | Trades |
|---|---:|---:|---:|
| HYBRID original | -3577 | -5.133 | 215 |
| ORB_FILTERED_HYBRID_BASIC | -335 | -0.984 | 60 |
| ORB_FILTERED_HYBRID_FILTERED | -142 | -0.523 | 35 |
| INTRADAY_LONG | 338 | 0.152 | 107 |
| FLAT | 0 | 0.000 | 0 |

作用：

- 证明去掉 MR / RANGE 后亏损明显减少；
- 证明诊断方向正确；
- 但仍未超过 FLAT 和 INTRADAY_LONG；
- 因此需要第二阶段 long-or-flat 方向。

### 2.3 第二阶段补充优化

最终 supplementary strategy：

```text
LONG_OR_FLAT_FILTERED / long_or_flat_filtered_004
```

规则：

- opening window = 30 bars
- opening return >= 20 points
- ER >= 0.25
- max trades per day = 1
- long only
- hold toward close
- stop-loss = 160 points
- no take-profit

Test 结果：

| Strategy | Test PnL | Sharpe | Max DD | Trades | Profit factor |
|---|---:|---:|---:|---:|---:|
| LONG_OR_FLAT_FILTERED | 991 | 0.911 | -724 | 68 | 1.244 |
| INTRADAY_LONG | 338 | 0.152 | -2647 | 107 | 1.025 |
| FLAT | 0 | 0.000 | 0 | 0 | 0.000 |

结论：

- `LONG_OR_FLAT_FILTERED` 在 test 中超过 INTRADAY_LONG 和 FLAT；
- 但它是 post-analysis exploratory result；
- 不能写成原始预设策略；
- robustness caveats 必须保留：
  - 10-point slippage 下变负；
  - test profit 集中在 2020-03；
  - 需要 fresh holdout / walk-forward validation。

---

## 3. 四位组员分工

下面分工按内容量尽量均衡。每位成员负责 report 的一组章节，同时需要核对对应代码和输出。

### Member 1：Introduction + Data + Project Motivation

负责 report 部分：

```text
Title
Abstract
1. Introduction
2. Data Description and Preprocessing
```

主要写作任务：

- 说明 HSI futures 为什么适合日内策略研究。
- 解释原始研究问题：为什么要 test regime-adaptive HYBRID。
- 解释为什么 benchmark 包括 FLAT、INTRADAY_LONG、ORB、MR。
- 描述数据字段、时间解析、day-session 过滤、duplicate handling。
- 描述 train / validation / test split。
- 在 Abstract 中保持两阶段逻辑：Testing + Improving。

需要看的代码：

```text
src/config.py
src/data_loader.py
src/preprocessing.py
main.py
```

需要看的输出：

```text
outputs/tables/data_schema.csv
outputs/tables/data_cleaning_summary.csv
outputs/tables/session_counts.csv
outputs/figures/price_series.png
outputs/figures/return_distribution.png
outputs/figures/intraday_volume_pattern.png
```

对应 report draft 位置：

```text
report/STAT8020_Project_Report_Draft.md
lines around sections 1-2
```

建议写作重点：

- 数据清洗要写得具体；
- 说明为什么只用 day session；
- 说明 test period 是 2020-01-02 到 2020-06-09，包含 COVID shock，样本外更困难；
- 不要提前说策略成功，Abstract 里要同时写 HYBRID 失败和 supplementary improvement。

交付内容：

- 完整润色 Abstract、Introduction、Data sections；
- 检查所有数据数字是否和表格一致；
- 检查图 1-3 的 caption 是否自然。

---

### Member 2：Strategy Methodology + Backtesting Design + Risk Management

负责 report 部分：

```text
3. Strategy Methodology
4. Backtesting Design
Appendix B. Backtesting Pseudo-Code
```

主要写作任务：

- 解释 ORB 策略逻辑和经济动机。
- 解释 MR 策略逻辑和 VWAP / fair value / z-score。
- 解释 HYBRID 如何通过 regime classifier 切换 ORB 和 MR。
- 解释 ER、RV、EXTREME / TREND / RANGE。
- 解释 risk management。
- 解释 next-bar execution、slippage、commission、forced exit。
- 加入 3.5 `LONG_OR_FLAT_FILTERED` 的 supplementary methodology，但强调 post-analysis。

需要看的代码：

```text
src/features.py
src/strategies.py
src/regime.py
src/risk_manager.py
src/backtester.py
strategy_optimization_exploration/scripts/exploratory_backtester.py
```

需要看的输出：

```text
outputs/tables/feature_sanity_summary.csv
outputs/tables/final_selected_params.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_selected_params.csv
```

对应 report draft 位置：

```text
sections 3-4
Appendix B
```

建议写作重点：

- 明确原始 HYBRID 是 pre-specified main strategy。
- `LONG_OR_FLAT_FILTERED` 是 diagnosis 后的 supplementary rule，不要写成最初就设计好的主策略。
- Backtesting design 一定要强调 no look-ahead：signal at t, execute at t+1 open。
- 成本设定：2 points slippage per side + 2 points round-trip commission。

交付内容：

- 完成策略公式和文字解释；
- 检查策略逻辑和代码是否一致；
- 确保 3.5 不喧宾夺主，只作为 supplementary methodology。

---

### Member 3：Optimization + Original Empirical Results + Risk/Robustness

负责 report 部分：

```text
5. Parameter Optimization
6. Empirical Results
7. Slippage and Transaction Cost Analysis
8. Robustness and Market Regime Analysis
Appendix A. Parameter Grids
```

主要写作任务：

- 解释 staged optimization：先 ORB，再 MR，再 regime/HYBRID。
- 说明 medium grid 为什么用于 final result。
- 报告原始 HYBRID、ORB、MR、benchmark 的 train / validation / test 结果。
- 解释为什么原始 HYBRID 失败。
- 解释 slippage sensitivity：HYBRID 即使低 slippage 也弱，说明 gross signal 不够强。
- 解释 monthly PnL 和 regime performance。

需要看的代码：

```text
src/optimization.py
src/metrics.py
src/plots.py
main.py
```

需要看的输出：

```text
outputs/tables/final_selected_params.csv
outputs/tables/orb_train_grid.csv
outputs/tables/orb_validation_top5.csv
outputs/tables/mr_train_grid.csv
outputs/tables/mr_validation_top5.csv
outputs/tables/regime_train_grid.csv
outputs/tables/regime_validation_top5.csv
outputs/tables/performance_summary.csv
outputs/tables/risk_metrics.csv
outputs/tables/trade_statistics.csv
outputs/tables/slippage_sensitivity.csv
outputs/tables/monthly_pnl.csv
outputs/tables/regime_performance.csv
outputs/logs/all_trades_hybrid.csv
outputs/figures/out_of_sample_cumulative_pnl.png
outputs/figures/hybrid_drawdown.png
outputs/figures/slippage_sensitivity.png
outputs/figures/monthly_pnl_heatmap.png
```

对应 report draft 位置：

```text
sections 5-8
Appendix A
```

关键数字：

```text
HYBRID test PnL = -3577
HYBRID test Sharpe = -5.133
ORB test PnL = -1954
MR test PnL = -3227
INTRADAY_LONG test PnL = 338
FLAT test PnL = 0
HYBRID test trades = 215
HYBRID profit factor = 0.619
```

建议写作重点：

- 原始 HYBRID 失败是核心 empirical result。
- 不要因为后面 long-or-flat 成功就淡化第 6 节的 negative result。
- 解释 MR/RANGE 为什么拖累：regime_performance 中 RANGE test loss 很大。
- 解释 benchmark 选择：
  - FLAT = 不交易基准；
  - INTRADAY_LONG = 简单日内多头基准；
  - ORB/MR = component benchmark。

交付内容：

- 完成原始结果章节；
- 检查表格数值；
- 检查风险和 robustness 解释；
- 确保第 5.3 supplementary protocol 与 Member 4 的第 11 节一致。

---

### Member 4：Supplementary Optimization + Discussion + Conclusion + Reproducibility

负责 report 部分：

```text
9. Implementation Difficulty and Real-Time Trading Issues
10. Discussion
11. Strategy Improvement and Exploratory Optimization
12. Conclusion
Appendix C. Reproducibility Note
References
```

主要写作任务：

- 解释实盘实现困难：slippage、bid-ask、午休、数据质量、参数漂移。
- 整合项目讨论：为什么 HYBRID 理论上有价值但实证失败。
- 写完整 improvement narrative：
  1. HYBRID failed；
  2. diagnosis found MR/RANGE drag；
  3. first-stage ORB-filtered Hybrid reduced loss but did not beat benchmark；
  4. second-stage LONG_OR_FLAT_FILTERED beat benchmark；
  5. result is post-analysis exploratory。
- 写最终 conclusion。
- 检查 Appendix C reproduction commands。

需要看的代码：

```text
main.py
strategy_optimization_exploration/scripts/run_exploration.py
strategy_optimization_exploration/scripts/run_long_or_flat_final.py
strategy_optimization_exploration/scripts/exploratory_optimization.py
strategy_optimization_exploration/scripts/exploratory_backtester.py
```

需要看的输出：

First-stage outputs:

```text
outputs/tables/supplementary_strategy_comparison.csv
outputs/tables/supplementary_improvement_summary.csv
outputs/tables/supplementary_regime_trade_breakdown.csv
```

Second-stage outputs:

```text
strategy_optimization_exploration/outputs/tables/exploration_validation_ranking.csv
strategy_optimization_exploration/outputs/tables/exploration_test_selected_results.csv
strategy_optimization_exploration/outputs/tables/exploration_improvement_vs_baseline.csv
strategy_optimization_exploration/outputs/tables/exploration_best_strategy_summary.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_performance_summary.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_trade_statistics.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_monthly_pnl.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_slippage_sensitivity.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_improvement_vs_baseline.csv
strategy_optimization_exploration/notes/long_or_flat_final_result_summary.md
strategy_optimization_exploration/notes/final_recommendations.md
```

对应 report draft 位置：

```text
sections 9-12
Appendix C
References
```

关键数字：

```text
ORB_FILTERED_HYBRID_BASIC test PnL = -335
ORB_FILTERED_HYBRID_FILTERED test PnL = -142
LONG_OR_FLAT_FILTERED test PnL = 991
LONG_OR_FLAT_FILTERED Sharpe = 0.911
LONG_OR_FLAT_FILTERED trades = 68
LONG_OR_FLAT_FILTERED profit factor = 1.244
Long-or-flat beats INTRADAY_LONG by 653 points
Long-or-flat beats FLAT by 991 points
5-point slippage PnL = 480
10-point slippage PnL = -1202
March 2020 PnL = 1455
```

建议写作重点：

- 第 11 节必须保持“post-analysis exploratory”口径。
- 不能写成“我们一开始就选择 long-or-flat，所以策略成功”。
- 要明确 first-stage improvement 的作用：验证诊断，但未 beat benchmark。
- 要明确 second-stage improvement 的作用：直接过滤 INTRADAY_LONG benchmark，test beat benchmark。
- Robustness caveats 必须保留。

交付内容：

- 完成第 9-12 节润色；
- 确保 conclusion 是 two-part conclusion；
- 检查 references 格式；
- 检查 reproduction commands 是否可读。

---

## 4. Report Section 与文件对应表

| Report section | 主要负责 | 代码文件 | 输出文件 |
|---|---|---|---|
| Abstract | Member 1 | 全项目摘要 | `performance_summary.csv`, `long_or_flat_final_performance_summary.csv` |
| 1 Introduction | Member 1 | `PROJECT_PROPOSAL_v2.md` | 无特定表格 |
| 2 Data | Member 1 | `data_loader.py`, `preprocessing.py`, `config.py` | `data_schema.csv`, `data_cleaning_summary.csv`, `session_counts.csv` |
| 3 Methodology | Member 2 | `features.py`, `strategies.py`, `regime.py`, `risk_manager.py` | `final_selected_params.csv` |
| 4 Backtesting | Member 2 | `backtester.py`, `metrics.py` | `stage3_backtest_metrics.csv`, trade logs |
| 5 Optimization | Member 3 | `optimization.py` | train grids, validation top5, `final_selected_params.csv` |
| 6 Empirical Results | Member 3 | `main.py`, `metrics.py` | `performance_summary.csv`, `trade_statistics.csv` |
| 7 Slippage | Member 3 | `main.py`, `plots.py` | `slippage_sensitivity.csv`, slippage figures |
| 8 Robustness / Regime | Member 3 | `metrics.py` | `monthly_pnl.csv`, `regime_performance.csv` |
| 9 Implementation | Member 4 | `backtester.py`, `risk_manager.py` | no single table; use discussion |
| 10 Discussion | Member 4 | all | all main findings |
| 11 Improvement | Member 4 | `strategy_optimization_exploration/scripts/` | supplementary and `long_or_flat_final_*` outputs |
| 12 Conclusion | Member 4 | all | final comparison tables |
| Appendix | Members 2-4 | all relevant code | grids and reproduction outputs |

---

## 5. 统一写作口径

所有人写作时统一用以下表述。

### 5.1 原始策略

推荐：

> The original pre-specified Hybrid strategy failed to outperform the benchmark out of sample.

不要写：

> The Hybrid strategy was successful.

### 5.2 补充优化

推荐：

> The long-or-flat strategy is a post-analysis supplementary improvement motivated by the failure diagnosis.

不要写：

> We selected LONG_OR_FLAT_FILTERED as the main strategy from the beginning.

### 5.3 Benchmark

推荐：

> FLAT tests whether trading adds value over doing nothing. INTRADAY_LONG tests whether a complex intraday strategy improves over simple daily long exposure. ORB and MR are component benchmarks for the Hybrid strategy.

### 5.4 Caveats

必须保留：

```text
post-analysis exploratory
requires further validation
sensitive to high slippage
profit concentrated in March 2020
not confirmed live-trading alpha
```

---

## 6. 组员拿到代码后如何开始

建议每个人按这个顺序：

1. 先读 `README.md` 的最终结论和运行流程。
2. 再读 `report/report_final_logic.md`。
3. 打开 `report/STAT8020_Project_Report_Draft.md`，只改自己负责章节。
4. 查看自己章节对应的代码和输出文件。
5. 不要重新跑大规模优化，除非组内统一决定。
6. 不要改原始 `outputs/` 中的结果。
7. 如果需要引用 long-or-flat，使用 `strategy_optimization_exploration/outputs/` 下 `long_or_flat_final_*` 文件。

---

## 7. 推荐复现命令

完整复现：

```bash
python -m py_compile src/*.py main.py
python main.py --medium
python main.py --supplementary
python -m py_compile strategy_optimization_exploration/scripts/*.py
python strategy_optimization_exploration/scripts/run_exploration.py --fast
python strategy_optimization_exploration/scripts/run_long_or_flat_final.py
```

只复现最终报告主要结果：

```bash
python main.py --medium
python strategy_optimization_exploration/scripts/run_long_or_flat_final.py
```

---

## 8. 最终交付前检查清单

每个成员完成自己部分后检查：

- [ ] 自己负责章节和 report draft 的编号一致。
- [ ] 数字和 CSV 输出一致。
- [ ] 图表路径正确。
- [ ] 没有把 `LONG_OR_FLAT_FILTERED` 写成原始主策略。
- [ ] 没有删除 HYBRID 失败这个主结论。
- [ ] caveats 保留完整。
- [ ] 语言风格和其他章节一致。
- [ ] 引用和参考文献格式统一。

最终整合时检查：

- [ ] title 使用 `Testing and Improving Regime-Adaptive Intraday Strategies for Hang Seng Index Futures`。
- [ ] group member names 和 date 已填写。
- [ ] Abstract 同时包含 HYBRID failure 和 supplementary improvement。
- [ ] Section 11 包含 first-stage 和 second-stage improvement。
- [ ] Conclusion 是 two-part conclusion。
- [ ] PDF / Word 中图表没有错位。

