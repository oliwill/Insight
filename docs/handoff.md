# Handoff Snapshot

Status date: 2026-06-03

## What Is Working

| Area | Status | Entry point |
|---|---|---|
| One-click Cockpit analysis | implemented | `python scripts/analyze_stock.py <TICKER>` |
| Data-only analysis context | implemented | `python run_analysis.py <TICKER>` |
| Obsidian wiki persistence | implemented | `run_analysis.write_analysis_to_obsidian()` |
| Evidence extraction | implemented | `input.evidence.EvidenceExtractor` |
| Five-dimension Research Score | implemented | `analyzer.research_score.ResearchScoreEngine` |
| Timing State | implemented | `analyzer.timing_engine.TimingEngine` |
| Timeline backtesting | implemented | `backtest.runner.BacktestRunner` |
| Scheduled review | implemented | `scripts/run_review.py` |
| MCP server | implemented | `python trader_mcp.py` |
| Telegram bot | implemented | `python telegram_bot.py --polling` |
| Inbox watcher | implemented | `python inbox_watcher.py` |
| Podwise sync | implemented | `python scripts/podwise_sync.py` |
| Yahoo HK symbol mapping guard | implemented | `tests/test_yahoo_symbol.py` |
| Safe Obsidian section append guard | implemented | `tests/test_section_write.py` |
| Wyckoff chart link/report rendering guard | implemented | `tests/test_report_generator.py` |

## Current Contracts

- Stock wiki filenames must use underscores: `AAPL.US` → `AAPL_US.md`.
- `Research Score` measures thesis/company quality.
- `Timing State` measures entry quality and must remain separate from Research Score.
- Cockpit sections are replaced on each analysis: `证据表`, `五维打分`, `交易时机状态`, `与上次分析相比`.
- Longitudinal sections are append-only: `分析时间线`, `预测验证`, `研究笔记`, `资料索引`.
- Pipeline modules should emit `*_error` fields instead of stopping the full report.
- Yahoo-backed modules normalize internal 5-digit HK symbols to Yahoo 4-digit `.HK` symbols while preserving canonical wiki identity.
- Appended generated Markdown must not create new top-level wiki sections; module headings are stripped and research-note headings are demoted.

## Required First Checks for a New Agent

```bash
git status --short
python -m py_compile config.py run_analysis.py scripts/analyze_stock.py trader_mcp.py
PYTHONIOENCODING=utf-8 python -m pytest tests/test_yahoo_symbol.py tests/test_section_write.py tests/test_report_generator.py tests/test_backtest_review.py
python -c "from config import Config; print(Config.get_wiki_dir())"
python scripts/scan_inbox.py --dry-run --json
```

On Windows, prefer the consolidated wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run_smoke_tests.ps1 -PythonExe "C:\path\to\python.exe"
```

If `pytest` or `.env` paths are not ready yet, run syntax-only checks first:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run_smoke_tests.ps1 -SkipPytest -SkipRuntimeChecks
```

Write-smoke examples for the canonical US + HK paths:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run_write_smoke_examples.ps1 -PythonExe ".\.venv\Scripts\python.exe"
```

This command was validated on 2026-06-03 for:

- `HIMS.US` -> `HIMS_US.md` plus chart output
- `03986.HK` -> `03986_HK.md`

Windows Task Scheduler validation wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\verify_scheduled_tasks.ps1 -PythonExe ".\.venv\Scripts\python.exe" -DryRunInbox -Force
```

This command was validated on 2026-06-03 and produced successful `LastTaskResult = 0` for:

- `trader-obsidian-inbox`
- `trader-obsidian-review`
- `trader-obsidian-dashboard`

Do not run `python scripts/analyze_stock.py <TICKER>` unless the user wants a report written to Obsidian.

## Documentation Map

| File | Read when |
|---|---|
| `README.md` / `README.zh.md` | onboarding and command overview |
| `CLAUDE.md` | AI operating rules for this project |
| `docs/architecture.md` | understanding data flow and module boundaries |
| `docs/integration-guide.md` | connecting MCP, Telegram, Inbox watcher, Podwise |
| `docs/runbook.md` | operations and troubleshooting |
| `MCP_CONFIG.md` | MCP client configuration |
| `SCHEDULER.md` | launchd / scheduler setup |
| `INTEGRATION_PLAN.md` | integrated capability status, not a future plan |

## Known Caveats

- `scheduler.py --daemon` uses `os.fork()` and is for macOS/Linux. On Windows, use `scripts/windows/register_scheduled_tasks.ps1` or foreground mode.
- macOS notifications use `osascript`; on Windows the notification module prints fallback text.
- `scripts/backtest_raycat.py` uses a fixed ticker/date list and is a source-specific utility, not a generic backtest importer.
- HIMS.US and 03986.HK have been validated as end-to-end Obsidian write smoke examples for the current analysis pipeline.
- Full investment-grade stock analysis still needs external finance skills for real-time GEX/options flow, insider/congressional trades, supply-chain mapping, and SEPA confirmation.
