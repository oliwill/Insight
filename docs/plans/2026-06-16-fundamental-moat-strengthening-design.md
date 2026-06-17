# 基本面护城河分析强化 — 分阶段设计

## 背景

`analyzer/fundamental.py` 已存在八段式护城河压力测试的完整接入：

- `MOAT_STRESS_TEST_PROMPT_TEMPLATE`（84 行）— 与用户提供的 prompt 一字不差
- `build_moat_stress_test()`（325 行）— 确定性生成事实包/推断/三视角/结论
- 管线 `data/analysis_pipeline.py:368`、脚本 `scripts/analyze_stock.py:152`、渲染 `analyzer/report_generator.py:1095`、测试两处均已接通

**核心落差**：当前产出是"确定性脚手架 + prompt 文本留给外部"，没有真正调用 LLM 产出八段式叙事长文。且全仓无任何 LLM 客户端调用（`data/supply_chain.py:4` 明确写"不调用外部 LLM/API"）。

## 设计原则

1. **确定性优先**：与项目既有范式一致，所有规则可复现、可测试、离线可跑。
2. **分层可选**：LLM 叙事层默认关闭，不引入硬性运行时依赖。
3. **每阶段独立可交付**：阶段一完成后系统即可用且质量提升，不依赖后续阶段。
4. **样本驱动决策**：阶段一交付后用真实样本评估，再决定阶段二是否启动。

---

## 阶段一：确定性脚手架强化（本次实现）

**目标**：在不调用 LLM 的前提下，最大化 `build_moat_stress_test()` 的信息密度和分析锐度。

### 1.1 同行相对强弱（`build_moat_stress_test` 新增输入维度）

当前 `peers` 只取了名字（`_company_peer_names`），没有利用同行财务做横向对比。新增：

- 在 `build_moat_stress_test()` 内部，从 peers 列表中提取可用的 `market_cap` / `gross_margin` / `revenue_growth`（若 peer dict 含这些字段）
- 计算目标公司相对同行中位数的偏离度，产出 `peer_relative_strength` 区块
- 驱动新的推断规则，例如："毛利率高于同行中位数 X%，定价权相对优势更可信"

**改动文件**：`analyzer/fundamental.py`（`build_moat_stress_test` + 新增 `_peer_relative_strength` 辅助函数）

**注意**：peer dict 字段不一定齐全，所有同行对比必须有 "样本不足时降级" 的兜底（返回空、不报错）。

### 1.2 竞争对手攻击模拟的三档预算参数化

当前 `competitor_attack_vectors` 是单档的定性描述。prompt 原文里第四段要求"低/中/高预算"三档。在脚手架层把它们结构化：

- 新增 `attack_budget_tiers` 区块，基于目标公司 `market_cap` 自动推断三档预算量级（例如低=市值的 1%、中=5%、高=20%，并对微型股做下限保护）
- 每档给出 `first_year_focus`、`realistic_3_year_reach`、`recommended_angle`（正面/绕开）
- 这些是**规则推断**，不是 LLM 生成

**改动文件**：`analyzer/fundamental.py`

### 1.3 待验证假设的行业化裁剪

当前 `assumptions_to_verify`（425-433 行）是七条通用假设，对所有公司一视同仁。改为按 `business_model` / `sector` 加权：

- 平台公司 → 提升"网络效应是否真实""双边留存"权重
- 基础设施/资源型 → 提升"产能周期""监管/牌照"权重
- 产品公司 → 提升"客户集中度""切换成本"权重
- 不删除通用假设，而是给每条加 `priority` 字段（high/medium/low）

**改动文件**：`analyzer/fundamental.py`

### 1.4 结论分类的边界条件细化

当前 `classification`（506-514 行）三分类逻辑较粗。补充：

- 增加"周期性公司"识别：当 `operating_margin` 历史波动大（若 fundamentals 含多年数据）或属于周期行业（energy/semiconductor/commodity）时，`classification` 附带 `cyclical_caveat` 说明
- `fragility_signals` 增加"同业相对估值"信号（若同行 PE 可得）

**改动文件**：`analyzer/fundamental.py`

### 1.5 报告渲染对齐新增字段

`_format_moat_stress_test`（report_generator.py:1095）需要渲染 1.1-1.4 新增的区块：

- `peer_relative_strength` → 新增 `#### 同行相对强弱` 小节
- `attack_budget_tiers` → 新增 `#### 竞争对手攻击模拟（三档预算）` 小节
- `assumptions_to_verify` 的 `priority` → 在已有渲染里加优先级标签
- `cyclical_caveat` → 并入最终判断行

**改动文件**：`analyzer/report_generator.py`

### 1.6 测试

- 扩展 `tests/test_report_generator.py:318` 的测试夹具，覆盖新字段渲染
- 新增 `tests/test_moat_stress_test.py`：单元测试 `build_moat_stress_test` 的同行对比降级、预算量级推断、行业化假设优先级
- 保持现有测试全绿（夹具新增字段不破坏旧断言）

**改动文件**：`tests/test_report_generator.py`、新增 `tests/test_moat_stress_test.py`

### 阶段一交付标准

