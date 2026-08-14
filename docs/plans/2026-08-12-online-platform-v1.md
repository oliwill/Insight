# 线上化平台 v1 实施计划（2026-08-12）

目标：把单用户 CLI 分析流水线做成多用户网站 —— 用户注册、自选、分析股票、追踪分析历史。

## 已拍板决策（用户确认）

| 决策 | 选择 | 理由 |
|---|---|---|
| 分析引擎 | 确定性 pipeline + LLM 报告增强 | 评分/时机保持确定性（成本可控、可复现）；LLM 只做报告叙事段，失败静默降级 |
| 前端 | Jinja2 + HTMX | CRUD + 长文渲染场景，单进程部署最简单 |
| 部署 | Docker Compose 单机 VPS | 一人可维护，SQLite + 文件卷足够 |
| 部署环境 | 海外 VPS | yfinance 直连无障碍；docker build 验证 + 上线一条龙 |
| LLM 深度 | 维持现状（AI 解读卡片） | 每分析几百 token，失败不影响主报告 |
| 注册策略 | 邀请码制（`INVITE_CODE` 留空则开放） | 零第三方依赖，挡垃圾注册 |
| 追踪深度 | 维持现状（历史列表） | backtest 预测验证待数据积累后再接 |

## Phase 0：文档发现（已完成，代码侦察结论）

### Allowed APIs（复用清单）

| API | 位置 | 用途 |
|---|---|---|
| `generate_analysis(code) -> dict` | `data/analysis_pipeline.py` | 全量数据（基本面/技术/Wyckoff/流动性/期权/供应链/情绪/板块），各阶段失败降级，`_data_sources` 记录来源 |
| `ResearchScoreEngine` | `analyzer/research_score.py` | 五维加权评分（确定性） |
| `TimingEngine` | `analyzer/timing_engine.py` | Ready/Wait/Watch/Avoid 状态机（确定性） |
| `ReportGenerator.generate(stock_code, market_data, research_score, timing_state, evidence)` | `analyzer/report_generator.py:27` | 结构化 Markdown 报告 |
| `ReportQualityEvaluator` | `analyzer/report_quality.py` | 报告结构质检 |
| `MemoryManager` | `memory/manager.py` | wiki 持久化；**模块级路径常量（53-57 行）需参数化** |
| `_stock_wiki_path/_stock_materials_dir/_ensure_dirs` | `memory/utils.py` | 路径函数；**用 Config 全局，需参数化** |
| 图表路径 | `analyzer/report_generator.py:819-838` | `Config.WIKI_BASE_DIR/Charts/{CODE}_wyckoff.png`，需参数化 |
| 分析 9 步主流程 | `scripts/analyze_stock.py:main` | web 分析服务的蓝本（fetch→chart→evidence→score→timing→compare→report→quality→write） |
| 写回核心 | `run_analysis.py:write_analysis_to_obsidian` | 报告/任务写盘 |

### 反模式（禁止）

- 禁止改 `Config` 全局为 contextvar/线程局部切换用户 —— 显式传参
- 禁止给 `generate_analysis` 加 user 参数 —— 数据层保持无用户概念
- 禁止 Python 侧引入 markdown 渲染库 —— 前端 marked.js CDN 渲染
- 禁止 SQLAlchemy/Celery/Redis —— stdlib sqlite3 + 进程内线程池
- 禁止 LLM 进入评分/时机路径 —— LLM 只做报告叙事增强，失败返回确定性文本
- 禁止修改 `generate_analysis` 签名 —— 兼容 CLI/MCP/Telegram

## Phase 1：多用户存储参数化（前置，最大改造）

**What**：`MemoryManager`/`memory.utils`/`ReportGenerator` 图表路径支持 `base_dir` 参数，默认 None → 沿用 Config 全局（CLI/测试零回归）。

**References**：
- `memory/manager.py:53-57`（模块级常量 → 实例属性），方法内引用点：136-188（index/log）、631-634、742-857、930-934（遍历）
- `memory/utils.py:19-52`（`_ensure_dirs`/`_stock_wiki_path`/`_stock_materials_dir` 加 `base_dir=None`）
- `analyzer/report_generator.py:819-838`（`generate` 加 `wiki_base=None`，图表 relpath 基于用户 wiki dir）
- `scripts/analyze_stock.py:95-101`（`generate_wyckoff_chart` 的 `os.getenv('WIKI_BASE_DIR')` → 参数）
- 用户 vault 布局：`data/users/{user_id}/vault/{Analysis,Materials,Charts}/`，`index.md`、`log.md`、`tasks.json` 同根

**Verification**：
1. `python -m pytest tests/test_section_write.py tests/test_dashboard_update.py tests/test_core_scoring.py tests/test_yahoo_symbol.py -v` 全绿（默认行为不变）
2. 新增 `tests/test_memory_manager_multi_user.py`：两个 `base_dir` 分别写 `Analysis/TEM_US.md`，内容互不串扰；默认 `base_dir=None` 时路径等于 Config 全局

**Guards**：保留模块级常量与旧签名；不动 `WIKI_SECTIONS` 顺序（写回契约）。

## Phase 2：SQLite 数据层 + 认证

**What**：users/sessions/watchlists/analysis_jobs/analysis_records 表 + 邮箱密码认证 + session。

**References**：
- `config.py` 增：`WEB_DB_PATH`（默认 `data/web.db`）、`SESSION_TTL_DAYS`（7）、`ANALYSIS_DAILY_QUOTA`（10）
- 新建 `web/db.py`：sqlite3 连接（`PRAGMA journal_mode=WAL`）、迁移、DAO
- 新建 `web/security.py`：`hashlib.pbkdf2_hmac` + 随机盐；`secrets.token_urlsafe(32)` session + DB 存储（可撤销）
- 新建 `web/deps.py`：`get_current_user` FastAPI 依赖

