# 设计文档：每日关注简报（Daily Brief）

> 状态：待审阅（本阶段只产出设计文档，不动业务代码）
> 日期：2026-08-14

## 0. 交付物与范围

**本阶段唯一动作**：将本设计文档写入 `docs/daily-brief-design.md`，供审阅后再决定是否实施。

**目标**：每日自动挑出「近 7 天分析最频繁的 3 只股票」，把它们的近期分析 + 近期文章用 LLM 压成一份简短 brief，推送给你（飞书/微信为主），并沉淀到 Obsidian。

---

## 1. 已定决策（本次评审结论）

| 决策点 | 结论 |
| --- | --- |
| 频率 | 每日跑，**9:00**（`SCHEDULE_BRIEF=0 9 * * *`） |
| 选股口径 | **只用「分析时间线」频次**，不碰 web watchlists（易过量） |
| 发送通道 | **飞书 / 微信为主** + Obsidian 沉淀（不是 Telegram） |
| 摘要 | **上 LLM**（复用现有客户端，失败静默降级） |

---

## 2. 现状积木（已确认可复用）

| 环节 | 复用 | 位置 |
| --- | --- | --- |
| 定时任务 | croniter 守护进程 + `SCHEDULE_*` + `DEFAULT_SCHEDULE` | `scheduler.py` |
| 分析频次 | 各 wiki「分析时间线」append-only，条目带 `**YYYY-MM-DD**` 时间戳；已有同样的日期正则 | `memory/manager.py:813` |
| 枚举股票 | 读 `Analysis/` 下各 wiki 文件 | `Config.get_wiki_dir()` |
| 近期文章 | `mm.get_materials(code)`（Materials/{code}/）+ `get_related_materials(code)`（Inbox） | `memory/manager.py:593` |
| 最新分析 | 各 wiki `综合评估`/`五维打分`/`交易时机状态` 段 + 最新时间线 | `memory/manager.py` |
| LLM 摘要 | DeepSeek 兼容 OpenAI Chat Completions、`llm_available()` + 静默降级 | `web/llm_client.py` |
| 落盘 | 参考 `复盘_YYYYMMDD.md` 写入方式 | `scripts/weekly_review.py:103` |
| 通知兜底 | `notify()`（osascript）/ `notify_telegram()` | `notification.py` |

**缺的只有两样**：① 飞书/微信的发送函数；② 一条把上面拼起来的编排脚本。

---

## 3. 数据流

```
每日 9:00 (scheduler._tick 新增 brief 分支)
   │
   ▼
scripts/daily_brief.py
   1. 选股 ── Analysis/*.md 各解析「分析时间线」，数近 7 天条目 → top-3
   2. 收集 ── 每股拉 最新分析段落 + 最新时间线 + 近 N 篇材料标题/摘要
   3. 生成 ── llm_client 压成简短 brief（失败→确定性模板兜底）
   4. 发送 ── 飞书 webhook → 企业微信 webhook → 桌面通知 → 日志
   5. 落盘 ── Analysis/简报_YYYYMMDD.md（与推送内容同源）
```

---

## 4. 核心设计

### 4.1 选股（分析频次 top-3）

```python
def pick_top_stocks(days: int = 7, top_n: int = 3) -> list[tuple[str, int]]:
    for f in (Config.get_wiki_dir() / "*.md").glob:
        排除 index.md / log.md / 复盘_*.md / 简报_*.md
        timeline = 解析「分析时间线」段
        count = len(日期 ∈ [今天-days, 今天] 的条目)
    → 按 count 降序取前 top_n（count=0 的不选）
```

- 复用 `memory/manager.py` 里现成的 `_get_section_content(wiki, "分析时间线")` + `re.findall(r"\*\*(\d{4}-\d{2}-\d{2})", timeline)`。
- **边界**：近 7 天 0 只被分析 → brief 输出「近 7 天无分析记录，跳过」，只写日志，不发推送（避免打扰）。

### 4.2 收集（每股）

```python
def collect(stock_code) -> dict:
    wiki = mm.get_stock_wiki(code)
    return {
        "code": code,
        "name": 从 wiki 标题解析,
        "count": 近 7 天分析时间线条数,
        "research": 最新时间线的 Research 分,
        "timing": 最新时间线的 Timing 状态,
        "view": 最新时间线的「核心观点」,
        "dims": {"行业": ..., "护城河": ..., "增长": ..., "估值": ..., "团队": ...},  # 从「五维打分」表格提取各维度 Adjusted 分
        "verdict": 五维打分综合行的 verdict（如「观察」）,
        "entry": 从「交易时机状态」段提取的第一条触发条件,
        "invalidation": 从「交易时机状态」段提取的第一条失效条件,
        "materials": [{"title", "source_type", "timestamp", "summary"}],  # summary = 材料 ## 摘要 段
    }
```

- 材料只读 `## 摘要` 段，**不读 `## 原文`**（正文留给 evidence 索引链路），保证 brief 收集快、成本低。

