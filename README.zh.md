# trader-obsidian

[English](README.md) | 简体中文

一套以 Claude Code 为推理引擎、Obsidian 为长期研究工作台的股票分析系统。系统会收集行情与基本面数据，从 vault 中抽取证据，把“公司质量评分”和“交易时机判断”分离，并把结构化分析写回 Markdown 文件。

## 工作流

```
Inbox / Materials / 股票 wiki
    ↓
data.analysis_pipeline.generate_analysis()
    ↓
EvidenceExtractor → ResearchScoreEngine → TimingEngine
    ↓
ReportGenerator + MemoryManager
    ↓
Obsidian Analysis wiki + Dashboard + Tasks
```

核心分层：

| 层级 | 作用 | 输出 |
|---|---|---|
| 证据层 | 把 wiki、Materials、Inbox 内容转成结构化 claim | `## 证据表` |
| Research Score | 五维公司/投资 thesis 质量评分 | `## 五维打分` |
| Timing State | 独立于公司质量的交易时机状态机 | `Ready / Wait / Watch / Avoid` |
| Backtest | 在持有窗口后验证历史时间线信号 | `## 预测验证` + `output/review_*` |
| Public skill | 给没有完整本地环境的用户复用 AI 研究工作流 | `skills/stock-research-cockpit` |

## 快速上手

```bash
git clone https://github.com/oliwill/Insight.git
cd Insight
pip install -r requirements.txt
cp .env.example .env
```

最小 `.env`：

```env
WIKI_BASE_DIR=/path/to/your/obsidian/vault/4_Trader
WIKI_SUBDIR=Analysis
MATERIALS_SUBDIR=Materials
OBSIDIAN_INBOX_DIR=/path/to/your/obsidian/vault/Inbox
OBSIDIAN_TASKS_DIR=/path/to/your/obsidian/vault/Tasks
OBSIDIAN_DASHBOARD_PATH=/path/to/your/obsidian/vault/Dashboard.md
ANALYSIS_TIMEOUT=30
```

可选集成见 `.env.example`：长桥、NewsAPI、Telegram bot、Inbox watcher 目录、Podwise、scheduler cron 字符串。

## Public AI Skill

如果用户暂时不想安装完整本地管线，可以先使用可分发 skill：

```text
skills/stock-research-cockpit/
```

这个 skill 把核心研究流程封装成 AI 指令：

- Skill-only 模式：任何能读取该 skill 目录的 AI agent 都可以使用。
- Local companion 模式：当本 repo、CLI 或 MCP server 可用时，调用本地数据和 Obsidian 工作流。
- External finance-skills 模式：接入估值、情绪、source-reader、市场结构等外部 finance skills。

它保留产品边界：证据驱动研究、五维 Research Score、独立 Timing State、数据缺口披露、不执行交易。

## 常用命令

```bash
# 一键 Cockpit 分析；直接写入 Obsidian
python scripts/analyze_stock.py AAPL
python scripts/analyze_stock.py 00700
python scripts/analyze_stock.py 603906

# Claude Code 编排入口：只输出结构化数据或执行基础扫描
python run_analysis.py AAPL
python run_analysis.py --scan
python run_analysis.py --dashboard
python run_analysis.py --inbox

# 定时任务入口
python scripts/scan_inbox.py --dry-run --json
python scripts/run_review.py --days-after 30 --lookback 90
python scripts/update_dashboard.py --json
python scripts/update_dashboard.py --json --reason scheduled
python scripts/update_dashboard.py --json --reason manual
python scripts/update_dashboard.py --restore-backup --json

# 可选工具
python inbox_watcher.py
python telegram_bot.py --polling
python scripts/podwise_sync.py --list
python scripts/backtest_raycat.py
python trader_mcp.py
```

## Obsidian 目录结构

推荐结构：

```
vault/
├── Inbox/                 # 用户投放素材
├── Tasks/                 # write_task() 创建的任务文件
├── Dashboard.md           # 组合仪表盘
└── 4_Trader/
    ├── Analysis/          # 股票 wiki：AAPL_US.md
    ├── Materials/         # 按股票归档的原始素材
    └── Charts/            # 自动生成的 Wyckoff 图表
```

文件命名规则：股票代码中的 `.` 和 `/` 都替换成 `_`。

| 股票代码 | Wiki 文件 |
|---|---|
| `TEM.US` | `TEM_US.md` |
| `600487.SH` | `600487_SH.md` |
| `00100.HK` | `00100_HK.md` |

股票代码归一化会保留项目内部规范，同时适配不同数据源。Yahoo 相关模块会把 5 位港股代码转换为 Yahoo 的 4 位 `.HK` 格式：`03986.HK` → `3986.HK`，`00700.HK` → `0700.HK`，`00388.HK` → `0388.HK`。具体示例由 `tests/test_yahoo_symbol.py` 保护。

