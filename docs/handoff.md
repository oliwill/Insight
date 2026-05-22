# Handoff

## Completed

- Core scoring kernel is available through `input.evidence`, `analyzer.research_score` and `analyzer.timing_engine`.
- Obsidian writeback can persist cockpit sections for evidence, research score, timing state and comparison text.
- Research notes are demoted before append so generated reports stay inside `## 研究笔记`.
- Timeline/history parsing supports both legacy `评分:` rows and cockpit `Research:` / `Timing:` rows.
- Yahoo-backed helpers normalize HK symbols to Yahoo's four-digit `.HK` format while preserving internal wiki identity.
- Backtest timeline parsing remains compatible with legacy rows that have no explicit action word by defaulting to `HOLD`.

## Current PRs

| PR | Status | Scope |
|---|---|---|
| #2 | Merged | Batch B — core scoring/timing integration with Obsidian writeback |
| #3 | Open | Batch C — Yahoo symbol compatibility and backtest timeline compatibility |

## Recommended Next Batch

Batch D should stay focused on external entry points after Batch C merges:

- `inbox_watcher.py`
- `telegram_bot.py`
- `scripts/podwise_sync.py`
- `trader_mcp.py`
- `scripts/backtest_raycat.py`

Do not mix Batch D with documentation/config cleanup. Batch E should update `.env.example`, `requirements.txt`, README/CLAUDE/AGENTS and scheduler/MCP docs after the runtime interfaces are stable.

## Verification Baseline

Before merging Batch C or starting Batch D, run:

```bash
python -m pytest tests/test_yahoo_symbol.py tests/test_backtest_timeline.py tests/test_data_manager_env.py tests/test_section_write.py tests/test_core_scoring.py -v
```

Expected result for the Batch C branch: 19 passing tests.
