# 设计文档：Obsidian 证据写入时索引 + 分析时检索（Evidence-at-Ingest）

> 状态：待审阅（本阶段只产出设计文档，不动业务代码）
> 日期：2026-08-14

## 0. 交付物与范围

**本阶段的唯一动作**：将本设计文档写入 `docs/evidence-ingest-architecture.md`，供审阅后再决定是否实施。

**要解决的两个问题**：

1. 笔记随量增长后，若在分析时才对笔记做「读取→理解→判断→总结」，成本线性上升；
2. 当前无法确认分析是否真正参考了存进 Obsidian 的笔记。

---

## 1. 现状事实（已从代码确认）

| 事实 | 位置 | 影响 |
| --- | --- | --- |
| 证据抽取是**纯正则**，无 LLM 参与 | `input/evidence.py::EvidenceExtractor` | 笔记从未被真正「理解」 |
| 每篇材料最多取 3 行、总计 top-30 | `extract()` + `_candidate_lines` | 笔记参与度浅 |
| 分数影响仅 ±0.15/0.35/0.6，多数 `confidence_only`（0 影响） | `research_score.py::_apply_evidence` | 对最终分数影响微弱 |
| 只喂个股目录材料 + Inbox + wiki 先验，**不含行业/宏观/策略类笔记** | `analyze_stock.py` 调 `mm.get_materials(code)` | 跨类目召回缺失 |
| `run_analysis.py` / `data/analysis_pipeline.py` **完全没有接 evidence** | grep 无 evidence 引用 | 两条入口行为不一致 |
| 已有可选 LLM 客户端（DeepSeek 兼容、静默降级） | `config.py` + `web/llm_client.py` | 阶段 B 可零依赖复用 |
| 查询是 `rglob + 子串` 线性扫描 | `search_materials` / `query_by_keyword` | 量大了会变慢，但暂不在热路径 |

**结论**：用户担心的「耗时」尚未发生（因为根本没做理解）；但「是否参考了」的怀疑成立——当前是浅层、不透明、低影响。

---

## 2. 设计原则

1. **写入时刻 vs 分析时刻分离**：昂贵的「理解」在摄入（ingest）时做一次并落盘；分析时只做「检索 + 引用」，O(1)/O(log n)。
2. **溯源优先**：每次分数调整必须带 `note_id + source_path + 维基链接`，报告可回看「哪条笔记、影响了什么、影响多少」。
3. **渐进式、可降级**：正则抽取是**永远在线的确定性兜底**；LLM 摘要是**可选增强**，无 key 或失败时静默回退（沿用 `web/llm_client` 模式）。
4. **资源约束友好**：存储用 stdlib `sqlite3`（单文件、无服务、支持 FTS5）；不引入向量库除非进阶段 C。
5. **不破坏现有契约**：`EvidenceExtractor` 对外 API 保持兼容，内部改为读索引；`_apply_evidence` 语义不变，只增加来源字段。

---

## 3. 目标架构（数据流）

```
写入时刻（ingest，一次性，可慢）                    分析时刻（analyze，每次，要快）
─────────────────────────────────────           ─────────────────────────────
笔记 → EvidenceExtractor（正则 claims）┐
      └→ note_summarizer（LLM，可选）  ├→ claims_store（SQLite，落盘）
                                          │     · claims 表（结构化）
                                          │     · note_tickers 表（跨类目关联）
                                          │     · FTS5 全文索引
                                          ▼
                                   ┌──────────────────┐
                                   │  retrieve(ticker) │← 按 ticker+维度+时间衰减取 top-K
                                   └──────────────────┘
                                          ▼
                              research_score._apply_evidence（带 source 溯源）
                                          ▼
                              报告「参考材料」区（列出用了哪些笔记 + 影响值）
```

---

## 4. 阶段 A：写入时索引 + 全链路溯源（零新依赖）

### 4.1 数据模型（SQLite：`WIKI_BASE_DIR/evidence_index.db`）