## 分析输出结构

每只股票 wiki 初始化后包含这些核心 section：

| Section | 写入模块 |
|---|---|
| `综合评估` | `MemoryManager.update_evaluation_table()` |
| `证据表` | `EvidenceExtractor` + `update_cockpit_sections()` |
| `五维打分` | `ResearchScoreEngine` |
| `交易时机状态` | `TimingEngine` |
| `与上次分析相比` | `scripts/analyze_stock.py` 对比 helper |
| `分析时间线` | `MemoryManager.append_to_timeline()` |
| `预测验证` | `BacktestRunner` / `ReviewScheduler` |
| `财报预期` | `data.earnings.EarningsCalendar` |
| `流动性分析` | `data.liquidity.LiquidityAnalyzer` |
| `期权市场` | `data.options.OptionsAnalyzer` |
| `社交情绪` | `data.search.StockSearchEngine` + `SentimentAnalyzer` |
| `研究笔记` | `ReportGenerator` 完整 Markdown 报告 |
| `交叉引用` | `data.correlation.CorrelationAnalyzer` |
| `资料索引` | `MemoryManager.save_material()` |

## 评分框架

`ResearchScoreEngine` 实现五维评分：

| 维度 | 权重 | 主要输入 |
|---|---:|---|
| 行业/TAM | 20% | 行业、同行、搜索/社交信号 |
| 护城河 | 20% | 护城河分析、利润率、同行对照 |
| 增长质量 | 20% | 营收增长、盈利增长、利润率、自由现金流 |
| 估值 | 25% | P/S、PSG、Forward PE、分析师目标价 |
| 团队/治理 | 15% | 内部人持股/信号、SBC 压力 |

门槛：≥75 高信心 / 60–75 标准候选 / 45–60 观察 / <45 Pass。

`TimingEngine` 独立输出交易时机状态：

| 状态 | 含义 |
|---|---|
| `Ready` | 买点可行动，但仍需控制仓位 |
| `Wait` | thesis 可能成立，但缺少触发条件 |
| `Watch` | 低置信设置，仅观察或极小仓试探 |
| `Avoid` | 公司质量或交易时机风险过高 |

## 数据源

| 数据源 | 用途 | 要求 |
|---|---|---|
| Yahoo Finance | 历史价、基本面、期权、财报、新闻 | 默认 |
| DuckDuckGo HTML | Web / 社交搜索 fallback | 默认 |
| NewsAPI | 新闻增强 | `NEWSAPI_KEY` |
| 长桥 | 港股/A 股报价和 K 线 | 长桥凭据 |
| Obsidian vault | 历史 thesis、素材、Inbox 证据 | `.env` 路径 |
| 外部 finance-skills | 专业数据、估值、分析师预期、情绪、TradingView 和只读社交/source readers | 可选 Claude Code skills：`himself65/finance-skills` |

流水线容错：单个模块失败会返回 `*_error` 字段，数据源尝试状态会写入 `_data_sources`，不阻断其他模块生成报告。

## 模块地图

| 模块 | 作用 |
|---|---|
| `data.analysis_pipeline` | 一次性数据收集和技术指标计算 |
| `analyzer.research_score` | 证据调整后的五维评分 |
| `analyzer.timing_engine` | Ready/Wait/Watch/Avoid 交易时机状态机 |
| `input.evidence` | 从 wiki/materials/Inbox 抽取结构化证据 |
| `analyzer.report_generator` | 生成最终 Markdown 报告 |
| `analyzer.report_quality` | 检查报告结构、数据缺口披露和 Research/Timing 分离 |
| `skills/stock-research-cockpit` | 可分发的股票研究 cockpit AI skill |
| `memory.manager` | Obsidian wiki、Materials、时间线、Dashboard 持久化 |
| `backtest.runner` / `backtest.review` | 时间线信号验证、扩展指标和复盘报告 |
| `trader_mcp.py` | 面向 Claude Desktop / MCP 客户端的 MCP server |
| `telegram_bot.py` | 可选移动端命令入口 |
| `inbox_watcher.py` | 可选目录监听，触发 Inbox 扫描 |
| `scripts/podwise_sync.py` | 可选播客笔记导入 Obsidian |

## 更多文档

- `docs/architecture.md` — 系统设计和数据流
- `docs/integration-guide.md` — MCP、Telegram、Inbox、Podwise 集成步骤
- `docs/runbook.md` — 运维、调度、验证和故障排查
- `docs/handoff.md` — 面向新 agent 和维护者的当前交接快照
- `MCP_CONFIG.md` — MCP server 配置参考
- `SCHEDULER.md` — launchd 与 Python scheduler 说明

## License

MIT
