# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

**trader-obsidian** is an Obsidian-native stock research system.

- **Workbench**: Obsidian vault Markdown files.
- **Execution**: Claude Code and Python scripts.
- **Persistence**: stock wiki pages, archived Materials, Dashboard, Tasks.
- **Core model**: separate long-term research quality from short-term trade timing.

## Non-Negotiable Obsidian Write Rules

Analysis reports must be written to the configured Obsidian vault.

- Use `Config.get_wiki_dir()` for stock wiki pages.
- Current intended path on this machine: `C:\Users\Lzw\Downloads\Documents\obsidian\Lzw\Lzw\4_Trader\Analysis\`.
- Convert `.` and `/` in stock codes to `_` for filenames:
  - `TEM.US` → `TEM_US.md`
  - `600487.SH` → `600487_SH.md`
  - `00100.HK` → `00100_HK.md`
- Prefer `write_analysis_to_obsidian()` over direct `Write` calls.
- Do not create duplicate files by mixing `MemoryManager.init_stock_wiki()` with a manual `Write` to a different path.

## Quick Commands

Run from project root:

```bash
# One-click Cockpit analysis: fetches data, scores, builds timing state, writes Obsidian
python scripts/analyze_stock.py AAPL

# Data-only Claude Code orchestration path
python run_analysis.py AAPL
python run_analysis.py --scan
python run_analysis.py --dashboard
python run_analysis.py --inbox

# Scheduled-task wrappers
python scripts/scan_inbox.py --dry-run --json
python scripts/run_review.py --days-after 30 --lookback 90
python scripts/update_dashboard.py --json
python scripts/update_dashboard.py --json --reason scheduled
python scripts/update_dashboard.py --restore-backup --json

# Optional interfaces
python trader_mcp.py
python telegram_bot.py --polling
python inbox_watcher.py
python scripts/podwise_sync.py --list

