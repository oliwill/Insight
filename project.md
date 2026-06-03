# trader-obsidian 项目进度

更新时间：2026-05-27
维护方式：每次完成阶段性开发、修复关键问题或调整方向后更新本文件。

## 1. 项目定位

`trader-obsidian` 是一个以 Obsidian 为长期研究工作台、以 Python 和 Claude Code 为执行与推理层的股票研究系统。

核心目标：

- 将股票研究资料、市场数据、分析结论和复盘结果沉淀到 Obsidian Markdown 文件中。
- 区分长期公司/投资逻辑质量与短期交易时机，避免把“好公司”和“好买点”混为一谈。
- 通过 Inbox、Materials、Stock Wiki、Dashboard 和 Tasks 构建可持续迭代的研究闭环。

## 2. 当前状态快照

| 模块 | 当前状态 | 入口 / 参考 |
|---|---|---|
| 一键 Cockpit 分析 | 已实现 | `python scripts/analyze_stock.py <TICKER>` |
| 数据采集与分析上下文 | 已实现 | `python run_analysis.py <TICKER>` |
| Obsidian 写入 | 已实现 | `run_analysis.write_analysis_to_obsidian()` |
| 证据提取 | 已实现 | `input.evidence.EvidenceExtractor` |
| 五维 Research Score | 已实现 | `analyzer.research_score.ResearchScoreEngine` |
| Timing State | 已实现 | `analyzer.timing_engine.TimingEngine` |
| 时间线回测 | 已实现 | `backtest.runner.BacktestRunner` |
| 定期复盘 | 已实现 | `scripts/run_review.py` |
| MCP 服务 | 已实现 | `python trader_mcp.py` |
| Telegram Bot | 已实现 | `python telegram_bot.py --polling` |
| Inbox Watcher | 已实现 | `python inbox_watcher.py` |
| Podwise 同步 | 已实现 | `python scripts/podwise_sync.py` |
| Yahoo 港股代码映射测试 | 已实现 | `tests/test_yahoo_symbol.py` |
| Obsidian section 安全写入测试 | 已实现 | `tests/test_section_write.py` |
| 报告生成渲染回归测试 | 已实现 | `tests/test_report_generator.py` |

## 3. 关键项目约束

这些约束比普通任务优先级更高：

1. 股票 wiki 必须写入配置的 Obsidian vault，不要在仓库里手写分析报告副本。
2. 股票文件名统一把 `.` 和 `/` 替换成 `_`：`AAPL.US` → `AAPL_US.md`。
3. `Research Score` 衡量公司/ thesis 质量；`Timing State` 衡量入场时机，二者必须保持分离。
4. Cockpit sections 每次分析可替换：`证据表`、`五维打分`、`交易时机状态`、`与上次分析相比`。
5. 长期 sections 以追加为主：`分析时间线`、`预测验证`、`研究笔记`、`资料索引`。
6. 数据模块失败时应返回 `*_error` 字段，不应阻断整个报告生成。
7. 生成内容写入已有 wiki section 时，不能破坏 Obsidian 顶层结构。

## 4. 当前里程碑

### M0：基础研究管线

状态：已完成

交付物：

- 市场数据、基本面、技术面、Wyckoff、财报、流动性、期权、搜索/情绪、相关股票、ETF 检测等数据进入 `generate_analysis()`。
- `scripts/analyze_stock.py` 能完成一键分析并写入 Obsidian。

### M1：Obsidian 研究闭环

状态：已完成

交付物：

- Stock Wiki 初始化与更新。
- Materials、Inbox、Dashboard、Tasks 的读写链路。
- Timeline 和预测验证 section 可持续追加。

### M2：研究质量与交易时机分离

状态：已完成

交付物：

- 五维 Research Score。
- Ready / Wait / Watch / Avoid Timing State。
- 报告中明确区分“值得研究/持有”和“是否适合现在入场”。

### M3：自动化入口与集成

状态：进行中维护

已完成：

- MCP 服务。
- Telegram Bot。
- Inbox Watcher。
- Podwise 同步。
- Scheduler / launchd 相关文档。

后续重点：

