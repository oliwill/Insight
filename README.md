# Insight

English | [简体中文](README.zh.md)

A stock analysis system that uses Claude Code as the reasoning engine and Obsidian as the durable research workspace. It collects market data, extracts evidence from your vault, separates company-quality scoring from trade timing, and writes structured analysis back to Markdown files.

## Workflow

```
Inbox / Materials / stock wiki
    ↓
data.analysis_pipeline.generate_analysis()
    ↓
StockChainAnalyzer → fundamentals.supply_chain
    ↓
WyckoffAnalyzer + 趋势博弈四模块（成交量语言 / 道氏通道 / 多空博弈 / 多时间框架）
    ↓
EvidenceExtractor → ResearchScoreEngine → TimingEngine
    ↓
ReportGenerator + MemoryManager / generate_full_report.py
    ↓
Obsidian Analysis wiki + Dashboard + Tasks
```

Core distinction:

| Layer | Purpose | Output |
| --- | --- | --- |
| Evidence | Convert wiki, Materials and Inbox snippets into typed claims | `## 证据表` |
| Supply-chain position | Deterministic Serenity-style bottleneck context inside fundamentals | `fundamentals.supply_chain` + report `### 产业链位置` |
| Moat stress test | Deterministic narrative pressure test for new-entrant / industry / long-term investor views | `fundamentals.moat_stress_test` + report `### 护城河压力测试` |
| Research Score | Five-dimension company/thesis quality score | `## 五维打分` |
| Trend-game framework | Four technical analyzers encoding 道氏通道 / 成交量语言 / 多空博弈 / 多时间框架 | `volume_profile` / `dow_channel` / `force_balance` / `multi_timeframe` dicts + TimingEngine sub-scores |
| Timing State | Entry quality state machine independent from research quality | `Ready / Wait / Watch / Avoid` |
| Full report | 11-section AGENTS.md A-J report with valuation reverse-engineering, 3-scenario targets, trading grid, alerts | `scripts/generate_full_report.py` → Obsidian section |
| Backtest | Verify historical timeline signals after a holding window | `## 预测验证` + `output/review_*` |
| Public skill | Reusable AI workflow for users without the full local setup | `skills/stock-research-cockpit` |

## Quick Start

```bash
git clone https://github.com/oliwill/Insight.git
cd Insight
pip install -r requirements.txt
cp .env.example .env
```

Minimal `.env`:

```env
WIKI_BASE_DIR=/path/to/your/obsidian/vault/4_Trader
WIKI_SUBDIR=Analysis
MATERIALS_SUBDIR=Materials
OBSIDIAN_INBOX_DIR=/path/to/your/obsidian/vault/Inbox
OBSIDIAN_TASKS_DIR=/path/to/your/obsidian/vault/Tasks
OBSIDIAN_DASHBOARD_PATH=/path/to/your/obsidian/vault/Dashboard.md
ANALYSIS_TIMEOUT=30
```

Optional integrations are documented in `.env.example`: Longbridge, NewsAPI, Telegram bot, Inbox watcher folders, Podwise, and scheduler cron strings.

## Skills Update

This version updates the skills layer so the research workflow can be reused outside the full local pipeline. It includes:

| Skill set | Path | Purpose |
| --- | --- | --- |
| Public cockpit skill | `skills/stock-research-cockpit/` | Portable AI workflow for evidence-backed stock research |
| Finance companion plugin | `.agents/skills/` | Agent-layer companion for valuation, estimates, sentiment, source-readers, market analysis, startup tools, UI tools, and skill authoring |
| Skill lockfile | `skills-lock.json` | Records the imported finance-skill sources and hashes |

The public skill is the recommended starting point for users who only want the research workflow:

```text
skills/stock-research-cockpit/
```

The skill packages the core workflow as AI instructions:

- Skill-only mode for any AI agent that can read the skill folder.
- Local companion mode when this repo, CLI, or MCP server is available.
- External finance-skills mode for richer valuation, sentiment, source-reader, and market-structure coverage through an agent-layer companion.