# External finance skills refresh
npx plugins add himself65/finance-skills
```

## Standard Analysis Workflow

When the user asks to analyze a stock, use this sequence unless they explicitly request a narrower operation.

1. **Fetch project data**:

   ```bash
   python run_analysis.py AAPL
   ```

   Inspect:
   - `stock_info`: price, market, sector, industry.
   - `fundamentals`: valuation, margins, growth, analyst targets, and `supply_chain` when the deterministic Serenity adapter can map the ticker to an industry-chain theme.
   - `technicals`: MA, RSI, MACD, KDJ, Bollinger, support/resistance.
   - `wyckoff`: phase, support, resistance, confidence.
   - `earnings`, `liquidity`, `options`, `web_search`, `peers`, `etf`.
   - `wiki_context` and `inbox_materials`.

2. **Run finance-skills as an agent-layer companion**:

   External source of truth: `himself65/finance-skills` v8.0.1, installed with `npx plugins add himself65/finance-skills`. Use the installed skill name that matches the canonical repo skill below; local installations may expose bare names such as `company-valuation`, plugin-prefixed names such as `finance-market-analysis:company-valuation`, or legacy `finance-skills-*` names.

   Plugin groups: market-analysis, data-providers, social-readers, startup-tools, ui-tools, and skill-creator. Keep these outside the Python pipeline: they are Claude Code / agent companion capabilities, not deterministic local modules.

   Taxonomy:
   - **Baseline**: expected in comprehensive public-equity analysis when available and relevant to the claim.
   - **Conditional**: invoked only when the ticker, asset type, event, liquidity, or source requirement triggers it.
   - **Explicit-only**: used only when the user asks for that workflow; do not auto-invoke during normal stock analysis.

   | Canonical skill | Group | Policy | Purpose | When |
   |---|---|---|---|---|
   | `yfinance-data` | market-analysis | Conditional | prices, financial statements, options chains, dividends, earnings, analyst recommendations | use when local project data is missing, stale, inconsistent, or needs Yahoo-specific ownership / recommendation / options detail |
   | `funda-data` | data-providers | Baseline | analyst-grade research, filings, transcripts, options flow/GEX, insider/congressional trading, supply chain | every full stock analysis; required when any of these data gaps can change the thesis |
   | `company-valuation` | market-analysis | Baseline | DCF + relative + SOTP triangulation, WACC sensitivity, Bull/Base/Bear implied price | every comprehensive report with fair value, target price, or over/undervalued conclusion |
   | `estimate-analysis` | market-analysis | Baseline | EPS/revenue estimate revisions, estimate spread, growth projections, analyst accuracy | every full stock analysis and any earnings/guide-driven setup |
   | `stock-correlation` | market-analysis | Baseline | peer baseline, co-movement, pair-trading candidates, related stocks | every full stock analysis |
   | `finance-sentiment` | data-providers | Baseline | Reddit / X / news / Polymarket structured sentiment | every full stock analysis when narrative, rumor, crowding, or event sentiment can move price |
   | `sepa-strategy` | market-analysis | Baseline | Minervini trend template, SEPA stage, VCP, entry rules, position sizing | every full stock analysis before calling a setup actionable |
   | `stock-liquidity` | market-analysis | Conditional | spreads, volume profile, market impact, Amihud ratio | small-cap, ADR, thin-liquidity names, or any sizing decision above watchlist size |
   | `earnings-preview` | market-analysis | Conditional | consensus, beat/miss history, analyst sentiment before earnings | within 30 days before earnings |
   | `earnings-recap` | market-analysis | Conditional | actual vs estimate, price reaction, margin trends after earnings | after earnings, before updating the thesis |
   | `options-payoff` | market-analysis | Conditional | interactive payoff curve for spreads, straddles, condors, screenshots, multi-leg positions | whenever the user discusses an options trade or asks for payoff / P&L visualization |
   | `etf-premium` | market-analysis | Conditional | ETF premium/discount vs NAV, AP arbitrage, gamma/dealer-driven surge decomposition | ETFs, leveraged/inverse/bond/crypto/international funds, or ETF GEX / NAV questions |
   | `saas-valuation-compression` | market-analysis | Explicit-only | private SaaS ARR multiple compression across rounds | SaaS private-market or funding-round valuation questions, not normal public-equity analysis |
   | `tradingview-reader` | data-providers | Conditional | TradingView desktop quotes, full options chains with greeks/IV, screeners, chart state, watchlists, alerts | when the user asks for TradingView data or when local option-chain / IV / screener data is insufficient |
   | `hormuz-strait` | data-providers | Conditional | Strait of Hormuz shipping, oil, insurance, and crisis timeline monitoring | energy, tanker, shipping, insurance, defense, and oil-price geopolitical risk analysis |
   | `twitter-reader` | social-readers | Conditional | read-only Twitter/X research and KOL signals | when named KOLs, X posts, or X-native sentiment are part of the thesis |
   | `telegram-reader` | social-readers | Conditional | read-only Telegram channel research | when a Telegram channel is a cited source |
   | `discord-reader` | social-readers | Conditional | read-only Discord research | when a Discord community is a cited source |
   | `linkedin-reader` | social-readers | Conditional | read-only LinkedIn feed / job-search signal | hiring, GTM, layoffs, executive or enterprise-sales channel checks |
   | `yc-reader` | social-readers | Conditional | Y Combinator company data | startup/vendor/customer context, especially private company checks |
   | `opencli-reader` | social-readers | Conditional | generic read-only fallback for 90+ sources such as Yahoo Finance, Bloomberg, Reuters, Eastmoney, Xueqiu, Reddit, Substack, arXiv | only when no dedicated finance skill covers the source; never invoke write operations |
   | `startup-analysis` | startup-tools | Explicit-only | startup/company evaluation workflows | only when the user asks for startup analysis, vendor/customer diligence, or startup job/VC framing |
   | `generative-ui` | ui-tools | Explicit-only | interactive charts, widgets, dashboards, visual explainers | only when the user asks for a visual/interactive artifact |
   | `skill-creator` | skill-creator | Explicit-only | create, modify, evaluate, or package skills | only when maintaining skills themselves |

   Full-analysis checklist:

   - [ ] Agent companion: apply the Baseline / Conditional / Explicit-only taxonomy above; do not treat plugin skills as Python pipeline dependencies.
   - [ ] Baseline data: `yfinance-data` or local `run_analysis.py` output is current enough for price, fundamentals, options, earnings, and ownership.
   - [ ] Professional data: `funda-data` covers GEX/options flow, insider/congressional trades, supply-chain context, filings/transcripts, or explicitly records what remains unavailable.
   - [ ] Valuation: `company-valuation` supports any target price or fair-value claim; `estimate-analysis` checks analyst revision momentum.
   - [ ] Peers and setup: `stock-correlation` establishes comparable context; `sepa-strategy` confirms stage, trend template, VCP, entry, and sizing.
   - [ ] Market structure: `stock-liquidity` checks tradability; `finance-sentiment` checks structured narrative/crowding; `tradingview-reader` is used when full option-chain greeks/IV, TradingView screener data, chart state, alerts, or watchlists matter.
   - [ ] Event-specific tools: `earnings-preview` before earnings, `earnings-recap` after earnings, `options-payoff` for options trades, `etf-premium` for ETFs, `hormuz-strait` for oil/shipping/geopolitical exposure.
   - [ ] Source-specific readers: prefer `twitter-reader`, `telegram-reader`, `discord-reader`, `linkedin-reader`, or `yc-reader` when the source matches; use `opencli-reader` only as a read-only fallback.
   - [ ] If a required skill is unavailable or a gap remains, state the gap explicitly instead of implying coverage.

   Safety note: external reader/data skills run with agent permissions. Keep all social/source readers read-only; never invoke write/post/trade operations or any trade-execution workflow. Installer risk flags were highest for `telegram-reader` and non-zero for `discord-reader`, `funda-data`, `twitter-reader`, and `tradingview-reader`, so use those only when the source is necessary for the thesis and record any unavailable data explicitly.

3. **Write the analysis** using `write_analysis_to_obsidian()` or `scripts/analyze_stock.py` output path.

4. **Refresh Dashboard separately when needed**:

   ```bash
   python scripts/update_dashboard.py --json --reason post-analysis
   python scripts/update_dashboard.py --json --reason manual
   ```

   Use the daily scheduled refresh or an explicit operator refresh; do not auto-run a Dashboard update after every single ticker by default.

## Cockpit Architecture

The current one-click script is `scripts/analyze_stock.py`.

It performs:

1. `data.analysis_pipeline.generate_analysis(stock_code)`.
2. Optional moat enrichment via `analyzer.fundamental.FundamentalAnalyzer`.
3. Deterministic Serenity-style supply-chain enrichment via `data.supply_chain.StockChainAnalyzer`; the result is exposed as `market_data["supply_chain"]` and `fundamentals["supply_chain"]`.
4. Wyckoff chart generation into `WIKI_BASE_DIR/Charts/{CODE}_wyckoff.png`.
5. Obsidian evidence extraction:
   - `MemoryManager.get_materials()`
   - `MemoryManager.get_stock_context()`
   - `inbox_scanner.get_related_materials()`
   - `input.evidence.EvidenceExtractor`
6. Five-dimension scoring via `analyzer.research_score.ResearchScoreEngine`.
7. Trade timing via `analyzer.timing_engine.TimingEngine`.
8. Report generation via `analyzer.report_generator.ReportGenerator`.
9. Report quality check via `analyzer.report_quality.ReportQualityEvaluator`.
10. Wiki write via `run_analysis.write_analysis_to_obsidian()`.

### Research Score vs Timing State

Do not conflate these two:

| Layer | Question | Output |
|---|---|---|
| Research Score | Is the company/thesis worth owning? | 0–100 five-dimension score |
| Timing State | Is now a good entry? | `Ready`, `Wait`, `Watch`, `Avoid` |

A high Research Score with `Wait` means: thesis may be good, entry is not ready.
A low Research Score with `Ready` technicals should not become a high-conviction buy.

## Five-Dimension Scoring

`analyzer.research_score.ResearchScoreEngine` uses:

| Dimension | Weight | Main inputs |
|---|---:|---|
| 行业/TAM | 20% | sector, industry, peers, social/prediction-market attention, `supply_chain` bottleneck exposure |
| 护城河 | 20% | moat object, gross margin, ROE, peer context, supply-chain scarcity/certification barrier |
| 增长质量 | 20% | revenue growth, earnings growth, gross margin, FCF, supply-chain demand pressure |
| 估值 | 25% | P/S, PSG, forward PE, analyst target, peers |
| 团队/治理 | 15% | insider ownership/signal, SBC ratio |

Thresholds: ≥75 高信心 / 60–75 标准建仓候选 / 45–60 观察 / <45 Pass.

## Serenity Supply-Chain Enrichment

`data.supply_chain.StockChainAnalyzer` is the per-stock adapter for Serenity-style industry-chain analysis.

- It uses deterministic mappings, `data/serenity` knowledge, and optional local cache files; Python code must not call external LLM APIs for this enrichment.
- `generate_analysis()` exposes the result at both `market_data["supply_chain"]` and `market_data["fundamentals"]["supply_chain"]`.
- `ResearchScoreEngine` uses the supply-chain data only as additive evidence for 行业/TAM, 护城河, and 增长质量; missing `supply_chain` must preserve the original score behavior.
- `ReportGenerator` renders the block as `### 产业链位置` inside `## 三、基本面与估值`; do not create a separate top-level Obsidian section for it.
- Supply-chain data must not mask missing core financial fundamentals; data-gap disclosure should still flag missing PE/PB/PS/margins/growth/cash-flow data.