- 确认 Windows 环境下调度方案是否需要独立文档或脚本封装。
- 为常用入口建立更明确的 smoke test 清单。
- 补齐自动化入口的回归测试覆盖，尤其是 watcher / bot / scheduler 的可测试边界。

### M4：投资级分析增强

状态：待推进

待补强方向：

- 实时 GEX / options flow。
- Insider / congressional trading。
- Supply-chain mapping。
- SEPA stage confirmation。
- 跨来源结构化 sentiment。

当前策略：本地模块提供基线数据和结构；完整投资级分析仍需要 Claude Code 调用外部 finance skills 补足实时和专业数据。

## 5. 工作看板

### Now

| 任务 | 优先级 | 状态 | 下一步 |
|---|---|---|---|
| Git 可交付基线整理 | P0 | 进行中 | 在 `codex/p0-delivery-baseline` 上确认当前改动分组，并形成可提交状态。 |
| 测试环境与 smoke test 入口 | P0 | 已完成 | 使用 `requirements-dev.txt` 安装测试依赖后运行 `scripts/windows/run_smoke_tests.ps1`。 |
| 最小回归清单固化 | P0 | 已完成 | 保持 runbook 中的 py_compile、pytest、Inbox dry-run、review ticker discovery 为默认验证入口。 |

### Next

| 任务 | 优先级 | 说明 |
|---|---|---|
| Dashboard 更新策略复核 | P1 | 明确何时自动更新、何时手动更新，以及失败时如何恢复。 |
| 自动化入口测试边界 | P2 | 给 watcher / bot / scheduler 补参数解析、dry-run 和 fallback 测试。 |
| 外部 finance skills 缺口清单化 | P2 | 把 GEX、insider、supply chain、SEPA、sentiment 的调用时机写成 checklist。 |

### Later

| 方向 | 价值 | 备注 |
|---|---|---|
| 更完整的回测指标 | 提高策略反馈质量 | 可扩展 `backtest.runner` 和 review 输出。 |
| 多数据源容错策略 | 提高分析稳定性 | 针对 Yahoo / DuckDuckGo / NewsAPI / Longbridge 分层降级。 |
| 报告质量评估器 | 降低生成报告的漂移风险 | 检查是否遗漏关键 section、是否混淆 Research Score 和 Timing State。 |

### Done

| 日期 | 事项 | 说明 |
|---|---|---|
| 2026-06-03 | 固化 HIMS.US / 03986.HK 写入型 smoke example | 新增 `scripts/windows/run_write_smoke_examples.ps1` 和 `scripts/verify_write_smoke.py`；HIMS.US wiki+chart 验证通过，03986.HK wiki 验证通过。 |
| 2026-06-03 | 完成 Windows Task Scheduler 实机验证 | 新增 `scripts/windows/verify_scheduled_tasks.ps1`；`trader-obsidian-inbox` / `review` / `dashboard` 三条任务注册、触发和日志验证通过。 |
| 2026-06-03 | 修复 review runner 的 Windows PowerShell 兼容问题 | `run_scheduled_task.ps1` 改为 `Start-Process` + stdout/stderr 文件重定向，避免 loguru stderr 被误判为任务失败。 |
| 2026-06-03 | 修复 backtest Decimal 价格序列兼容性 | `backtest/core.py` 强制将 close 序列转为 float，并补充 Decimal 回归测试。 |
| 2026-06-02 | 建立 P0 smoke test 基线 | 新增 `requirements-dev.txt` 与 `scripts/windows/run_smoke_tests.ps1`；当前完整 smoke 通过，21 个回归测试通过。 |
| 2026-06-02 | 修复复盘 ticker discovery 噪声 | 过滤 Obsidian wikilink、路径、人物名和主题名，避免定期复盘扫描非股票项。 |
| 2026-06-02 | 改善报告可读性和复盘入口 | 报告标题改为股票名称+代码，空数据模块自动省略并汇总数据缺口；复盘全量扫描增加 wiki 文件 fallback 和 `--list-tickers`。 |
| 2026-06-02 | 完成 Windows 定时任务方案 | 新增 `scripts/windows/run_scheduled_task.ps1` 和 `scripts/windows/register_scheduled_tasks.ps1`，`SCHEDULER.md` / runbook 已记录 Task Scheduler 流程。 |
| 2026-05-27 | 固化 smoke test 清单 | `docs/runbook.md` 和 `docs/handoff.md` 已记录最小验证命令，当前三项回归测试通过。 |
| 2026-05-25 | 创建 `project.md` | 建立项目进度、里程碑、看板和风险的统一管理入口。 |

