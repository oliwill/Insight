# 设计文档：Serenity 产业链分析集成到个股基本面分析

**日期**: 2026-06-12
**状态**: 待实现
**分支**: codex/p0-delivery-baseline

---

## 背景

项目已有两套系统并存：
- **个股财务分析流水线** (`run_analysis.py` / `scripts/analyze_stock.py`)：数据获取 → 五维打分 → 报告生成 → Obsidian 写回
- **产业链扫描模块** (`data/serenity/`)：行业主题 → 产业链拆解 → 瓶颈评分 → 候选公司排序

当前二者互不通讯：做个股分析时缺少供应链卡位维度；产业链扫描也只能按主题独立跑，无法从个股反查。

目标：让每只股票的个股分析自动包含产业链卡位信息，作为基本面的子维度。

---

## 核心设计原则

1. **只加不改**：现有评分逻辑、报告段落、Obsidian 写回逻辑全部保留
2. **只调顺序**：报告段落重新排序为结论前置结构
3. **产业链归入基本面**：供应链分析结果作为 `fundamentals.supply_chain` 字段，不创建独立 section
4. **LLM + 缓存双轨**：首次分析调 LLM 拆链，结果缓存 90 天，后续分析复用
5. **向后兼容**：`supply_chain` 为空/null 时评分逻辑保持不变，不报错

---

## 新增模块

### `data/serenity/stock_chain_analyzer.py`

个股产业链定位器。输入股票代码 + sector/industry，输出该股在产业链中的位置和瓶颈暴露度。

```python
@dataclass
class StockChainPosition:
    topic: str                       # 产业链主题
    matched_via: str                 # "knowledge_base" | "llm" | "cache"
    chain_layers: List[dict]         # 拆解后的产业链层级
    target_layer_index: int          # 该股所在层级索引
    target_role: str                 # "控制瓶颈" | "供应瓶颈" | "受益于需求" | "蹭主题"
    bottleneck_score: float          # 所在层级瓶颈分 0-10
    bottleneck_grade: str            # "强瓶颈" | "中等瓶颈" | "弱瓶颈"
    supplier_concentration: str      # "high" | "medium" | "low"
    certification_barrier: str       # "high" | "medium" | "low"
    peer_companies: List[str]        # 同层级竞争/合作公司
    upstream_risks: List[str]        # 上游依赖风险
    downstream_exposure: str         # 下游客户暴露
    evidence_level: str              # "strong" | "medium" | "weak"
    generated_at: str                # ISO timestamp
```

#### 分析流程

```
StockChainAnalyzer.analyze(stock_code, sector, industry)
  ├─ 1. 查缓存
  │    路径: .claude/cache/supply_chain/{normalized_code}.json
  │    有效期: 90 天
  │    → 命中：matched_via="cache"，直接返回
  │
  ├─ 2. 查知识库（INDUSTRY_KNOWLEDGE）
  │    从 sector/industry 推断主题词 → LAYER_MAP 匹配
  │    → 命中：匹配到预制产业链模板，填回 StockChainPosition
  │
  ├─ 3. LLM 推理（知识库未命中）
  │    使用 SERENITY_PROMPT 模板 + stock_info 上下文
  │    由 Claude Code 在分析阶段推理产业链位置
  │    → 返回结构化链分析 JSON
  │
  └─ 4. 写缓存
       缓存分析结果到本地 JSON 文件
```

#### 缓存策略

- **位置**：`.claude/cache/supply_chain/{normalized_code}.json`
- **格式**：`StockChainPosition` 的 JSON 序列化
- **有效期**：90 天（产业链变化慢）
- **刷新触发**：超过有效期自动重新分析；后续可加 `--refresh-chain` 参数

---

## 修改文件

### 1. `data/analysis_pipeline.py`

目标：在 `generate_analysis()` 的 Step 1 末尾注入供应链卡位数据。

```python
# Step 1 末尾新增（在 fundamentals 获取之后）：
try:
    from data.serenity.stock_chain_analyzer import StockChainAnalyzer
    sector = info.sector if info else None
    industry = info.industry if info else None
    sca = StockChainAnalyzer()
    supply_chain = sca.analyze(code, sector or "", industry or "")
    if supply_chain and fund:
        fund['supply_chain'] = supply_chain
except ImportError:
    pass  # stock_chain_analyzer 不存在时静默跳过
except Exception as e:
    output['supply_chain_error'] = str(e)
```

改动量：~10 行，加在 `get_fundamentals()` 成功后。

### 2. `analyzer/research_score.py`

目标：`_industry_score()` 和 `_moat_score()` 读取 `supply_chain` 数据加权。

```python
# _industry_score() 新增：
supply_chain = fundamentals.get('supply_chain')
if supply_chain:
    bn = supply_chain.get('bottleneck_score', 0)
    if bn >= 7:
        score += 2.0
        evidence.append(f"产业链瓶颈暴露度高 ({bn}/10)")
    elif bn >= 5:
        score += 1.0
        evidence.append(f"产业链瓶颈暴露度中等 ({bn}/10)")
    if supply_chain.get('target_role') in ('控制瓶颈', '供应瓶颈'):
        score += 0.5
        evidence.append(f"产业链角色: {supply_chain['target_role']}")

# _moat_score() 新增：
supply_chain = fundamentals.get('supply_chain')
if supply_chain:
    cert = supply_chain.get('certification_barrier', '')
    conc = supply_chain.get('supplier_concentration', '')
    if cert == 'high':
        score += 0.8
        evidence.append("客户认证壁垒高（产业链数据）")
    if conc == 'high':
        score += 0.5
        evidence.append("供应商高度集中（产业链数据）")
```

