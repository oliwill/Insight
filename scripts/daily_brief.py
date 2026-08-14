#!/usr/bin/env python3
"""
每日关注简报（Daily Brief）

按「分析时间线」频次挑出近 N 天分析最频繁的 top-K 股票，把它们的近期分析 +
近期文章压成一份简短 brief，推送（飞书为主）并沉淀到 Obsidian。

用法:
    python scripts/daily_brief.py            # 生成并落盘，不推送
    python scripts/daily_brief.py --notify   # 生成 + 推送（飞书/webhook）
    python scripts/daily_brief.py --json     # 输出 JSON 结果（供 scheduler 解析）

被 scheduler.py 调用（默认每日 9:00）:
    SCHEDULE_BRIEF=0 9 * * *
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import Config
from memory.manager import MemoryManager
from input.brief_summarizer import summarize_brief, deterministic_template
from notification import notify_brief

# 非个股 wiki 文件（跳过）
_SKIP_STEMS = {"index", "log"}


def _extract_section(wiki_text: str, section_name: str) -> str:
    """从 wiki 全文里截取某个 `## section` 的内容（与 memory/manager 逻辑一致）。"""
    pattern = rf"^##\s+{re.escape(section_name)}\s*$"
    m = re.search(pattern, wiki_text, flags=re.MULTILINE)
    if not m:
        return ""
    start = wiki_text.find("\n", m.start()) + 1
    nxt = re.search(r"^##[^\n#]", wiki_text[start:], flags=re.MULTILINE)
    end = start + nxt.start() if nxt else len(wiki_text)
    return wiki_text[start:end].strip()


def _parse_title(wiki_text: str) -> tuple[str, str]:
    """解析 H1 `# 名称 (CODE)` → (name, code)。"""
    m = re.search(r"^#\s+(.+?)\s*\(([^)]+)\)", wiki_text, flags=re.MULTILINE)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", ""


def _latest_timeline(wiki_text: str) -> dict:
    """从「分析时间线」段解析最近一条：research / timing / view。"""
    timeline = _extract_section(wiki_text, "分析时间线")
    if not timeline or timeline.startswith("（暂无"):
        return {}
    blocks = [b.strip() for b in re.split(r"\n(?=-\s\*\*)", timeline) if b.strip()]
    if not blocks:
        return {}
    last = blocks[-1]
    first_line = last.split("\n", 1)[0]
    m = re.search(r"Research:\s*([\d.]+)/100", first_line)
    t = re.search(r"Timing:\s*([A-Za-z]+)", first_line)
    v = re.search(r"核心观点:\s*(.+)", last)
    return {
        "research": m.group(1) if m else None,
        "timing": t.group(1) if t else None,
        "view": v.group(1).strip() if v else "",
    }


def pick_top_stocks(days: int, top_n: int) -> list[tuple[str, str, int]]:
    """按近 `days` 天「分析时间线」频次排序，返回 [(code, name, count)]。"""
    wiki_dir = Config.get_wiki_dir()
    if not wiki_dir.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days)
    scored = []
    for f in wiki_dir.glob("*.md"):
        stem = f.stem
        if stem in _SKIP_STEMS or stem.startswith(("复盘_", "简报_")):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        name, code = _parse_title(text)
        if not code:
            code = stem  # 兜底：用文件名 stem
        timeline = _extract_section(text, "分析时间线")
        count = 0
        for m in re.finditer(r"\*\*(\d{4}-\d{2}-\d{2})", timeline):
            try:
                d = datetime.strptime(m.group(1), "%Y-%m-%d")
            except ValueError:
                continue
            if d >= cutoff:
                count += 1
        if count > 0:
            scored.append((code, name or code, count))

    scored.sort(key=lambda x: (-x[2], x[0]))
    return scored[:top_n]


_STATE_LABEL = {"Ready": "可关注", "Wait": "观望", "Watch": "观察", "Avoid": "回避"}

_DIM_SHORT = {
    "行业/TAM": "行业",
    "护城河": "护城河",
    "增长质量": "增长",
    "估值": "估值",
    "团队/治理": "团队",
}


def _parse_five_dimensions(wiki_text: str) -> tuple[dict, str]:
    """解析「五维打分」表格 → ({"行业": "5.6", ...}, 综合verdict)。"""
    section = _extract_section(wiki_text, "五维打分")
    dims = {}
    verdict = ""
    for line in section.split("\n"):
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip().strip("*") for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        dim = cells[0]
        if dim == "维度":
            continue
        if dim == "综合":
            verdict = cells[5]
        else:
            dims[_DIM_SHORT.get(dim, dim)] = cells[2]
    return dims, verdict


def _first_bullet(section: str, subsection: str) -> str:
    """取 `### {subsection}` 下的第一条 bullet。"""
    m = re.search(rf"###\s*{re.escape(subsection)}\s*\n((?:\s*[-*]\s*.+\n?)+)", section)
    if not m:
        return ""
    lines = [
        ln.strip().lstrip("-* ").strip()
        for ln in m.group(1).split("\n")
        if ln.strip().startswith(("-", "*"))
    ]
    return lines[0] if lines else ""


def _parse_timing(wiki_text: str) -> dict:
    """解析「交易时机状态」段 → {state, entry, invalidation}。"""
    section = _extract_section(wiki_text, "交易时机状态")
    state = ""
    m = re.search(r"状态：\**([A-Za-z]+)\**", section)
    if m:
        state = m.group(1)
    return {
        "state": state,
        "entry": _first_bullet(section, "触发条件"),
        "invalidation": _first_bullet(section, "失效条件"),
    }


def _material_summary(filepath: str) -> str:
    """读材料文件的 `## 摘要` 段（不读 ## 原文），压成一行。"""
    if not filepath:
        return ""
    try:
        text = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    summary = _extract_section(text, "摘要")
    return re.sub(r"\s+", " ", summary).strip()[:100]