**Verification**：新增 `tests/test_web_auth.py`：注册/重复注册/登录/错密码/登出/session 过期（monkeypatch 时间）。

**Guards**：不用 bcrypt（Windows 编译依赖）、不用 JWT（DB session 可撤销）。密码不落日志。

## Phase 3：分析服务 + worker + LLM 增强

**What**：分析任务执行器（线程池）+ 用户级分析编排 + LLM 叙事增强。

**References**：
- 新建 `web/analysis_service.py`：`run_analysis_job(job)` 复刻 `scripts/analyze_stock.py` 9 步流程，全部走用户 `base_dir`；产出 `{report_md, research_score, timing_state, chart_path, _data_sources, errors}`；写用户 vault + `analysis_records` 表
- 新建 `web/tasks.py`：`ThreadPoolExecutor(max_workers=2)` + `Semaphore(2)`（数据源配额兜底）+ 状态机 `pending→running→succeeded|failed` + `error` 字段 + 180s 任务超时标注
- 新建 `web/llm_client.py`：requests POST `{LLM_BASE_URL}/chat/completions`（DeepSeek 兼容 OpenAI 格式）；prompt 输入确定性数据 → 输出「核心观点/关键判断/主要风险」叙事段；`LLM_API_KEY/LLM_BASE_URL/LLM_MODEL` 配置；20s 超时；失败返回 None → 报告用确定性文本
- 配置：`config.py` 增 LLM_* 项

**Verification**：
- `tests/test_analysis_service.py`：fake pipeline，断言 job 状态迁移、写盘路径、错误降级
- `tests/test_llm_client.py`：mock requests，断言 prompt 结构、超时降级为 None
- `tests/test_analysis_jobs.py`：并发提交 4 个任务，断言 semaphore 串行与状态一致

**Guards**：LLM 不接触评分字段；错误不吞（写 `job.error`）；分析产物路径全部从用户 id 派生。

## Phase 4：FastAPI + Jinja2/HTMX 前端

**What**：应用组装 + 页面 + API。

**References**（routers 参考旧 `web/` pyc 骨架命名：public/stocks/watchlist/timeline/portfolio/jobs/health，源码已删，全新实现）：
- 新建 `web/app.py`（FastAPI 实例、静态挂载、异常处理）、`web/server.py`（uvicorn 入口）
- 新建 `web/routers/auth.py`（注册/登录/登出）、`stocks.py`（搜索/发起分析/详情）、`watchlist.py`（增删查/批量分析）、`jobs.py`（状态轮询）、`timeline.py`（历史列表/详情）
- 新建 `web/ratelimit.py`：登录尝试 IP 限流 + 每用户日配额
- 重写 `web/frontend/`：Jinja2 模板（login/register/watchlist/stock_detail/timeline）+ HTMX + marked.js + Tailwind CDN；`/media/{uid}/{filename}` 路由从用户目录服务图表 PNG（防目录穿越：`Path.resolve()` 必须落在用户目录内）
- 依赖新增到 `requirements.txt`：fastapi、uvicorn、jinja2、python-multipart

**Verification**：
- `tests/test_web_api.py`（TestClient）：注册→登录→加自选→发起分析（fake pipeline）→轮询 job→详情页 200→时间线列表
- `tests/test_media.py`：目录穿越 payload（`../`、绝对路径）返回 403/404
- 浏览器 smoke：`uvicorn web.server:app` → 手动全流程

**Guards**：所有用户数据读取必须过 `get_current_user`；模板转义开启（Jinja2 默认）；不写任何 `.env` 密钥到前端。

## Phase 5：Docker + 部署

**What**：镜像 + compose + 部署清单。

**References**：
- 新建 `Dockerfile`：`python:3.12-slim` + `fonts-noto-cjk`（matplotlib 中文）+ `tzdata`；`pip install -r requirements.txt`
- 新建 `docker-compose.yml`：api 服务 + `./data:/app/data` 卷 + `env_file: .env`
- `.env.example` 增 WEB_DB_PATH/LLM_*/SESSION_TTL_DAYS/ANALYSIS_DAILY_QUOTA
- `docs/runbook.md` 增线上部署章节

**Verification**：`docker compose up -d` → `curl /health` 200 → 注册 → 分析 smoke → 重启容器数据不丢。

**Guards**：`.env` 不提交；容器非 root 用户运行（可选加固）；yfinance 可达性检查（部署在海外 VPS 则无碍；国内 VPS 需在 runbook 注明代理方案）。

## Phase 6：总验证

1. `python -m pytest tests/ -v` 全绿（含新增 web 测试）
2. CLI 回归：`python scripts/analyze_stock.py HIMS.US`（默认路径行为不变）
3. write-smoke 契约：`scripts/windows/run_write_smoke_examples.ps1`（如可跑）
4. `docker compose` 端到端 smoke 清单（注册→自选→分析→追踪→重启保数据）

## 风险与对策

| 风险 | 对策 |
|---|---|
| 多用户共享数据源配额（yfinance 限流、SerpAPI/NewsAPI key） | worker semaphore(2) + 每用户日配额 10 次 |
| 旧 `web/` 源码已删、git 未跟踪 | 全新实现，pyc 骨架仅作设计参考 |
| matplotlib 中文在 slim 镜像缺字体 | Dockerfile 装 fonts-noto-cjk |
| LLM token 成本 | 每用户配额内开关控制；失败静默降级确定性文本 |
| 分析任务重（30s+） | 线程池 + job 表 + 前端 htmx 轮询，不做 HTTP 同步等待 |
