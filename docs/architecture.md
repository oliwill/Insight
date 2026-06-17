# Architecture

trader-obsidian is an Obsidian-native research pipeline. Python collects and structures data; Claude Code or an MCP client performs reasoning; `MemoryManager` persists the result into Markdown.

## Components

```mermaid
flowchart TD
    Inbox[Obsidian Inbox] --> Scanner[inbox_scanner]
    Materials[Obsidian Materials] --> Evidence[input.evidence]
    Wiki[Stock wiki] --> Evidence
    Scanner --> Pipeline[data.analysis_pipeline]
    Pipeline --> SupplyChain[data.supply_chain]
    SupplyChain --> Score
    SupplyChain --> Report
    Pipeline --> Score[analyzer.research_score]
    Evidence --> Score
    Pipeline --> Timing[analyzer.timing_engine]
    Score --> Timing
    Pipeline --> Report[analyzer.report_generator]
    Score --> Report
    Timing --> Report
    Evidence --> Report
    Report --> Quality[analyzer.report_quality]
    Report --> Memory[memory.manager]
    Memory --> Wiki
    Memory --> Dashboard[Dashboard.md]
    Memory --> Tasks[Tasks]
    Wiki --> Backtest[backtest.runner / review]
    Backtest --> Wiki
```

## Main Paths

| Path | Role |
|---|---|
| `scripts/analyze_stock.py` | one-click Cockpit analysis and Obsidian write |
| `run_analysis.py` | data fetch, scan/dashboard commands, write helpers |
| `data/analysis_pipeline.py` | one-call data pipeline |
| `data.supply_chain.py` | per-stock Serenity-style supply-chain position adapter |
| `data/serenity/` | deterministic industry-chain knowledge, bottleneck scoring, and standalone Serenity scan support |
| `input/evidence.py` | extracts typed evidence from wiki, Materials, Inbox |
| `analyzer/research_score.py` | five-dimension research score |
| `analyzer/timing_engine.py` | trade-timing state machine |
| `analyzer/report_generator.py` | final Markdown report |
| `analyzer/report_quality.py` | report structure, data-gap, and Research/Timing separation checks |
| `skills/stock-research-cockpit/` | reusable AI skill for public stock research cockpit workflows |
| `himself65/finance-skills` plugin | optional Claude Code / agent-layer companion for valuation, estimates, sentiment, source readers, startup tools, UI tools, and skill authoring |
| `memory/manager.py` | wiki/Materials/index/log persistence |
| `backtest/runner.py` | timeline signal parsing, verification, and extended metrics |
| `backtest/review.py` | scheduled review workflow |
| `trader_mcp.py` | MCP server entry point |
| `telegram_bot.py` | optional Telegram command interface |
| `inbox_watcher.py` | optional filesystem watcher |

## Data Pipeline

`generate_analysis(code)` returns a dict with these top-level fields when available:

| Field | Source |
|---|---|
| `wiki_status`, `wiki_summary` | `MemoryManager.get_stock_context()` |
| `stock_info` | `DataManager.get_stock_info()` |
| `fundamentals` | `DataManager.get_fundamentals()` |
| `supply_chain` | `data.supply_chain.StockChainAnalyzer`, also copied into `fundamentals.supply_chain` |
| `earnings` | `data.earnings.EarningsCalendar` |
| `technicals` | local MA/RSI/MACD/KDJ/Bollinger/support calculations |
| `wyckoff` | `analyzer.wyckoff.WyckoffAnalyzer` |
| `liquidity` | `data.liquidity.LiquidityAnalyzer` |
| `options` | `data.options.OptionsAnalyzer` |
| `web_search` | `data.search.StockSearchEngine` |
| `peers` | `data.correlation.CorrelationAnalyzer` |
| `etf` | `data.etf.ETFAnalyzer`, only when symbol is detected as ETF |
| `_data_sources` | `DataManager.get_source_status()` source-attempt diagnostics |

Each stage catches local failures and emits a `*_error` key instead of aborting the entire pipeline. Data-source fallbacks are recorded under `_data_sources`.

## Agent-Layer Finance Skills

The `himself65/finance-skills` plugin is an optional agent-layer companion. It is not imported by Python modules and must not become a dependency of `data.analysis_pipeline` or the deterministic scoring/reporting path.

Use the plugin from Claude Code or another skill-aware agent after local data is collected:

```text
run_analysis.py / analyze_stock_tool
    ↓
Claude Code applies finance-skills taxonomy
    ↓
write_analysis_to_obsidian() / write_analysis_tool
```

Policy tiers:

| Tier | Skills |
|---|---|
| Baseline | `funda-data`, `company-valuation`, `estimate-analysis`, `stock-correlation`, `finance-sentiment`, `sepa-strategy` |
| Conditional | `yfinance-data`, `stock-liquidity`, `earnings-preview`, `earnings-recap`, `options-payoff`, `etf-premium`, `tradingview-reader`, `hormuz-strait`, `twitter-reader`, `telegram-reader`, `discord-reader`, `linkedin-reader`, `yc-reader`, `opencli-reader` |
| Explicit-only | `startup-analysis`, `generative-ui`, `saas-valuation-compression`, `skill-creator` |

