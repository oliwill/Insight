# Handoff Snapshot

Status date: 2026-06-12

## What Is Working

| Area | Status | Entry point |
|---|---|---|
| One-click Cockpit analysis | implemented | `python scripts/analyze_stock.py <TICKER>` |
| Data-only analysis context | implemented | `python run_analysis.py <TICKER>` |
| Obsidian wiki persistence | implemented | `run_analysis.write_analysis_to_obsidian()` |
| Evidence extraction | implemented | `input.evidence.EvidenceExtractor` |
| Five-dimension Research Score | implemented | `analyzer.research_score.ResearchScoreEngine` |
| Timing State | implemented | `analyzer.timing_engine.TimingEngine` |
| Timeline backtesting with extended metrics | implemented | `backtest.runner.BacktestRunner` |
| Data-source fallback diagnostics | implemented | `data.manager.DataManager.get_source_status()` |
| Report quality evaluator | implemented | `analyzer.report_quality.ReportQualityEvaluator` |
| Serenity per-stock supply-chain enrichment | implemented | `data.supply_chain.StockChainAnalyzer` |
| Public AI skill | implemented | `skills/stock-research-cockpit` |
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
- Data-source fallback attempts should be inspectable via `_data_sources` in `generate_analysis()` output.
- Generated reports should pass the quality evaluator for the title/data-time header, required sections, Research Score / Timing State separation, and data-gap disclosure.
- `supply_chain` is additive fundamental context exposed at `market_data["supply_chain"]` and `fundamentals["supply_chain"]`; it must not create a separate top-level Obsidian section or hide missing financial fundamentals.
- The report reading path is top-down: `# CODE Name`, `**数据时间**`, `## 一、本次分析总结`, optional dynamic `关键判断`, short `数据质量提醒`, then evidence and detailed modules.
- Yahoo-backed modules normalize internal 5-digit HK symbols to Yahoo 4-digit `.HK` symbols while preserving canonical wiki identity.
- Appended generated Markdown must not create new top-level wiki sections; module headings are stripped and research-note headings are demoted.

## Required First Checks for a New Agent

```bash
git status --short
python -m py_compile config.py run_analysis.py scripts/analyze_stock.py trader_mcp.py notification.py analyzer/report_quality.py
PYTHONIOENCODING=utf-8 python -m pytest tests/test_yahoo_symbol.py tests/test_section_write.py tests/test_report_generator.py tests/test_report_quality.py tests/test_supply_chain.py tests/test_analysis_pipeline_supply_chain.py tests/test_fundamental_supply_chain.py tests/test_research_score_supply_chain.py tests/test_serenity/test_bottleneck_scorer.py tests/test_serenity/test_report_builder.py tests/test_backtest_review.py tests/test_data_source_resilience.py tests/test_dashboard_update.py tests/test_automation_entrypoints.py tests/test_scheduler.py tests/test_m3_boundaries.py
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

M3 automation regression guards:

- `tests/test_m3_boundaries.py` covers Telegram bot helper/command contracts, Inbox watcher debounce and scan contracts, and Windows script invariants.
- `scripts/windows/run_smoke_tests.ps1` compiles `telegram_bot.py`, `inbox_watcher.py`, and `scheduler.py`, and includes automation/scheduler/M3 tests in the pytest set.

M4 investment-grade regression guards:

- `tests/test_backtest_review.py` covers extended backtest metrics: expectancy, median/best/worst returns, profit factor, and aggregate max drawdown.
- `tests/test_data_source_resilience.py` covers Longbridge-to-Yahoo fallback and source-attempt diagnostics.
- `tests/test_report_quality.py` covers report title/data-time header, required sections, Research Score / Timing State separation, and data-gap disclosure.
- `scripts/windows/run_smoke_tests.ps1` compiles `analyzer/report_quality.py` and includes the M4 tests above.

Public skill distribution:

- `skills/stock-research-cockpit` is the first reusable AI skill version of the research workflow.
- It supports skill-only mode, local companion mode, and optional external finance skills.
- `skills/stock-research-cockpit/evals/evals.json` contains the initial qualitative test prompts; full with-skill/baseline eval viewer runs are still future work.

Do not run `python scripts/analyze_stock.py <TICKER>` unless the user wants a report written to Obsidian.

## Documentation Map

| File | Read when |
|---|---|
| `README.md` / `README.zh.md` | onboarding and command overview |
| `CLAUDE.md` | AI operating rules for this project |
| `docs/architecture.md` | understanding data flow, module boundaries, and Serenity supply-chain enrichment |
| `docs/integration-guide.md` | connecting MCP, Telegram, Inbox watcher, Podwise, and supply-chain data consumers |
| `docs/runbook.md` | operations and troubleshooting |
| `MCP_CONFIG.md` | MCP client configuration |
| `SCHEDULER.md` | launchd / scheduler setup |
| `INTEGRATION_PLAN.md` | integrated capability status, not a future plan |

## Known Caveats

- `scheduler.py --daemon` uses `os.fork()` and is for macOS/Linux. On Windows, use `scripts/windows/register_scheduled_tasks.ps1` or foreground mode.
- macOS notifications use `osascript`; on Windows the notification module prints fallback text.
- `scripts/backtest_raycat.py` uses a fixed ticker/date list and is a source-specific utility, not a generic backtest importer.
- HIMS.US and 03986.HK have been validated as end-to-end Obsidian write smoke examples for the current analysis pipeline.
- Full investment-grade stock analysis uses external finance skills from `himself65/finance-skills` v8.0.1 as an agent-layer companion, installed with `npx plugins add himself65/finance-skills`:
  - Baseline: `funda-data`, `company-valuation`, `estimate-analysis`, `stock-correlation`, `finance-sentiment`, `sepa-strategy`.
  - Conditional: `yfinance-data`, `stock-liquidity`, `earnings-preview`, `earnings-recap`, `options-payoff`, `etf-premium`, `tradingview-reader`, `hormuz-strait`, and read-only source readers (`twitter-reader`, `telegram-reader`, `discord-reader`, `linkedin-reader`, `yc-reader`, `opencli-reader`).
  - Explicit-only: `saas-valuation-compression`, `startup-analysis`, `generative-ui`, `skill-creator`.
  - Plugin groups: market-analysis, data-providers, social-readers, startup-tools, ui-tools, skill-creator.
  - Keep source readers read-only, never invoke write/post/trade actions, and record unavailable skills/data gaps explicitly.