def _currency_symbol(code: str) -> str:
    """简报展示用货币符号（A股¥ / 港股HK$ / 美股$）。"""
    if code.endswith(".HK"):
        return "HK$"
    if code.endswith(".US"):
        return "$"
    return "¥"


def _normalize_money(text: str, code: str) -> str:
    """把文本里的裸 $ 替换为正确货币符号（兼容旧 wiki 的 $ 残留，不碰 HK$）。"""
    cur = _currency_symbol(code)
    if cur == "$" or not text:
        return text
    return re.sub(r"(?<![A-Za-z])\$", cur, text)


def _parse_target(wiki_text: str, code: str) -> str:
    """从「综合评估」综合行提取分析师目标价 → "¥72.50 vs 当前 ¥77.48（潜在 -6.4%）"。"""
    section = _extract_section(wiki_text, "综合评估")
    m = re.search(
        r"分析师目标价\s*[¥$]?\s*([\d.]+)\s*vs\s*当前\s*[¥$]?\s*([\d.]+)\s*[^0-9]*([+-][\d.]+)%",
        section,
    )
    if not m:
        return ""
    cur = _currency_symbol(code)
    return f"{cur}{m.group(1)} vs 当前 {cur}{m.group(2)}（潜在 {m.group(3)}%）"


def collect(mm: MemoryManager, code: str, name: str, count: int) -> dict:
    """收集一只股票的近期分析快照 + 近期文章概要。"""
    wiki = mm.get_stock_wiki(code) or ""
    latest = _latest_timeline(wiki)
    dims, verdict = _parse_five_dimensions(wiki)
    timing = _parse_timing(wiki)
    materials = []
    for m in mm.get_materials(code, limit=Config.BRIEF_MATERIALS_LIMIT) or []:
        materials.append(
            {
                "title": m.get("title") or "无标题",
                "source_type": m.get("source_type") or "",
                "timestamp": m.get("timestamp") or "",
                "summary": _material_summary(m.get("filepath", "")),
            }
        )
    return {
        "code": code,
        "name": name,
        "count": count,
        "research": latest.get("research"),
        "verdict": verdict,
        "timing": latest.get("timing") or timing.get("state"),
        "target": _parse_target(wiki, code),
        "dims": dims,
        "entry": _normalize_money(timing.get("entry", ""), code),
        "invalidation": _normalize_money(timing.get("invalidation", ""), code),
        "materials": materials,
    }


def write_brief_note(brief: str, today: str) -> Path:
    """沉淀到 Analysis/简报_YYYYMMDD.md（与推送内容同源）。"""
    wiki_dir = Config.get_wiki_dir()
    wiki_dir.mkdir(parents=True, exist_ok=True)
    path = wiki_dir / f"简报_{today}.md"
    header = f"# 每日关注简报 {today}\n\n> 生成：{datetime.now().strftime('%Y-%m-%d %H:%M')} | 按近{Config.BRIEF_LOOKBACK_DAYS}天分析频次自动生成\n\n"
    path.write_text(header + brief, encoding="utf-8")
    return path


def build_brief() -> dict:
    """主流程：选股 → 收集 → 生成 → 落盘。返回结构化结果（不含发送）。"""
    mm = MemoryManager()
    days = Config.BRIEF_LOOKBACK_DAYS
    top_n = Config.BRIEF_TOP_N

    stocks = pick_top_stocks(days, top_n)
    if not stocks:
        return {
            "success": True,
            "skipped": True,
            "reason": f"近{days}天无分析记录",
            "stocks": 0,
        }

    collected = [collect(mm, code, name, count) for code, name, count in stocks]

    brief = summarize_brief(collected, days) or deterministic_template(collected, days)

    today = datetime.now().strftime("%Y%m%d")
    note_path = write_brief_note(brief, today)

    return {
        "success": True,
        "skipped": False,
        "stocks": len(collected),
        "top": [c["code"] for c in collected],
        "note_path": str(note_path),
        "brief": brief,
    }


def main():
    parser = argparse.ArgumentParser(description="Daily Brief - 每日关注简报")
    parser.add_argument("--notify", action="store_true", help="推送到飞书/webhook")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    try:
        result = build_brief()
    except Exception as e:
        result = {"success": False, "error": str(e)}

    if args.notify and result.get("success") and not result.get("skipped"):
        today = datetime.now().strftime("%Y-%m-%d")
        channel = notify_brief(f"每日关注简报 {today}", result["brief"])
        result["channel"] = channel

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif result.get("success"):
        if result.get("skipped"):
            print(f"跳过：{result['reason']}")
        else:
            note = result.get("note_path", "")
            channel = result.get("channel", "none")
            print(f"简报已生成 {result['stocks']} 只 → {note}（通道: {channel}）")
    else:
        print(f"简报生成失败：{result.get('error')}")

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
