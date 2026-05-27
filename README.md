# STAT8020 HSI Futures Intraday Strategy Project

项目题目：

**Testing and Improving Regime-Adaptive Intraday Strategies for Hang Seng Index Futures**

本项目是 STAT8020 Quantitative Strategies and Algorithmic Trading 课程项目。项目使用 `hi1_20170701_20200609.csv` 的恒生指数期货 1 分钟 OHLCV 数据，完成一个从策略假设、数据清洗、特征工程、回测、参数选择、样本外检验、失败诊断到补充优化的完整量化研究流程。

项目最终采用“两阶段”逻辑：

1. **Testing**：检验原始 pre-specified regime-adaptive `HYBRID` 策略是否能 outperform benchmark。
2. **Improving**：在原始策略失败后，基于 trade-level diagnosis 做 post-analysis supplementary optimization，最终得到 `LONG_OR_FLAT_FILTERED` 作为探索性改进。

重要原则：

- 原始 HYBRID 结果不被覆盖、不被改写。
- 优化探索结果独立保存在 `strategy_optimization_exploration/`。
- `LONG_OR_FLAT_FILTERED` 是 post-analysis exploratory result，不是原始预设主策略。

---

## 1. 最终结论

### 1.1 原始 HYBRID 主策略失败

原始主策略：

```text
TREND   -> ORB
RANGE   -> MR
EXTREME -> flat / close
```

Medium-mode test 结果：

| Strategy | Test PnL points | Sharpe | Trades |
|---|---:|---:|---:|
| HYBRID | -3577 | -5.133 | 215 |
| ORB | -1954 | -1.687 | 164 |
| MR | -3227 | -3.558 | 229 |
| INTRADAY_LONG | 338 | 0.152 | 107 |
| FLAT | 0 | 0.000 | 0 |

结论：

- 原始 HYBRID 没有 outperform benchmark。
- MR / RANGE trades 是主要拖累。
- HYBRID turnover 较高，交易成本和错误信号持续累积。
- 原始 HYBRID 不建议用于 live deployment。

### 1.2 第一阶段优化：ORB-filtered Hybrid

第一阶段优化思路是去掉 RANGE / MR：

```text
TREND   -> ORB
RANGE   -> flat
EXTREME -> flat / close
```

Test 结果：

| Strategy | Test PnL points | Sharpe | Trades |
|---|---:|---:|---:|
| HYBRID original | -3577 | -5.133 | 215 |
| ORB_FILTERED_HYBRID_BASIC | -335 | -0.984 | 60 |
| ORB_FILTERED_HYBRID_FILTERED | -142 | -0.523 | 35 |
| INTRADAY_LONG | 338 | 0.152 | 107 |
| FLAT | 0 | 0.000 | 0 |

解释：

- 去掉 RANGE / MR 后，亏损和交易次数大幅下降。
- 这验证了“MR / RANGE 是主要拖累”的诊断。
- 但该阶段仍没有超过 `FLAT` 和 `INTRADAY_LONG`。

### 1.3 第二阶段优化：LONG_OR_FLAT_FILTERED

第二阶段改变目标：不再尝试复杂双向 regime switching，而是直接改进 `INTRADAY_LONG` benchmark。

最终 supplementary strategy：

```text
LONG_OR_FLAT_FILTERED / long_or_flat_filtered_004
```

核心规则：

- opening window = 30 bars
- opening return >= 20 points
- ER >= 0.25
- max trades per day = 1
- long only
- hold toward close
- stop-loss = 160 points
- no take-profit

Test 结果：

| Strategy | Test PnL points | Sharpe | Max DD | Trades | Profit factor |
|---|---:|---:|---:|---:|---:|
| LONG_OR_FLAT_FILTERED | 991 | 0.911 | -724 | 68 | 1.244 |
| HYBRID | -3577 | -5.133 | -3689 | 215 | 0.619 |
| ORB | -1954 | -1.687 | -3187 | 164 | 0.822 |
| MR | -3227 | -3.558 | -3276 | 229 | 0.692 |
| INTRADAY_LONG | 338 | 0.152 | -2647 | 107 | 1.025 |
| FLAT | 0 | 0.000 | 0 | 0 | 0.000 |

它在 test sample 中：

- 比 HYBRID 高 4568 points
- 比 ORB 高 2945 points
- 比 MR 高 4218 points
- 比 INTRADAY_LONG 高 653 points
- 比 FLAT 高 991 points

但必须谨慎解释：

- 这是 post-analysis exploratory result。
- 不是原始 pre-specified strategy。
- test 盈利集中在 2020-03。
- 10-point slippage per side 下结果转负。
- 需要 fresh holdout / walk-forward validation 才能更强地证明稳健性。

---

## 2. 项目目录结构