- [ ] `build_moat_stress_test` 产出包含 `peer_relative_strength`、`attack_budget_tiers`、带 `priority` 的 `assumptions_to_verify`、`cyclical_caveat`（按需）
- [ ] peer 字段缺失时所有同行对比安全降级，不抛异常
- [ ] 报告渲染新增对应小节，且在数据缺失时不产生空标题
- [ ] 全部测试通过，含新增测试
- [ ] 用一个真实样本（建议 MU.US 或现有 fixture 里的标的）跑完整管线，人工确认信息密度提升

---

## 阶段二：LLM 叙事层（默认关闭，flag 开启）

**前提**：阶段一交付后，用 3-5 个真实样本评估脚手架质量。若确认"结构化结论不够、需要八段式叙事长文"才启动。

### 边界

- 新增 `analyzer/llm_narrative.py`，**不修改** `build_moat_stress_test` 的确定性产出
- 引入 LLM client 抽象层（`analyzer/llm_client.py`），支持 mock，便于离线测试
- 通过环境变量 `INSIGHT_LLM_ENABLED=1` 或 CLI flag 开启，默认关闭
- 开启时：把阶段一的确定性事实包 + prompt 喂给 LLM，产出八段式长文，写入 `moat_stress_test.narrative`
- 关闭时：完全不影响现有流程，`narrative` 字段不存在

### 风险点（阶段二启动前需决策）

- LLM 产出不可复现 → 测试如何断言（建议只测结构不测内容）
- 成本/延迟 → 是否缓存结果到本地
- 失败降级 → LLM 超时/报错时回退到纯脚手架

---

## 阶段三：prompt 参数化 + 渲染打磨

- prompt 模板的 `【金额】`/`【3-10 年】` 占位符改为从 `subject` 上下文填充
- 报告增加"如何使用此 prompt"指引区块（引导用户把 prompt + 事实包复制到外部 LLM）
- Obsidian 章节模板（`skills/stock-research-cockpit/references/`）与报告章节对齐
- 文档更新（README 中 moat stress test 行的描述补全）

---

## 不做的事（YAGNI）

- 不在阶段一引入任何 LLM 依赖
- 不重写 `FundamentalAnalyzer` 的护城河六维评分（`_assess_moat`），它与 `build_moat_stress_test` 是互补的两套产出，阶段一只强化后者
- 不动 `data/supply_chain.py` 的产业链逻辑（它已经有独立的产出，通过 `fundamentals.supply_chain` 被脚手架消费）
- 不引入新的外部数据源（如同行财务 API）——只用 peers 列表里**已经存在**的字段，缺失即降级

---

## 阶段一样本评估发现的独立工作项（2026-06-16）

用 4 支跨市场股票（amkr.us 美股 / 01060 港股 / 603906 A股 / mraay.us 日股ADR）跑完整管线后，发现以下问题。它们**独立于阶段一**，是既有的数据源/逻辑缺陷，记录为单独待办，不阻塞阶段一交付。

### 独立工作项 A：`_infer_business_model` 关键词匹配过宽

- **现象**：AMKR（艾克尔，半导体封测代工）被归类为"平台公司"，实为重资产封测制造（应为"基础设施公司"）
- **根因**：`analyzer/fundamental.py` 的 `_infer_business_model` 用子串匹配，business_summary 里的 "platform data storage" 和 "networking" 命中了平台型关键词（`platform`/`network`）
- **影响**：导致 AMKR 的 `assumptions_to_verify` 优先级失真——供应链卡位被压成 low，但 AMKR 恰恰靠产能/封装技术卡位
- **修复方向**：词边界匹配（`\bplatform\b` 而非 `platform` 子串）、或优先用 industry 字段判定、或对 "data platform"/"platform storage" 这类技术语境加负向规则
- **风险**：会牵动其他股票的业务模式归类，需回归测试

### 独立工作项 B：peers 数据全面性富化

- **现象**：4 支样本的 `peer_relative_strength` 全部降级（`available: None`）
- **根因**：`data/correlation.py` 的 `CorrelationAnalyzer.SECTOR_PEERS` 预设表覆盖窄，AMKR/01060/603906/MRAAY 均无条目，`find_peers` 返回空列表；即使有 peers，当前产出也只有 `{ticker, correlation, sector}`，不含财务字段
- **影响**：阶段一新增的"同行相对强弱"小节在生产数据下长期不激活，信息密度打折扣
- **解决方向**：用 finance skills 富化——
  - `stock-correlation` skill：用 yfinance 找相关股票（扩展现有 SECTOR_PEERS 逻辑，不再依赖硬编码表）
  - `funda-data` skill 的 REST API（`https://api.funda.ai/v1`，需 `FUNDA_API_KEY`）：补 peer 的 market_cap/gross_margin/revenue_growth/pe_forward 等财务字段
- **设计约束**：富化后的 peers 仍需保持"字段缺失即降级"的契约，`_peer_relative_strength` 已经支持，无需改动

### 阶段一样本评估总体结论

阶段一的三个新字段（三档预算攻击模拟、周期性识别、假设行业化优先级）在 4 支跨市场股票上全部正确工作，降级路径安全可靠。peer_relative_strength 因数据源覆盖问题未激活，但其逻辑本身已通过单元测试验证。当前不迫切进入阶段二（LLM 叙事层），peers 富化（工作项 B）的 ROI 高于 LLM 叙事。
