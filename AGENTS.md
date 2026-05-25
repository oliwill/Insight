# AGENTS.md

This file provides guidance to coding agents working in this repository.

## Project Overview

**trader-obsidian** is an Obsidian-native stock research system.

- **Workbench**: Obsidian vault Markdown files.
- **Execution**: Python scripts, Claude Code, and MCP clients.
- **Persistence**: stock wiki pages, archived Materials, Dashboard, Tasks.
- **Core model**: keep long-term Research Score separate from short-term Timing State.

## Non-Negotiable Obsidian Write Rules

Analysis reports must be written to the configured Obsidian vault.

- Use `Config.get_wiki_dir()` for stock wiki pages.
- Resolve the exact wiki path from `Config.get_wiki_dir()`; do not hardcode a personal vault path.
- Convert `.` and `/` in stock codes to `_` for filenames:
  - `TEM.US` → `TEM_US.md`
  - `600487.SH` → `600487_SH.md`
  - `00100.HK` → `00100_HK.md`
- Prefer `write_analysis_to_obsidian()` over direct file writes.
- Do not create duplicate files by mixing `MemoryManager.init_stock_wiki()` with a manual write to a different path.

## Quick Commands

Run from the project root:

```bash
# Regression checks for the current writeback/scoring contracts
python -m pytest tests/test_core_scoring.py tests/test_section_write.py tests/test_yahoo_symbol.py tests/test_backtest_timeline.py tests/test_data_manager_env.py -v
python -c "from input.evidence import EvidenceExtractor; from analyzer.research_score import ResearchScoreEngine; from analyzer.timing_engine import TimingEngine; from run_analysis import write_analysis_to_obsidian; print('core/writeback imports ok')"

# One-click Cockpit analysis; writes directly to Obsidian
python scripts/analyze_stock.py AAPL

# Data-only orchestration path and maintenance commands
python run_analysis.py AAPL
python run_analysis.py --scan
python run_analysis.py --dashboard
python run_analysis.py --inbox

# Scheduled wrappers and optional interfaces
python scripts/scan_inbox.py --dry-run --json
python scripts/run_review.py --days-after 30 --lookback 90
python scripts/update_dashboard.py --json
python scripts/weekly_review.py --json
python trader_mcp.py
python telegram_bot.py --polling
python inbox_watcher.py
python scripts/podwise_sync.py --list
```

Do not run `python scripts/analyze_stock.py <TICKER>` unless the user wants a report written to Obsidian.

## Standard Analysis Workflow

When the user asks to analyze a stock, use this sequence unless they explicitly request a narrower operation.

1. **Fetch project data**:

   ```bash
   python run_analysis.py AAPL
   ```

   Inspect `stock_info`, `fundamentals`, `technicals`, `wyckoff`, `earnings`, `liquidity`, `options`, `web_search`, `peers`, `etf`, `wiki_context`, and `inbox_materials`.

2. **Gather external finance context when needed**. Claude Code agents should use the finance skills named in `CLAUDE.md` for real-time GEX/options flow, insider/congressional trading, analyst estimates, supply-chain mapping, SEPA confirmation, and cross-source sentiment. Other agents should gather equivalent data explicitly and label missing data rather than fabricating it.

3. **Generate or write analysis**:
   - For the local full workflow, prefer `python scripts/analyze_stock.py <TICKER>`.
   - For manual writeback, call `write_analysis_to_obsidian()` so Cockpit sections are replaced safely and report headings are demoted under `研究笔记`.

4. **Update Dashboard** after a completed write:

   ```bash
   python run_analysis.py --dashboard
   ```

## Full Manual Analysis Requirements

For a comprehensive human-facing stock analysis, follow the full manual report contract in `CLAUDE.md`: required sections A–J, explicit uncertainty labels for missing data, and the Obsidian front matter fields for title, source/author, dates, tags, score, PSG, target price, current price, stage, moat score, insider signal, liquidity, and earnings date. Non-Claude agents should apply the same content contract, using their own source/author values only when they are the actual writer.

