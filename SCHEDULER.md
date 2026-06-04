# 定时任务调度

trader-obsidian supports three automation layers:

1. **Scheduled wrappers** in `scripts/` for Inbox scan, review, and Dashboard update.
2. **Windows Task Scheduler** helpers in `scripts/windows/`.
3. **macOS launchd** plist files in `launchd/`.
4. **Python scheduler daemon** in `scheduler.py`.

## Scheduled Wrappers

```bash
python scripts/scan_inbox.py --dry-run --json
python scripts/scan_inbox.py --notify

python scripts/run_review.py --days-after 30 --lookback 90 --json
python scripts/run_review.py --list-tickers --json
python scripts/run_review.py AAPL.US NVDA.US --notify

python scripts/update_dashboard.py --json
python scripts/update_dashboard.py --notify
python scripts/update_dashboard.py --json --reason scheduled
python scripts/update_dashboard.py --restore-backup --json
```

`--notify` uses macOS `osascript`; on Windows it falls back to console output.

For Dashboard, use:

- scheduled refresh: `scripts/update_dashboard.py --json --reason scheduled`
- operator refresh: `scripts/update_dashboard.py --json --reason manual`
- batch refresh after analysis/review work: `scripts/update_dashboard.py --json --reason post-analysis`
- recovery: `scripts/update_dashboard.py --restore-backup --json`

## Option A: Windows Task Scheduler

Use Windows Task Scheduler for unattended Windows runs. Do not use `python scheduler.py --daemon` on Windows because daemon mode depends on `os.fork()`.

First verify the wrapper manually from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run_scheduled_task.ps1 -Task inbox -DryRun
powershell -ExecutionPolicy Bypass -File scripts\windows\run_scheduled_task.ps1 -Task review
powershell -ExecutionPolicy Bypass -File scripts\windows\run_scheduled_task.ps1 -Task dashboard
```

Register the three scheduled tasks for the current Windows user:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\register_scheduled_tasks.ps1 -Force
```

Validate registration and one-shot execution:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\verify_scheduled_tasks.ps1 -PythonExe ".\.venv\Scripts\python.exe" -DryRunInbox -Force
```

Defaults:

| Task | Frequency | Command |
|---|---:|---|
| `trader-obsidian-inbox` | every 30 minutes | `scripts\scan_inbox.py --json` |
| `trader-obsidian-review` | daily 09:00 | `scripts\run_review.py --days-after 30 --lookback 90 --json` |
| `trader-obsidian-dashboard` | daily 08:00 | `scripts\update_dashboard.py --json --reason scheduled` |

Useful options:

```powershell
# Keep Inbox scans read-only while testing
powershell -ExecutionPolicy Bypass -File scripts\windows\register_scheduled_tasks.ps1 -DryRunInbox -Force

# Use a specific Python interpreter
powershell -ExecutionPolicy Bypass -File scripts\windows\register_scheduled_tasks.ps1 -PythonExe "C:\path\to\python.exe" -Force

# Change schedules
powershell -ExecutionPolicy Bypass -File scripts\windows\register_scheduled_tasks.ps1 -InboxInterval PT1H -ReviewTime 18:30 -DashboardTime 08:30 -Force
```

Inspect and remove tasks:

```powershell
Get-ScheduledTask -TaskName "trader-obsidian-*"
Unregister-ScheduledTask -TaskName "trader-obsidian-inbox" -Confirm:$false
Unregister-ScheduledTask -TaskName "trader-obsidian-review" -Confirm:$false
Unregister-ScheduledTask -TaskName "trader-obsidian-dashboard" -Confirm:$false
```

Logs are written under `logs\scheduler\*.log` in the project root.

## Option B: macOS launchd

The plist files currently contain example paths. Before loading them, edit:

- `ProgramArguments[1]`
- `WorkingDirectory`
- `EnvironmentVariables.PYTHONPATH`

Then:

```bash
cp launchd/*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.trader-obsidian.inbox.plist
launchctl load ~/Library/LaunchAgents/com.trader-obsidian.review.plist
launchctl load ~/Library/LaunchAgents/com.trader-obsidian.dashboard.plist
launchctl list | grep trader-obsidian
```

Stop:

```bash
launchctl unload ~/Library/LaunchAgents/com.trader-obsidian.inbox.plist
launchctl unload ~/Library/LaunchAgents/com.trader-obsidian.review.plist
launchctl unload ~/Library/LaunchAgents/com.trader-obsidian.dashboard.plist
```

| Task | Frequency | plist |
|---|---:|---|
| Inbox scan | every 30 minutes | `com.trader-obsidian.inbox.plist` |
| Backtest review | daily 09:00 | `com.trader-obsidian.review.plist` |
| Dashboard update | daily 08:00 | `com.trader-obsidian.dashboard.plist` |

Logs:

- `/tmp/trader-inbox.log` / `/tmp/trader-inbox.err`
- `/tmp/trader-review.log` / `/tmp/trader-review.err`
- `/tmp/trader-dashboard.log` / `/tmp/trader-dashboard.err`

## Option C: Python Scheduler

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

Caveat: daemon mode uses `os.fork()` and is intended for macOS/Linux. On Windows, use Windows Task Scheduler above or run foreground mode manually.

## Option D: Folder Watcher

`inbox_watcher.py` watches new `.md` files and triggers `python run_analysis.py --scan` with debounce.

```bash
python inbox_watcher.py
python inbox_watcher.py --daemon
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