```text
financial8020/
├── hi1_20170701_20200609.csv
├── PROJECT_PROPOSAL_v2.md
├── project requirements_2026.pdf
├── main.py
├── requirements.txt
├── README.md
├── PROGRESS.md
├── TODO.md
├── RUN_LOG.md
├── PROJECT_STATE.json
├── src/
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
│   ├── tables/
│   ├── figures/
│   └── logs/
├── strategy_optimization_exploration/
│   ├── scripts/
│   ├── outputs/
│   │   ├── tables/
│   │   ├── figures/
│   │   └── logs/
│   └── notes/
└── report/
    ├── STAT8020_Project_Report_Draft.md
    └── report_final_logic.md
```

---

## 3. 环境安装

进入项目目录：

```bash
cd /Users/xuwantong/PycharmProjects/financial8020
```

安装依赖：

```bash
python -m pip install -r requirements.txt
```

主要依赖：

```text
pandas
numpy
matplotlib
seaborn
scipy
tqdm
```

基础语法检查：

```bash
python -m py_compile src/*.py main.py
python -m py_compile strategy_optimization_exploration/scripts/*.py
```

---

## 4. 原始项目运行流程

### 4.1 数据阶段

```bash
python main.py --stage data
```

输出：

```text
outputs/tables/data_schema.csv
outputs/tables/data_cleaning_summary.csv
outputs/tables/session_counts.csv
```

### 4.2 特征阶段

```bash
python main.py --stage features
```

输出：

```text
outputs/tables/feature_sanity_summary.csv
```

### 4.3 小样本回测检查

```bash
python main.py --stage backtest
```

输出：

```text
outputs/tables/stage3_backtest_metrics.csv
outputs/logs/stage3_trades_orb.csv
outputs/logs/stage3_trades_mr.csv
outputs/logs/stage3_trades_hybrid.csv
```

### 4.4 Fast mode

```bash
python main.py --fast
```

用途：快速检查完整 pipeline 能否端到端运行。

### 4.5 Medium mode

```bash
python main.py --medium
```

用途：生成主报告使用的原始 HYBRID / ORB / MR / benchmark medium-mode 结果。

主要输出：

```text
outputs/tables/final_selected_params.csv
outputs/tables/performance_summary.csv
outputs/tables/risk_metrics.csv
outputs/tables/trade_statistics.csv
outputs/tables/monthly_pnl.csv
outputs/tables/regime_performance.csv
outputs/tables/slippage_sensitivity.csv
outputs/tables/report_summary.md
outputs/logs/all_trades_hybrid.csv
outputs/figures/
```

### 4.6 原始 supplementary mode

```bash
python main.py --supplementary
```

用途：运行第一阶段 ORB-filtered Hybrid 补充实验。

主要输出：

```text
outputs/tables/supplementary_strategy_comparison.csv
outputs/tables/supplementary_improvement_summary.csv
outputs/tables/supplementary_regime_trade_breakdown.csv
outputs/tables/supplementary_orb_filtered_hybrid_basic_trades.csv
outputs/tables/supplementary_orb_filtered_hybrid_filtered_trades.csv
outputs/figures/supplementary_cumulative_pnl_comparison.png
outputs/figures/supplementary_test_cumulative_pnl_comparison.png
outputs/figures/supplementary_trade_count_comparison.png
```

这些输出保留为 first-stage improvement evidence。

---

## 5. 策略优化探索运行流程

所有第二阶段探索代码和输出都在：

```text
strategy_optimization_exploration/
```

### 5.1 探索性策略搜索

```bash
python strategy_optimization_exploration/scripts/run_exploration.py --fast
```

该脚本会：

- 读取原始数据和 split。
- 读取原始 baseline。
- 测试 ORB-filtered、low-turnover、strict MR、long-only ORB、ORB-to-close、extreme trend、long-or-flat 等候选。
- 用 train / validation 做筛选。
- 只对 validation-screened candidates 做 test comparison。
- 输出所有探索表格、图像、日志和 notes。

主要输出：

```text
strategy_optimization_exploration/outputs/tables/exploration_all_results.csv
strategy_optimization_exploration/outputs/tables/exploration_validation_ranking.csv
strategy_optimization_exploration/outputs/tables/exploration_test_selected_results.csv
strategy_optimization_exploration/outputs/tables/exploration_improvement_vs_baseline.csv
strategy_optimization_exploration/outputs/tables/exploration_best_strategy_summary.csv
strategy_optimization_exploration/outputs/figures/exploration_*.png
strategy_optimization_exploration/notes/result_summary.md
strategy_optimization_exploration/notes/final_recommendations.md
```

### 5.2 LONG_OR_FLAT final output pass

```bash
python strategy_optimization_exploration/scripts/run_long_or_flat_final.py
```

用途：固定最终 `LONG_OR_FLAT_FILTERED / long_or_flat_filtered_004`，生成报告所需完整表格和图像。

主要输出：

```text
strategy_optimization_exploration/outputs/tables/long_or_flat_final_performance_summary.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_risk_metrics.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_trade_statistics.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_trade_log_all.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_monthly_pnl.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_slippage_sensitivity.csv
strategy_optimization_exploration/outputs/tables/long_or_flat_final_improvement_vs_baseline.csv
strategy_optimization_exploration/outputs/figures/long_or_flat_final_*.png
strategy_optimization_exploration/notes/long_or_flat_final_result_summary.md
```

