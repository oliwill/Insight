# Insight 项目进度追踪

> 最后更新：2026-06-16

## 已完成

### Finance skills agent-layer 融入 (2026-06-16)
- [x] 手动安装 `himself65/finance-skills` plugin bundle：market-analysis、data-providers、social-readers、startup-tools、ui-tools、skill-creator
- [x] 明确 finance skills 是 Claude Code / agent-layer companion，不是 Python pipeline 依赖
- [x] 建立 Baseline / Conditional / Explicit-only taxonomy
- [x] 同步 `CLAUDE.md`、README、integration guide、runbook、handoff、architecture、website 文案
- [x] 保留 source readers 只读边界：不发帖、不外部写入、不执行交易
- [x] 验证：pytest 回归 `72 passed, 2 warnings`；`node --check website/app.js` 与 Python 编译检查需在本地命令可用时继续作为发布前检查

### Serenity 产业链扫描集成 (2026-06-12)
- [x] 设计 SerenityIntegrator：将产业链分析结果映射到 Obsidian Wiki 的多个 section
- [x] 实现综合评估更新：行业/TAM 维度自动填充
- [x] 实现五维打分：基于瓶颈分析计算行业/TAM、护城河、增长质量三个维度
- [x] 实现证据表：候选公司作为结构化证据条目
- [x] 实现交叉引用：产业链相关公司自动列出
- [x] 保留研究笔记：完整产业链分析 Markdown 追加
- [x] 实现分析时间线：自动追加扫描记录
- [x] 修复 MNTS 别名映射错误（MNTS 是 Momentus，非 MRAM）
- [x] 编写完整集成测试
- [x] 编写集成文档 SERENITY_INTEGRATION.md
- [x] 全部 56 个测试通过

### Serenity 基础模块 (2026-06-12 早)
- [x] `reference.py`：LAYER_MAP 别名映射 + INDUSTRY_KNOWLEDGE 知识库（MRAM、AI 半导体、CPO、GPU、HBM）
- [x] `chain_analyzer.py`：知识库精确匹配 → 模糊匹配 → 骨架兜底
- [x] `bottleneck_scorer.py`：瓶颈评分 + 候选排序
- [x] `report_builder.py`：Markdown 生成 + Obsidian 写入
- [x] `scripts/serenity_scan.py`：CLI 入口

### 其他已完成
- [x] 分析流水线 (`data/analysis_pipeline.py`)
- [x] 报告生成器 (`analyzer/report_generator.py`)
- [x] MemoryManager Wiki 系统
- [x] 五维打分引擎 (`analyzer/research_score_engine.py`)
- [x] 交易时机引擎 (`analyzer/timing_engine.py`)

## 进行中

（暂无）

## 待办（按优先级）

### P1 — 高优先级
- [ ] **DollarLiquidity 宏观流动性数据接入**：已验证 `/api/regime`、`/api/series/{indicatorId}`、`/api/correlation` 三个端点，需要实现数据拉取和集成
- [ ] **web_searcher.py 实现**：`--depth deep` 模式，联网查公告/财报/订单，补充知识库未覆盖的主题
- [ ] **扩充知识库**：添加更多产业主题（机器人、固态电池、先进封装等）

### P2 — 中优先级
- [ ] **Dashboard 整合 Serenity 结果**：在 Dashboard 中展示产业链分析结果
- [ ] **合并 codex/p0-delivery-baseline 到 GitHub master**
- [ ] **MNTS (Momentus) 独立分析**：创建空间基础设施产业链知识库

### P3 — 低优先级
- [ ] **Serenity 知识库自动更新**：定期从网络抓取产业链变化
- [ ] **多股票对比**：在同一产业链中对比多个候选公司
- [ ] **产业链可视化**：生成产业链拓扑图

## 命令参考

```powershell
# Serenity 产业链扫描
cd E:\Git\ClaudeCode\insight

# 打印 Markdown 到 stdout
.\.venv\Scripts\python.exe scripts/serenity_scan.py "MRAM" --dry-run

# 打印 JSON 到 stdout
.\.venv\Scripts\python.exe scripts/serenity_scan.py "MRAM" --dry-run --json

# 写入 Obsidian（需外出权限）
.\.venv\Scripts\python.exe scripts/serenity_scan.py "MRAM"

# 全部测试
.\.venv\Scripts\python.exe -m pytest

# 仅 Serenity 测试
.\.venv\Scripts\python.exe -m pytest tests/test_serenity/ -v
```

## 关键文件

| 文件 | 用途 |
|------|------|
| `data/serenity/integrator.py` | SerenityIntegrator — 将产业链分析融入 Obsidian 框架 |
| `data/serenity/chain_analyzer.py` | 产业链拆解 + 知识库查找 |
| `data/serenity/reference.py` | INDUSTRY_KNOWLEDGE 知识库 + LAYER_MAP 别名 |
| `data/serenity/bottleneck_scorer.py` | 瓶颈评分 + 候选排序 |
| `data/serenity/report_builder.py` | Markdown 生成 + Obsidian 写入 |
| `scripts/serenity_scan.py` | CLI 入口 |
| `SERENITY_INTEGRATION.md` | 集成文档 |
| `project.md` | 本文件 — 项目进度追踪 |

## 环境信息

- Windows, Python 3.12.13, PowerShell 7
- `.venv\Scripts\python.exe`（非 `python`）
- Obsidian 路径：`C:\Users\Lzw\Downloads\Documents\obsidian\Lzw\Lzw\4_Trader\Analysis\`
- `.env` 配置：`WIKI_BASE_DIR` + `WIKI_SUBDIR`