```sql
CREATE TABLE IF NOT EXISTS notes (
  note_id     TEXT PRIMARY KEY,          -- 材料文件 id（ingest 已生成 mid）
  path        TEXT NOT NULL,             -- 相对 materials/ 的路径
  title       TEXT,
  source_type TEXT,
  ticker      TEXT,                      -- 主关联股票（可空，category 笔记为空）
  ingested_at TEXT,
  llm_summary TEXT                       -- 阶段 B 才填充，先留空
);

CREATE TABLE IF NOT EXISTS claims (
  claim_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  note_id     TEXT REFERENCES notes(note_id),
  claim       TEXT,                      -- 抽取的断言（<=160 字）
  evidence_type TEXT,                    -- fact/opinion/rumor/counter
  credibility TEXT,
  affected_dimensions TEXT,              -- JSON 数组
  score_impact TEXT,                     -- up/down/confidence_only/watch_only
  created_at  TEXT
);

CREATE TABLE IF NOT EXISTS note_tickers (  -- 阶段 A 关键：跨类目关联
  note_id TEXT,
  ticker  TEXT,                          -- 规范化代码（AAPL.US / 00700.HK / SH603087）
  score   REAL,                          -- 关联强度（命中标题/tag/正文加权）
  PRIMARY KEY (note_id, ticker)
);

CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(claim, content='claims', content_rowid='claim_id');
```

### 4.2 新模块 `memory/claims_store.py`（stdlib sqlite3）

```python
class ClaimsStore:
    def upsert_note(self, note_id, path, title, source_type, ticker, tickers: list[str], claims: list[dict]) -> None
    def retrieve(self, ticker: str, dimensions: list[str] | None = None, limit: int = 20) -> list[dict]
        # 1) note_tickers 精确命中 2) FTS5 全文召回 3) 按 credibility×时间衰减排序
    def list_referenced(self, ticker: str) -> list[dict]   # 供报告「参考材料」区
    def rebuild(self) -> None                                # 扫 materials/ + wiki 重建，幂等
```

### 4.3 改动点

- `input/ingest.py::MaterialInput.ingest()`：写文件后，调用 `ClaimsStore.upsert_note(...)`，把正则 claims + ticker 关联**在写入时落盘**（`note_tickers` 从 tags + 标题 + 正文 ticker 提及推导）。
- `input/evidence.py`：`EvidenceExtractor.extract()` 增加「从 `ClaimsStore` 读索引」路径，避免分析时全文重扫；保留原签名与正则兜底。
- `analyzer/research_score.py::_apply_evidence()`：`EvidenceItem` 增加 `note_id`/`source_path` 字段，每次 delta 的 `adjustment_reason` 附带 `来源：{title}（{wikilink}）`。
- `analyzer/report_generator.py`：新增「## 参考材料」区，列出 `list_referenced(ticker)` 的结果：`| 笔记 | 影响维度 | 分数影响 | 来源链接 |`。
- `scripts/analyze_stock.py`：把 `get_materials` 改成读 `ClaimsStore.retrieve`（个股 + 行业/宏观/策略类关联笔记一起召回）。
- 新增 `scripts/rebuild_evidence_index.py`：从现有 `materials/` 一次性重建索引（幂等）。

### 4.4 时间衰减（写入时即可做）

opinion/technical 类 claim 在 `retrieve` 时乘 `0.5 ** (age_days / 90)`（90 天半衰期）；fact/filing 类不衰减。

---

## 5. 阶段 B：写入时 LLM 摘要 + 分析时检索（复用现有 LLM 客户端）

### 5.1 新模块 `input/note_summarizer.py`（镜像 `web/llm_client.py` 模式）

```python
def summarize_note(title, content, source_type) -> dict | None:
    # 未配置 Config.LLM_API_KEY 或调用失败 → 返回 None（静默降级为正则 claims）
    # 返回 {tickers: [...], dimensions: {...五维}, direction, key_metrics: [...], credibility, time_sensitivity}
```

