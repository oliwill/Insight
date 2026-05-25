# 定时任务调度

trader-obsidian supports four automation layers:

1. **Scheduled wrappers** in `scripts/` for Inbox scan, review, Dashboard update, and weekly review.
2. **macOS launchd** plist files in `launchd/`.
3. **Python scheduler daemon** in `scheduler.py` for scan/review/dashboard.
4. **Other OS schedulers** such as cron or Windows Task Scheduler calling wrapper scripts directly.

## Scheduled Wrappers

```bash
python scripts/scan_inbox.py --dry-run --json
python scripts/scan_inbox.py --notify

python scripts/run_review.py --days-after 30 --lookback 90 --json
python scripts/run_review.py AAPL.US NVDA.US --notify

python scripts/update_dashboard.py --json
python scripts/update_dashboard.py --notify

python scripts/weekly_review.py --json
python scripts/weekly_review.py --notify
```

`--notify` uses macOS `osascript`; on Windows it falls back to console output.

## Option A: OS Scheduler

Use your platform scheduler to call the wrapper scripts directly.

| Task | Frequency | wrapper command | launchd plist |
|---|---:|---|---|
| Inbox scan | every 30 minutes | `python scripts/scan_inbox.py --notify` | `com.trader-obsidian.inbox.plist` |
| Backtest review | daily 09:00 | `python scripts/run_review.py --notify` | `com.trader-obsidian.review.plist` |
| Dashboard update | daily 08:00 | `python scripts/update_dashboard.py --notify` | `com.trader-obsidian.dashboard.plist` |
| Weekly framework review | Saturday 10:00 | `python scripts/weekly_review.py --notify` | `com.trader-obsidian.weekly-review.plist` |

The plist files contain example absolute paths; edit `ProgramArguments`, `WorkingDirectory`, and `PYTHONPATH` before loading them.

### Windows Task Scheduler

Use Task Scheduler to call the wrapper scripts directly instead of `scheduler.py --daemon`, because daemon mode uses `os.fork()`.

Create one task per wrapper with these fields:

| Task Scheduler field | Value |
|---|---|
| Program/script | `C:\path\to\obsidiantrader\.venv\Scripts\python.exe` or `python` |
| Add arguments | `scripts\scan_inbox.py --notify` |
| Start in | `C:\path\to\obsidiantrader` |

Recommended triggers:

| Task | Trigger | Add arguments |
|---|---|---|
| Inbox scan | every 30 minutes | `scripts\scan_inbox.py --notify` |
| Backtest review | daily 09:00 | `scripts\run_review.py --notify` |
| Dashboard update | daily 08:00 | `scripts\update_dashboard.py --notify` |
| Weekly framework review | Saturday 10:00 | `scripts\weekly_review.py --notify` |

Validation commands from the project root:

```bash
python scripts/scan_inbox.py --dry-run --json
python scripts/run_review.py --days-after 30 --lookback 90 --json
python scripts/update_dashboard.py --json
python scripts/weekly_review.py --json
```

If the task runs under a different Windows user, confirm that user's `.env` paths point to the same Obsidian vault and that `python -c "from config import Config; print(Config.get_wiki_dir())"` prints the expected wiki directory.

Logs:

- `/tmp/trader-inbox.log` / `/tmp/trader-inbox.err`
- `/tmp/trader-review.log` / `/tmp/trader-review.err`
- `/tmp/trader-dashboard.log` / `/tmp/trader-dashboard.err`
- `/tmp/trader-weekly-review.log` / `/tmp/trader-weekly-review.err`

## Dashboard Refresh Strategy

`Dashboard.md` is a generated status surface. Treat `scripts/update_dashboard.py` as the scheduler-facing entry point and `run_analysis.py --dashboard` as the manual/operator entry point.

Recommended cadence:

| Trigger | Command | Purpose |
|---|---|---|
| After manual analysis write | `python run_analysis.py --dashboard` | refresh immediately after stock wiki, task, or log changes |
| Daily scheduled refresh | `python scripts/update_dashboard.py --notify` | keep Obsidian current even when no scan job runs |
| Automation validation | `python scripts/update_dashboard.py --json` | emit machine-readable success/path/timing output |
| MCP client request | `update_dashboard_tool` | rebuild on demand from chat or external client |

Implementation notes:

- Dashboard output path comes from `OBSIDIAN_DASHBOARD_PATH`.
- Stock overview comes from `Analysis/index.md` through `MemoryManager.get_index()`.
- Pending task count scans Markdown files under `OBSIDIAN_TASKS_DIR` for `status: pending`.
- Recent activity comes from `MemoryManager.get_recent_log(n=5)`.
- If a scheduled refresh appears stale, run the `--json` command first and compare the reported `dashboard_path` with the Obsidian note path.

## Option B: Python Scheduler

The Python scheduler currently runs scan, review, and dashboard tasks. Use `scripts/weekly_review.py` through launchd, cron, or Windows Task Scheduler for weekly framework review automation.

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python scheduler.py              # foreground
python scheduler.py --daemon     # background daemon on POSIX systems
python scheduler.py --status
python scheduler.py --stop
```

`.env` schedule keys:

```env
SCHEDULE_SCAN_INBOX=*/30 * * * *
SCHEDULE_REVIEW=0 9 * * *
SCHEDULE_DASHBOARD=0 8 * * *
SCHEDULE_NOTIFY=true
```

Caveat: daemon mode uses `os.fork()` and is intended for macOS/Linux. On Windows, run foreground mode or use Windows Task Scheduler to call the wrapper scripts.

## Option C: Folder Watcher

`inbox_watcher.py` watches new `.md` files and triggers `python run_analysis.py --scan` with debounce.

```bash
python inbox_watcher.py
python inbox_watcher.py --daemon  # same PID-managed watcher path, not a forked background daemon
python inbox_watcher.py --stop
```

Required for watcher:

```env
OBSIDIAN_INBOX_DIR=/path/to/Inbox
OBSIDIAN_CLIPPINGS_DIR=/path/to/Clippings
OBSIDIAN_RAW_DIR=/path/to/Raw
```

Dependency: `watchdog` from `requirements.txt`.

## Review Output

`scripts/run_review.py` uses `backtest.review.ReviewScheduler`:

- Parses wiki timeline entries, including new `Research: ... | Timing: ...` entries.
- Writes verified results into each stock wiki `## 预测验证` section.
- Generates `output/review_YYYYMMDD.md`, `.csv`, and `.png` via `backtest.report.ReportGenerator`.
- Appends a global MemoryManager log entry.

`scripts/weekly_review.py` runs the same review pipeline, analyzes the aggregate results with `backtest.framework_analyzer.FrameworkAnalyzer`, writes `Analysis/复盘_YYYYMMDD.md`, and creates a review task for framework suggestions.
