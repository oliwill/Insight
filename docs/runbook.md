# Runbook

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Required `.env` paths:

```env
WIKI_BASE_DIR=/path/to/your/obsidian/vault
WIKI_SUBDIR=4_Trader/Analysis
MATERIALS_SUBDIR=4_Trader/Materials
OBSIDIAN_INBOX_DIR=/path/to/your/obsidian/vault/Inbox
OBSIDIAN_TASKS_DIR=/path/to/your/obsidian/vault/4_Trader/Tasks
OBSIDIAN_DASHBOARD_PATH=/path/to/your/obsidian/vault/Dashboard.md
ANALYSIS_TIMEOUT=30
```

Optional Longbridge credentials:

```env
LONGBRIDGE_APP_KEY=
LONGBRIDGE_APP_SECRET=
LONGBRIDGE_ACCESS_TOKEN=
```

If credentials are missing or Longbridge times out, Yahoo Finance is used as fallback.

## Verification Commands

Core scoring/writeback checks:

```bash
python -m pytest tests/test_core_scoring.py tests/test_section_write.py -v
```

Data/backtest compatibility checks:

```bash
python -m pytest tests/test_yahoo_symbol.py tests/test_backtest_timeline.py tests/test_data_manager_env.py -v
```

Import smoke:

```bash
python - <<'PY'
from input.evidence import EvidenceExtractor
from analyzer.research_score import ResearchScoreEngine
from analyzer.timing_engine import TimingEngine
from run_analysis import write_analysis_to_obsidian
from analyzer.report_generator import ReportGenerator
print('imports ok')
PY
```

## Operational Checks

Show Inbox status:

```bash
python run_analysis.py --inbox
```

Rebuild dashboard:

```bash
python run_analysis.py --dashboard
```

Run one quick analysis:

```bash
python scripts/analyze_stock.py AAPL
```

This writes to Obsidian. Confirm `.env` points to the intended vault before running it.

## Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| Empty Yahoo data for HK stock | Provider symbol should be four-digit `.HK` | Run `python -m pytest tests/test_yahoo_symbol.py -v` |
| Duplicate `##` sections in wiki | Raw append skipped heading stripping/demotion | Use `write_analysis_to_obsidian()` or `MemoryManager.update_cockpit_sections()` |
| Backtest ignores new cockpit rows | Timeline parser regression | Run `python -m pytest tests/test_backtest_timeline.py -v` |
| Longbridge unavailable | Missing `.env` credentials or SDK issue | Confirm `LONGBRIDGE_*` env vars and SDK install |