---

## 6. 核心代码模块说明

### 6.1 `src/`

原始项目代码：

| File | Role |
|---|---|
| `src/config.py` | 数据路径、交易时间、split 日期、合约参数、成本假设 |
| `src/data_loader.py` | 读取 CSV，校验 OHLCV 列，解析 datetime |
| `src/preprocessing.py` | 去重、过滤 day session、验证 session、划分 train/val/test |
| `src/features.py` | return、VWAP、rolling fair value、z-score、ER、RV、opening range |
| `src/regime.py` | EXTREME / TREND / RANGE 分类 |
| `src/strategies.py` | ORB、MR、HYBRID pure signal |
| `src/risk_manager.py` | stop-loss、take-profit、max trades、daily loss、forced exit |
| `src/backtester.py` | 原始回测引擎、benchmark、supplementary ORB-filtered variants |
| `src/metrics.py` | PnL、Sharpe、drawdown、trade stats、monthly/regime performance |
| `src/optimization.py` | ORB/MR/regime staged optimization |
| `src/plots.py` | 主报告图像 |
| `src/utils.py` | 通用工具 |

### 6.2 `main.py`

主入口，支持：

```bash
python main.py --stage data
python main.py --stage features
python main.py --stage backtest
python main.py --fast
python main.py --medium
python main.py --supplementary
python main.py --improvement
```

### 6.3 `strategy_optimization_exploration/scripts/`

探索优化代码：

| File | Role |
|---|---|
| `exploratory_backtester.py` | 隔离的探索性回测器，不修改原始 `src/backtester.py` |
| `exploratory_strategies.py` | 探索候选策略定义和 family 标记 |
| `exploratory_optimization.py` | 候选参数网格和 validation score |
| `exploratory_plots.py` | 探索图像 |
| `run_exploration.py` | 探索性策略搜索主脚本 |
| `run_long_or_flat_final.py` | 最终 long-or-flat 报告输出脚本 |

---

## 7. 报告文件

主报告：

```text
report/STAT8020_Project_Report_Draft.md
```

最终报告逻辑说明：

```text
report/report_final_logic.md
```

报告最终主线：

```text
1. 原始研究问题：regime-adaptive HYBRID 是否 outperform benchmark
2. 原始 HYBRID 完整实现和 medium-mode 测试
3. 样本外失败：HYBRID 不 beat INTRADAY_LONG / FLAT
4. 诊断：MR / RANGE 和 high turnover 是拖累
5. 第一阶段优化：ORB-filtered Hybrid 显著减少亏损但仍不 beat benchmark
6. 第二阶段优化：LONG_OR_FLAT_FILTERED beat INTRADAY_LONG 和 FLAT
7. 诚实 caveat：post-analysis、March 2020 concentration、10-point slippage negative
8. 结论：原 HYBRID 不建议实盘；long-or-flat 方向值得后续验证
```

---

## 8. 重要注意事项

1. 不要把 `LONG_OR_FLAT_FILTERED` 写成原始 pre-specified strategy。
2. 原始主结果仍然是 HYBRID 样本外失败。
3. `strategy_optimization_exploration/` 是 post-analysis exploratory work。
4. `LONG_OR_FLAT_FILTERED` 虽然 test beat benchmark，但需要 fresh holdout 或 walk-forward validation。
5. 10-point slippage 下 long-or-flat 结果转负，说明策略仍有执行成本风险。
6. Test profit 主要来自 2020-03，报告里需要保留这个 caveat。
7. `outputs/` 是原始项目输出；`strategy_optimization_exploration/outputs/` 是探索优化输出，二者不要混用。

---

## 9. 推荐最终复现顺序

如果从头复现：

```bash
python -m py_compile src/*.py main.py
python main.py --medium
python main.py --supplementary
python -m py_compile strategy_optimization_exploration/scripts/*.py
python strategy_optimization_exploration/scripts/run_exploration.py --fast
python strategy_optimization_exploration/scripts/run_long_or_flat_final.py
```

如果只想复现最终报告主结果：

```bash
python main.py --medium
python strategy_optimization_exploration/scripts/run_long_or_flat_final.py
```

---

## 10. 当前项目状态

已完成：

- 原始数据清洗与 split。
- ORB / MR / HYBRID 原始策略实现。
- 主回测和 medium-mode 参数选择。
- 原始 HYBRID 样本外失败诊断。
- 第一阶段 ORB-filtered Hybrid 补充实验。
- 第二阶段 long-or-flat 探索优化。
- `LONG_OR_FLAT_FILTERED` final report outputs。
- 主报告 draft 和最终 report logic。

下一步：

- 填写 group member names 和 submission date。
- 检查报告格式、图表引用、页数要求。
- 根据课程要求转换为 PDF / Word。

