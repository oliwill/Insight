# Serenity 产业链扫描 — 设计文档

日期：2026-06-12
状态：已确认，开始实现
入口：`scripts/serenity_scan.py`

## 动机

单只股票深度报告回答了"这家公司好不好"的问题，但第一次遇到热门主题（AI 半导体、机器人减速器、CPO）时，用户需要的是一个上游判断：这个方向该不该花时间研究？产业链里卡在哪？谁的逻辑最清楚？

Serenity 方法论把热点拆成产业链层级，逐层找瓶颈，再筛出优先级最高的候选方向。

## 设计

### 输入

```
python scripts/serenity_scan.py <topic> [--depth normal|deep] [--export-md] [--dry-run] [--json]
```

| 参数 | 默认 | 说明 |
|---|---|---|
| topic | 必填 | 自然语言热点词 |
| --depth | normal | normal 纯 LLM 知识；deep 联网查公告/财报/订单 |
| --export-md | 无 | 不写入，只打印 Markdown 到 stdout |
| --dry-run | 无 | 不写入，只打印 JSON 到 stdout |
| --json | 无 | 与 --dry-run 配合控制输出格式 |

### 文件结构

```
scripts/serenity_scan.py              ← CLI 入口 + workflow dispatch
data/serenity/
├── __init__.py
├── reference.py                       ← Serenity 打分规则 + 提示词模板
├── chain_analyzer.py                  ← 热点解析 + 产业链拆解（LLM 驱动）
├── bottleneck_scorer.py               ← 瓶颈评分 + 候选公司筛选
├── report_builder.py                  ← Markdown 生成 + Obsidian 写入
└── web_searcher.py                    ← deep depth 联网搜索（P2）
tests/test_serenity/
├── __init__.py
├── test_bottleneck_scorer.py          ← 评分单元测试
└── test_report_builder.py             ← 输出格式测试
└── test_data/
    └── ai_semiconductor.json          ← 样例 JSON fixture
```

### 数据流

1. `scripts/serenity_scan.py` 解析参数 → 调用 `chain_analyzer.analyze(topic, depth)`
2. `chain_analyzer.py` 产出结构化 JSON：层级列表 + 候选公司列表
3. `bottleneck_scorer.py` 对每个层级打分，给候选公司排序
4. `report_builder.py` 转成 Markdown，可选写入 Obsidian
5. `depth=deep` 时，`web_searcher.py` 在步骤 2-3 间插入联网查证

### 链式分析 JSON 结构

```json
{
  "topic": "AI 半导体",
  "depth": "normal",
  "summary": { "description": "...", "demand_driver": "..." },
  "layers": [
    {
      "name": "芯片/器件",
      "key_companies_cn": ["...", "..."],
      "key_companies_global": ["...", "..."],
      "supply_demand": "tight",
      "expansion_difficulty": "high",
      "certification_barrier": true,
      "scarcity": "medium"
    }
  ],
  "candidates": [
    {
      "company": "...",
      "layer": "芯片/器件",
      "rationale": "...",
      "evidence": "order/certification/financial/analyst",
      "valuation_pressure": "medium",
      "risks": ["...", "..."],
      "priority": 1
    }
  ]
}
```

### 瓶颈打分规则

每层级最多 10 分：

| 条件 | 分数 |
|---|---|
| 低供应商数量（≤3 家） | +2 |
| 验证周期 ≥ 18 个月 | +2 |
| 扩产困难（18 个月以上） | +2 |
| 客户认证严格 | +1 |
| 材料/工艺稀缺 | +1 |
| 地缘限制 | +1 |
| 专利壁垒 | +1 |

瓶颈等级：≤4 弱、5-6 中等、≥7 强。

### 写入 Obsidian 的 Markdown 结构

追加到该方向/公司的 `研究笔记`，格式：

```
### [YYYY-MM-DD HH:mm] 产业链扫描：{topic}

### 一、主题定位
{描述 + 需求驱动}

### 二、产业链拆解
| 层级 | 中国公司 | 海外公司 | 供需判断 |
|---|---|---|---|

### 三、瓶颈判断
| 层级 | 瓶颈分 | 核心卡点 |
|---|---|---|

### 四、优先研究清单
1. **{公司}** — {环节}
   - 逻辑：{摘要}
   - 证据：{来源}
   - 风险：{主要风险}

### 五、基金/ETF 方向（可选）

### 六、下一步检查清单
- [ ] {待办项}
```

写入使用 `MemoryManager.append_to_section()`，标题经 `_demote_markdown_headings` 降级。

### 测试边界

- `test_bottleneck_scorer.py`：分数不溢出、所有层级都能打分、候选排序稳定、去重
- `test_report_builder.py`：6 个 section 全部存在、headers 顺序正确、无 section 丢失
- 边界：空输入、无层级匹配、空候选列表
- 不测试：`chain_analyzer.py`（LLM 调用）和 `web_searcher.py`（联网）

### 不做的

- 不修改 `ResearchScoreEngine`、`TimingEngine`、`ReportGenerator`
- `chain_analyzer.py` 和 `web_searcher.py` 不加入 CI 回归
- `--depth deep` 暂不实现（P2）
- Dashboard 整合暂不实现（P3）
