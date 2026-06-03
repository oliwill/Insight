# Skills Integration Status

This file records the current integration status of external finance/data workflow concepts into trader-obsidian. It is no longer an implementation plan.

## Integrated Modules

| Capability | Local module | Current integration point | Status |
|---|---|---|---|
| Yahoo Finance data | `data.manager`, `data.analysis_pipeline` | default market/fundamental/history source | active |
| Earnings preview/recap data | `data.earnings` | `generate_analysis()` → `earnings`; wiki `财报预期` | active |
| Sentiment/search | `data.search`, `data.sentiment_analyzer` | `generate_analysis()` → `web_search`; report `市场情绪` | active |
| Stock correlation / peers | `data.correlation` | `generate_analysis()` → `peers`; wiki `交叉引用` | active |
| Stock liquidity | `data.liquidity` | `generate_analysis()` → `liquidity`; wiki `流动性分析` | active |
| Options data | `data.options` | `generate_analysis()` → `options`; wiki `期权市场` | active |
| ETF detection | `data.etf` | `generate_analysis()` → `etf` only for ETFs | active |
| Evidence extraction | `input.evidence` | `scripts/analyze_stock.py` before scoring | active |
| Research scoring | `analyzer.research_score` | Cockpit `五维打分` | active |
| Timing state | `analyzer.timing_engine` | Cockpit `交易时机状态` and timeline | active |
| Backtest review | `backtest.runner`, `backtest.review` | `scripts/run_review.py`; wiki `预测验证` | active |

## Current Data Flow

```text
scripts/analyze_stock.py
├── data.analysis_pipeline.generate_analysis()
│   ├── Wiki history
│   ├── quote + fundamentals
│   ├── earnings
│   ├── K-line + technicals + Wyckoff
│   ├── liquidity
│   ├── options
│   ├── web/search/social
│   ├── peer correlation
│   └── ETF detection
├── input.evidence.EvidenceExtractor
├── analyzer.research_score.ResearchScoreEngine
├── analyzer.timing_engine.TimingEngine
├── analyzer.report_generator.ReportGenerator
└── run_analysis.write_analysis_to_obsidian()
```

## Wiki Section Mapping

| Section | Writer |
|---|---|
| `证据表` | `MemoryManager.update_cockpit_sections()` |
| `五维打分` | `ResearchScoreEngine.to_markdown()` |
| `交易时机状态` | `TimingEngine.to_markdown()` |
| `与上次分析相比` | `scripts/analyze_stock.py` comparison helper |
| `财报预期` | `data.earnings.EarningsCalendar` |
| `流动性分析` | `data.liquidity.LiquidityAnalyzer` |
| `期权市场` | `data.options.OptionsAnalyzer` |
| `社交情绪` | `run_analysis.write_analysis_to_obsidian()` from `web_search` |
| `交叉引用` | `data.correlation.CorrelationAnalyzer` |
| `预测验证` | `backtest.runner.BacktestRunner` / `backtest.review.ReviewScheduler` |

## Remaining External Skill Gap

The local modules provide baseline data and structure. For full investment-grade analysis, Claude Code should still call finance skills listed in `CLAUDE.md` when the user requests a stock analysis, especially for real-time GEX/options flow, insider/congressional trading, supply-chain mapping, SEPA stage confirmation, and cross-source sentiment.
