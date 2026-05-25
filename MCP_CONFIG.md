# MCP 配置说明

`trader_mcp.py` exposes the trader-obsidian workspace to MCP clients such as Claude Desktop. The server is read/write for the local Obsidian vault: it can scan Inbox, fetch analysis context, write analysis text, create task files, and update Dashboard.

## 1. Install Dependencies

```bash
cd /path/to/obsidiantrader
pip install -r requirements.txt
```

Required for MCP: `mcp>=1.0.0`, plus this project’s normal dependencies.

## 2. Configure `.env`

At minimum:

```env
WIKI_BASE_DIR=/path/to/your/obsidian/vault/4_Trader
WIKI_SUBDIR=Analysis
MATERIALS_SUBDIR=Materials
OBSIDIAN_INBOX_DIR=/path/to/your/obsidian/vault/Inbox
OBSIDIAN_TASKS_DIR=/path/to/your/obsidian/vault/Tasks
OBSIDIAN_DASHBOARD_PATH=/path/to/your/obsidian/vault/Dashboard.md
```

## 3. Configure Claude Desktop

Use absolute paths for both the script and `PYTHONPATH`.

### Windows example

```json
{
  "mcpServers": {
    "trader-obsidian": {
      "command": "python",
      "args": [
        "E:\\Git\\ClaudeCode\\obsidiantrader\\trader_mcp.py"
      ],
      "env": {
        "PYTHONPATH": "E:\\Git\\ClaudeCode\\obsidiantrader"
      }
    }
  }
}
```

### macOS / Linux example

```json
{
  "mcpServers": {
    "trader-obsidian": {
      "command": "python3",
      "args": [
        "/path/to/obsidiantrader/trader_mcp.py"
      ],
      "env": {
        "PYTHONPATH": "/path/to/obsidiantrader"
      }
    }
  }
}
```

## 4. Verify

Restart the MCP client, then ask:

```text
请列出 Inbox 中的所有材料
```

```text
获取 AAPL.US 的分析上下文
```

```text
扫描待处理的材料
```

If the client can call the tools and returns JSON/Markdown, the server is configured.

## Tools

| Tool | Function | Parameters |
|---|---|---|
| `scan_inbox_tool` | Scan Inbox and return all materials | none |
| `get_pending_analysis_tool` | Return unprocessed `analyze: true` materials | none |
| `get_related_materials_tool` | Return Inbox materials related to a stock | `stock_code` |
| `get_stock_context_tool` | Return full stock wiki context | `stock_code` |
| `get_stock_index_tool` | Return `Analysis/index.md` content | none |
| `get_recent_log_tool` | Return recent MemoryManager log entries | `n` optional |
| `analyze_stock_tool` | Fetch pipeline data; does not write report | `stock_code` |
| `write_analysis_tool` | Append analysis text to Obsidian | `stock_code`, `stock_name`, `analysis_text`, `score`, `core_view` |
| `create_task_tool` | Create an Obsidian task file | `title`, `ticker`, `task_type`, `description`, `priority`, `due_date` |
| `update_dashboard_tool` | Rebuild Dashboard.md | none |
| `search_stock_news_tool` | Search latest stock news | `stock_code`, `max_results` optional |
| `search_stock_sentiment_tool` | Search social/sentiment material | `stock_code`, `max_results` optional |
| `search_stock_all_tool` | Search news + social + analyst material | `stock_code` |

## Resources

| Resource | Content |
|---|---|
| `mcp://trader/inbox` | Inbox overview and pending count |
| `mcp://trader/stocks` | Tracked stock index |

## Notes

- `analyze_stock_tool` only returns data. The client still needs to reason over the data and call `write_analysis_tool` if it wants to persist a report.
- For a full local Cockpit report, prefer `python scripts/analyze_stock.py <TICKER>` outside MCP.
- `write_analysis_tool` uses `run_analysis.write_analysis_to_obsidian()` and therefore follows the underscore filename rule through `MemoryManager`.
