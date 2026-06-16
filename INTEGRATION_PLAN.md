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

## External Finance Skills Companion Policy

The local modules provide baseline data and structure. The `himself65/finance-skills` bundle is an agent-layer companion for Claude Code, not a Python pipeline dependency.

External source of truth: `himself65/finance-skills` v8.0.1.

Local installation status:

- `npx plugins add himself65/finance-skills` installed 24 skills into `.agents/skills/`.
- `skills-lock.json` records the GitHub source paths and computed hashes for those local skill copies.
- The installed plugin exposes six groups: market-analysis, data-providers, social-readers, startup-tools, ui-tools, and skill-creator.

Taxonomy:

- **Baseline**: expected in comprehensive public-equity analysis when available and relevant to the claim.
- **Conditional**: invoked only when the ticker, asset type, event, liquidity, or source requirement triggers it.
- **Explicit-only**: used only when the user asks for that workflow; do not auto-invoke during normal stock analysis.

### Market Analysis Skills

| Skill | Policy | Local coverage | Remaining gap / usage |
|---|---|---|---|
| `yfinance-data` | Conditional | `data.manager`, `data.analysis_pipeline`, `data.earnings`, `data.options` | Cross-check local Yahoo-derived output when data is stale, incomplete, inconsistent, or needs ownership / recommendations / screener detail. |
| `company-valuation` | Baseline | `ResearchScoreEngine` has valuation dimension; `ReportGenerator` has scenarios | Use for DCF + relative + SOTP triangulation, WACC sensitivity, and target-price claims. |
| `estimate-analysis` | Baseline | `data.earnings` has basic earnings info | Use for estimate revision momentum, EPS/revenue estimate spread, growth projections, and analyst accuracy. |
| `stock-correlation` | Baseline | `data.correlation` | Use for peer P/S baselines, co-movement, related stocks, and pair-trade context. |
| `stock-liquidity` | Conditional | `data.liquidity` | Use for spreads, volume profile, market impact, and Amihud ratio, especially small-cap / ADR / thin names. |
| `sepa-strategy` | Baseline | `TimingEngine` and technical/Wyckoff context | Use for Minervini trend template, SEPA stage, VCP, entry rules, and position sizing. |
| `earnings-preview` | Conditional | `data.earnings` | Use within 30 days before earnings. |
| `earnings-recap` | Conditional | `data.earnings` history only | Use after earnings for actual vs estimate, price reaction, margin trends, and call notes. |
| `options-payoff` | Conditional | `data.options` chain summary | Use for options position screenshots, spreads, straddles, condors, and payoff / P&L visualization. |
| `etf-premium` | Conditional | `data.etf` detects ETF only | Use for ETF premium/discount vs NAV, AP arbitrage, leveraged/inverse/bond/crypto ETF moves, and ETF GEX / dealer-driven surge questions. |
| `saas-valuation-compression` | Explicit-only | none | Use only for private SaaS funding-round / ARR multiple compression analysis. |

### Data Provider Skills

| Skill | Policy | Local coverage | Remaining gap / usage |
|---|---|---|---|
| `funda-data` | Baseline | local fundamentals, options, search are baseline only | Use for analyst-grade research, filings/transcripts, real-time quotes, options chains/GEX, insider/congressional trades, supply-chain mapping, and sector deep-dives. |
| `finance-sentiment` | Baseline | `data.search`, `data.sentiment_analyzer` | Use for structured Reddit / X / news / Polymarket sentiment and crowding. |
| `tradingview-reader` | Conditional | none | Use for read-only TradingView desktop quotes, full options chains with greeks/IV, screeners, chart state, watchlists, alerts, and chart screenshots. |
| `hormuz-strait` | Conditional | none | Use for oil, tanker, shipping, insurance, defense, and Strait of Hormuz geopolitical exposure. |

### Social Reader Skills

| Skill | Policy | Usage |
|---|---|---|
| `twitter-reader` | Conditional | Named KOLs, X posts, and X-native sentiment. |
| `telegram-reader` | Conditional | Telegram channel research sources. |
| `discord-reader` | Conditional | Discord community research sources. |
| `linkedin-reader` | Conditional | Hiring, layoffs, enterprise GTM, executive movement, or job-posting signals. |
| `yc-reader` | Conditional | Startup/vendor/customer context for YC companies. |
| `opencli-reader` | Conditional | Read-only fallback for sources without a dedicated skill, including Yahoo Finance, Bloomberg, Reuters, Eastmoney, Xueqiu, Reddit, Substack, arXiv, and similar opencli-supported sources. |

### Explicit-Only Plugin Groups

| Group | Skill | Usage |
|---|---|---|
| startup-tools | `startup-analysis` | Startup/company evaluation workflows only when requested. |
| ui-tools | `generative-ui` | Interactive charts, widgets, dashboards, or visual explainers only when requested. |
| skill-creator | `skill-creator` | Create, modify, evaluate, or package skills only when requested. |

If a required skill cannot be used, record the gap explicitly in the analysis instead of implying coverage.

Safety note: these external skills run with agent permissions. Treat all source readers as read-only, never invoke write/post/trade actions, never execute trades, and use higher-risk readers such as `telegram-reader`, `discord-reader`, `funda-data`, `twitter-reader`, and `tradingview-reader` only when the source materially affects the thesis.
