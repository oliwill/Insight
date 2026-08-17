# 设计文档：飞书远程指令机器人（Feishu Command Bot）

> 状态：✅ 已实现（2026-08-17）
> 日期：2026-08-14（实现完成 2026-08-17）

## 0. 交付物与范围

**实现记录**：`scripts/feishu_bot.py` + `tests/test_feishu_bot.py` 已落地并验证（232 测试全绿）。
实际实现相比本文档的增补：
- 「分析」指令完成后**自动创建飞书文档**并回复链接（`lark-cli docs +create`，需应用开通 `docx:document` 权限）
- 白名单未配置时 bot 回复发送者 open_id 引导（首次运行自助配置）
- 启动时自动清理僵尸订阅进程/残留锁文件，退出时强杀子进程（避免单实例锁残留导致下次启动失败）
- `--test` 模式本地验证指令处理（mock 鉴权+同步执行）
- 前置要求：lark-cli 登录的应用必须与用户消息的 bot 一致（open_id 按应用隔离）；Windows 下 lark-cli 是 npm shim，代码已解析为 `node run.js` 直调避免 cmd 元字符注入

**目标**：把飞书机器人变成**远程工具**——在飞书里发指令 → 本地跑分析 → 飞书回报告，并可选创建飞书文档。

---

## 1. 已确认的可行性（代码/Skill 验证）

| 环节 | 能力 | 位置 |
| --- | --- | --- |
| 收指令 | `lark-cli event +subscribe`：WebSocket 长连接监听消息，支持正则路由 | lark-event skill |
| 回消息 | `lark-cli im` 发送/回复消息 | lark-im skill |
| 建文档 | `lark-cli docs` 从 Markdown 创建飞书文档 | lark-doc skill |
| 本地跑分析 | `run_analysis.py` / `scripts/generate_full_report.py` / `scripts/daily_brief.py` | 本仓库 |
| 现有 bot 模式 | `telegram_bot.py`（/note /get /scan /inbox /task 指令机器人） | 本仓库 |
| CLI 就绪 | `lark-cli version 1.0.0` 已安装 | 本机 |

**核心区别**（与现有每日简报 webhook 相比）：webhook 是**单向推送**（只能发）；要实现"你发指令 → 机器人回复"，必须用**自建应用 + 事件订阅**（`lark-cli event +subscribe` 或自建应用的回调），这需要飞书**自建应用**（不是自定义机器人）。

---

## 2. 架构

```
飞书 App（自建应用）                   本地（Windows/macOS）
┌─────────────┐    WebSocket 长连接    ┌──────────────────────────────┐
│ 你发消息：    │ ◄──────────────────── │ lark-cli event +subscribe    │
│ "分析 MU.US" │                        │    ↓ (正则路由)               │
│              │                        │ feishu_bot.py 指令解析器      │
│              │                        │    ↓                         │
│              │                        │ 本地跑分析（run_analysis /   │
│              │                        │  generate_full_report）      │
│              │                        │    ↓                         │
│ 机器人回消息  │ ◄──────────────────── │ lark-cli im 回复摘要          │
│ 机器人建文档  │ ◄──────────────────── │ lark-cli docs 创建完整报告    │
└─────────────┘                        └──────────────────────────────┘
```

---

## 3. 指令集设计

| 指令 | 动作 | 回复 |
| --- | --- | --- |
| `分析 <代码>` | 跑 `run_analysis.py`（JSON 数据）或 `generate_full_report.py`（完整报告） | 飞书消息回摘要 + 可选建飞书文档 |
| `/get <代码>` | 读 vault 里已有的分析摘要 | 消息回摘要 |
| `/scan` | 触发 Inbox 扫描 | 回扫描结果 |
| `/brief` | 触发每日简报 | 回简报 + 可选建文档 |
| `/note <代码> <内容>` | 写入 Inbox（复用 ingest） | 确认 |
| `help` | 指令帮助 | 指令列表 |

**鉴权**：只接受你自己的 open_id（与 `telegram_bot.py` 的 `is_authorized` 同模式），避免任何人触发本地分析。

---

## 4. 模块设计

### 4.1 新模块 `scripts/feishu_bot.py`

