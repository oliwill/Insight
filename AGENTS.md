# Repository Guidelines

Guidance for AI assistants working in this repository. For the full analysis-report
specification (sections A–J, front matter, five-dimension scoring), see `CLAUDE.md`;
for component detail see `docs/architecture.md`; for ops commands see `docs/runbook.md`.

## Project Overview

**trader-obsidian** (a.k.a. *Insight*) is a Python stock-analysis pipeline that uses
Obsidian as the durable research workspace and an AI agent (Claude Code / Codex) as the
reasoning engine. It collects market data, extracts typed evidence from the vault,
separates company-quality scoring (Research Score) from trade timing (Timing State),
and writes structured Markdown back into the vault. It never executes trades.

## Architecture & Data Flow

```
Obsidian Inbox ──► inbox_scanner ──► data.analysis_pipeline.generate_analysis(code)
                                          │
Wiki / Materials ─► input.evidence ───────┤   (each stage emits `*_error` on failure,
                                          ▼    never aborts; fallbacks logged in `_data_sources`)
   data.supply_chain (Serenity) → analyzer.research_score (5-dim, weighted)
   analyzer.wyckoff + 趋势博弈四模块 ──────► analyzer.timing_engine (Ready/Wait/Watch/Avoid)
                                          ▼
                     analyzer.report_generator → analyzer.report_quality
                                          ▼
                     memory.manager ──► Analysis/{CODE}.md, Dashboard.md, Tasks/
                                          ▼
                     backtest.runner / review ──► ## 预测验证 + output/review_*
```

Key contracts an assistant must not break:

- **Wiki file naming**: symbol `.`/`/` → `_` (`TEM.US` → `TEM_US.md`, `03986.HK` → `03986_HK.md`), written under `Config.get_wiki_dir()`.
- **Wiki sections**: `证据表` / `五维打分` / `交易时机状态` / `与上次分析相比` are *replaced* each run; `分析时间线` / `预测验证` / `研究笔记` / `资料索引` are *append-only*.
- **Supply-chain enrichment** is additive and deterministic: no external LLM calls, no new top-level Obsidian sections, must not hide missing fundamentals (`docs/architecture.md`).
- The `himself65/finance-skills` agent plugin is **not** a Python dependency of `data.analysis_pipeline` or the scoring/reporting path. Social/source readers stay read-only.

## Key Directories

| Path | Purpose |
|---|---|
| `analyzer/` | Scoring & reporting: `research_score.py`, `timing_engine.py`, `report_generator.py`, `report_quality.py`, `fundamental.py`, `wyckoff*.py`, `dow_channel.py`, `volume_profile.py`, `force_balance.py`, `multi_timeframe.py` |
| `data/` | Data layer: `manager.py` (DataManager + symbol normalization), `analysis_pipeline.py`, `supply_chain.py`, `serenity/`, `search.py`, `options.py`, `earnings.py`, `liquidity.py`, `correlation.py`, `etf.py`, `akshare_source.py`, `sentiment_analyzer.py`, `portfolio_loader.py` |
| `memory/` | Vault persistence: `manager.py` (MemoryManager), `section_parser.py` |
| `input/` | Intake: `evidence.py` (EvidenceExtractor), `ingest.py` (tags_index.json) |
| `backtest/` | `runner.py`, `review.py`, `core.py`, `report.py`, `framework_analyzer.py` |
| `scripts/` | CLI entry points (see Development Commands) + `windows/` PowerShell wrappers |
| `tests/` | pytest suite, incl. `tests/test_serenity/` subpackage |
| `web/` | FastAPI-style `routers/` + `frontend/` |
| `website/` | Standalone static page (unrelated to `web/`) |
| `skills/` | Public agent skill `stock-research-cockpit/` + internal skills; locked by `skills-lock.json` |
| `docs/` | `architecture.md`, `runbook.md`, `integration-guide.md`, `handoff.md`, `plans/` |
| `launchd/` | macOS scheduled-job plists (Windows equivalent: `scripts/windows/*.ps1`) |
| `output/`, `tmp_analysis/`, `logs/` | Generated artifacts — never edit by hand |