## Cockpit Architecture

`scripts/analyze_stock.py` performs the current one-click workflow:

1. `data.analysis_pipeline.generate_analysis(stock_code)`.
2. Optional moat enrichment via `analyzer.fundamental.FundamentalAnalyzer`.
3. Wyckoff chart generation into `WIKI_BASE_DIR/Charts/{CODE}_wyckoff.png`.
4. Obsidian evidence extraction from Materials, stock wiki, and related Inbox items.
5. Five-dimension scoring via `analyzer.research_score.ResearchScoreEngine`.
6. Trade timing via `analyzer.timing_engine.TimingEngine`.
7. Report generation via `analyzer.report_generator.ReportGenerator`.
8. Wiki write via `run_analysis.write_analysis_to_obsidian()`.

## Research Score vs Timing State

Do not conflate these two outputs:

| Layer | Question | Output |
|---|---|---|
| Research Score | Is the company/thesis worth owning? | 0–100 five-dimension score |
| Timing State | Is now a good entry? | `Ready`, `Wait`, `Watch`, `Avoid` |

A high Research Score with `Wait` means the thesis may be good but the entry is not ready. Good technicals should not turn a low Research Score into a high-conviction buy.

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

New stock wikis created by `MemoryManager.init_stock_wiki()` contain structured sections including:

- `## 综合评估`
- `## 证据表`
- `## 五维打分`
- `## 交易时机状态`
- `## 与上次分析相比`
- `## 分析时间线`
- `## 预测验证`
- `## 财报预期`
- `## 流动性分析`
- `## 期权市场`
- `## 社交情绪`
- `## 研究笔记`
- `## 交叉引用`
- `## 资料索引`

`write_analysis_to_obsidian()` replaces Cockpit sections (`证据表`, `五维打分`, `交易时机状态`, `与上次分析相比`) and appends report content to `研究笔记`. Preserve Obsidian's top-level section structure; tests in `tests/test_section_write.py` guard this behavior.

## Symbol Normalization

| Input | Normalized | Market |
|---|---|---|
| `AAPL` | `AAPL.US` | US |
| `00700` | `00700.HK` | HK |
| `603906` | `SH603906` | CN Shanghai |
| `000001` | `SZ000001` | CN Shenzhen |

Use `DataManager.normalize_symbol()` when available. Yahoo-backed helpers convert canonical 5-digit HK symbols to Yahoo's 4-digit `.HK` format for requests (`03986.HK` → `3986.HK`, `00700.HK` → `0700.HK`, `00388.HK` → `0388.HK`) while preserving canonical wiki identity.

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

## Backtest and Review

- `backtest.runner.BacktestRunner` parses legacy `评分:` timeline entries and new `Research: ... | Timing: ...` entries.
- `scripts/run_review.py` runs scheduled reviews and writes results to `预测验证`.
- `scripts/weekly_review.py` runs review aggregation, writes `Analysis/复盘_YYYYMMDD.md`, and creates a review task for framework suggestions.
- `scripts/backtest_raycat.py` is a fixed-source utility for raycat.substack.com recommendations and writes `raycat_backtest_report.md` to the wiki directory.

## Common Failure Modes

| Error | Cause | Fix |
|---|---|---|
| `WIKI_BASE_DIR is required` | `.env` missing or empty | copy `.env.example` to `.env` and fill paths |
| Analysis not visible in Obsidian | wrong wiki path or duplicate filename | use `Config.get_wiki_dir()` and underscore filename rule |
| `ModuleNotFoundError: longbridge` | optional SDK missing | install requirements or rely on Yahoo fallback where possible |
| `ModuleNotFoundError: croniter/watchdog/telegram` | optional operational dependency missing | run `pip install -r requirements.txt` |
| `*_error` fields in analysis JSON | one pipeline module failed | proceed with available data and note limitation |
| `scheduler.py --daemon` fails on Windows | `os.fork()` unavailable | run foreground mode or use Windows Task Scheduler |
