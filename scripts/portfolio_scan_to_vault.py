"""Convert portfolio_scan JSON output into a mobile-friendly Obsidian .md report.

Writes to the vault's Trader/Watchlist/ so remotely-save syncs it to phone.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCAN_JSON = PROJECT_ROOT / "scripts" / "_portfolio_scan_out" / "scan_20260622_190048.json"
VAULT = Path(r"C:\Users\Lzw\Downloads\Documents\obsidian\Lzw\Lzw")
# Post-2026-07 layout is Trader/Watchlist; fall back to legacy 4_Trader/Watchlist if that's what exists.
_legacy = VAULT / "4_Trader" / "Watchlist"
OUT_DIR = (VAULT / "Trader" / "Watchlist") if (VAULT / "Trader").exists() else _legacy


def fmt_pct(x, with_sign=False):
    if x is None:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if with_sign and v > 0:
        return f"+{v:.1f}%"
    return f"{v:.1f}%"


def fmt_price(x):
    if x is None:
        return "—"
    try:
        return f"${float(x):.2f}"
    except (TypeError, ValueError):
        return "—"


def fmt_cap(x):
    if not x:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if v >= 1e12:
        return f"{v/1e12:.2f}T"
    if v >= 1e9:
        return f"{v/1e9:.2f}B"
    if v >= 1e6:
        return f"{v/1e6:.0f}M"
    return f"{v:.0f}"


def phase_emoji(phase):
    if not phase:
        return "❓"
    p = str(phase)
    if "吸筹" in p or "Accumulation" in p:
        return "🟢"
    if "主升" in p or "Markup" in p or "上升趋势" in p:
        return "🚀"
    if "派发" in p or "Distribution" in p:
        return "🔴"
    if "下跌" in p or "Decline" in p:
        return "🔻"
    return "⏸️"


def timing_emoji(state):
    s = str(state or "").lower()
    if s == "ready":
        return "✅ Ready"
    if s == "wait":
        return "⏳ Wait"
    if s == "watch":
        return "👀 Watch"
    if s == "avoid":
        return "🚫 Avoid"
    return state or "—"


def build_report(data):
    rows = sorted(data, key=lambda r: float(r.get("conviction") or 0), reverse=True)
    scan_ts = rows[0].get("ts", "")[:16].replace("T", " ") if rows else ""

    lines = []
    lines.append("---")
    lines.append('title: "📊 持仓组合扫描 — H2 翻倍潜力排序"')
    lines.append("source: Codex")
    lines.append("author: Codex")
    lines.append(f"published: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"created: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(
        'description: "25 支持仓按 conviction 排序，含 Wyckoff 阶段/timing/目标价空间/PSG"'
    )
    lines.append("tags:")
    lines.append("  - portfolio-scan")
    lines.append("  - watchlist")
    lines.append(f"  - scan-{datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"holdings_count: {len(rows)}")
    lines.append(f"scan_time: {scan_ts}")
    lines.append("---")
    lines.append("")
    lines.append("> 📱 **手机端查看提示**：本页已随 remotely-save 自动同步。表格左右滑动可查看完整内容。")
    lines.append("")
    lines.append(f"**扫描时间**：{scan_ts} · **持仓数**：{len(rows)}")
    lines.append("")

    # Top 5 高 conviction
    lines.append("## 🏆 Top 5 高信心持仓")
    lines.append("")
    for i, r in enumerate(rows[:5], 1):
        d = r.get("derived", {}) or {}
        f_ = r.get("fundamentals", {}) or {}
        w = r.get("wyckoff", {}) or {}
        lines.append(f"### {i}. {r['code']} · {r.get('name', '')} — conviction **{r.get('conviction', 0):.1f}**")
        lines.append("")
        lines.append(
            f"- 💰 现价 {fmt_price(r.get('price'))} → 目标 {fmt_price(f_.get('target_mean_price'))}"
            f"（**{fmt_pct(d.get('target_potential_pct')*100, with_sign=True)}** 空间）"
        )
        lines.append(
            f"- 📊 PSG **{d.get('psg', '—')}** · 营收增速 {fmt_pct(d.get('revenue_growth_pct'))}"
            f" · P/S {d.get('ps', '—')}"
        )
        lines.append(
            f"- {phase_emoji(w.get('phase'))} Wyckoff **{w.get('phase', '—')}**"
            f"（支撑 {fmt_price(w.get('support'))} / 阻力 {fmt_price(w.get('resistance'))}）"
        )
        lines.append(
            f"- {timing_emoji(r.get('timing_state'))} · 评分 {r.get('research_score', '—')}"
            f"（{r.get('research_verdict', '')}）"
        )
        reasons = r.get("timing_reasons") or []
        if reasons:
            lines.append(f"- 🧭 时机理由：{' / '.join(reasons)}")
        lines.append("")

    # 完整紧凑表
    lines.append("## 📋 全持仓概览（按 conviction 降序）")
    lines.append("")
    lines.append("| # | 代码 | 名称 | 现价 | 目标空间 | PSG | Wyckoff | Timing | 评分 | 结论 |")
    lines.append("|---|------|------|------|----------|-----|---------|--------|------|------|")
    for i, r in enumerate(rows, 1):
        d = r.get("derived", {}) or {}
        f_ = r.get("fundamentals", {}) or {}
        w = r.get("wyckoff", {}) or {}
        name = (r.get("name") or "")[:10]
        pot = d.get("target_potential_pct")
        pot_str = fmt_pct(pot * 100, with_sign=True) if pot is not None else "—"
        lines.append(
            f"| {i} | {r['code']} | {name} | {fmt_price(r.get('price'))} | "
            f"{pot_str} | {d.get('psg', '—')} | "
            f"{phase_emoji(w.get('phase'))} {w.get('phase', '—')} | "
            f"{timing_emoji(r.get('timing_state'))} | "
            f"{r.get('research_score', '—')} | {r.get('research_verdict', '—')} |"
        )
    lines.append("")

    # 风险/回调位
    lines.append("## ⚠️ 距高点回撤 & 趋势速览")
    lines.append("")
    lines.append("| 代码 | 距高点 | 短期趋势 | 中期趋势 | RSI | 量比 |")
    lines.append("|------|--------|----------|----------|-----|------|")
    for r in rows:
        d = r.get("derived", {}) or {}
        t = r.get("technicals", {}) or {}
        lines.append(
            f"| {r['code']} | {fmt_pct(d.get('pct_from_high'), with_sign=True)} | "
            f"{d.get('trend_short', '—')} | {d.get('trend_mid', '—')} | "
            f"{t.get('rsi_14', '—')} | {t.get('vol_ratio', '—')} |"
        )
    lines.append("")

    # 五维评分汇总
    lines.append("## 📐 五维评分（行业/护城河/增长/估值/团队）")
    lines.append("")
    lines.append("| 代码 | 行业 | 护城河 | 增长 | 估值 | 团队 | 总分 |")
    lines.append("|------|------|--------|------|------|------|------|")
    for r in rows:
        dims = r.get("research_dims") or {}
        lines.append(
            f"| {r['code']} | {dims.get('行业/TAM', '—')} | "
            f"{dims.get('护城河', '—')} | {dims.get('增长质量', '—')} | "
            f"{dims.get('估值', '—')} | {dims.get('团队/治理', '—')} | "
            f"**{r.get('research_score', '—')}** |"
        )
    lines.append("")

    lines.append("## 📌 操作建议")
    lines.append("")
    lines.append("- **🟢 Ready / 高 conviction（>70）**：维持/加仓，关注回调到支撑位加仓机会")
    lines.append("- **⏳ Wait / 中 conviction（55–70）**：持有观望，等回调或催化")
    lines.append("- **👀 Watch**：小仓位或观察，等趋势确认")
    lines.append("- **🚫 Avoid / 低 conviction（<55）**：考虑减仓，基本面或技术面转弱")
    lines.append("")
    lines.append("---")
    lines.append(f"*由 `portfolio_scan_to_vault.py` 于 {datetime.now().strftime('%Y-%m-%d %H:%M')} 生成*")

    return "\n".join(lines)


def main():
    if not SCAN_JSON.exists():
        print(f"ERROR: {SCAN_JSON} not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(SCAN_JSON.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    md = build_report(data)
    out_file = OUT_DIR / f"组合扫描_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    out_file.write_text(md, encoding="utf-8")

    # Also overwrite a stable "latest" filename for easy phone bookmarking
    latest = OUT_DIR / "组合扫描_LATEST.md"
    latest.write_text(md, encoding="utf-8")

    print(f"✅ Wrote: {out_file}")
    print(f"✅ Wrote: {latest}")
    print(f"   Holdings: {len(data)}")


if __name__ == "__main__":
    main()