It preserves the core product boundary: evidence-backed research, five-dimension Research Score, independent Timing State, data-gap disclosure, and no trade execution.

### Install skills

If you are using this repository with an AI agent that can load repo-local skills, no extra install step is needed. Keep the public skill folder in place:

```text
skills/stock-research-cockpit/
```

For a Codex-style local skills directory on macOS/Linux:

```bash
mkdir -p ~/.codex/skills
cp -R skills/stock-research-cockpit ~/.codex/skills/
```

For Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills" | Out-Null
Copy-Item -Recurse -Force ".\skills\stock-research-cockpit" "$env:USERPROFILE\.codex\skills\stock-research-cockpit"
```

If your agent reads skills from `~/.agents/skills`, copy the public skill there instead. Use whichever local skills directory your AI client indexes.

macOS/Linux:

```bash
mkdir -p ~/.agents/skills
cp -R skills/stock-research-cockpit ~/.agents/skills/
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.agents\skills" | Out-Null
Copy-Item -Recurse -Force ".\skills\stock-research-cockpit" "$env:USERPROFILE\.agents\skills\stock-research-cockpit"
```

To enable the optional finance companion plugin, install the upstream bundle and reload your AI agent:

```bash
npx plugins add himself65/finance-skills
```

The installed bundle has six groups: market-analysis, data-providers, social-readers, startup-tools, ui-tools, and skill-creator. Use it as an agent-layer companion, not as a Python pipeline dependency.

Policy taxonomy:

| Policy | Meaning | Examples |
| --- | --- | --- |
| Baseline | Expected in comprehensive public-equity analysis when available and relevant | `funda-data`, `company-valuation`, `estimate-analysis`, `stock-correlation`, `finance-sentiment`, `sepa-strategy` |
| Conditional | Invoke only when asset type, event, liquidity, data gap, or source requirement triggers it | `yfinance-data`, `stock-liquidity`, `earnings-preview`, `earnings-recap`, `options-payoff`, `etf-premium`, `tradingview-reader`, `hormuz-strait`, `twitter-reader`, `telegram-reader`, `discord-reader`, `linkedin-reader`, `yc-reader`, `opencli-reader` |
| Explicit-only | Use only when the user asks for that workflow | `startup-analysis`, `generative-ui`, `skill-creator`, `saas-valuation-compression` |

Keep social/source readers read-only. Do not post, write to external services, or execute trades through plugin skills.

If you maintain a manual `~/.agents/skills` directory, the vendored copy can also be copied directly:

```bash
mkdir -p ~/.agents/skills
cp -R .agents/skills/* ~/.agents/skills/
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.agents\skills" | Out-Null
Copy-Item -Recurse -Force ".\.agents\skills\*" "$env:USERPROFILE\.agents\skills\"
```

After copying skills into a local skills directory, restart or reload the AI agent so it can index the new folders.

## Website

A zero-dependency website prototype lives at `website/index.html`. Open it directly in a browser to try the interactive Stock Research Cockpit, inspect skill install commands, and preview the research workflow before connecting a local companion service.

## Commands

```bash
# One-click Cockpit analysis; writes directly to Obsidian
python scripts/analyze_stock.py AAPL
python scripts/analyze_stock.py 00700
python scripts/analyze_stock.py 603906

# Full 11-section report with trend-game framework (A-share / US / HK)
python scripts/generate_full_report.py SH688035 SZ002468          # draft to tmp_analysis/
python scripts/generate_full_report.py SH688035 --write           # write into Obsidian wiki section

# Claude Code orchestration data fetch
python run_analysis.py AAPL
python run_analysis.py --scan
python run_analysis.py --dashboard
python run_analysis.py --inbox

# Scheduled-task entry points
python scripts/scan_inbox.py --dry-run --json
python scripts/run_review.py --days-after 30 --lookback 90
python scripts/update_dashboard.py --json
python scripts/update_dashboard.py --json --reason scheduled
python scripts/update_dashboard.py --json --reason manual
python scripts/update_dashboard.py --restore-backup --json

# Optional utilities
python inbox_watcher.py
python telegram_bot.py --polling
python scripts/podwise_sync.py --list
python scripts/backtest_raycat.py
python trader_mcp.py
```

## Obsidian Structure

Recommended layout:

```
vault/
├── Inbox/                 # user drops source notes here
├── Tasks/                 # task files created by write_task()
├── Dashboard.md           # portfolio/research dashboard
└── 4_Trader/
    ├── Analysis/          # stock wiki pages: AAPL_US.md
    ├── Materials/         # archived materials per stock
    └── Charts/            # generated Wyckoff charts
```

File naming rule: `.` and `/` in stock codes are replaced by `_`.

| Stock code | Wiki file |
| --- | --- |
| `TEM.US` | `TEM_US.md` |
| `600487.SH` | `600487_SH.md` |
| `00100.HK` | `00100_HK.md` |

Ticker normalization keeps canonical internal symbols while adapting to each data source. For Yahoo-backed modules, 5-digit HK symbols are converted to Yahoo's 4-digit `.HK` format: `03986.HK` → `3986.HK`, `00700.HK` → `0700.HK`, `00388.HK` → `0388.HK`. Tests in `tests/test_yahoo_symbol.py` guard these examples.

## Analysis Output

Each stock wiki is initialized with these core sections:

| Section | Updated by |
| --- | --- |
| `综合评估` | `MemoryManager.update_evaluation_table()` |
| `证据表` | `EvidenceExtractor` + `update_cockpit_sections()` |
| `五维打分` | `ResearchScoreEngine` |
| `交易时机状态` | `TimingEngine` |
| `与上次分析相比` | `scripts/analyze_stock.py` comparison helper |
| `分析时间线` | `MemoryManager.append_to_timeline()` |
| `预测验证` | `BacktestRunner` / `ReviewScheduler` |
| `财报预期` | `data.earnings.EarningsCalendar` |
| `流动性分析` | `data.liquidity.LiquidityAnalyzer` |
| `期权市场` | `data.options.OptionsAnalyzer` |
| `社交情绪` | `data.search.StockSearchEngine` + `SentimentAnalyzer` |
| `研究笔记` | `ReportGenerator` full Markdown report, including the fundamental `### 产业链位置` block when supply-chain data is available |
| `交叉引用` | `data.correlation.CorrelationAnalyzer` |
| `资料索引` | `MemoryManager.save_material()` |

## Scoring Framework

`ResearchScoreEngine` implements the five-dimension framework:

| Dimension | Weight | Main inputs |
| --- | ---: | --- |
| 行业/TAM | 20% | sector, peers, search/social signals, Serenity supply-chain bottleneck exposure |
| 护城河 | 20% | moat analysis, margins, peer context, supply-chain layer scarcity/certification barriers |
| 增长质量 | 20% | revenue growth, earnings growth, margins, FCF, supply-chain demand pressure |
| 估值 | 25% | P/S, PSG, forward PE, analyst target |
| 团队/治理 | 15% | insider ownership/signal, SBC pressure |

Thresholds: ≥75 high-conviction / 60–75 standard candidate / 45–60 watch / <45 pass.

`TimingEngine` then produces a separate trade-timing state from ten sub-scores (trend, Wyckoff, volume profile, Dow channel, force balance, multi-timeframe, price quality, catalyst, liquidity, sentiment):

| State | Meaning |
| --- | --- |
| `Ready` | actionable setup if position sizing is acceptable |
| `Wait` | thesis may be valid, but entry trigger is missing |
| `Watch` | low-confidence setup; monitor only or tiny probe |
| `Avoid` | research quality or timing risk is too poor |

## Moat Stress Test

Beyond the numeric moat dimension above, the pipeline produces a deterministic **narrative pressure test** that models the company from three perspectives simultaneously: a well-funded **new entrant** trying to build the same business from zero, an **industry researcher** mapping the real profit pools and scarce resources, and a **long-term investor** judging whether the moat is durable enough to hold.

The test is generated by `analyzer.fundamental.build_moat_stress_test()` and rendered as `### 护城河压力测试` inside the fundamental section. It is **LLM-free and fully reproducible** — every claim is sourced from disclosed financials, supply-chain bottleneck position, peer context, and rule-based inferences. The raw eight-section prompt is emitted as `fundamentals.moat_stress_test.prompt` so it can be fed to an external model for deeper long-form analysis.

Each report includes:

| Block | Purpose |
| --- | --- |
| 已确认事实 / 合理推断 / 待验证假设 | Evidence graded by confidence, with assumptions tagged `high`/`medium`/`low` priority by business model and sector |
| 创业者 / 产业研究员 / 长期投资者视角 | The same company framed three ways |
| 同行相对强弱 | Target vs peer median for margin, growth, market cap, ROE — degrades gracefully when peer financials are absent |
| 竞争对手攻击模拟（三档预算） | Low/mid/high attacker budgets derived from the company's market cap, each with a first-year focus, three-year reach, and recommended angle (正面进攻 / 绕开细分) |
| 周期性提示 | Cyclical caveat for energy / semiconductor / commodity firms, so current margins are not mistaken for steady-state profitability |
| 结论 | One-line business, one-line moat, hardest-to-copy asset, market fear, key verification metric, and a final classification (短期被高估的叙事 vs 正在把投入转化为长期壁垒的公司) |

The moat stress test is **additive**: it never overrides the numeric moat score or the Timing State. It is the narrative layer that explains *why* a score is what it is.

## Trend-Game Analysis Framework

Beyond the existing Wyckoff + SEPA technical layer, the pipeline runs four `BaseAnalyzer` modules that encode a 道氏/博弈-style technical framework. They run on daily OHLCV only (no extra data source needed) and feed into `TimingEngine` as new sub-scores.

| Analyzer | File | What it detects |
| --- | --- | --- |
| Volume Profile | `analyzer/volume_profile.py` | 成交量语言：平量推升（最优、筹码锁定）/ 量价齐升 / 量价紊乱 / 爆冲巨量（抢帽子骗局）/ 缩量阴跌 |
| Dow Channel | `analyzer/dow_channel.py` | 道氏通道：方向 / 斜率趋缓（扶老太太下楼）/ 颈线争夺（交地/衢地）/ 顶底三步信号 / 摩擦上沿下沿 |
| Force Balance | `analyzer/force_balance.py` | 多空博弈（九地形态）：主力吸筹证据 / 派发证据 / 筹码锁定可能性 / 散户陷阱风险，用可观测代理变量映射定性概念 |
| Multi-Timeframe | `analyzer/multi_timeframe.py` | 日/周/月趋势一致性（pandas resample，不改造数据源），检测"日线狗啃月线流畅" |

Each analyzer is registered in `analyzer/models.py` and wired into `data/analysis_pipeline.py`, producing `volume_profile` / `dow_channel` / `force_balance` / `multi_timeframe` dicts. `TimingEngine` consumes them via four new sub-scores (`_volume_score` / `_channel_score` / `_force_balance_score` / `_timeframe_score`), with a combined delta range of roughly [-49, +45] layered on the existing six sub-scores. Top/bottom channel signals require confirmation (neckline break for tops, slope slowdown + low position for bottoms), and volume-spike detection only scans the most recent 20 trading days.

### Full Report Generator

`scripts/generate_full_report.py` produces an 11-section report aligned to the AGENTS.md A-J standard, with the trend-game framework as an enhancement layer on top of the existing technical analysis (传统指标 + SEPA + Wyckoff):

| Section | Content |
| --- | --- |
| 一、公司与催化剂 (A) | business + trigger event + supply-chain position |
| 二、基本面与增长质量 (C) | financial table + 5-dimension growth quality |
| 三、护城河分析 (B2) | 4-dimension star rating + competitive threat + moat window |
| 四、估值锚点 (D) | PS peer comparison + PSG + **reverse-engineering** (overpay multiple / implied years) + **odds prototype** (增长型/催化型/困境反转/周期底部) |
| 五、技术面 (B) | **综合结论** + 传统指标 + SEPA Stage + Wyckoff + 趋势博弈四模块 |
| 六、市场结构与情绪 (E) | liquidity + force balance (gracefully skips options/short/sentiment when unavailable, e.g. A-shares) |
| 七、风险量化 (F) | each risk quantified as revenue ±X% / valuation ±Y% / probability |
| 八、三情景目标价 (G) | Bull/Base/Bear via PS-relative valuation + probability-weighted target |
| 九、操作格网 (H) | Fibonacci + ATR + 道氏通道 levels with position sizing and R/R |
| 十、警戒线/加仓信号 (I) | auto-extracted observable boolean conditions from trend-game signals |
| 十一、催化剂日历 (J) | earnings/industry/macro events with upside/downside reactions |
| 术语表 | glossary for PSG/RSI/MACD/KDJ/MA/ATR/PE/PB/ROE/SEPA/Wyckoff/VCP |

## Data Sources

| Source | Used for | Requirement |
| --- | --- | --- |
| Yahoo Finance | price history, fundamentals, options, earnings, news | default |
| DuckDuckGo HTML | web/social fallback search | default |
| NewsAPI | news enrichment | `NEWSAPI_KEY` |
| Longbridge | HK/CN quotes and K-lines | Longbridge credentials |
| Obsidian vault | prior theses, materials, Inbox evidence | `.env` paths |
| External finance-skills plugin | agent-layer companion for analyst-grade data, valuation, estimates, sentiment, TradingView, and read-only social/source readers | optional: `npx plugins add himself65/finance-skills` |

The pipeline is fault-tolerant: failed modules return `*_error` fields, data-source attempts are exposed under `_data_sources`, and the rest of the report can still be generated.

## Module Map

| Module | Purpose |
| --- | --- |
| `data.supply_chain` | per-stock Serenity-style supply-chain position and bottleneck analysis |
| `data.analysis_pipeline` | one-call data collection, technical calculations, and trend-game framework wiring |
| `analyzer.research_score` | evidence-adjusted five-dimension scoring |
| `analyzer.timing_engine` | Ready/Wait/Watch/Avoid timing state machine (with trend-game sub-scores) |
| `analyzer.volume_profile` | 成交量语言 analyzer (平量推升/爆冲巨量/量价紊乱) |
| `analyzer.dow_channel` | 道氏通道 analyzer (通道/斜率/颈线/顶底信号) |
| `analyzer.force_balance` | 多空博弈 analyzer (九地形态/吸筹派发/散户陷阱) |
| `analyzer.multi_timeframe` | 多时间框架 analyzer (日/周/月一致性) |
| `input.evidence` | rule-based evidence extraction from wiki/materials/Inbox |
| `analyzer.report_generator` | final Markdown report generation (pipeline) |
| `scripts/generate_full_report` | 11-section full report with valuation reverse-engineering + 3-scenario targets |
| `analyzer.report_quality` | report structure, data-gap, and Research/Timing separation checks |
| `skills/stock-research-cockpit` | reusable AI skill for stock research cockpit reports |
| `memory.manager` | Obsidian wiki, Materials, timeline, dashboard persistence |
| `backtest.runner` / `backtest.review` | timeline signal verification, extended metrics, and review reports |
| `trader_mcp.py` | MCP server for Claude Desktop / MCP clients |
| `telegram_bot.py` | optional mobile command interface |
| `inbox_watcher.py` | optional folder watcher that triggers Inbox scans |
| `scripts/podwise_sync.py` | optional Podcast note import into Obsidian |

## More Documentation

- `docs/architecture.md` — system design and data flow
- `docs/integration-guide.md` — MCP, Telegram, Inbox and Podwise integration steps
- `docs/runbook.md` — operations, scheduling, verification and troubleshooting
- `docs/handoff.md` — current handoff snapshot for new agents and maintainers
- `MCP_CONFIG.md` — MCP server configuration reference
- `SCHEDULER.md` — launchd and Python scheduler notes

## License

MIT
