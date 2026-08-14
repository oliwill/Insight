#!/usr/bin/env python3
"""
组合批量扫描 - 用 insight 框架对持仓做 lean 排名扫描

策略：
  1. Lean 扫描所有持仓：price + fundamentals + technicals + wyckoff
     → 计算 Research Score + Timing，输出排名表
  2. Top 5 再跑完整 pipeline 并写入 Obsidian（由调用方决定，本脚本只做 lean）

不写入 Obsidian，只输出排名 JSON + markdown 到 stdout / 文件。

用法:
  .venv/Scripts/python.exe scripts/portfolio_scan.py
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from data.manager import DataManager
from data.analysis_pipeline import compute_technicals
from analyzer.research_score import ResearchScoreEngine
from analyzer.timing_engine import TimingEngine
from data.portfolio_loader import fetch_positions


# Fallback 持仓清单（仅在长桥拉取失败时使用）
FALLBACK_PORTFOLIO = [
    # 美股
    "MU", "TSM", "AAOI", "GOOG", "OKLO", "TSLA", "HIMS", "TSEM",
    "ASTS", "CRWD", "GLW", "AMZN", "MRAAY", "OUST", "AMKR", "QS",
    "AA", "FCX", "ALAB", "OCC", "LPTH", "POET", "TEM", "MNTS",
    # 港股
    "1060.HK",
]

WYCKOFF_MIN_ROWS = 100


def scan_one(dm: DataManager, code: str, position=None) -> dict:
    """Lean scan: price + fundamentals + technicals + wyckoff + scores.

    position: 可选的 Position 对象（来自长桥），用于附带持仓数量/成本价。
    """
    out = {"code": code, "ts": datetime.now().isoformat(timespec="seconds")}
    # 附带持仓信息（成本价、数量、市值）—— 来源是长桥实仓
    if position is not None:
        out["holding_qty"] = position.quantity
        out["holding_cost"] = position.cost_price
        out["holding_currency"] = position.currency
    try:
        info = dm.get_stock_info(code)
        out["price"] = float(info.price) if info.price else None
        out["name"] = info.name
        out["sector"] = info.sector
        out["industry"] = info.industry
        out["market"] = info.market
    except Exception as e:
        out["stock_info_error"] = str(e)
        out["price"] = None

    try:
        fund = dm.get_fundamentals(code) or {}
        out["fundamentals"] = fund
    except Exception as e:
        out["fundamentals_error"] = str(e)
        out["fundamentals"] = {}

    market_data = {
        "stock_info": {
            "code": code,
            "price": out.get("price"),
            "sector": out.get("sector", ""),
            "industry": out.get("industry", ""),
        },
        "fundamentals": out.get("fundamentals", {}),
        "peers": [],
        "web_search": {},
        "liquidity": {},
        "options": {},
        "earnings": {},
        "supply_chain": {},
    }

    # K线 + 技术指标 + Wyckoff
    try:
        df = dm.get_historical_data(code, period="1y")
        if df is not None and len(df) > 0:
            df = df.sort_values("date").reset_index(drop=True)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            out["kline_rows"] = len(df)
            techs = compute_technicals(df)
            out["technicals"] = techs
            market_data["technicals"] = techs

            if len(df) >= WYCKOFF_MIN_ROWS:
                try:
                    from analyzer.wyckoff import WyckoffAnalyzer
                    wa = WyckoffAnalyzer()
                    w = wa.analyze(df.reset_index(), out.get("fundamentals", {}))
                    struct = w.details.get("structure")
                    if struct:
                        out["wyckoff"] = {
                            "phase": struct.market_phase.value,
                            "support": round(float(struct.support_level), 2),
                            "resistance": round(float(struct.resistance_level), 2),
                            "confidence": round(struct.confidence * 100),
                        }
                        market_data["wyckoff"] = out["wyckoff"]
                    out["wyckoff_score"] = w.score
                except Exception as e:
                    out["wyckoff_error"] = str(e)
        else:
            out["kline_rows"] = 0
    except Exception as e:
        out["technicals_error"] = str(e)

    # Research Score
    try:
        rs_engine = ResearchScoreEngine()
        rs = rs_engine.score(market_data, evidence=[])
        out["research_score"] = rs.total_adjusted_score
        out["research_verdict"] = rs.verdict
        out["research_confidence"] = rs.confidence
        out["research_dims"] = {
            name: round(d.adjusted_score, 1) for name, d in rs.dimensions.items()
        }
    except Exception as e:
        out["research_score_error"] = str(e)

    # Timing
    try:
        tm_engine = TimingEngine()
        tm = tm_engine.analyze(market_data, research_score=out.get("research_score"))
        out["timing_state"] = tm.state
        out["timing_internal"] = tm.internal_score
        out["timing_reasons"] = tm.reasons[:3]
    except Exception as e:
        out["timing_error"] = str(e)

    # 衍生指标（用于排名）
    out["derived"] = _derive_ranking_fields(out)
    return out


def _derive_ranking_fields(out: dict) -> dict:
    """从扫描结果提炼用于排名的关键字段。"""
    fund = out.get("fundamentals", {}) or {}
    techs = out.get("technicals", {}) or {}
    price = out.get("price") or 0
    target = fund.get("target_mean_price") or 0
    revenue_growth = fund.get("revenue_growth")
    if revenue_growth is not None and abs(revenue_growth) <= 1:
        revenue_growth = revenue_growth * 100
    ps = fund.get("ps") or fund.get("price_to_sales")
    psg = (ps / revenue_growth) if (ps and revenue_growth and revenue_growth > 0) else None
    potential = (target / price - 1) * 100 if (price and target) else None

    return {
        "ps": round(ps, 2) if ps else None,
        "pe_forward": fund.get("pe_forward"),
        "revenue_growth_pct": round(revenue_growth, 1) if revenue_growth is not None else None,
        "psg": round(psg, 2) if psg is not None else None,
        "target_potential_pct": round(potential, 1) if potential is not None else None,
        "rsi": techs.get("rsi_14"),
        "trend_short": techs.get("trend_short"),
        "trend_mid": techs.get("trend_mid"),
        "pct_from_high": techs.get("pct_from_high"),
        "wyckoff_phase": (out.get("wyckoff") or {}).get("phase"),
    }


def conviction_score(out: dict) -> float:
    """
    H2 翻倍潜力综合分。

    逻辑：高分 = 好标的 + 好时机 + 估值有空间 + 趋势配合
    - research_score: 0-100，公司/thesis 质量
    - timing_internal: 0-100，技术/时机
    - target_potential: 分析师目标价隐含空间（%）
    - trend bonus: 短中期多头加分
    """
    rs = out.get("research_score")
    tm = out.get("timing_internal")
    if rs is None or tm is None:
        return -1.0

    derived = out.get("derived", {}) or {}
    potential = derived.get("target_potential_pct") or 0
    # 估值空间封顶 +50（避免单只目标价离谱拉爆排名）
    potential_term = max(-30, min(50, potential)) * 0.3

    trend_bonus = 0.0
    if derived.get("trend_short") == "BULLISH":
        trend_bonus += 3
    if derived.get("trend_mid") == "BULLISH":
        trend_bonus += 4

    # Wyckoff 加权
    phase = (derived.get("wyckoff_phase") or "").lower()
    if any(k in phase for k in ["markup", "accumulation", "吸筹", "上升"]):
        trend_bonus += 5
    elif any(k in phase for k in ["distribution", "markdown", "派发", "下跌"]):
        trend_bonus -= 6

    # Timing state 加权
    state_weight = {"Ready": 1.0, "Wait": 0.85, "Watch": 0.6, "Avoid": 0.3}.get(
        out.get("timing_state"), 0.7
    )

    raw = (rs * 0.5 + tm * 0.5) * state_weight + potential_term + trend_bonus
    return round(raw, 1)


def main():
    dm = DataManager()

    # 从长桥拉取真实持仓；失败则退回 fallback 清单
    positions = fetch_positions()
    if positions:
        portfolio_source = "longbridge"
        holdings = {p.symbol: p for p in positions}
        portfolio = list(holdings.keys())
        print(f"=== 持仓来源: 长桥实仓（{len(portfolio)} 只）===", flush=True)
    else:
        portfolio_source = "fallback"
        holdings = {}
        portfolio = [_normalize_fb(c) for c in FALLBACK_PORTFOLIO]
        print(f"=== 持仓来源: fallback 硬编码（{len(portfolio)} 只）===", flush=True)
        print("（长桥拉取失败，建议运行 `longbridge auth login`）", flush=True)

    results = []
    total = len(portfolio)

    print(f"=== Portfolio lean scan: {total} tickers ===", flush=True)
    for i, code in enumerate(portfolio, 1):
        t0 = time.time()
        pos = holdings.get(code)
        qty_str = f" qty={int(pos.quantity)}" if pos else ""
        print(f"[{i}/{total}] {code}{qty_str} ...", flush=True, end=" ")
        try:
            out = scan_one(dm, code, position=pos)
        except Exception as e:
            out = {"code": code, "fatal_error": str(e)}
        out["conviction"] = conviction_score(out)
        elapsed = time.time() - t0
        rs = out.get("research_score", "ERR")
        tm = out.get("timing_state", "ERR")
        cv = out.get("conviction", -1)
        print(f"research={rs} timing={tm} conviction={cv} ({elapsed:.1f}s)", flush=True)
        results.append(out)
        # yfinance 限速
        time.sleep(0.4)

    # 按 conviction 排序
    ranked = sorted(results, key=lambda x: x.get("conviction", -1), reverse=True)

    # 输出 JSON
    out_dir = project_root / "scripts" / "_portfolio_scan_out"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"scan_{ts}.json"
    payload = {
        "scan_ts": ts,
        "portfolio_source": portfolio_source,
        "holdings_count": len(portfolio),
        "ranked": ranked,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nJSON saved: {json_path}", flush=True)

    # 输出 markdown 排名表
    md = _build_markdown(ranked, portfolio_source=portfolio_source)
    md_path = out_dir / f"scan_{ts}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Markdown saved: {md_path}", flush=True)

    # stdout 摘要
    print("\n=== Ranking (by conviction) ===", flush=True)
    for i, r in enumerate(ranked, 1):
        d = r.get("derived", {}) or {}
        qty = r.get("holding_qty")
        qty_str = f" qty={int(qty)}" if qty else ""
        print(
            f"{i:>2}. {r['code']:<8} conviction={r.get('conviction'):<6}{qty_str} "
            f"R={r.get('research_score'):<5} T={r.get('timing_state'):<6} "
            f"PSG={d.get('psg')} pot={d.get('target_potential_pct')}% "
            f"phase={d.get('wyckoff_phase')}",
            flush=True,
        )


def _normalize_fb(code: str) -> str:
    """fallback 清单归一化（复用 DataManager 规则）。"""
    from data.manager import DataManager
    return DataManager.normalize_symbol(code)


def _build_markdown(ranked: list, portfolio_source: str = "unknown") -> str:
    source_label = {
        "longbridge": "🟢 长桥实仓",
        "fallback": "🟡 fallback 硬编码",
        "unknown": "未知来源",
    }.get(portfolio_source, portfolio_source)
    lines = [
        f"# 组合扫描排名 ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
        "",
        f"**持仓来源**：{source_label}",
        "",
        "按 H2 翻倍潜力综合分（conviction）排序。综合分 = (Research×0.5 + Timing×0.5) × TimingState权重 + 目标价空间 + 趋势/Wyckoff bonus。",
        "",
        "| # | 代码 | 名称 | 持仓 | 成本 | 现价 | 浮动% | Conviction | Research | Timing | RSI | 趋势 | Wyckoff | PSG | 目标空间 | 营收增速 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|---|---:|---:|---:|",
    ]
    for i, r in enumerate(ranked, 1):
        d = r.get("derived", {}) or {}
        name = (r.get("name") or "")[:18]
        trend = f"{(d.get('trend_short') or '-')[:3]}/{(d.get('trend_mid') or '-')[:3]}"
        psg = d.get("psg")
        psg_str = f"{psg:.1f}" if psg is not None else "-"
        # 持仓列
        qty = r.get("holding_qty")
        qty_str = f"{int(qty)}" if qty else "-"
        cost = r.get("holding_cost")
        price = r.get("price")
        cost_str = f"{cost:.2f}" if cost is not None else "-"
        price_str = f"{price:.2f}" if price else "-"
        # 浮动盈亏%
        if cost is not None and price and cost != 0:
            pnl = (price / cost - 1) * 100
            pnl_str = f"{pnl:+.1f}%"
        else:
            pnl_str = "-"
        lines.append(
            f"| {i} | {r['code']} | {name} | {qty_str} | {cost_str} | {price_str} | {pnl_str} | "
            f"{r.get('conviction','-')} | {r.get('research_score','-')} | {r.get('timing_state','-')} | "
            f"{d.get('rsi','-')} | {trend} | {d.get('wyckoff_phase','-')} | "
            f"{psg_str} | {d.get('target_potential_pct','-')}% | {d.get('revenue_growth_pct','-')}% |"
        )
    # 维度明细
    lines.append("\n## 五维评分明细\n")
    lines.append("| 代码 | 行业/TAM | 护城河 | 增长 | 估值 | 团队 | 综合 | Verdict |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for r in ranked:
        dims = r.get("research_dims", {}) or {}
        lines.append(
            f"| {r['code']} | {dims.get('行业/TAM','-')} | {dims.get('护城河','-')} | "
            f"{dims.get('增长质量','-')} | {dims.get('估值','-')} | {dims.get('团队/治理','-')} | "
            f"{r.get('research_score','-')} | {r.get('research_verdict','-')} |"
        )
    # 错误汇总
    errs = [r for r in ranked if any(k.endswith("_error") or k == "fatal_error" for k in r.keys())]
    if errs:
        lines.append("\n## 错误/警告\n")
        for r in errs:
            el = [f"{k}={v}" for k, v in r.items() if k.endswith("_error") or k == "fatal_error"]
            lines.append(f"- **{r['code']}**: {'; '.join(el)[:200]}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
