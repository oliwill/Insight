#!/usr/bin/env python3
"""
飞书远程指令机器人 —— lark-cli 事件订阅 + 本地分析

在飞书里给机器人发指令 → 本地执行 → 飞书回复摘要（可选创建飞书文档）。

用法:
    python scripts/feishu_bot.py              # 前台常驻监听（Ctrl+C 退出）
    python scripts/feishu_bot.py --test "分析 MU.US"   # 本地测指令处理（不连飞书）

.env:
    FEISHU_BOT_ALLOWED_OPEN_ID=ou_xxx    # 唯一允许触发的 open_id（白名单）
    FEISHU_BOT_CMD_PREFIX=/                # 可选，指令前缀（默认 / 或自然语言"分析"）
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 先加载 .env（config.py 是懒加载的，这里显式读，否则下方 getenv 拿到空）
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_DIR / ".env")
except ImportError:
    pass

_ALLOWED_OPEN_ID = os.getenv("FEISHU_BOT_ALLOWED_OPEN_ID", "").strip()

_LARK = "lark-cli"
_EVENT_TYPES = "im.message.receive_v1"


# ---------- 工具 ----------


def _run(cmd: list[str], timeout: int = 120) -> str:
    """跑本地命令，返回 stdout（失败返回空串）。"""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=PROJECT_DIR,
        )
        return (r.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"[ERR] {e}"


def _lark_prefix() -> list[str]:
    """解析 lark-cli 真实可执行路径（npm shim → node 脚本），避免 shell=True。"""
    import shutil

    try:
        exe = shutil.which("lark-cli")
    except Exception:
        exe = None
    if not exe:
        return ["lark-cli"]
    p = Path(exe)
    if p.suffix.lower() == ".cmd":
        # npm 全局 shim: node "<dir>\node_modules\@larksuite\cli\scripts\run.js" %*
        js = p.parent / "node_modules" / "@larksuite" / "cli" / "scripts" / "run.js"
        if js.exists():
            return ["node", str(js)]
    return [str(p)]


def _lark_run(args: list[str], timeout: int = 60) -> str:
    """跑 lark-cli（无 shell，避免 cmd 元字符注入）。"""
    try:
        r = subprocess.run(
            _lark_prefix() + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=PROJECT_DIR,
        )
        return (r.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"[ERR] {e}"


def _lark_im_reply(message_id: str, text: str) -> None:
    """用 bot 身份回复消息（文本）。"""
    _lark_run(
        ["im", "+messages-reply", "--message-id", message_id, "--text", text[:3800]]
    )


def _lark_im_send(open_id: str, text: str) -> None:
    """给用户发一条新消息（文本）。"""
    _lark_run(["im", "+messages-send", "--user-id", open_id, "--text", text[:3800]])


def _lark_docs_create(title: str, markdown: str) -> str | None:
    """用 lark-cli 从 Markdown 创建飞书文档，返回文档 URL（失败返回 None）。"""
    out = _lark_run(
        ["docs", "+create", "--title", title, "--markdown", markdown], timeout=60
    )
    try:
        d = json.loads(out)
        doc_id = d.get("doc_id") or (d.get("data") or {}).get("doc_id") or ""
        if doc_id:
            return f"https://feishu.cn/docx/{doc_id}"
    except Exception:
        pass
    return None


def is_authorized(open_id: str) -> bool:
    return bool(_ALLOWED_OPEN_ID) and open_id == _ALLOWED_OPEN_ID


def extract_text(content_raw: str) -> str:
    """事件 content 字段是 JSON 字符串，取 text。"""
    try:
        d = json.loads(content_raw)
        if isinstance(d, dict):
            return str(d.get("text", ""))
        return str(d)
    except Exception:
        return str(content_raw)


# ---------- 指令实现 ----------

HELP_TEXT = """🤖 Insight 分析助手指令：
📊 分析 <代码> — 完整分析（如：分析 MU.US / 分析 00700.HK / 分析 600519.SH）
📋 /get <代码> — 读取 vault 已有分析摘要
📬 /brief — 生成每日关注简报
🔄 /scan — 扫描 Inbox
📝 /note <代码> <内容> — 写入笔记到 Inbox
❓ help — 帮助"""


def _ccy(code: str) -> str:
    if code.upper().endswith(".HK"):
        return "HK$"
    if code.upper().endswith(".US"):
        return "$"
    return "¥"


def _pct(v):
    """小数→百分比显示；已是百分比原样。"""
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f * 100:g}%" if abs(f) <= 1 else f"{f:g}%"


def _build_report_markdown(md: dict, research, timing, code: str) -> str:
    """从 market_data 生成完整分析报告 Markdown（供飞书文档）。"""
    info = md.get("stock_info", {}) or {}
    fund = md.get("fundamentals", {}) or {}
    wk = md.get("wyckoff", {}) or {}
    vp = md.get("volume_profile", {}) or {}
    dc = md.get("dow_channel", {}) or {}
    fb = md.get("force_balance", {}) or {}
    mtf = md.get("multi_timeframe", {}) or {}
    cur = _ccy(code)
    name = info.get("name") or code
    price = info.get("price")

    def _num(v, suffix="", default="—"):
        if v is None:
            return default
        try:
            f = float(v)
        except (TypeError, ValueError):
            return str(v)
        return f"{f:g}{suffix}"

    lines = [f"# {name}（{code}）分析报告", ""]
    lines.append(f"> 生成：{datetime.now():%Y-%m-%d %H:%M} | 数据：Insight 分析流水线")
    lines.append("")

    lines.append("## 核心结论")
    lines.append(
        f"- **Research**：{research.total_adjusted_score:.1f}/100（{research.verdict}）"
    )
    lines.append(f"- **Timing**：{timing.state}")
    target = fund.get("target_mean_price")
    if target and price:
        pot = (target / price - 1) * 100
        lines.append(f"- **目标价**：{cur}{float(target):g}（潜在 {pot:+.1f}%）")
    if price:
        lines.append(f"- **现价**：{cur}{float(price):g}")
    lines.append("")

    mcap = fund.get("market_cap")
    rows = [
        ("PE(TTM)", _num(fund.get("pe_ttm"))),
        ("PE(Forward)", _num(fund.get("pe_forward"))),
        ("PB", _num(fund.get("pb"))),
        ("毛利率", _pct(fund.get("gross_margin"))),
        ("ROE", _pct(fund.get("roe"))),
        ("市值", _num(mcap / 1e8 if mcap else None, "亿")),
    ]
    rev_g = fund.get("revenue_growth")
    if rev_g is not None:
        try:
            from data.constants import normalize_growth_rate

            g = normalize_growth_rate(rev_g)
            rows.append(("营收增速", f"{g:+.1f}%" if g is not None else "—"))
        except Exception:
            pass

    lines.append("## 基本面")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    for k, v in rows:
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("## 技术面")
    lines.append(f"- Wyckoff：{wk.get('phase', '—')}")
    lines.append(f"- 成交量形态：{vp.get('regime', '—')}")
    lines.append(
        f"- 道氏通道：{dc.get('channel_direction', '—')} / 颈线 {dc.get('neckline_signal', '—')}"
    )
    lines.append(f"- 多空博弈：{fb.get('bull_bear_state', '—')}")
    lines.append(f"- 多时间框架：{mtf.get('alignment', '—')}")
    lines.append("")

    lines.append("## 免责声明")
    lines.append("本报告由 Insight 全自动生成，仅供研究参考，不构成投资建议。")
    return "\n".join(lines)


def cmd_analyze(code: str) -> str:
    """进程内完整分析：数据 + 五维打分 + 时机状态 + 可选建飞书文档。"""
    try:
        from data.analysis_pipeline import generate_analysis
        from analyzer.research_score import ResearchScoreEngine
        from analyzer.timing_engine import TimingEngine
    except ImportError as e:
        return f"❌ 无法加载分析引擎：{e}"

    md = generate_analysis(code)
    if not md or md.get("stock_info_error"):
        return f"❌ {code} 分析失败：{md.get('stock_info_error', '数据不可用')}"

    info = md.get("stock_info", {}) or {}
    fund = md.get("fundamentals", {}) or {}
    wk = md.get("wyckoff", {}) or {}
    name = info.get("name") or code
    price = info.get("price")
    cur = _ccy(code)

    try:
        research = ResearchScoreEngine().score(md, [])
        timing = TimingEngine().analyze(
            md, research_score=research.total_adjusted_score
        )
    except Exception as e:
        return f"❌ 评分失败：{e}"

    lines = [f"📊 {name}（{code}）"]
    if price:
        lines.append(f"   价格：{cur}{price:g}")
    lines.append(
        f"   Research {research.total_adjusted_score:.1f}/100（{research.verdict}）｜ Timing {timing.state}"
    )
    target = fund.get("target_mean_price")
    if target and price:
        pot = (target / price - 1) * 100
        lines.append(f"   🎯 目标价：{cur}{target:g}（潜在 {pot:+.1f}%）")
    pe = fund.get("pe_ttm") or fund.get("pe_forward")
    rev_g = fund.get("revenue_growth")
    if pe:
        try:
            lines.append(f"   PE：{float(pe):.1f}")
        except (TypeError, ValueError):
            pass
    if rev_g is not None:
        try:
            from data.constants import normalize_growth_rate

            g = normalize_growth_rate(rev_g)
            if g is not None:
                lines.append(f"   营收增速：{g:+.1f}%")
        except Exception:
            pass
    wk_phase = wk.get("phase")
    if wk_phase:
        lines.append(f"   Wyckoff：{wk_phase}")

    summary = "\n".join(lines)
    # 建飞书文档（失败静默，不影响摘要回复）
    try:
        doc_url = _lark_docs_create(
            f"{name}（{code}）分析报告",
            _build_report_markdown(md, research, timing, code),
        )
        if doc_url:
            summary += f"\n\n📄 完整报告：{doc_url}"
    except Exception:
        pass
    return summary


def cmd_get(code: str) -> str:
    """读 vault 已有分析（复用 daily_brief 的 collect 逻辑）。"""
    try:
        from memory.manager import MemoryManager
        from scripts.daily_brief import collect
    except ImportError as e:
        return f"❌ {e}"
    mm = MemoryManager()
    wiki = mm.get_stock_wiki(code)
    if not wiki:
        return f"❌ vault 中无 {code} 的分析记录，试试「分析 {code}」"
    c = collect(mm, code, code, 1)
    lines = [f"📋 {c['name']}（{c['code']}）"]
    lines.append(
        f"   Research {c['research'] or 'N/A'}/100（{c['verdict'] or '—'}）｜ Timing {c['timing'] or 'N/A'}"
    )
    if c.get("target"):
        lines.append(f"   🎯 {c['target']}")
    dims = c.get("dims") or {}
    if dims:
        lines.append("   " + " ｜ ".join(f"{k} {v}" for k, v in dims.items()))
    if c.get("entry"):
        lines.append(f"   触发：{c['entry']}")
    if c.get("invalidation"):
        lines.append(f"   警戒：{c['invalidation']}")
    return "\n".join(lines)


def cmd_brief() -> str:
    out = _run([sys.executable, "scripts/daily_brief.py", "--json"], timeout=300)
    try:
        d = json.loads(out)
    except Exception:
        return "❌ 简报生成失败"
    if d.get("skipped"):
        return d.get("reason", "近7天无分析")
    brief = d.get("brief", "")
    return f"📬 每日关注简报\n{brief[:3500]}" if brief else "❌ 简报为空"


def cmd_scan() -> str:
    out = _run(
        [sys.executable, "scripts/scan_inbox.py", "--dry-run", "--json"], timeout=120
    )
    try:
        d = json.loads(out)
        n = d.get("pending_count", d.get("count", "?"))
        return f"🔄 Inbox 待处理：{n} 条"
    except Exception:
        return f"🔄 Inbox 扫描完成\n{out[:1500]}"


def cmd_note(code: str, content: str) -> str:
    try:
        from input.ingest import MaterialInput

        path = MaterialInput().ingest(
            content=content,
            title=f"飞书笔记 {code}",
            stock_code=code,
            source_type="feishu_bot",
        )
        return f"✅ 已写入 Inbox：{path}"
    except Exception as e:
        return f"❌ 写入失败：{e}"


def _spawn(target) -> None:
    """后台线程执行（长耗时指令不阻塞事件循环）。测试时可替换为同步执行。"""
    threading.Thread(target=target, daemon=True).start()


def dispatch(text: str, open_id: str, message_id: str) -> None:
    """处理一条消息：校验 → 分发 → 回复。"""
    if not _ALLOWED_OPEN_ID:
        # 首次运行引导：未配置白名单时，告诉发送者其 open_id（供写入 .env）
        _lark_im_reply(
            message_id,
            f"⚙️ Insight 助手尚未配置白名单。你的 open_id 是 `{open_id}`，\n"
            f"请在 .env 中设置 FEISHU_BOT_ALLOWED_OPEN_ID={open_id} 后重启 bot。",
        )
        return
    if not is_authorized(open_id):
        return  # 非白名单：忽略（不回消息，防暴露）
    text = text.strip()
    if not text:
        return

    low = text.lower()
    if low in {"help", "帮助", "指令", "/help"}:
        _lark_im_reply(message_id, HELP_TEXT)
        return

    m = re.match(r"^(分析|analyse)\s+([A-Za-z0-9.\-]+)", text, re.IGNORECASE)
    if m:
        code = m.group(2)
        _lark_im_reply(message_id, f"⏳ 正在分析 {code}，请稍候（约 30-60s）…")
        _spawn(lambda: _lark_im_reply(message_id, cmd_analyze(code)))
        return

    m = re.match(r"^/get\s+([A-Za-z0-9.\-]+)", low)
    if m:
        _spawn(lambda: _lark_im_reply(message_id, cmd_get(m.group(1))))
        return

    if low.startswith("/brief"):
        _spawn(lambda: _lark_im_reply(message_id, cmd_brief()))
        return

    if low.startswith("/scan"):
        _spawn(lambda: _lark_im_reply(message_id, cmd_scan()))
        return

    m = re.match(r"^/note\s+([A-Za-z0-9.\-]+)\s+(.+)", text, re.DOTALL)
    if m:
        _spawn(lambda: _lark_im_reply(message_id, cmd_note(m.group(1), m.group(2))))
        return

    _lark_im_reply(message_id, "❓ 无法识别的指令，发送 help 查看可用指令。")


# ---------- 事件循环 ----------


def _kill_stale_subscribers() -> None:
    """杀掉残留的 lark-cli 订阅进程 + 清理残留锁文件（僵尸进程会占单实例锁）。"""
    try:
        if os.name == "nt":
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.CommandLine -match 'larksuite.*run\\.js' -and "
                    "$_.CommandLine -match 'subscribe' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
        else:
            subprocess.run(
                ["pkill", "-f", "event.*+subscribe"], capture_output=True, timeout=10
            )
    except Exception:
        pass
    # 清理残留锁文件（0 字节标记，无持有进程时可安全删）
    lock_dir = Path.home() / ".lark-cli" / "locks"
    if lock_dir.exists():
        for f in lock_dir.glob("*.lock"):
            try:
                f.unlink()
            except OSError:
                pass


def run_event_loop() -> None:
    _kill_stale_subscribers()
    if not _ALLOWED_OPEN_ID:
        print(
            "⚠️  未配置 FEISHU_BOT_ALLOWED_OPEN_ID，bot 将忽略所有消息。请在 .env 填写你的 open_id。"
        )
    print(f"🚀 飞书指令机器人启动（监听 {_EVENT_TYPES}）…")
    proc = subprocess.Popen(
        _lark_prefix()
        + ["event", "+subscribe", "--event-types", _EVENT_TYPES, "--quiet"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=PROJECT_DIR,
    )
    if proc.stdout is None:
        print("❌ 无法读取 lark-cli 输出")
        return
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                # lark-cli 的非 JSON 行（多行错误 JSON 的片段/状态行）忽略
                if "another event +subscribe" in line or '"ok": false' in line:
                    print(f"❌ 事件订阅失败：{line.strip()[:200]}", file=sys.stderr)
                    break
                continue
            # 订阅错误（如单实例锁被占）显式报出，避免用户误以为 bot 没反应
            if not ev.get("ok", True) and ev.get("error"):
                err = ev["error"]
                print(
                    f"❌ 事件订阅失败：{err.get('message', err)}"
                    f"（若为 single-instance 锁，先杀掉旧 bot 进程或删 ~/.lark-cli/locks/ 下的锁文件）",
                    file=sys.stderr,
                )
                break
            if ev.get("header", {}).get("event_type") != _EVENT_TYPES:
                continue
            msg = ev.get("event", {}).get("message", {}) or {}
            sender = ev.get("event", {}).get("sender", {}) or {}
            sender_id = sender.get("sender_id", {}) or {}
            open_id = sender_id.get("open_id", "")
            message_id = msg.get("message_id", "")
            content = extract_text(msg.get("content", ""))
            if open_id and message_id and content:
                print(f"[{datetime.now():%H:%M:%S}] {open_id}: {content[:80]}")
                dispatch(content, open_id, message_id)
    finally:
        proc.kill()  # 强杀 node 子进程，避免孤儿占锁


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # 本地测试指令处理（不连飞书，打印结果）
        text = sys.argv[2] if len(sys.argv) > 2 else "help"
        print(dispatch_quiet(text))
        return
    run_event_loop()


def dispatch_quiet(text: str) -> str:
    """测试用：返回指令会回复的内容（mock 鉴权+同步执行，不真正发飞书）。"""
    from unittest.mock import patch

    mod = sys.modules[__name__]
    results = {}

    def fake_reply(message_id, text):
        results["reply"] = text

    with (
        patch.object(mod, "_lark_im_reply", fake_reply),
        patch.object(mod, "is_authorized", lambda oid: True),
        patch.object(mod, "_spawn", lambda target: target()),
    ):
        dispatch(text, "ou_test", "om_test")
    return results.get("reply", "(无回复)")


if __name__ == "__main__":
    main()