## Development Commands

Run from project root.

```bash
# Install
pip install -r requirements.txt            # runtime
pip install -r requirements-dev.txt        # + pytest

# Core workflow
python scripts/analyze_stock.py AAPL       # canonical one-click analysis → writes Obsidian wiki
python run_analysis.py AAPL                # JSON data dump for agent reasoning (no write)
python run_analysis.py --scan              # process pending Inbox items
python run_analysis.py --dashboard         # update Dashboard.md
python one_shot_analysis.py AAPL           # JSON via subprocess-isolated pipeline (timeout-wrapped)

# Scheduled-task equivalents (also run by scheduler.py / launchd / Task Scheduler)
python scripts/scan_inbox.py --dry-run --json
python scripts/run_review.py --list-tickers --json
python scripts/update_dashboard.py --json
python scripts/weekly_review.py
python scripts/portfolio_scan.py           # batch lean scan of holdings
python scripts/generate_full_report.py     # 11-section A–J full report
python scripts/serenity_scan.py            # industry-chain scan
python scripts/podwise_sync.py             # import podcast notes into vault

# Optional interfaces
python trader_mcp.py                       # MCP server (scan/context/write/search tools)
python telegram_bot.py --polling           # /note /get /scan /inbox /task
python inbox_watcher.py                    # watchdog on Inbox/Clippings/Raw
python scheduler.py                        # croniter-based daemon (SCHEDULE_* env vars)

# Windows smoke tests
powershell -ExecutionPolicy Bypass -File scripts\windows\run_smoke_tests.ps1
powershell -ExecutionPolicy Bypass -File scripts\windows\run_write_smoke_examples.ps1 -PythonExe ".\.venv\Scripts\python.exe"
```

## Code Conventions & Common Patterns

- **Language**: Python, snake_case throughout; docstrings, report headings, and user-facing strings are commonly Chinese — match the surrounding language.
- **Config**: single source is `config.py` — a `Config` class reading env vars once via `python-dotenv` at import. Add new settings there with `os.getenv(..., default)`, not scattered `os.environ` reads. Validate with `Config.validate()` / `ensure_config()`.
- **Error handling**: pipeline stages catch failures locally and attach a `*_error` key to the result dict instead of raising; source fallbacks are recorded under `_data_sources` (`data/analysis_pipeline.py`). Don't let one failed source abort the whole analysis.
- **Data-source fallback**: Longbridge → Yahoo Finance (`yfinance`) → akshare (CN A-shares). Missing Longbridge credentials must degrade silently to Yahoo.
- **Timeout isolation**: external data fetches run through the `one_shot_analysis.py` subprocess wrapper governed by `ANALYSIS_TIMEOUT` (default 30s). On `"error": "timeout"`, proceed with partial data and note the limitation.
- **stdout hygiene**: CLI tools that emit JSON reconfigure UTF-8 (`sys.stdout.reconfigure(encoding='utf-8')`) and redirect `loguru`/logging to stderr so stdout stays parseable.
- **Symbol normalization**: canonical forms are `AAPL.US`, `00700.HK`, `SH603906` / `SZ000001`; use `DataManager.normalize_symbol()`. Yahoo helpers convert HK to 4-digit form (`00700.HK` → `0700.HK`) only at the data-request boundary.
- **Synchronous codebase** — no async/await in the pipeline; concurrency is via subprocesses and the filesystem.
- **State** lives in the Obsidian vault (Markdown + front matter) and JSON side files (`tags_index.json`, `data/cache/supply_chain/*.json`, `tmp_analysis/`). There is no database.
- **Scheduling**: cron strings from `SCHEDULE_*` env vars via `croniter`; macOS uses `launchd/*.plist`, Windows uses `scripts/windows/register_scheduled_tasks.ps1`.