### 4.3 生成 brief（LLM + 确定性兜底）

复用 `web/llm_client.py` 的 OpenAI 兼容 POST 模式，新增一个共享函数：

```python
# input/brief_summarizer.py（新）
def summarize_brief(stocks: list[dict], lookback_days: int) -> str | None:
    # 未配置 Config.LLM_API_KEY 或调用失败 → 返回 None（调用方降级为确定性模板）
    # system prompt：你是投资简报助手，把 N 只股票按固定结构压缩成中文日报：
    #   每股含「评分 / 五维打分 / 核心观点 / 相关文章(标题+一句话概要) / 操作(状态+触发+警戒)」。
    #   只用提供的数据，缺的字段写「—」；不编造、不给买卖指令。
```

- **确定性兜底模板**（LLM 失败/未配置时）：

```
📊 今日关注简报 · 2026-08-14（近7天分析频次 Top N）

1️⃣ 甘李药业（SH603087）｜近7天分析 3 次
   评分：Research 52.5/100（观察）｜ Timing Wait
   基本面：行业 5.6 ｜ 护城河 7.4 ｜ 增长 4.4 ｜ 估值 3.5 ｜ 团队 6.0
   🎯 目标价：¥72.50 vs 当前 ¥77.48（潜在 -6.4%）
   相关文章：
     ·《甘李药业 2025 年报关键财务数据（akshare 三表整理）》— 2025营收+33%/归母+86%至11.44亿；2026Q1季度减速
     ·《博凡格鲁肽(GZR18) GLP-1 海外授权公告》— GZR18全球首款双周GLP-1 III期；半年3笔BD出海
   操作：Wait 观望 ｜ 触发：等待 RSI 从过热区回落后再评估 ｜ 警戒：有效跌破 Wyckoff 支撑 $54.89

数据截至：最近分析 2026-08-14 ｜ 全文见 Obsidian [[简报_20260814]]
⚠️ 仅供研究参考，不构成投资建议
```

- **去重共享**：把 `web/llm_client.py` 里的 `requests.post(...chat/completions...)` 抽成 `complete(system, user, max_tokens) -> str | None`，`enhance_summary` 与 `summarize_brief` 共用（向后兼容，不改 `enhance_summary` 对外签名）。

- **字段→数据来源**（全 vault 读，不重新取价）：

| 字段 | 来源 |
| --- | --- |
| 名称/代码/分析次数 | wiki H1 + `分析时间线` |
| 基本面（五维打分） | wiki `五维打分` 表格各维度 Adjusted 分（行业/护城河/增长/估值/团队）+ 综合 verdict |
| 核心观点 | `分析时间线` 最新一条「核心观点」 |
| 文章概要 | 材料文件 `## 摘要` 段 |
| 操作（状态/触发/警戒） | wiki `交易时机状态` 段（Timing + entry/invalidation triggers） |
| 数据时间戳 | `分析时间线` 最新一条日期 |

### 4.4 发送通道（飞书/微信为主）

扩展 `notification.py`，新增两个 webhook 发送器 + 一个通道链，**镜像现有 `notify_telegram` 的 urllib 模式**：

```python
def notify_feishu(title: str, message: str) -> bool:
    # 飞书自定义机器人 webhook：POST https://open.feishu.cn/open-apis/bot/v2/hook/{token}
    # body: {"msg_type": "text", "content": {"text": f"{title}\n{message}"}}
    # 依赖 env: FEISHU_WEBHOOK_URL

def notify_wecom(title: str, message: str) -> bool:
    # 企业微信机器人 webhook：POST https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}
    # body: {"msgtype": "markdown", "markdown": {"content": f"**{title}**\n{message}"}}
    # 依赖 env: WECOM_WEBHOOK_URL

def notify_brief(title: str, message: str) -> str:   # 返回实际使用的通道名
    # 通道链：飞书 → 企业微信 → Telegram(已有) → 桌面通知 → stderr 打印
    # 任一成功即返回；全部未配置/失败则打印日志（永不抛异常）
```

- **微信说明**：个人微信无官方 API，用**企业微信机器人 webhook**（免费、一个 URL、支持 markdown）最省事；文档里注明可用 Server酱/PushPlus 作为替代（同 urllib 模式，改个端点即可）。
- **飞书 markdown 说明**：v1 用 `msg_type: "text"`（简单、够用）；如需富文本再升级 `interactive` 卡片（不在本阶段范围）。
- **决策**：默认优先飞书，你只需在 `.env` 填 `FEISHU_WEBHOOK_URL` 或 `WECOM_WEBHOOK_URL` 之一即可，切换无需改代码。

### 4.5 落盘 Obsidian（沉淀）

- 写 `Analysis/简报_YYYYMMDD.md`（与 `weekly_review` 的 `复盘_YYYYMMDD.md` 同目录约定）。
- 内容 = 推送给你的那段 brief（同源，不另生成）。
- **不追加到 Dashboard**（保持 Dashboard 只读汇总职责，避免与 `update_dashboard` 冲突；如需展示可后续加）。

