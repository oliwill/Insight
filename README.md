# trader-obsidian

English | [简体中文](README.zh.md)

A stock analysis system that uses Claude Code as the reasoning engine and Obsidian as the durable research workspace. It collects market data, extracts evidence from your vault, separates company-quality scoring from trade timing, and writes structured analysis back to Markdown files.

## Workflow

```
Inbox / Materials / stock wiki
    ↓
data.analysis_pipeline.generate_analysis()
    ↓
EvidenceExtractor → ResearchScoreEngine → TimingEngine
    ↓
ReportGenerator + MemoryManager
    ↓
Obsidian Analysis wiki + Dashboard + Tasks
```

Core distinction:

| Layer | Purpose | Output |
|---|---|---|
| Evidence | Convert wiki, Materials and Inbox snippets into typed claims | `## 证据表` |
| Research Score | Five-dimension company/thesis quality score | `## 五维打分` |
| Timing State | Entry quality state machine independent from research quality | `Ready / Wait / Watch / Avoid` |
| Backtest | Verify historical timeline signals after a holding window | `## 预测验证` + `output/review_*` |
| Public skill | Reusable AI workflow for users without the full local setup | `skills/stock-research-cockpit` |

## Quick Start

```bash
git clone https://github.com/oliwill/Insight.git
cd Insight
pip install -r requirements.txt
cp .env.example .env
```

Minimal `.env`:

```env
WIKI_BASE_DIR=/path/to/your/obsidian/vault/4_Trader
WIKI_SUBDIR=Analysis
MATERIALS_SUBDIR=Materials
OBSIDIAN_INBOX_DIR=/path/to/your/obsidian/vault/Inbox
OBSIDIAN_TASKS_DIR=/path/to/your/obsidian/vault/Tasks
OBSIDIAN_DASHBOARD_PATH=/path/to/your/obsidian/vault/Dashboard.md
ANALYSIS_TIMEOUT=30
```

Optional integrations are documented in `.env.example`: Longbridge, NewsAPI, Telegram bot, Inbox watcher folders, Podwise, and scheduler cron strings.

## Skills Update

This version updates the skills layer so the research workflow can be reused outside the full local pipeline. It includes:

| Skill set | Path | Purpose |
|---|---|---|
| Public cockpit skill | `skills/stock-research-cockpit/` | Portable AI workflow for evidence-backed stock research |
| Finance companion skills | `.agents/skills/` | Optional valuation, estimates, sentiment, source-reader, and market-analysis helpers |
| Skill lockfile | `skills-lock.json` | Records the imported finance-skill sources and hashes |

The public skill is the recommended starting point for users who only want the research workflow:

```text
skills/stock-research-cockpit/
```

The skill packages the core workflow as AI instructions:

- Skill-only mode for any AI agent that can read the skill folder.
- Local companion mode when this repo, CLI, or MCP server is available.
- External finance-skills mode for richer valuation, sentiment, source-reader, and market-structure coverage.

It preserves the core product boundary: evidence-backed research, five-dimension Research Score, independent Timing State, data-gap disclosure, and no trade execution.

### Install skills

If you are using this repository with an AI agent that can load repo-local skills, no extra install step is needed. Keep the public skill folder in place:

```text
skills/stock-research-cockpit/
```

For a Codex-style local skills directory on macOS/Linux:

```bash
mkdir -p ~/.codex/skills
cp -R skills/stock-research-cockpit ~/.codex/skills/
```

For Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills" | Out-Null
Copy-Item -Recurse -Force ".\skills\stock-research-cockpit" "$env:USERPROFILE\.codex\skills\stock-research-cockpit"
```

If your agent reads skills from `~/.agents/skills`, copy the public skill there instead. Use whichever local skills directory your AI client indexes.

macOS/Linux:

```bash
mkdir -p ~/.agents/skills
cp -R skills/stock-research-cockpit ~/.agents/skills/
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.agents\skills" | Out-Null
Copy-Item -Recurse -Force ".\skills\stock-research-cockpit" "$env:USERPROFILE\.agents\skills\stock-research-cockpit"
```

To enable the optional finance companion skills, copy the vendored skill bundle as well:

```bash
mkdir -p ~/.agents/skills
cp -R .agents/skills/* ~/.agents/skills/
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.agents\skills" | Out-Null
Copy-Item -Recurse -Force ".\.agents\skills\*" "$env:USERPROFILE\.agents\skills\"
```

After copying skills into a local skills directory, restart or reload the AI agent so it can index the new folders.

## Commands

```bash
# One-click Cockpit analysis; writes directly to Obsidian
python scripts/analyze_stock.py AAPL
python scripts/analyze_stock.py 00700
python scripts/analyze_stock.py 603906

# Claude Code orchestration data fetch
python run_analysis.py AAPL
python run_analysis.py --scan
python run_analysis.py --dashboard
python run_analysis.py --inbox

# Scheduled-task entry points
python scripts/scan_inbox.py --dry-run --json
python scripts/run_review.py --days-after 30 --lookback 90
python scripts/update_dashboard.py --json
python scripts/update_dashboard.py --json --reason scheduled
python scripts/update_dashboard.py --json --reason manual
python scripts/update_dashboard.py --restore-backup --json

# Optional utilities
python inbox_watcher.py
python telegram_bot.py --polling
python scripts/podwise_sync.py --list
python scripts/backtest_raycat.py
python trader_mcp.py
```

## Obsidian Structure

Recommended layout:

```
vault/
├── Inbox/                 # user drops source notes here
├── Tasks/                 # task files created by write_task()
├── Dashboard.md           # portfolio/research dashboard
└── 4_Trader/
    ├── Analysis/          # stock wiki pages: AAPL_US.md
    ├── Materials/         # archived materials per stock
    └── Charts/            # generated Wyckoff charts
```

File naming rule: `.` and `/` in stock codes are replaced by `_`.

| Stock code | Wiki file |
|---|---|
| `TEM.US` | `TEM_US.md` |
| `600487.SH` | `600487_SH.md` |
| `00100.HK` | `00100_HK.md` |

Ticker normalization keeps canonical internal symbols while adapting to each data source. For Yahoo-backed modules, 5-digit HK symbols are converted to Yahoo's 4-digit `.HK` format: `03986.HK` → `3986.HK`, `00700.HK` → `0700.HK`, `00388.HK` → `0388.HK`. Tests in `tests/test_yahoo_symbol.py` guard these examples.

## Analysis Output

Each stock wiki is initialized with these core sections:

| Section | Updated by |
|---|---|
| `综合评估` | `MemoryManager.update_evaluation_table()` |
| `证据表` | `EvidenceExtractor` + `update_cockpit_sections()` |
| `五维打分` | `ResearchScoreEngine` |
| `交易时机状态` | `TimingEngine` |
| `与上次分析相比` | `scripts/analyze_stock.py` comparison helper |
| `分析时间线` | `MemoryManager.append_to_timeline()` |
| `预测验证` | `BacktestRunner` / `ReviewScheduler` |
| `财报预期` | `data.earnings.EarningsCalendar` |
| `流动性分析` | `data.liquidity.LiquidityAnalyzer` |
| `期权市场` | `data.options.OptionsAnalyzer` |
| `社交情绪` | `data.search.StockSearchEngine` + `SentimentAnalyzer` |
| `研究笔记` | `ReportGenerator` full Markdown report |
| `交叉引用` | `data.correlation.CorrelationAnalyzer` |
| `资料索引` | `MemoryManager.save_material()` |

## Scoring Framework

`ResearchScoreEngine` implements the five-dimension framework:

| Dimension | Weight | Main inputs |
|---|---:|---|
| 行业/TAM | 20% | sector, peers, search/social signals |
| 护城河 | 20% | moat analysis, margins, peer context |
| 增长质量 | 20% | revenue growth, earnings growth, margins, FCF |
| 估值 | 25% | P/S, PSG, forward PE, analyst target |
| 团队/治理 | 15% | insider ownership/signal, SBC pressure |

Thresholds: ≥75 high-conviction / 60–75 standard candidate / 45–60 watch / <45 pass.

`TimingEngine` then produces a separate trade-timing state:

| State | Meaning |
|---|---|
| `Ready` | actionable setup if position sizing is acceptable |
| `Wait` | thesis may be valid, but entry trigger is missing |
| `Watch` | low-confidence setup; monitor only or tiny probe |
| `Avoid` | research quality or timing risk is too poor |

## Data Sources

| Source | Used for | Requirement |
|---|---|---|
| Yahoo Finance | price history, fundamentals, options, earnings, news | default |
| DuckDuckGo HTML | web/social fallback search | default |
| NewsAPI | news enrichment | `NEWSAPI_KEY` |
| Longbridge | HK/CN quotes and K-lines | Longbridge credentials |
| Obsidian vault | prior theses, materials, Inbox evidence | `.env` paths |
| External finance-skills | analyst-grade data, valuation, estimates, sentiment, TradingView, and read-only social/source readers | optional Claude Code skills from `himself65/finance-skills` |

The pipeline is fault-tolerant: failed modules return `*_error` fields, data-source attempts are exposed under `_data_sources`, and the rest of the report can still be generated.

## Module Map

| Module | Purpose |
|---|---|
| `data.analysis_pipeline` | one-call data collection and technical calculations |
| `analyzer.research_score` | evidence-adjusted five-dimension scoring |
| `analyzer.timing_engine` | Ready/Wait/Watch/Avoid timing state machine |
| `input.evidence` | rule-based evidence extraction from wiki/materials/Inbox |
| `analyzer.report_generator` | final Markdown report generation |
| `analyzer.report_quality` | report structure, data-gap, and Research/Timing separation checks |
| `skills/stock-research-cockpit` | reusable AI skill for stock research cockpit reports |
| `memory.manager` | Obsidian wiki, Materials, timeline, dashboard persistence |
| `backtest.runner` / `backtest.review` | timeline signal verification, extended metrics, and review reports |
| `trader_mcp.py` | MCP server for Claude Desktop / MCP clients |
| `telegram_bot.py` | optional mobile command interface |
| `inbox_watcher.py` | optional folder watcher that triggers Inbox scans |
| `scripts/podwise_sync.py` | optional Podcast note import into Obsidian |

## More Documentation

- `docs/architecture.md` — system design and data flow
- `docs/integration-guide.md` — MCP, Telegram, Inbox and Podwise integration steps
- `docs/runbook.md` — operations, scheduling, verification and troubleshooting
- `docs/handoff.md` — current handoff snapshot for new agents and maintainers
- `MCP_CONFIG.md` — MCP server configuration reference
- `SCHEDULER.md` — launchd and Python scheduler notes

## License

MIT
