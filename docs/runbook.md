# Runbook

Operational checks and troubleshooting for trader-obsidian.

## Install / Update Dependencies

```bash
pip install -r requirements.txt
```

Optional features require the same requirements file:

| Feature | Dependency |
|---|---|
| MCP server | `mcp` |
| Python scheduler | `croniter` |
| Inbox watcher | `watchdog` |
| Telegram bot | `python-telegram-bot` |
| Yahoo Finance data | `yfinance` |
| Longbridge data | `longbridge` |

## Smoke Tests

Run from project root.

```bash
# Verify imports and syntax
python -m py_compile config.py run_analysis.py scripts/analyze_stock.py trader_mcp.py
python -m py_compile data/manager.py data/earnings.py data/liquidity.py data/options.py data/correlation.py data/etf.py data/search.py

# Verify regression guards
PYTHONIOENCODING=utf-8 python -m pytest tests/test_yahoo_symbol.py tests/test_section_write.py

# Verify config is visible
python -c "from config import Config; print(Config.get_wiki_dir())"

# Fetch data without writing a report
python run_analysis.py AAPL

# Scan Inbox without mutating files
python scripts/scan_inbox.py --dry-run --json

# Update Dashboard
python scripts/update_dashboard.py --json

# Run weekly review without writing a full stock analysis
python scripts/weekly_review.py --json
```

For a full report write:

```bash
python scripts/analyze_stock.py AAPL
```

For fixed US + HK end-to-end smoke checks:

```bash
PYTHONIOENCODING=utf-8 python scripts/analyze_stock.py HIMS.US
PYTHONIOENCODING=utf-8 python scripts/analyze_stock.py 03986.HK
```

Expected side effects:

- `Analysis/HIMS_US.md` and `Analysis/03986_HK.md` exist under `Config.get_wiki_dir()` after the fixed smoke checks.
- `Analysis/AAPL_US.md` exists under `Config.get_wiki_dir()` if the quick-start AAPL example is tested.
- `Charts/{CODE}_wyckoff.png` may exist under `WIKI_BASE_DIR/Charts` if enough historical rows are available.
- Top-level sections such as `研究笔记`, `财报预期`, `流动性分析`, `期权市场`, and `交叉引用` should appear once as line-anchored `##` headings.
- Report headings inside `研究笔记` should be nested as `###` or lower, not `#` or `##`.
- Dashboard updates when `python run_analysis.py --dashboard` or `python scripts/update_dashboard.py --json` is run.

## Dashboard Operations

Dashboard is regenerated from repository/vault state; do not patch the generated Markdown by hand.

### Manual refresh

```bash
python run_analysis.py --dashboard
```

Use this after writing a stock analysis, changing task status files, or appending analysis log entries.

### Scheduler refresh

```bash
python scripts/update_dashboard.py --json
python scripts/update_dashboard.py --notify
```

Use the wrapper for cron, launchd, Windows Task Scheduler, and automation checks. `--json` reports `success`, `dashboard_path`, `elapsed_seconds`, and `timestamp`; `--notify` adds desktop notification output where supported.

### Verify stale Dashboard reports

1. Run `python scripts/update_dashboard.py --json` from the project root.
2. Confirm `success` is true and `dashboard_path` equals `.env` `OBSIDIAN_DASHBOARD_PATH`.
3. Run `python -c "from config import Config; print(Config.get_wiki_dir())"` and compare the printed wiki path with the vault opened in Obsidian.
4. If task counts look wrong, inspect Markdown files under `OBSIDIAN_TASKS_DIR` for `status: pending`.
5. If tracked-stock counts look wrong, inspect `Analysis/index.md` under the configured wiki directory.

## Common Operations

### Run one stock analysis

```bash
python scripts/analyze_stock.py AAPL
```

### Fetch JSON for Claude Code reasoning

```bash
python run_analysis.py AAPL
```

### Process Inbox queue

```bash
python run_analysis.py --scan
```

### Run review/backtest

```bash
python scripts/run_review.py --days-after 30 --lookback 90
```

### Run weekly framework review

