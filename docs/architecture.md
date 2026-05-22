# Architecture

trader-obsidian turns research material and market data into structured Obsidian stock wiki pages.

## Analysis Pipeline

```text
Inbox / Materials / existing stock wiki
    -> input.evidence.EvidenceExtractor
    -> analyzer.research_score.ResearchScoreEngine
    -> analyzer.timing_engine.TimingEngine
    -> analyzer.report_generator.ReportGenerator
    -> run_analysis.write_analysis_to_obsidian
    -> Obsidian Analysis/{CODE}.md
```

The pipeline keeps three concerns separate:

| Layer | Responsibility |
|---|---|
| Evidence | Convert wiki, Materials and Inbox text into typed claims with credibility and score impact. |
| Research Score | Score company quality across five weighted dimensions, adjusted by evidence. |
| Timing State | Produce a separate Ready / Wait / Watch / Avoid state for entry timing. |

`ReportGenerator.generate()` can include the research score, timing state and evidence table in the rendered report. `write_analysis_to_obsidian()` writes structured cockpit sections before appending the full report under `研究笔记`.

## Obsidian Writeback

`MemoryManager.update_cockpit_sections()` replaces structured sections such as `证据表`, `五维打分`, `交易时机状态` and `与上次分析相比`. Module-specific appenders strip matching `##` headings, and full reports are demoted before being appended under `研究笔记`. This prevents duplicate top-level wiki sections.

Timeline rows support two formats:

```text
- **YYYY-MM-DD HH:MM** | 价格: 10 | 评分: 55/100 | 类型: Claude Code 分析
- **YYYY-MM-DD HH:MM** | 价格: 10 | Research: 72/100 | Timing: Ready | 类型: Cockpit 分析
```

History consumers parse both formats so learning statistics and backtests remain compatible.

## Data Symbol Model

The internal code is the canonical wiki identity. Yahoo Finance requests use provider-specific symbols.

| Internal code | Yahoo Finance symbol |
|---|---|
| `AAPL.US` | `AAPL` |
| `00700.HK` | `0700.HK` |
| `03986.HK` | `3986.HK` |
| `SH603906` | `603906.SS` |
| `SZ000001` | `000001.SZ` |

Do not rename Obsidian wiki files to Yahoo symbols. Keep `.` and `/` replaced with `_` in filenames.