## Wiki Sections

New stock wikis created by `MemoryManager.init_stock_wiki()` contain:

- `## 综合评估`
- `## 证据表`
- `## 五维打分`
- `## 交易时机状态`
- `## 与上次分析相比`
- `## 不对称原型`
- `## 分析时间线`
- `## 预测验证`
- `## 关键事件`
- `## 财报预期`
- `## 财报前情景预判`
- `## 流动性分析`
- `## 期权市场`
- `## 内部人信号`
- `## SBC与稀释`
- `## KOL观点汇总`
- `## 社交情绪`
- `## 研究笔记`
- `## 交叉引用`
- `## 资料索引`

`write_analysis_to_obsidian()` replaces Cockpit sections (`证据表`, `五维打分`, `交易时机状态`, `与上次分析相比`) and appends report content to `研究笔记`.

When appending generated Markdown into existing wiki sections, preserve Obsidian's top-level section structure: strip duplicate module `##` headings before appending to the matching section, and demote generated report headings before writing to `研究笔记`. Keep this behavior covered by `tests/test_section_write.py`.

## Report Requirements for Full Manual Stock Analysis

If writing a comprehensive human-facing analysis manually, include these sections in order:

1. 公司与催化剂
2. 技术面, including SEPA Stage / trend template / VCP assessment
3. 护城河分析
4. 基本面 and growth quality
5. 估值锚点: P/S, PSG, peer table, reverse valuation, asymmetric archetype
6. 市场结构: short interest, IV, GEX, unusual options, structured sentiment, insider signal
7. 风险量化
8. 三情景目标价
9. 操作格网
10. 警戒线 / 加仓信号
11. 关键催化剂日历

