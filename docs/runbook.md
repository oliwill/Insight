# Runbook

Operational checks and troubleshooting for trader-obsidian.

## Install / Update Dependencies

```bash
pip install -r requirements.txt
```

For local development and regression tests:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

On Windows, if `python` is not on `PATH`, create a virtual environment or pass
the interpreter explicitly to the smoke-test wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run_smoke_tests.ps1 -PythonExe "C:\path\to\python.exe"
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

On Windows, prefer the wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run_smoke_tests.ps1
```

If you are bootstrapping a machine before installing `pytest` or before `.env`
paths are ready, you can still run syntax-only checks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run_smoke_tests.ps1 -SkipPytest -SkipRuntimeChecks
```

Manual equivalent:

```bash
# Verify imports and syntax
python -m py_compile config.py run_analysis.py scripts/analyze_stock.py trader_mcp.py
python -m py_compile data/manager.py data/earnings.py data/liquidity.py data/options.py data/correlation.py data/etf.py data/search.py

# Verify regression guards
PYTHONIOENCODING=utf-8 python -m pytest tests/test_yahoo_symbol.py tests/test_section_write.py tests/test_report_generator.py

# Verify config is visible
python -c "from config import Config; print(Config.get_wiki_dir())"

# Fetch data without writing a report
python run_analysis.py AAPL

# Scan Inbox without mutating files
python scripts/scan_inbox.py --dry-run --json

# Check which stocks scheduled review will scan
python scripts/run_review.py --list-tickers --json

# Update Dashboard
python scripts/update_dashboard.py --json
```

For a full report write:

```bash
python scripts/analyze_stock.py AAPL
```

For US + HK end-to-end smoke checks:

```bash
PYTHONIOENCODING=utf-8 python scripts/analyze_stock.py HIMS.US
PYTHONIOENCODING=utf-8 python scripts/analyze_stock.py 03986.HK
```

Expected side effects:

- `Analysis/AAPL_US.md`, `Analysis/HIMS_US.md`, or `Analysis/03986_HK.md` exists under `Config.get_wiki_dir()` depending on the symbol tested.
- `Charts/{CODE}_wyckoff.png` may exist under `WIKI_BASE_DIR/Charts` if enough historical rows are available.
- Top-level sections such as `研究笔记`, `财报预期`, `流动性分析`, `期权市场`, and `交叉引用` should appear once as line-anchored `##` headings.
- Report headings inside `研究笔记` should be nested as `###` or lower, not `#` or `##`.
- Dashboard updates when `python run_analysis.py --dashboard` is run.

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
python scripts/run_review.py --list-tickers --json
python scripts/run_review.py --days-after 30 --lookback 90
```

### Register Windows scheduled tasks

Run from project root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run_scheduled_task.ps1 -Task inbox -DryRun
powershell -ExecutionPolicy Bypass -File scripts\windows\register_scheduled_tasks.ps1 -Force
Get-ScheduledTask -TaskName "trader-obsidian-*"
```

Use `-DryRunInbox` on the registration command if Inbox scans should remain read-only while testing.

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
| `ModuleNotFoundError: croniter` | scheduler dependency missing | `pip install -r requirements.txt` |
| `ModuleNotFoundError: watchdog` | watcher dependency missing | `pip install -r requirements.txt` |
| `ModuleNotFoundError: telegram` | Telegram dependency missing | `pip install -r requirements.txt` |
| `ModuleNotFoundError: longbridge` | optional SDK missing | install requirements or accept Yahoo fallback |
| `*_error` in analysis JSON | one pipeline module failed | continue with available fields and note limitation |
| macOS notification fails on Windows | `osascript` unavailable | expected fallback; use console/log output |
| `scheduler.py --daemon` fails on Windows | `os.fork()` unavailable | use `scripts/windows/register_scheduled_tasks.ps1` or run foreground |
| Windows scheduled task does not run | wrong Python path or working directory | re-register with `-PythonExe "C:\path\to\python.exe"` and check `logs\scheduler\*.log` |

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