- 复用 `config.py` 现有 `LLM_API_KEY / LLM_BASE_URL / LLM_MODEL`（DeepSeek 兼容 OpenAI Chat Completions），**零新依赖**。
- 摄入时调用一次，结果写 `notes.llm_summary`；分析时优先读摘要，无摘要则用正则 claims 兜底。
- 把「分析时理解」一次性前置为「写入时理解」，写入成本可缓存、可批量。

### 5.2 分析时检索

`ClaimsStore.retrieve(ticker)` 返回 top-K（默认 20）：ticker 精确命中 + tag 关联 + FTS5 关键词 + LLM 摘要的维度/方向，按 `credibility × 时间衰减` 排序，注入 `research_score`。

---

## 6. 阶段 C：语义检索（可选，触发条件明确）

- 仅当「笔记量 > 数千条 且 关键词/ticker 召回不足」时启用。
- 写入时用本地 `sentence-transformers`（或复用 `LLM_BASE_URL` 的 embedding 端点）算向量，存 `sqlite-vec`。
- 分析时语义相似度 top-K，解决「笔记没写 ticker 但内容相关」的召回。
- **默认不实施**，避免资源约束下过度设计。

---

## 7. 可观测性（回答「是否参考了」的三道保险）

1. **溯源**：`_apply_evidence` 每条 delta 带 `note_id + title + [[wikilink]]`。
2. **报告「参考材料」区**：列出实际用到的笔记与各自影响值。
3. **debug 开关**：`DEBUG_EVIDENCE=1` 时打印「检索到哪些笔记、为什么（命中 ticker/tag/FTS/维度）」。

---

## 8. 迁移与兼容

- **向后兼容**：`EvidenceExtractor.extract()` 签名不变；无索引时自动回退到现有正则全文扫描路径（旧行为）。
- **重建**：`scripts/rebuild_evidence_index.py` 幂等（重复跑结果一致）；对现有 `tags_index.json` 不动，仅新增 `evidence_index.db`。
- **双入口一致**：`run_analysis.py` 的 `data/analysis_pipeline.py` 后续也可接同一 `ClaimsStore.retrieve`（本阶段设计预留接口，不强制改）。

---

## 9. 验收标准与测试

- `tests/test_claims_store.py`（新）：
  1. `ingest()` 写入后，`retrieve(ticker)` 能返回该材料 claims + 溯源字段；
  2. category 笔记打 `半导体` tag 后，`retrieve("MU.US")` 能跨类目召回；
  3. 无 `LLM_API_KEY` 时 ingest 不崩（正则兜底）；
  4. `rebuild()` 幂等（跑两次计数相同）；
  5. 1000 条假笔记下 `retrieve` 延迟不随总量线性增长（走索引）；
- `tests/test_framework_fixes.py` 不回归（206 通过基线）。
- 手工验收：对 `MU.US` / `09988.HK` 各跑一次 `analyze_stock.py`，报告出现「参考材料」区且每条带来源链接。

---

## 10. 明确假设与默认选择

| 决策点 | 默认选择 | 理由 |
| --- | --- | --- |
| 存储 | SQLite（`evidence_index.db`，stdlib） | 单文件、无服务、FTS5、并发安全，优于 JSON |
| 兜底 | 正则 claims 永远在线 | 项目「无外部 LLM 调用不破坏主流程」契约 |
| LLM 摘要 | 复用 `Config.LLM_*` + DeepSeek 兼容 | 已存在，零新依赖 |
| 检索 top-K | 默认 20 | 与现有 `get_materials(limit=20)` 对齐 |
| 时间衰减 | opinion/technical 90 天半衰期，fact 不衰减 | 已在代码注释中预留「需时间衰减」 |
| 阶段 C | 默认不做 | 资源约束，明确触发条件 |
| 迁移 | 一次性 `rebuild_evidence_index.py`，幂等 | 不破坏现有 `tags_index.json` |

**实施顺序建议**（审阅通过后）：阶段 A → 跑验收测试 → 阶段 B（复用 LLM 客户端）→ 阶段 C 视量而定。