改动量：每个函数 ~8 行，supply_chain 为空时完全跳过。

### 3. `analyzer/report_generator.py`

目标：段落顺序调整为结论前置，产业链卡位归入基本面段落。

```python
# 新段落顺序：
sections = [
    "综合评估（结论前置）",    # NEW: 一句话结论
    "公司与催化剂",            # 公司身份、主营、催化剂
    "产业链卡位",              # NEW: 供应链位置、瓶颈评分（基本面子模块）
    "基本面与增长质量",        # 营收/盈利/毛利率/FCF/ROE（保留现有逻辑）
    "估值锚点",                # P/S、PSG、同行对照、三情景
    "技术面",                  # SEPA、Wyckoff、支撑阻力（保留现有逻辑）
    "五维打分",                # （保留现有逻辑）
    "操作格网",                # 建仓/加仓/减仓/止损
    "风险量化",                # （保留现有逻辑）
    "关键催化剂日历",          # （保留现有逻辑）
]
```

改动量：调整 `sections` 列表顺序，新增「综合评估」和「产业链卡位」两个段落的生成函数。

### 4. `scripts/analyze_stock.py`

目标：透传 `supply_chain` 到 `ReportGenerator`。

```python
# 在 score 和 analysis_text 生成之间，将 supply_chain 注入 market_data：
# （已在 analysis_pipeline.py 中注入 fundamentals.supply_chain，此处无需额外改动）
# ReportGenerator.generate() 直接从 market_data.fundamentals.supply_chain 读取
```

改动量：0 行（supply_chain 已在 pipeline 层注入 fundamentals）。

---

## 不动的内容

以下模块完全保持不变：

- `data/serenity/chain_analyzer.py` — 独立产业链扫描
- `data/serenity/bottleneck_scorer.py` — 瓶颈评分
- `data/serenity/integrator.py` — Serenity → Obsidian 段写入
- `data/serenity/report_builder.py` — 产业链报告生成
- `data/serenity/reference.py` — 知识库常量（只加数据，不加代码）
- `scripts/serenity_scan.py` — CLI 入口
- `input/evidence.py` — 证据提取
- `analyzer/timing_engine.py` — 时机判断
- `analyzer/report_quality.py` — 报告质量
- `run_analysis.py` — `write_analysis_to_obsidian()`
- 所有测试文件

---

## 报告输出结构

```
## 综合评估（结论前置）

{公司名} ({代码}) 是一家{一句话定位}，当前股价 ${XX.XX}，PE X.X 倍，
PB X.X 倍，PSG X.XX。经过基本面、产业链卡位、技术面和五维分析，
综合评分 XX/100，建议{建仓/观望/减仓}，建议建仓区间 $XX–$XX，
12 个月目标价 $XX.XX（上行 +XX%），止损线 $XX.XX。

## 公司与催化剂
[现有内容完全保留]

## 产业链卡位  ← 基本面子模块
- 所属产业链主题: {topic}
- 位置: 第 N 层「{层级名}」
- 角色: {控制瓶颈 / 供应瓶颈 / 受益于需求 / 蹭主题}
- 瓶颈评分: {X}/10 ({瓶颈等级})
- 供应商集中度: {高/中/低}
- 客户认证壁垒: {高/中/低}
- 同层级关键公司: {列表}
- 上游依赖风险: {列表}
- 证据强度: {strong/medium/weak}

## 基本面与增长质量
[现有内容完全保留]

## 估值锚点
[现有内容完全保留]

## 技术面
[现有内容完全保留]

## 五维打分
[现有内容完全保留]

## 市场结构
[现有内容完全保留]

## 风险量化
[现有内容完全保留]

## 三情景目标价
[现有内容完全保留]

## 操作格网
[现有内容完全保留]

## 警戒线 / 加仓信号
[现有内容完全保留]

## 关键催化剂日历
[现有内容完全保留]
```

---

## 验证

### 单元测试
```bash
# 新增测试
python -m pytest tests/test_serenity/test_stock_chain_analyzer.py -v

# 确保现有测试不受影响
python -m pytest tests/test_serenity/ -v
python -m pytest tests/ -v
```

### 端到端验证
```bash
# 分析一只科技股（应触发 LLM 拆链）
python run_analysis.py NVDA

# 检查输出 JSON 中的 fundamentals.supply_chain 字段存在且非空
# 检查 Obsidian 中 NVDA 页面的报告结构符合新顺序

# 二次分析同一只股票（应命中缓存）
python run_analysis.py NVDA
# supply_chain.matched_via 应为 "cache"

# 冷门股（无知识库匹配，应走 LLM）
python run_analysis.py MDB
# 不应报错，supply_chain 应含有效数据或为空

# 产业链扫描 CLI 保持可用
python scripts/serenity_scan.py "AI 半导体"
```