---

## 5. 新增 / 改动文件清单

| 文件 | 动作 | 内容 |
| --- | --- | --- |
| `scripts/daily_brief.py` | 新增 | 编排：选股→收集→生成→发送→落盘；`--json` / `--notify` 参数 |
| `input/brief_summarizer.py` | 新增 | `summarize_brief()`（LLM）+ `_deterministic_template()` 兜底 |
| `notification.py` | 改动 | 加 `notify_feishu` / `notify_wecom` / `notify_brief` |
| `config.py` | 改动 | 加 `SCHEDULE_BRIEF` / `BRIEF_LOOKBACK_DAYS` / `BRIEF_TOP_N` / `BRIEF_MATERIALS_LIMIT` / `FEISHU_WEBHOOK_URL` / `WECOM_WEBHOOK_URL` |
| `web/llm_client.py` | 改动（小） | 抽 `complete()` 共享函数，`enhance_summary` 改调用它（对外签名不变） |
| `scheduler.py` | 改动（小） | `DEFAULT_SCHEDULE["brief"]="0 9 * * *"` + `last_runs["brief"]` + `_tick` 分支 + `_task_arguments` 加 `daily_brief.py` |
| `.env.example` | 改动 | 补 `SCHEDULE_BRIEF` / `FEISHU_WEBHOOK_URL` / `WECOM_WEBHOOK_URL` 示例 |
| `memory/manager.py` | 改动（可选） | 加 `list_analysis_frequency(days)` 辅助（或直接在脚本里解析，不强制） |

---

## 6. 配置新增

```ini
# 每日简报
SCHEDULE_BRIEF=0 9 * * *
BRIEF_LOOKBACK_DAYS=7
BRIEF_TOP_N=3
BRIEF_MATERIALS_LIMIT=5
# 通知通道（填一个即可；飞书优先）
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx
```

> 与现有约定一致：`SCHEDULE_*` 的实际默认值放在 `scheduler.py::DEFAULT_SCHEDULE`，`config.py` 只读 env。

---

## 7. 边界情况与降级

| 场景 | 行为 |
| --- | --- |
| 近 7 天无分析 | 只写日志，不发推送 |
| 少于 3 只 | 有几只推几只（≥1 才推送） |
| `LLM_API_KEY` 未配置/超时 | 确定性模板兜底，brief 仍生成 |
| 飞书/微信都未配置 | 回退桌面通知 → stderr 打印 |
| 飞书/微信发送失败 | 降级到下一通道，永不抛异常（`*_error` 记日志） |
| 某只 wiki 无「分析时间线」段 | 跳过该股票 |

---

## 8. 验收标准与测试

- `tests/test_daily_brief.py`（新）：
  1. `pick_top_stocks`：构造 3 个临时 wiki，时间线条数不同 → 正确排序取 top-N、排除 0 计数；
  2. 时间窗口：7 天外的条目不计入；
  3. `_deterministic_template`：无 LLM 时产出非空 brief（含 3 只股票）；
  4. `summarize_brief`：`LLM_API_KEY=None` 时返回 None（不崩）；
  5. `notify_brief`：mock 飞书成功 → 返回 `"feishu"`；全未配置 → 不抛异常、返回 `"log"`；
  6. `collect` 读材料 `## 摘要` 段、不读 `## 原文`；`fundamentals`/`operation` 从 wiki 段解析，缺则「—」。
- 不回归：现有 206 测试通过基线。
- 手工验收：本地跑 `python scripts/daily_brief.py --notify`，Obsidian 出现 `简报_YYYYMMDD.md`，飞书/微信收到同内容推送。

---

## 9. 明确假设与默认选择

| 决策点 | 默认选择 | 理由 |
| --- | --- | --- |
| 调度 | `0 9 * * *`（每日 9:00） | 你已定 |
| 选股 | 分析时间线频次，7 天窗口，top-3 | 你已定，watchlists 排除 |
| 通知主通道 | 飞书 webhook 优先，企业微信次之 | 免费、单 URL、无 OAuth；与现有 urllib 模式一致 |
| 微信实现 | 企业微信机器人 webhook | 个人微信无官方 API |
| 摘要 | LLM 复用 `complete()`，确定性模板兜底 | 你已定；降级兜底符合项目契约 |
| brief 内容 | 详版：每股约 8 行（评分/基本面/观点/文章概要/操作）；材料只读 `## 摘要` 不读 `## 原文` | 你已定；vault-only 零新取价 |
| 落盘 | 独立 `简报_YYYYMMDD.md`，不动 Dashboard | 与 `复盘_*.md` 约定一致，避免职责冲突 |
| 富文本 | v1 用 text/markdown 纯文本 | 够用；飞书 interactive 卡片留作后续增强 |

**实施顺序建议**（审阅通过后）：`config`+`notification` → `input/brief_summarizer` → `scripts/daily_brief` → `scheduler` 接入 → 验收测试 → 补 `.env.example`。