## 6. 风险与阻塞

| 风险 | 影响 | 当前处理 |
|---|---|---|
| Windows 环境没有稳定 Python 命令 | smoke test 和自动任务不可复现 | 使用 `scripts/windows/run_smoke_tests.ps1 -PythonExe ...`，并通过 `requirements-dev.txt` 固化 `pytest`。 |
| Windows 与 macOS/Linux 调度能力不一致 | 自动任务在 Windows 上可能不能直接使用 daemon 模式 | Windows 已验证 Task Scheduler 方案；不要默认 `scheduler.py --daemon` 可用。 |
| 外部实时数据不足 | 投资级分析可能缺少 GEX、内部人、供应链等关键变量 | 完整分析时调用外部 finance skills，并在报告中标注数据缺口。 |
| Obsidian section 被错误覆盖 | 长期研究历史可能丢失或结构损坏 | 保持 section 写入测试，修改写入逻辑时优先跑 `tests/test_section_write.py`。 |
| Research Score 与 Timing State 混淆 | 导致错误交易建议 | 所有报告和代码改动都明确二者职责边界。 |

## 7. 决策记录

| 日期 | 决策 | 原因 | 影响 |
|---|---|---|---|
| 2026-06-02 | P0 先收敛到可交付基线 | 当前功能基本完成，但本地分支落后、工作区脏、Python/pytest 验证入口不稳定 | 后续新增功能前，先保证 Git 基线、测试环境和 smoke test 可复现。 |
| 2026-05-25 | 使用 `project.md` 作为项目进度管理入口 | 项目已有 README / docs / handoff，但缺少面向进度推进的单页看板 | 后续阶段性任务、风险和里程碑集中维护在本文件。 |
| 2026-05-25 | 不把 `INTEGRATION_PLAN.md` 当未来计划使用 | 该文件当前记录的是 Skills Integration Status | 未来计划和任务推进放在 `project.md`，集成状态继续留在 `INTEGRATION_PLAN.md`。 |

## 8. 每周更新流程

建议每周或每次阶段性开发后按以下顺序更新：

1. 更新“当前状态快照”中发生变化的模块状态。
2. 把完成的任务从 `Now` / `Next` 移到 `Done`。
3. 检查是否有新的风险或阻塞。
4. 补充重要决策到“决策记录”。
5. 如果改动影响外部使用方式，同步更新：
   - `README.md` / `README.zh.md`
   - `docs/integration-guide.md`
   - `docs/runbook.md`
   - `docs/architecture.md`
   - `docs/handoff.md`

## 9. 新 Agent 接手检查

开始处理任务前先运行或检查：

```bash
git status --short
python -m py_compile config.py run_analysis.py scripts/analyze_stock.py trader_mcp.py
python -c "from config import Config; print(Config.get_wiki_dir())"
python scripts/scan_inbox.py --dry-run --json
```

注意：不要在用户未明确要求写入报告时运行 `python scripts/analyze_stock.py <TICKER>`，因为它会写入 Obsidian。

## 10. 关联文档

| 文档 | 用途 |
|---|---|
| `README.md` / `README.zh.md` | 项目介绍、安装和命令入口 |
| `CLAUDE.md` | Claude Code 在本项目中的操作规则 |
| `docs/architecture.md` | 架构、数据流和模块边界 |
| `docs/integration-guide.md` | MCP、Telegram、Inbox、Podwise 集成说明 |
| `docs/runbook.md` | 运维、调度、验证和故障排查 |
| `docs/handoff.md` | 新维护者接手快照 |
| `INTEGRATION_PLAN.md` | 已集成能力状态 |
| `MCP_CONFIG.md` | MCP 配置参考 |
| `SCHEDULER.md` | 调度与 launchd 说明 |
