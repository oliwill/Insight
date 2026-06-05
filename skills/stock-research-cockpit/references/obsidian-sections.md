# Obsidian Section Contract

Use this when the user wants Obsidian write-back or compatibility with `trader-obsidian`.

## Stock Wiki Sections

Core cockpit sections are replaceable on each analysis:

- `证据表`
- `五维打分`
- `交易时机状态`
- `与上次分析相比`

Longitudinal sections are append-only:

- `分析时间线`
- `预测验证`
- `研究笔记`
- `资料索引`

Module sections may append:

- `财报预期`
- `流动性分析`
- `期权市场`
- `社交情绪`
- `交叉引用`

## File Naming

Replace `.` and `/` with `_` in wiki filenames:

- `AAPL.US` -> `AAPL_US.md`
- `03986.HK` -> `03986_HK.md`

## Write Safety

- Ask before writing unless the user explicitly requested a write.
- Prefer dry-run or preview for new users.
- Do not create duplicate top-level sections.
- Generated report headings under `研究笔记` should be demoted to avoid breaking the wiki structure.