Social/source readers stay read-only. They must not post, message, write to external services, or execute trades.

## Cockpit Analysis Flow

`scripts/analyze_stock.py` is the canonical full local workflow:

1. Fetch all pipeline data.
2. Enrich moat details through `FundamentalAnalyzer` when possible.
3. Generate a Wyckoff chart at `WIKI_BASE_DIR/Charts/{CODE}_wyckoff.png`.
4. Load saved Materials, prior stock wiki and related Inbox items.
5. Extract evidence with `EvidenceExtractor`.
6. Build a `ResearchScore` with `ResearchScoreEngine`.
7. Build a `TimingState` with `TimingEngine`.
8. Compare current score/timing with prior wiki timeline if available.
9. Generate Markdown with `ReportGenerator`.
10. Evaluate report structure with `ReportQualityEvaluator`.
11. Persist via `write_analysis_to_obsidian()`.

## Supply-Chain Enrichment

`StockChainAnalyzer` adapts Serenity-style theme research to individual stock analysis:

1. Resolve ticker / company / sector / industry to a Serenity topic using deterministic maps and keywords.
2. Read optional local cache from `data/cache/supply_chain/{NORMALIZED_CODE}.json` when present.
3. Reuse `ChainAnalyzer` and `BottleneckScorer` from `data/serenity/` to score layers.
4. Locate the target company by cache `target_layer_name`, candidate company match, or layer key-company match before falling back to the highest bottleneck layer.
5. Return compact `supply_chain` data for scoring and report rendering.

The enrichment is additive. It must not call external LLM APIs, create a separate top-level Obsidian section, or hide missing financial fundamentals.

## Research Score

`ResearchScoreEngine` outputs base and evidence-adjusted five-dimension scores.

| Dimension | Weight |
|---|---:|
| 行业/TAM | 20% |
| 护城河 | 20% |
| 增长质量 | 20% |
| 估值 | 25% |
| 团队/治理 | 15% |

Evidence can adjust dimension scores when source credibility and impact rules support it. Rumors and low-credibility opinions are marked as `watch_only` or confidence-only and should not become hard score upgrades.

## Timing State

`TimingEngine` intentionally answers a different question from Research Score.

Inputs include:

- technical trend, RSI, volume ratio
- Wyckoff phase/support/resistance
- price distance to MA/support/analyst target
- earnings window
- liquidity and short-interest risk
- sentiment crowding and Put/Call ratio
- Research Score as a guardrail

Output states:

| State | Use |
|---|---|
| `Ready` | actionable setup |
| `Wait` | thesis may be valid, but wait for trigger |
| `Watch` | low-confidence monitor state |
| `Avoid` | risk/reward or thesis quality too weak |

## Wiki Persistence Model

`MemoryManager.init_stock_wiki()` creates a stock page with structured sections. Current Cockpit sections are replaced on each analysis:

- `证据表`
- `五维打分`
- `交易时机状态`
- `与上次分析相比`

Longitudinal sections are append-only:

- `分析时间线`
- `预测验证`
- `研究笔记`
- `资料索引`

The timeline supports both legacy entries and new Cockpit entries:

```text
- **YYYY-MM-DD HH:MM** | 价格: 123.45 | Research: 68.0/100 | Timing: Wait | 类型: Cockpit 分析
  - 核心观点: ...
  - 触发条件: ...
```

## Backtest Model

`BacktestRunner.backtest_wiki_timeline()` parses timeline entries older than the selected holding window. If `Timing: Ready`, it turns the core view into a synthetic BUY signal; legacy BUY/SELL/HOLD words are also parsed. Results are appended to `预测验证`.

`ReviewScheduler` wraps this into a full review run and generates Markdown/CSV/chart artifacts under `output/`. Backtest results include verified count, expectancy, median/best/worst return, profit factor, and aggregate max drawdown.

## Interfaces

| Interface | Entry | Notes |
|---|---|---|
| CLI one-click analysis | `python scripts/analyze_stock.py AAPL` | writes full report |
| CLI data fetch | `python run_analysis.py AAPL` | prints JSON for Claude Code |
| MCP | `python trader_mcp.py` | exposes scan/context/write/search tools |
| Telegram | `python telegram_bot.py --polling` | `/note`, `/get`, `/scan`, `/inbox`, `/task` |
| Watcher | `python inbox_watcher.py` | watches Inbox/Clippings/Raw for new Markdown |
| Scheduler | `python scheduler.py` or launchd | periodic scan/review/dashboard |
| Podwise import | `python scripts/podwise_sync.py` | imports podcast notes as Obsidian material |
