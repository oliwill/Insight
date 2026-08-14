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

For the optional finance-skills agent companion:

```bash
npx plugins add himself65/finance-skills
```

This installs the six plugin groups used by agent workflows: market-analysis, data-providers, social-readers, startup-tools, ui-tools, and skill-creator. They are not Python pipeline dependencies.

Policy summary:

- Baseline: `funda-data`, `company-valuation`, `estimate-analysis`, `stock-correlation`, `finance-sentiment`, `sepa-strategy`
- Conditional: `yfinance-data`, `stock-liquidity`, `earnings-preview`, `earnings-recap`, `options-payoff`, `etf-premium`, `tradingview-reader`, `hormuz-strait`, `twitter-reader`, `telegram-reader`, `discord-reader`, `linkedin-reader`, `yc-reader`, `opencli-reader`
- Explicit-only: `startup-analysis`, `generative-ui`, `saas-valuation-compression`, `skill-creator`

Keep social/source readers read-only; do not post, write to external services, or execute trades through plugin skills.

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

Write-smoke examples for the canonical US + HK paths:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run_write_smoke_examples.ps1 -PythonExe ".\.venv\Scripts\python.exe"
```

This runs:

- `python scripts/analyze_stock.py HIMS.US`
- `python scripts/analyze_stock.py 03986.HK`

and then verifies the expected wiki files, section structure, and research-note heading nesting.

If you are bootstrapping a machine before installing `pytest` or before `.env`
paths are ready, you can still run syntax-only checks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run_smoke_tests.ps1 -SkipPytest -SkipRuntimeChecks
```

Manual equivalent:

```bash
# Verify imports and syntax
python -m py_compile config.py run_analysis.py scripts/analyze_stock.py trader_mcp.py notification.py telegram_bot.py inbox_watcher.py scheduler.py
python -m py_compile data/manager.py data/earnings.py data/liquidity.py data/options.py data/correlation.py data/etf.py data/search.py data/supply_chain.py analyzer/report_quality.py

# Verify Serenity supply-chain guards
PYTHONIOENCODING=utf-8 python -m pytest tests/test_supply_chain.py tests/test_analysis_pipeline_supply_chain.py tests/test_fundamental_supply_chain.py tests/test_research_score_supply_chain.py tests/test_serenity/test_bottleneck_scorer.py tests/test_serenity/test_report_builder.py

# Verify regression guards
PYTHONIOENCODING=utf-8 python -m pytest tests/test_yahoo_symbol.py tests/test_section_write.py tests/test_report_generator.py tests/test_report_quality.py tests/test_backtest_review.py tests/test_data_source_resilience.py tests/test_dashboard_update.py tests/test_automation_entrypoints.py tests/test_scheduler.py tests/test_m3_boundaries.py

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
python scripts/update_dashboard.py --json --reason manual
python scripts/update_dashboard.py --restore-backup --json
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
- Generated reports should start with `# CODE Name`, `**数据时间**`, then `## 一、本次分析总结`; the top section should front-load the deterministic one-sentence conclusion, current action, main tension, primary risk, dynamic `关键判断`, and short data-quality reminders before detailed evidence.
- When available, Serenity supply-chain analysis should appear inside `## 三、基本面与估值` as `### 产业链位置`; it should not hide missing financial fundamentals in `## 数据缺口`.
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

### Update Dashboard

```bash
python scripts/update_dashboard.py --json --reason manual
python scripts/update_dashboard.py --json --reason post-analysis
python scripts/update_dashboard.py --restore-backup --json
```

Dashboard update strategy:

1. scheduled task uses `--reason scheduled`
2. manual maintenance uses `--reason manual`
3. batch refresh after a multi-stock run uses `--reason post-analysis`
4. restore uses `--restore-backup`

The current policy is conservative: do not auto-update the Dashboard after every single `scripts/analyze_stock.py <TICKER>` run. Use the daily scheduled refresh plus explicit manual or batch refreshes.

### Register Windows scheduled tasks

Run from project root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run_scheduled_task.ps1 -Task inbox -DryRun
powershell -ExecutionPolicy Bypass -File scripts\windows\register_scheduled_tasks.ps1 -Force
Get-ScheduledTask -TaskName "trader-obsidian-*"
```

Use `-DryRunInbox` on the registration command if Inbox scans should remain read-only while testing.

To register and immediately trigger all three scheduled tasks for validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\verify_scheduled_tasks.ps1 -PythonExe ".\.venv\Scripts\python.exe" -DryRunInbox -Force
```

This will:

- re-register `trader-obsidian-inbox`
- re-register `trader-obsidian-review`
- re-register `trader-obsidian-dashboard`
- trigger each task once
- print `LastRunTime`, `LastTaskResult`, and the newly created scheduler log files

M3 regression boundary:

- `tests/test_m3_boundaries.py` checks Telegram bot authorization/normalization/write and scan command contracts.
- `tests/test_m3_boundaries.py` checks Inbox watcher debounce, Markdown-only filtering, scan command, and notification fallback contracts.
- `tests/test_m3_boundaries.py` checks Windows scheduler scripts keep hidden PowerShell windows, scheduled Dashboard reason, stdout/stderr logging, Task Scheduler verification polling, and smoke wrapper coverage.
- `scripts\windows\run_smoke_tests.ps1` includes `telegram_bot.py`, `inbox_watcher.py`, `scheduler.py`, `tests\test_automation_entrypoints.py`, `tests\test_scheduler.py`, and `tests\test_m3_boundaries.py`.

M4 investment-grade regression boundary:

- `tests/test_backtest_review.py` covers extended backtest metrics: verified count, expectancy, median/best/worst return, profit factor, and aggregate max drawdown.
- `tests/test_data_source_resilience.py` covers Longbridge-to-Yahoo fallback and `DataManager.get_source_status()` attempt records.
- `tests/test_report_quality.py` covers report quality checks for the title/data-time header, required sections, Research Score / Timing State separation, and data-gap disclosure.
- `generate_analysis()` includes `_data_sources` so degraded data-source paths can be inspected in JSON output.

If a scheduled Dashboard update looks wrong:

1. run `python scripts/update_dashboard.py --restore-backup --json`
2. rerun `python scripts/update_dashboard.py --json --reason manual`
3. inspect `logs\scheduler\dashboard-*.log`

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
| `supply_chain.status` is `unknown` | ticker did not map to a known Serenity theme/cache | treat as missing industry-chain context; add a cache entry only if the mapping is known |
| `supply_chain_error` in analysis JSON | supply-chain enrichment failed | proceed with financial/technical data and inspect `data/supply_chain.py` mapping/cache inputs |
| Finance companion plugin unavailable | plugin not installed or agent not reloaded | run `npx plugins add himself65/finance-skills`, reload the agent, or disclose the missing data gap |
| Source reader attempts to write/post | wrong workflow for research mode | stop; social/source readers are read-only and must not post, write to external services, or execute trades |
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
| `WEB_DB_PATH` | no | Web SQLite 路径（默认 `data/web.db`） |
| `USERS_DATA_DIR` | no | 用户 vault 根目录（默认 `data/users`） |
| `WEB_PORT` | no | uvicorn 端口（默认 8000） |
| `SESSION_TTL_DAYS` | no | 登录会话有效期（默认 7） |
| `ANALYSIS_DAILY_QUOTA` | no | 每用户每日分析配额（默认 10） |
| `INVITE_CODE` | no | 注册邀请码（留空 = 开放注册） |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | no | LLM 报告增强（DeepSeek 兼容 API） |

## Web Platform Deployment（线上化）

本地开发：

```bash
python -m web.server            # http://127.0.0.1:8000
```

Docker 单机部署（VPS）：

```bash
# 1. 服务器准备 .env（复制 .env.example，填 WIKI_* 路径与可选 LLM_API_KEY）
cp .env.example .env

# 2. 构建并启动
docker compose up -d --build
curl http://127.0.0.1:8000/health   # {"status":"ok"}

# 3. 数据持久化
#    ./data 目录（SQLite + 用户 vault）挂在宿主机，重启/重建容器不丢数据

# 4. 更新
git pull && docker compose up -d --build
```

网络与数据源注意事项：

- **yfinance 可达性**：分析依赖 yfinance/akshare 拉取行情。部署在海外 VPS 无碍；
  国内 VPS 需确保服务器能访问 Yahoo Finance（配置代理或换数据源）。
- **数据源配额**：多用户共享服务器侧 API key。`_workers=2` 信号量 + `ANALYSIS_DAILY_QUOTA`
  兜底，避免限流打爆。
- **LLM 成本**：`LLM_API_KEY` 留空时报告为纯确定性文本（评分/时机不受影响）。
  配置后每次分析消耗少量 token，受日配额约束。
- **反向代理**（可选）：用 Nginx/Caddy 反代 8000 端口并启用 HTTPS。
  Caddy 单行即可：`insight.example.com { reverse_proxy 127.0.0.1:8000 }`。

冒烟清单：

```bash
curl -s http://127.0.0.1:8000/health
# 注册 → 自选 → 发起分析 → 任务页轮询 → 详情页报告渲染 → 追踪页历史
```

## Safe Recovery Notes

- Prefer fixing `.env` paths over moving generated wiki files manually.
- Before deleting duplicate wiki files, compare contents and keep the file following the underscore rule.
- Do not bypass pre-commit hooks or force-reset the repository to solve generated-file issues.
- If a scan marked an Inbox item processed too early, edit its front matter back to `processed: false` or remove `processed` / `processed_at`.