```bash
python scripts/weekly_review.py --json
```

This writes `Analysis/复盘_YYYYMMDD.md` and creates a review task for framework suggestions.

### Backtest raycat fixed list

```bash
python scripts/backtest_raycat.py
```

This writes `raycat_backtest_report.md` into the wiki directory.

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `WIKI_BASE_DIR is required` | `.env` missing/empty | copy `.env.example` to `.env` and fill paths |
| Wiki file not visible in Obsidian | wrong `WIKI_BASE_DIR` / `WIKI_SUBDIR` | print `Config.get_wiki_dir()` and compare with vault |
| Duplicate `TEM.US.md` and `TEM_US.md` | manual write used wrong filename | keep underscore file, remove duplicate only after confirming content |
| Dashboard update reports success but Obsidian is stale | `OBSIDIAN_DASHBOARD_PATH` points to another vault/file | compare JSON `dashboard_path` with the file open in Obsidian |
| Dashboard task count is wrong | task front matter/status text differs from `status: pending` | inspect `OBSIDIAN_TASKS_DIR` Markdown statuses |
| Dashboard stock count is wrong | stale or missing `Analysis/index.md` | run a stock analysis or inspect MemoryManager index output |
| `ModuleNotFoundError: croniter` | scheduler dependency missing | `pip install -r requirements.txt` |
| `ModuleNotFoundError: watchdog` | watcher dependency missing | `pip install -r requirements.txt` |
| `ModuleNotFoundError: telegram` | Telegram dependency missing | `pip install -r requirements.txt` |
| `ModuleNotFoundError: longbridge` | optional SDK missing | install requirements or accept Yahoo fallback |
| `*_error` in analysis JSON | one pipeline module failed | continue with available fields and note limitation |
| macOS notification fails on Windows | `osascript` unavailable | expected fallback; use console/log output |
| `scheduler.py --daemon` fails on Windows | `os.fork()` unavailable | run foreground or use Windows Task Scheduler |

## Environment Variable Reference

| Variable | Required | Used by |
|---|---|---|
| `WIKI_BASE_DIR` | yes | `Config`, `MemoryManager`, charts |
| `WIKI_SUBDIR` | yes | wiki path under base dir |
| `MATERIALS_SUBDIR` | yes | material archive path |
| `OBSIDIAN_INBOX_DIR` | yes | Inbox scanner/watcher |
| `OBSIDIAN_TASKS_DIR` | yes | task writer, Telegram log |
| `OBSIDIAN_DASHBOARD_PATH` | yes | dashboard writer |
| `ANALYSIS_TIMEOUT` | yes | timeout conventions |
| `LONGBRIDGE_APP_KEY` / `SECRET` / `ACCESS_TOKEN` | no | Longbridge data |
| `SERPAPI_KEY` | no | reserved search enrichment |
| `NEWSAPI_KEY` | no | `data.search` NewsAPI branch |
| `OBSIDIAN_CLIPPINGS_DIR` | no | watcher, Podwise fallback |
| `OBSIDIAN_RAW_DIR` | no | watcher |
| `TELEGRAM_BOT_TOKEN` | no | Telegram bot |
| `TELEGRAM_USER_ID` | no | Telegram bot allowlist |
| `PODWISE_CLI_PATH` | no | Podwise sync |
| `PODWISE_SYNC_DAYS` | no | Podwise sync |
| `PODWISE_OUTPUT_DIR` | no | Podwise sync |
| `SCHEDULE_SCAN_INBOX` | no | Python scheduler |
| `SCHEDULE_REVIEW` | no | Python scheduler |
| `SCHEDULE_DASHBOARD` | no | Python scheduler |
| `SCHEDULE_NOTIFY` | no | Python scheduler |

## Safe Recovery Notes

- Prefer fixing `.env` paths over moving generated wiki files manually.
- Before deleting duplicate wiki files, compare contents and keep the file following the underscore rule.
- Do not bypass pre-commit hooks or force-reset the repository to solve generated-file issues.
- If a scan marked an Inbox item processed too early, edit its front matter back to `processed: false` or remove `processed` / `processed_at`.
