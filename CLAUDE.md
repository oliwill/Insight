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
- Resolve the exact wiki path from `Config.get_wiki_dir()`; do not hardcode a vault path.
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

# Optional interfaces
python trader_mcp.py
python telegram_bot.py --polling
python inbox_watcher.py
python scripts/podwise_sync.py --list
```

## Standard Analysis Workflow

When the user asks to analyze a stock, use this sequence unless they explicitly request a narrower operation.

1. **Fetch project data**:

   ```bash
   python run_analysis.py AAPL
   ```

   Inspect:
   - `stock_info`: price, market, sector, industry.
   - `fundamentals`: valuation, margins, growth, analyst targets.
   - `technicals`: MA, RSI, MACD, KDJ, Bollinger, support/resistance.
   - `wyckoff`: phase, support, resistance, confidence.
   - `earnings`, `liquidity`, `options`, `web_search`, `peers`, `etf`.
   - `wiki_context` and `inbox_materials`.

2. **Run required finance skills for current data gaps**:

   | Skill | Purpose | When |
   |---|---|---|
   | `finance-skills-funda-data` | options flow/GEX, insider/congressional trading, analyst estimates, supply chain | every full stock analysis |
   | `finance-skills-stock-correlation` | peer P/S baseline and related stocks | every full stock analysis |
   | `finance-skills-finance-sentiment` | Reddit / X / Polymarket structured sentiment | every full stock analysis |
   | `finance-skills-sepa-strategy` | Stage + trend-template + VCP setup | every full stock analysis |
   | `finance-skills-earnings-preview` | consensus and beat/miss setup | within 30 days before earnings |
   | `finance-skills-earnings-recap` | actual vs expected, reaction, call notes | after earnings |
   | `finance-skills-stock-liquidity` | ADTV, spread, market impact | small-cap or thin-liquidity names |
   | `finance-skills-twitter-reader` | KOL signals | when a named KOL or holding signal matters |

3. **Write the analysis** using `write_analysis_to_obsidian()` or `scripts/analyze_stock.py` output path.

4. **Update dashboard** after a completed write:

   ```bash
   python run_analysis.py --dashboard
   ```

## Cockpit Architecture

The current one-click script is `scripts/analyze_stock.py`.

It performs:

1. `data.analysis_pipeline.generate_analysis(stock_code)`.
2. Optional moat enrichment via `analyzer.fundamental.FundamentalAnalyzer`.
3. Wyckoff chart generation into `WIKI_BASE_DIR/Charts/{CODE}_wyckoff.png`.
4. Obsidian evidence extraction:
   - `MemoryManager.get_materials()`
   - `MemoryManager.get_stock_context()`
   - `inbox_scanner.get_related_materials()`
   - `input.evidence.EvidenceExtractor`
5. Five-dimension scoring via `analyzer.research_score.ResearchScoreEngine`.
6. Trade timing via `analyzer.timing_engine.TimingEngine`.
7. Report generation via `analyzer.report_generator.ReportGenerator`.
8. Wiki write via `run_analysis.write_analysis_to_obsidian()`.

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
| 行业/TAM | 20% | sector, industry, peers, social/prediction-market attention |
| 护城河 | 20% | moat object, gross margin, ROE, peer context |
| 增长质量 | 20% | revenue growth, earnings growth, gross margin, FCF |
| 估值 | 25% | P/S, PSG, forward PE, analyst target, peers |
| 团队/治理 | 15% | insider ownership/signal, SBC ratio |

Thresholds: ≥75 高信心 / 60–75 标准建仓候选 / 45–60 观察 / <45 Pass.

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