## Important Files

| File | Role |
|---|---|
| `scripts/analyze_stock.py` | Canonical full local workflow (fetch → score → chart → report → write) |
| `run_analysis.py` | CLI orchestration: JSON fetch, `--scan`, `--dashboard`, `write_analysis_to_obsidian()`, `write_task()` |
| `data/analysis_pipeline.py` | `generate_analysis(code)` — one-call pipeline returning the full data dict |
| `memory/manager.py` | MemoryManager: wiki init, section replace/append, timeline, Materials, evaluation table |
| `config.py` + `.env.example` | All configuration; copy `.env.example` → `.env` and set vault paths |
| `CLAUDE.md` | Authority for the comprehensive-report format (11 sections, front matter, scoring weights) |
| `docs/architecture.md` | Component map, pipeline fields, persistence model, interfaces |
| `docs/runbook.md` | Ops commands, smoke tests, troubleshooting |
| `trader_mcp.py` | MCP server entry |
| `skills-lock.json` | Imported finance-skill sources + hashes |

Required env vars (see `.env.example`): `WIKI_BASE_DIR`, `OBSIDIAN_INBOX_DIR`,
`OBSIDIAN_TASKS_DIR`, `OBSIDIAN_DASHBOARD_PATH` (+ `ANALYSIS_TIMEOUT`).
`LONGBRIDGE_*`, `SERPAPI_KEY`, `NEWSAPI_KEY`, `TELEGRAM_*`, `PODWISE_*` are optional
enhancements with graceful fallbacks. Never commit `.env`.

## Runtime/Tooling Preferences

- **Python 3.12+** (3.12 and 3.14 both verified in use); plain `pip` + `requirements.txt` — no Poetry/uv/conda.
- Virtual environment recommended; on Windows reference it explicitly, e.g. `.venv\Scripts\python.exe`.
- Key deps: `pandas`, `numpy`, `yfinance`, `akshare`, `longbridge`, `matplotlib`, `loguru`, `python-dotenv`, `requests`, `lxml`; optional: `mcp`, `croniter`, `watchdog`, `python-telegram-bot`.
- Cross-platform: macOS (`launchd/`) and Windows (`scripts/windows/*.ps1`); keep shell examples for both where relevant.
- Agent-layer finance skills install via `npx plugins add himself65/finance-skills` — agent tooling only, never a Python import.

## Testing & QA

- **Framework**: pytest (sole dev dependency). No coverage gate is enforced; tests are regression guards for pipeline and vault-write contracts.
- **Full suite**: `python -m pytest tests/ -v`
- **Core regression subset** (run before touching scoring/writeback):
  ```bash
  python -m pytest tests/test_core_scoring.py tests/test_section_write.py tests/test_yahoo_symbol.py tests/test_backtest_timeline.py tests/test_data_manager_env.py -v
  ```
- **Runbook guard suites**: supply-chain guards and regression guards are enumerated in `docs/runbook.md` — on Windows prefix with `PYTHONIOENCODING=utf-8`.
- **Conventions**: stdlib-style `test_*.py` functions; heavy use of `monkeypatch` (env vars, fake modules) and `tmp_path`; unit tests must not hit the network — fake/stub external sources (see `tests/test_data_manager_env.py`, `tests/test_data_source_resilience.py`).
- **Write-smoke gate**: after changing report/writeback code, run `scripts/windows/run_write_smoke_examples.ps1` (or `scripts/analyze_stock.py HIMS.US` + `03986.HK` manually) and `scripts/verify_write_smoke.py` to validate wiki file shape, section anchors, and heading nesting.
- **Syntax-only check** when pytest/.env unavailable: `python -m py_compile config.py run_analysis.py scripts/analyze_stock.py trader_mcp.py` (full list in `docs/runbook.md`).
