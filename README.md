# trader-obsidian

English | [简体中文](README.zh.md)

A stock analysis system that uses Claude Code as the execution engine and Obsidian as the knowledge base. Drop research materials into an Inbox folder, run an analysis command, and get a structured deep-dive written directly into your Obsidian vault.

## How It Works

```
Inbox / Materials / stock wiki
    ↓
input.evidence.EvidenceExtractor
    ↓
analyzer.research_score.ResearchScoreEngine
    ↓
analyzer.timing_engine.TimingEngine
    ↓
analyzer.report_generator.ReportGenerator
    ↓
run_analysis.write_analysis_to_obsidian
    ↓
Obsidian vault (Analysis wiki + Materials + Dashboard)
```

1. Drop a Substack article, Twitter thread, or research note into `Inbox/`
2. Run `python run_analysis.py --scan` or `python run_analysis.py AAPL`
3. Claude Code fetches market data, extracts evidence, computes research score/timing state, and writes structured cockpit sections directly to your Obsidian `.md` files

No Obsidian plugins required. Plain markdown files, synced via Dropbox/iCloud/remotely-save.

## Analysis Framework

Each analysis produces a structured report with these sections:

| Section | Content |
|---|---|
| A. 公司与催化剂 | Business description + recent catalysts + supply chain positioning |
| B. 技术面 | RSI/MACD/Bollinger + **SEPA Stage analysis** (trend template + VCP) |
| B2. 护城河 | Moat rating per dimension + competitive gap quantification |
| C. 基本面 | Financials + growth trajectory + **growth quality** (customer concentration, geo exposure, SBC) |
| D. 估值 | P/S + PSG + peer table + **reverse valuation** + asymmetric bet archetype |
| E. 市场结构 | Short interest + IV + **GEX** + options flow + structured sentiment |
| F. 风险量化 | 3–5 risks with revenue/valuation impact + probability |
| G. 三情景目标价 | Bull/Base/Bear with probability-weighted 12m target |
| H. 操作格网 | Entry grid by price level with position sizing |
| I. 警戒线/加仓信号 | Observable boolean conditions only |
| J. 催化剂日历 | Date × event × upside/downside scenario |

### Scoring — Five-Dimension Framework

| Dimension | Weight | Key Data Source |
|---|---|---|
| 行业/TAM | 20% | `stock-correlation` + `finance-sentiment` |
| 护城河 | 20% | `funda-data` supply chain + `stock-correlation` peers |
| 增长质量 | 20% | `yfinance-data` + `funda-data` SEC filings |
| 估值 | 25% | `funda-data` analyst estimates + peer multiples |
| 团队 | 15% | `funda-data` insider trades + congressional trades |

Thresholds: ≥75 high-conviction / 60–75 standard / 45–60 watch / <45 pass

### PSG Framework

`PSG = P/S ÷ Revenue Growth%`

- PSG < 1 → reasonable
- PSG 1–2 → elevated
- PSG > 2 → extreme overvaluation

## Quick Start

```bash
git clone https://github.com/oliwill/obsidiantrader.git
cd obsidiantrader
pip install -r requirements.txt
cp .env.example .env   # fill in your paths and optional API keys
```

Configure `.env`:

```env
WIKI_BASE_DIR=/path/to/your/obsidian/vault
WIKI_SUBDIR=4_Trader/Analysis
MATERIALS_SUBDIR=4_Trader/Materials
OBSIDIAN_INBOX_DIR=/path/to/your/obsidian/vault/Inbox
OBSIDIAN_TASKS_DIR=/path/to/your/obsidian/vault/4_Trader/Tasks
OBSIDIAN_DASHBOARD_PATH=/path/to/your/obsidian/vault/Dashboard.md
ANALYSIS_TIMEOUT=30

# Optional — falls back to Yahoo Finance if missing
LONGBRIDGE_APP_KEY=
LONGBRIDGE_APP_SECRET=
LONGBRIDGE_ACCESS_TOKEN=
```

## Commands

```bash
# Quick analysis (recommended) - generates formatted report and writes to Obsidian
python scripts/analyze_stock.py AAPL        # US stock
python scripts/analyze_stock.py 00700       # HK stock (auto-normalized to 00700.HK)
python scripts/analyze_stock.py 603906      # A-share (auto-normalized to SH603906)

# Full analysis workflow (Claude Code orchestration)
python run_analysis.py AAPL        # Outputs JSON for Claude Code analysis
python run_analysis.py --scan     # Process all pending Inbox items
python run_analysis.py --dashboard  # Rebuild Dashboard only
python run_analysis.py --inbox     # Show Inbox status
```

## Obsidian Vault Structure

```
vault/
├── Inbox/              ← drop materials here
│   └── NVDA_note.md
├── 4_Trader/           ← adjust prefix to match your vault numbering
│   ├── Analysis/       ← auto-managed stock wikis + weekly review reports
│   │   ├── AAPL_US.md
│   │   └── 复盘_20260510.md
│   ├── Materials/      ← raw material archives per stock
│   │   └── TSLA_US/
│   ├── Charts/         ← auto-generated Wyckoff charts
│   └── Tasks/          ← auto-created trade/research tasks
└── Dashboard.md        ← portfolio overview, auto-updated
```

> **Note**: The `4_Trader/` prefix matches a typical Obsidian folder-numbered vault. Set `WIKI_SUBDIR` and `MATERIALS_SUBDIR` in `.env` to match your actual structure.

## Inbox Material Format

Create a `.md` file in `Inbox/` with YAML frontmatter:

```yaml
---
title: NVDA Q1 earnings beat
source: twitter          # twitter | substack | wechat | pdf | note
ticker: NVDA
analyze: true
tags: AI, semiconductors, datacenter
---

Paste the content here...
```

After processing, `processed: true` and `processed_at` are appended automatically.

## Project Structure

```
trader-obsidian/
├── run_analysis.py       # main entry point (Claude Code orchestration)
├── scripts/
│   └── analyze_stock.py  # one-click analysis with formatted report
├── analyzer/
│   ├── research_score.py # five-dimension thesis/company quality scoring
│   ├── timing_engine.py  # Ready/Wait/Watch/Avoid timing state machine
│   ├── report_generator.py  # unified report formatting (tables + emojis)
│   ├── fundamental.py    # fundamental analysis + 6-dimension moat scoring
│   ├── trading_grid.py   # Fibonacci levels, ATR stops, R/R ratios
│   ├── wyckoff.py        # Wyckoff phase detection
│   ├── wyckoff_chart.py  # Wyckoff chart visualization (price, MA, zones, phases)
│   └── comprehensive.py  # combined scoring
├── data/
│   ├── analysis_pipeline.py  # complete data pipeline
│   ├── manager.py        # DataManager: Longbridge API + Yahoo Finance fallback
│   ├── sentiment_analyzer.py  # sentiment scoring: news, social, fear/greed
│   ├── earnings.py       # earnings calendar + surprise history
│   ├── options.py        # options chain: IV, GEX, unusual activity
│   ├── liquidity.py      # short interest, ADTV, market impact
│   └── correlation.py    # peer correlation matrix
├── memory/
│   ├── manager.py        # MemoryManager: wiki read/write, timeline, materials
│   ├── utils.py          # paths, dates, file I/O helpers
│   └── section_parser.py # Markdown section parsing/replacement
├── input/
│   ├── evidence.py       # typed evidence extraction from wiki/materials/Inbox
│   └── ingest.py         # material intake with tag indexing
├── inbox_scanner.py      # scans Inbox/ for pending analysis
├── skills/               # agent workflow checklists (think/check/hunt/learn)
└── backtest/
    ├── core.py           # BacktestEngine, BacktestResult, SignalPerformance
    ├── runner.py         # BacktestRunner: batch execution + wiki integration
    ├── review.py         # ReviewScheduler: daily review pipeline
    ├── framework_analyzer.py  # FrameworkAnalyzer: pattern analysis + framework suggestions
    └── report.py         # ReportGenerator: markdown/CSV/chart outputs
```

## Core Scoring and Timing

The reusable analysis kernel separates company quality from entry timing:

| Module | Responsibility |
|---|---|
| `input.evidence` | Convert wiki, Materials and Inbox snippets into typed evidence claims |
| `analyzer.research_score` | Produce base and evidence-adjusted five-dimension Research Score |
| `analyzer.timing_engine` | Produce a separate Ready/Wait/Watch/Avoid timing state |
| `run_analysis.write_analysis_to_obsidian` | Write evidence, score, timing, comparison, timeline and research-note sections into Obsidian without duplicate top-level headings |

Timeline/history consumers support both legacy `评分:` rows and cockpit `Research:` / `Timing:` rows, so backtests and learning stats remain compatible across report formats.

## Data Sources

| Source | Used For | Requires |
|---|---|---|
| Yahoo Finance | Fundamentals, history, options, earnings | Nothing (default) |
| Longbridge API | Real-time quotes, HK/CN stocks, K-lines | `pip3 install longbridge` + API credentials in `.env` |

The system silently falls back to Yahoo Finance if Longbridge credentials are absent or the API times out. Get credentials at [open.longportapp.com](https://open.longportapp.com/).

## Skills (Agent Workflows)

The `skills/` directory contains structured checklists that guide Claude Code through each workflow phase:

| Skill | Purpose |
|---|---|
| `think/` | Pre-analysis: goal setting, method selection, 5-dimension scoring guide |
| `check/` | Post-analysis: logic verification, anomaly detection, completeness checklist |
| `hunt/` | Debugging: systematic issue resolution |
| `learn/` | Pattern extraction from accumulated analyses |
| `backtest/` | Signal validation: entry/exit vs historical price |

## Symbol Normalization

| Input | Internal Code | Market | Yahoo Finance Code |
|---|---|---|---|
| `AAPL` | `AAPL.US` | US | `AAPL` |
| `00700` | `00700.HK` | HK | `0700.HK` |
| `03986.HK` | `03986.HK` | HK | `3986.HK` |
| `603906` | `SH603906` | CN Shanghai | `603906.SS` |
| `000001` | `SZ000001` | CN Shenzhen | `000001.SZ` |

`DataManager.normalize_symbol()` handles the canonical internal code. Yahoo-backed helpers convert HK symbols to Yahoo's four-digit `.HK` form for data requests while preserving the canonical code for wiki filenames and Obsidian identity.

## Project Documentation

- [Architecture](docs/architecture.md) — analysis pipeline, Obsidian writeback, symbol model
- [Runbook](docs/runbook.md) — setup, verification commands, troubleshooting
- [Handoff](docs/handoff.md) — completed batches, open PRs, next-batch guidance

## Requirements

- Python 3.9+
- Obsidian vault with a sync solution (Dropbox, iCloud, remotely-save, etc.)
- Claude Code CLI (for running the analysis agent)

Optional: [Longbridge](https://open.longportapp.com/) account for real-time HK/CN data.

## License

MIT