Use explicit uncertainty labels when data is missing; do not fabricate values.

## Obsidian Front Matter for Comprehensive Reports

When writing a complete report as a standalone stock wiki page or replacing a page, include:

```yaml
---
title: "{TICKER} {评分}/100 — {核心观点简述}"
source: claude-code
author: "Claude Code"
published: {YYYY-MM-DD}
created: {YYYY-MM-DD HH:MM}
description: "{一句话总结：如 PSG XX，12 个月目标价 $X，建仓价位 $Y}"
tags:
  - stock-analysis
  - {sector}
  - {sub-sector}
  - 12m-target-{目标价}
  - psg-{PSG值}
stock_code: {TICKER.US}
score: {评分}
psg: {PSG值}
target_price: {加权目标价}
current_price: {当前价格}
stage: "{Stage 1 底部整理 / Stage 2 主升浪 / Stage 3 顶部 / Stage 4 下跌}"
moat_score: {护城河综合评分 /10}
insider_signal: "{positive / neutral / negative}"
liquidity: "{liquid / normal / thin}"
earnings_date: "{YYYY-MM-DD}"
---
```

## Symbol Normalization

| Input | Normalized | Market |
|---|---|---|
| `AAPL` | `AAPL.US` | US |
| `00700` | `00700.HK` | HK |
| `603906` | `SH603906` | CN Shanghai |
| `000001` | `SZ000001` | CN Shenzhen |