```python
# 主循环：subprocess 跑 lark-cli event +subscribe（NDJSON 输出）
# 每行事件 → 解析（sender open_id / 消息文本）→ is_authorized 校验
# → 指令分发 → 子进程跑分析 → 回消息（lark-cli im）→ 可选建文档（lark-cli docs）

COMMANDS = {
    "分析": cmd_analyze,   # 完整分析
    "get": cmd_get,        # 已有分析摘要
    "scan": cmd_scan,      # Inbox 扫描
    "brief": cmd_brief,    # 每日简报
    "note": cmd_note,      # 写入 Inbox
    "help": cmd_help,
}

def cmd_analyze(code):
    # 1) subprocess: run_analysis.py <code> --json（或 generate_full_report.py）
    # 2) 解析结果 → 摘要文本
    # 3) im 回复摘要
    # 4) 可选: docs 创建飞书文档（完整报告）→ 回复文档链接
```

### 4.2 复用点

- `run_analysis.py` / `scripts/generate_full_report.py` / `scripts/daily_brief.py`：分析执行（无需改动）
- `telegram_bot.py` 的鉴权/指令分发/log 模式：参考
- `notification.notify_brief`：不适用（那是 webhook 单向），bot 用自己的 im 通道

### 4.3 配置（`.env` 新增）

```ini
# 飞书自建应用（机器人远程指令）
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_BOT_ALLOWED_OPEN_ID=ou_xxx    # 你的 open_id（只允许你触发）
```

> lark-cli 用 `lark-cli auth login` 登录（lark-shared skill），bot 身份/用户身份切换用 `--as bot|user`。

---

## 5. 前置条件（需要你先做的，我无法代做）

1. **创建飞书自建应用**：飞书开放平台（open.feishu.cn）→ 创建企业自建应用（应用名如"Insight 分析助手"）。
2. **开通权限**：应用里添加权限——`im:message`（发消息）、`im:message.group_at_msg` / `im:message.p2p_msg`（接收消息）、`docs:document`（建文档）、`im:chat`（可选）。
3. **事件订阅**：应用 → 事件与回调 → 添加事件 `im.message.receive_v1`（收到消息）；订阅方式选 **长连接（WebSocket）**（对应 `lark-cli event +subscribe`，无需公网回调地址）。
4. **发布版本**：自建应用需创建版本并发布（企业自建应用一般无需审核，但需"启用"）。
5. **拿到你的 open_id**：应用发布后，在飞书里发条消息给机器人，用 `lark-cli im +search` 或事件日志拿到你的 open_id 填进 `.env`。
6. **登录 lark-cli**：`lark-cli auth login`（如需）。

---

## 6. 边界情况与降级

| 场景 | 行为 |
| --- | --- |
| 未授权 open_id 发指令 | 忽略并记日志（不回消息，避免暴露） |
| 分析超时（>ANALYSIS_TIMEOUT） | 回"分析超时，稍后重试"，不挂死 |
| lark-cli 事件断线 | 自动重连（订阅命令保持），日志记录 |
| 建文档失败 | 只回消息摘要，不回文档链接 |
| 无 `FEISHU_APP_*` 配置 | bot 启动即退出并提示配置 |

---

## 7. 验收标准与测试

- 手工验收：飞书里给机器人发 `分析 MU.US` → 收到消息摘要；发 `help` → 指令列表；发未授权用户消息 → 无响应。
- `tests/test_feishu_bot.py`（新，mock lark-cli 输出）：指令解析、鉴权拦截、`cmd_analyze` 子进程调用、摘要截断。
- 不回归：现有 219 测试全过。

---

## 8. 明确假设与默认选择

| 决策点 | 默认选择 | 理由 |
| --- | --- | --- |
| 收指令方式 | 自建应用 + `lark-cli event +subscribe`（WebSocket） | 无需公网服务器/回调，纯本地 |
| 鉴权 | 白名单 open_id（同 telegram_bot 模式） | 防他人触发本地分析 |
| 分析执行 | 子进程复用现有脚本 | 不改动分析主链路，隔离超时 |
| 文档创建 | `lark-cli docs` 从报告 Markdown 建 | 复用 lark-doc skill，零新依赖 |
| 部署 | `scripts/windows/` 计划任务或常驻进程 | 与现有调度一致 |

**实施顺序建议**（审阅通过后）：前置应用配置 → `scripts/feishu_bot.py` → 鉴权与指令分发 → 分析/文档动作 → 测试 → 接入常驻调度。

---

## 9. 参考

- lark 相关 skill：`lark-shared`（认证）、`lark-im`（收发消息）、`lark-doc`（建文档）、`lark-event`（事件订阅）
- 现有机器人：`telegram_bot.py`（指令模式参考）
- 分析入口：`run_analysis.py` / `scripts/generate_full_report.py` / `scripts/daily_brief.py`
