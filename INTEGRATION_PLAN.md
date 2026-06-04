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

## Remaining External Skill Gap Checklist

The local modules provide baseline data and structure. For full investment-grade analysis, Claude Code should still call finance skills listed in `CLAUDE.md` when the user requests a stock analysis.

External source of truth: `himself65/finance-skills` v8.0.1.

Local installation status:

- `npx skills add himself65/finance-skills` installed 24 skills into `.agents/skills/`.
- `skills-lock.json` records the GitHub source paths and computed hashes for those local skill copies.
- This project uses the market-analysis, data-providers, and social-readers groups for stock research by default. Startup, UI, and skill-authoring skills remain available only for explicit user requests.

### Market Analysis Skills

| Skill | Local coverage | Remaining gap / usage |
|---|---|---|
| `yfinance-data` | `data.manager`, `data.analysis_pipeline`, `data.earnings`, `data.options` | Cross-check local Yahoo-derived output when data is stale, incomplete, or needs ownership / recommendations / screener detail. |
| `company-valuation` | `ResearchScoreEngine` has valuation dimension; `ReportGenerator` has scenarios | Use for DCF + relative + SOTP triangulation, WACC sensitivity, and target-price claims. |
| `estimate-analysis` | `data.earnings` has basic earnings info | Use for estimate revision momentum, EPS/revenue estimate spread, growth projections, and analyst accuracy. |
| `stock-correlation` | `data.correlation` | Use for peer P/S baselines, co-movement, related stocks, and pair-trade context. |
| `stock-liquidity` | `data.liquidity` | Use for spreads, volume profile, market impact, and Amihud ratio, especially small-cap / ADR / thin names. |
| `sepa-strategy` | `TimingEngine` and technical/Wyckoff context | Use for Minervini trend template, SEPA stage, VCP, entry rules, and position sizing. |
| `earnings-preview` | `data.earnings` | Use within 30 days before earnings. |
| `earnings-recap` | `data.earnings` history only | Use after earnings for actual vs estimate, price reaction, margin trends, and call notes. |
| `options-payoff` | `data.options` chain summary | Use for options position screenshots, spreads, straddles, condors, and payoff / P&L visualization. |
| `etf-premium` | `data.etf` detects ETF only | Use for ETF premium/discount vs NAV, AP arbitrage, leveraged/inverse/bond/crypto ETF moves, and ETF GEX / dealer-driven surge questions. |
| `saas-valuation-compression` | none | Use only for private SaaS funding-round / ARR multiple compression analysis. |

### Data Provider Skills

| Skill | Local coverage | Remaining gap / usage |
|---|---|---|
| `funda-data` | local fundamentals, options, search are baseline only | Use for analyst-grade research, filings/transcripts, real-time quotes, options chains/GEX, insider/congressional trades, supply-chain mapping, and sector deep-dives. |
| `finance-sentiment` | `data.search`, `data.sentiment_analyzer` | Use for structured Reddit / X / news / Polymarket sentiment and crowding. |
| `tradingview-reader` | none | Use for read-only TradingView desktop quotes, full options chains with greeks/IV, screeners, chart state, watchlists, alerts, and chart screenshots. |
| `hormuz-strait` | none | Use for oil, tanker, shipping, insurance, defense, and Strait of Hormuz geopolitical exposure. |

### Social Reader Skills

| Skill | Usage |
|---|---|
| `twitter-reader` | Named KOLs, X posts, and X-native sentiment. |
| `telegram-reader` | Telegram channel research sources. |
| `discord-reader` | Discord community research sources. |
| `linkedin-reader` | Hiring, layoffs, enterprise GTM, executive movement, or job-posting signals. |
| `yc-reader` | Startup/vendor/customer context for YC companies. |
| `opencli-reader` | Read-only fallback for sources without a dedicated skill, including Yahoo Finance, Bloomberg, Reuters, Eastmoney, Xueqiu, Reddit, Substack, arXiv, and similar opencli-supported sources. |

If a required skill cannot be used, record the gap explicitly in the analysis instead of implying coverage.

Safety note: these external skills run with agent permissions. Treat all source readers as read-only, never invoke write/post/trade actions, and use higher-risk readers such as `telegram-reader`, `discord-reader`, `funda-data`, `twitter-reader`, and `tradingview-reader` only when the source materially affects the thesis.
