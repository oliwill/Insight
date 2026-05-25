# Integration Guide

This guide is for connecting trader-obsidian to external tools: Obsidian, MCP clients, Telegram, folder watchers, and Podwise.

## Obsidian Setup

Recommended vault layout:

```text
vault/
├── Inbox/
├── Tasks/
├── Dashboard.md
└── 4_Trader/
    ├── Analysis/
    ├── Materials/
    └── Charts/
```

Minimal `.env`:

```env
WIKI_BASE_DIR=/path/to/vault/4_Trader
WIKI_SUBDIR=Analysis
MATERIALS_SUBDIR=Materials
OBSIDIAN_INBOX_DIR=/path/to/vault/Inbox
OBSIDIAN_TASKS_DIR=/path/to/vault/Tasks
OBSIDIAN_DASHBOARD_PATH=/path/to/vault/Dashboard.md
```

`MemoryManager` creates `Analysis`, `Materials`, and wiki files as needed.

## Inbox Material Format

Create Markdown files in `OBSIDIAN_INBOX_DIR`:

```yaml
---
title: NVDA Q1 earnings beat
source: twitter
ticker: NVDA
analyze: true
tags: AI, semiconductors, datacenter
---

Paste source content here.
```

Supported source values are flexible strings. `EvidenceExtractor` currently treats filings/earnings/company announcements as high credibility, news/articles/Substack/WeChat/PDF/notes as medium credibility, and Twitter/Reddit/Telegram/community/rumor sources as low credibility.

## MCP Client Integration

Run the server:

```bash
python trader_mcp.py
```

Claude Desktop Windows example:

```json
{
  "mcpServers": {
    "trader-obsidian": {
      "command": "python",
      "args": ["E:\\Git\\ClaudeCode\\obsidiantrader\\trader_mcp.py"],
      "env": {"PYTHONPATH": "E:\\Git\\ClaudeCode\\obsidiantrader"}
    }
  }
}
```

Main tools:

| Tool | Use |
|---|---|
| `scan_inbox_tool` | inspect all Inbox files |
| `get_pending_analysis_tool` | list queued materials |
| `get_stock_context_tool` | retrieve full stock wiki context |
| `analyze_stock_tool` | fetch pipeline data without writing |
| `write_analysis_tool` | write analysis text to Obsidian |
| `create_task_tool` | create task Markdown file |
| `update_dashboard_tool` | rebuild Dashboard |
| `search_stock_all_tool` | search news/social/analyst context |

Use `analyze_stock_tool` for data gathering and `write_analysis_tool` only after the client has produced analysis text.

## Telegram Bot

Install dependencies:

```bash
pip install -r requirements.txt
```

`.env`:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_USER_ID=your_numeric_user_id
```

Run:

```bash
python telegram_bot.py --polling
```

Commands:

| Command | Action |
|---|---|
| `/note [TICKER] content` | write note into Inbox |
| `/get TICKER` | return stock wiki summary |
| `/scan` | trigger Inbox scan |
| `/inbox` | show pending materials |
| `/task` | list task files |
| `/help` | show help |

If `TELEGRAM_USER_ID` is set, only that Telegram user is authorized.

## Folder Watcher

`inbox_watcher.py` watches Markdown creation/move events and triggers `run_analysis.py --scan` after a 2-second debounce.

`.env`:

```env
OBSIDIAN_INBOX_DIR=/path/to/vault/Inbox
OBSIDIAN_CLIPPINGS_DIR=/path/to/vault/Clippings
OBSIDIAN_RAW_DIR=/path/to/vault/Raw
```

Run:

```bash
python inbox_watcher.py
```

`--daemon` uses the same PID-managed watcher path in this script; on Windows prefer foreground mode or an OS scheduler.

## Podwise Integration

`podwise_sync.py` imports recent podcast episode notes into Obsidian and adds front matter:

```yaml
source: podwise
url: ...
analyze: true
tags: podcast
imported: YYYY-MM-DD HH:MM
```

`.env`:

```env
PODWISE_CLI_PATH=podwise
PODWISE_SYNC_DAYS=7
PODWISE_OUTPUT_DIR=/path/to/vault/Clippings
```

Commands:

```bash
python scripts/podwise_sync.py --list
python scripts/podwise_sync.py --days 3 --dry-run
python scripts/podwise_sync.py --days 7
```

The Podwise CLI must already be installed and authenticated.

## Scheduled Tasks

Use wrapper scripts for automation:

```bash
python scripts/scan_inbox.py --notify
python scripts/run_review.py --notify
python scripts/update_dashboard.py --notify
python scripts/weekly_review.py --notify
```

On macOS, use launchd or cron to call the wrapper scripts directly. On Windows, use Windows Task Scheduler to call the wrapper scripts directly.

## File Naming Contract

All integrations must follow the stock wiki filename rule:

```text
stock_code.replace(".", "_").replace("/", "_") + ".md"
```

Do not write `TEM.US.md`; write `TEM_US.md` through `MemoryManager` or `write_analysis_to_obsidian()`.

## Symbol Normalization for Integrations

External callers may pass canonical internal codes such as `HIMS.US`, `03986.HK`, or `00700.HK`. The app keeps those canonical codes for wiki identity and file naming, then normalizes Yahoo-backed requests internally. Yahoo HK examples:

| Internal code | Yahoo symbol |
|---|---|
| `03986.HK` | `3986.HK` |
| `00700.HK` | `0700.HK` |
| `00388.HK` | `0388.HK` |

## Safe Markdown Section Writes

Markdown appended into an existing wiki section must not introduce same-level `##` headings. The current write path strips matching module section headings before append and demotes generated report headings under `研究笔记`, so downstream integrations should prefer `write_analysis_to_obsidian()` instead of writing raw Markdown directly into a wiki page.
