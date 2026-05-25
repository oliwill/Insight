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

The local modules provide baseline data and structure. Full investment-grade analysis still needs external finance skills for real-time and specialized signals that are not guaranteed by the local pipeline.

Before writing a full stock report, run this checklist and either include the result or mark the item as unavailable:

| Gap | Preferred skill | Trigger | Report placement |
|---|---|---|---|
| Real-time GEX / options flow | `finance-skills-funda-data` | every full US stock analysis, and any name where options positioning is part of the thesis | `期权市场`, risk/catalyst notes |
| Insider / congressional trading | `finance-skills-funda-data` | every full US stock analysis; explicitly note when the issuer is non-US or data is unavailable | `内部人信号`, governance score notes |
| Analyst estimates and target revisions | `finance-skills-funda-data` | every full stock analysis | valuation notes, earnings setup |
| Supply-chain / customer exposure | `finance-skills-funda-data` | hardware, semis, industrials, platform ecosystems, or any thesis dependent on key customers/suppliers | company moat and catalyst sections |
| SEPA stage / trend-template confirmation | `finance-skills-sepa-strategy` | every full stock analysis, especially before assigning `Ready` timing | `技术面`, `交易时机状态` |
| Cross-source sentiment | `finance-skills-finance-sentiment` | every full stock analysis; compare against local `web_search` before scoring TAM/attention | `社交情绪`, risk notes |
| Peer P/S baseline and related stocks | `finance-skills-stock-correlation` | every full stock analysis where valuation uses peer context | valuation and `交叉引用` |
| Earnings preview / recap | `finance-skills-earnings-preview` or `finance-skills-earnings-recap` | within 30 days before earnings, or after a reported quarter | `财报预期`, `财报前情景预判`, catalyst notes |
| Liquidity / market impact | `finance-skills-stock-liquidity` | small-cap, low-ADTV, wide-spread, HK/CN names, or any position-sizing discussion | `流动性分析` |
| Named KOL or holder signal | `finance-skills-twitter-reader` | when a specific KOL, fund manager, or public holder is part of the user's prompt or evidence | `KOL 观点汇总` |

If a skill is unavailable, do not fabricate the missing signal. Label the gap in the report and keep Research Score separate from Timing State.
