# Insight — 产品需求文档（PRD）

> 状态：现行
> 最后更新：2026-08-14
> Owner：本人（个人投资者 / 独立开发者）

---

## 1. 问题与背景（Why / Why Now）

**问题**：本人在 Obsidian 中积累了大量优质分析内容（研报、公告、行业笔记），但这些笔记**没有被真正用起来**——当前分析管线对笔记的利用是纯正则关键词抽取，浅层、不透明、低影响，且无法确认分析是否真的参考了笔记。同时，分析一只股票需要把「公司值不值得长期持有」和「现在是不是好的买入时机」混在一处判断，缺乏可重复、可验证的纪律。

**为什么是现在**：笔记量已积累到一定规模，需要规模化、低成本地利用它们；单股分析流水线已经跑通并验证可行，是时候把「每日最关注股票的跟踪」和「笔记的系统性利用」产品化、自动化。

## 2. 客户与场景

**客户**：本人（个人投资者 / 研究者）。资源受限（个人开发者，无团队），追求工具的品牌质量与可重复性。

**核心场景**：
1. **每日盘前跟踪**：早上 9:00 自动推送「近 7 天最关注的 top-3 股票」简报（评分 + 目标价 + 五维 + 文章概要 + 操作）到飞书。
2. **单股深度分析**：对某只股票跑完整分析，产出结构化的 Research Score + Timing State，写入 Obsidian。
3. **复盘验证**：历史预测在持有窗口后回测，输出胜率/收益率，沉淀到「预测验证」。

## 3. 目标与成功标准

**产品目标**：一个「Obsidian 原生的、可重复的、证据可追溯的」个人股票研究流水线——研究质量（Research Score）与交易时机（Timing State）严格分离，永不在缺数据时编造结论。

**成功标准（可衡量）**：

| 指标 | 目标 | 如何验证 |
|---|---|---|
| 每日简报按时推送 | 每日 9:00 飞书送达 | `daily_brief.py --notify` 返回 `channel: feishu` |
| 研究报告结构化 | 每股 wiki 含 Research/Timing/五维打分 | `scripts/verify_write_smoke.py` 通过 |
| 研究/时机分离 | 两者独立、互不污染 | `test_core_scoring.py` 等回归 |
| 缺数据不编造 | 缺目标价/同行/数据时不输出伪结论 | `test_framework_fixes.py` |
| 回归测试全绿 | 全部 pytest 通过 | `python -m pytest tests/` |
| 预测可回测 | 历史预测可验证胜率/收益率 | `scripts/run_review.py` |

## 4. 范围（In / Out）

**In scope**：
- 数据采集（Longbridge → Yahoo → akshare 三级降级）
- 证据抽取、五维打分（Research Score）、交易时机状态机（Timing State）
- 趋势博弈四模块（成交量语言 / 道氏通道 / 多空博弈 / 多时间框架）
- 供应链（Serenity）与护城河压力测试
- 完整报告生成（11 节 A–J）+ 每日关注简报（Daily Brief）+ 飞书/微信推送
- 回测复盘 + 预测验证
- Obsidian 沉淀（wiki / Dashboard / Tasks / 简报）
- Web 平台（多用户在线分析）

**Out of scope**（红线）：
- **永不执行真实交易**（无下单/买卖动作）
- source readers（Twitter/Telegram/Discord 等）**只读**，不发帖、不外部写入
- LLM 只做叙事增强/摘要，**不参与确定性评分**，不编造数字、不给买卖指令

## 5. 当前功能（已实现）

| 模块 | 说明 | 状态 |
|---|---|---|
| 分析流水线 | `data/analysis_pipeline.generate_analysis()` 一次取全数据 | ✅ |
| 五维打分 | `analyzer/research_score.py`（行业/护城河/增长/估值/团队，加权） | ✅ |
| Timing 状态机 | `analyzer/timing_engine.py`（Ready/Wait/Watch/Avoid，与 Research 分离） | ✅ |
| 趋势博弈四模块 | 成交量语言/道氏通道/多空博弈/多时间框架 | ✅ |
| 供应链 | `data/supply_chain.py` + `data/serenity/` | ✅ |
| 完整报告 | `scripts/generate_full_report.py`（11 节 A–J + 三情景目标价） | ✅ |
| **每日关注简报** | `scripts/daily_brief.py`（分析频次 top-3 → LLM/模板摘要 → 飞书推送 + Obsidian 落盘） | ✅ 2026-08-14 |
| Web 平台 | `web/`（多用户、分析记录、自选股） | ✅（线上化 v1） |
| 回测复盘 | `scripts/run_review.py` / `scripts/weekly_review.py` | ✅ |
| 公开 Skill | `skills/stock-research-cockpit/` | ✅ |

**数据准确性契约**（2026-08-14 修复并锁定）：增速统一为百分比（`normalize_growth_rate`）、A 股成交量统一为股（×100）、缺同行基准显式披露、A 股/港股/美股货币符号正确、成交量爆冲只扫近 20 日、道氏顶底信号需确认、财报窗口硬顶 Wait。

## 6. 路线图

| 优先级 | 事项 | 设计文档 |
|---|---|---|
| P0（下一步） | **证据写入时索引 + 分析时检索**（把笔记"理解"前置到 ingest，分析报告可溯源"参考了哪些笔记"） | `docs/evidence-ingest-architecture.md` |
| P1 | 每日简报 LLM 摘要持续优化（已接 OpenCode Go / DeepSeek V4 Flash） | `docs/daily-brief-design.md` |
| P1 | DollarLiquidity 宏观流动性接入 | — |
| P2 | 供应链知识库扩充（机器人/固态电池/先进封装） | — |
| P2 | Dashboard 整合 Serenity 结果 | — |
| P3 | 语义检索（向量，笔记量到数千条后） | — |

## 7. 关键决策与开放问题

| 决策点 | 当前选择 | 理由 |
|---|---|---|
| 存储 | Obsidian vault（Markdown + front matter），无数据库 | 可读、可溯源、零依赖 |
| 数据源 | Longbridge → Yahoo → akshare（A 股）三级降级 | 免费优先、容错 |
| 通知 | 飞书自定义机器人 webhook 优先 | 免费、单 URL、无 OAuth |
| LLM | OpenCode Go（`deepseek-v4-flash`），可选增强、失败静默降级 | 推理模型，叙事/摘要 |
| 调度 | Windows 任务计划（`scripts/windows/*.ps1`），macOS 用 `launchd`/`scheduler.py` | 本人在 Windows |

**开放问题**：
- 证据索引（P0）落地后，是否要把「行业/宏观/策略」类笔记自动关联到个股分析（跨类目召回）？
- 简报是否加"较上次变化"行（需 vault 存结构化变化记录）。

---

## 8. 参考文档

- 架构：`docs/architecture.md`｜运维：`docs/runbook.md`｜交接：`docs/handoff.md`
- 报告规范：`CLAUDE.md`（11 节 A–J + 五维打分权重）
- 本阶段设计：`docs/daily-brief-design.md` / `docs/evidence-ingest-architecture.md`
- 进度追踪：`project.md`