Use `DataManager.normalize_symbol()` when available.

Yahoo-backed modules use Yahoo Finance symbol conventions after canonical normalization. HK wiki/internal codes remain 5-digit `.HK`, but Yahoo requests use 4-digit `.HK`: `03986.HK` → `3986.HK`, `00700.HK` → `0700.HK`, `00388.HK` → `0388.HK`. Keep this behavior covered by `tests/test_yahoo_symbol.py`.

## Environment Variables

Required:

- `WIKI_BASE_DIR`
- `WIKI_SUBDIR`
- `MATERIALS_SUBDIR`
- `OBSIDIAN_INBOX_DIR`
- `OBSIDIAN_TASKS_DIR`
- `OBSIDIAN_DASHBOARD_PATH`
- `ANALYSIS_TIMEOUT`

Optional:

- Longbridge: `LONGBRIDGE_APP_KEY`, `LONGBRIDGE_APP_SECRET`, `LONGBRIDGE_ACCESS_TOKEN`
- Search: `SERPAPI_KEY`, `NEWSAPI_KEY`
- Watcher folders: `OBSIDIAN_CLIPPINGS_DIR`, `OBSIDIAN_RAW_DIR`
- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`
- Podwise: `PODWISE_CLI_PATH`, `PODWISE_SYNC_DAYS`, `PODWISE_OUTPUT_DIR`
- Scheduler: `SCHEDULE_SCAN_INBOX`, `SCHEDULE_REVIEW`, `SCHEDULE_DASHBOARD`, `SCHEDULE_NOTIFY`

## MCP Tools

`trader_mcp.py` exposes:

- `scan_inbox_tool`
- `get_pending_analysis_tool`
- `get_related_materials_tool`
- `get_stock_context_tool`
- `get_stock_index_tool`
- `get_recent_log_tool`
- `analyze_stock_tool`
- `write_analysis_tool`
- `create_task_tool`
- `update_dashboard_tool`
- `search_stock_news_tool`
- `search_stock_sentiment_tool`
- `search_stock_all_tool`

Resources:

- `mcp://trader/inbox`
- `mcp://trader/stocks`

## Backtest and Review

- `backtest.runner.BacktestRunner` parses legacy `评分:` timeline entries and new `Research: ... | Timing: ...` entries.
- `scripts/run_review.py` runs scheduled reviews and writes results to `预测验证`.
- `scripts/backtest_raycat.py` is a fixed-source utility for raycat.substack.com recommendations and writes `raycat_backtest_report.md` to the wiki directory.

## Common Failure Modes

| Error | Cause | Fix |
|---|---|---|
| `WIKI_BASE_DIR is required` | `.env` missing or empty | copy `.env.example` to `.env` and fill paths |
| Analysis not visible in Obsidian | wrong wiki path or duplicate filename | use `Config.get_wiki_dir()` and underscore filename rule |
| `ModuleNotFoundError: longbridge` | optional SDK missing | install requirements or rely on Yahoo fallback where possible |
| `ModuleNotFoundError: croniter/watchdog/telegram` | optional operational dependency missing | run `pip install -r requirements.txt` |
| `*_error` fields in analysis JSON | one pipeline module failed | proceed with available data and note limitation |
| macOS notification not shown on Windows | `osascript` unavailable | expected; notification module prints fallback text |
