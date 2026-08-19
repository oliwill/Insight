#!/usr/bin/env python3
"""
完整版报告生成器 — AGENTS.md A-J 全章节 + 趋势博弈分析框架增强

输出 11 节完整分析报告到 Obsidian vault：
  一、公司与催化剂（A）
  二、基本面与增长质量（C）
  三、护城河分析（B2）
  四、估值锚点（D）★反向推导+赔率原型
  五、技术面（B）★趋势博弈分析框架四模块+SEPA合并大节
  六、市场结构与情绪（E）
  七、风险量化（F）
  八、三情景目标价（G）★PS相对估值法
  九、操作格网（H）★Fib+ATR+道氏通道
  十、警戒线/加仓信号（I）★从趋势博弈分析框架信号提取
  十一、催化剂日历（J）

用法: python scripts/generate_full_report.py [SYMBOL ...]
  不带参数则跑默认4只A股
"""

import argparse
import sys, os, math, warnings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

from config import Config
from data.constants import normalize_growth_rate
from data.manager import DataManager
from analyzer.wyckoff import WyckoffAnalyzer
from analyzer.volume_profile import VolumeProfileAnalyzer
from analyzer.dow_channel import DowChannelAnalyzer
from analyzer.force_balance import ForceBalanceAnalyzer
from analyzer.multi_timeframe import MultiTimeframeAnalyzer
from analyzer.timing_engine import TimingEngine

dm = DataManager()
_wk = WyckoffAnalyzer()
_va = VolumeProfileAnalyzer()
_dca = DowChannelAnalyzer()
_fa = ForceBalanceAnalyzer()
_ma = MultiTimeframeAnalyzer()
_te = TimingEngine()
WIKI = Config.get_wiki_dir()

# 同行基准（预计算）
PEER_BENCH = {
    "SH688035": {
        "ps_med": 7.1,
        "pe_med": 75.7,
        "top": "雅克科技(0.59)",
        "detail": "雅克科技PS8.3/新益昌PS7.1/中国巨石PS8.0",
    },
    "SZ002468": {
        "ps_med": 0.5,
        "pe_med": 13.9,
        "top": "顺丰控股(0.41)",
        "detail": "顺丰PS0.6/中国外运PS0.4",
    },
    "SH688106": {
        "ps_med": 7.1,
        "pe_med": 75.7,
        "top": "雅克科技(0.39)",
        "detail": "特种气体独立性强，相关性低",
    },
    "SH688188": {
        "ps_med": 17.5,
        "pe_med": 96.0,
        "top": "汇川技术(0.48)",
        "detail": "汇川PS3.6/北方华创PS13/中微PS27.5/华峰测控PS51",
    },
}


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean().iloc[-1]
    loss = (-delta.clip(upper=0)).rolling(period).mean().iloc[-1]
    if loss > 0:
        return float(100 - 100 / (1 + gain / loss))
    return 100.0 if gain > 0 else 50.0


def _macd(close):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(signal.iloc[-1]), float((macd - signal).iloc[-1])


def _boll(close, period=20, std=2):
    mid = close.rolling(period).mean().iloc[-1]
    s = close.rolling(period).std().iloc[-1]
    return float(mid + std * s), float(mid), float(mid - std * s)


def _kdj(high, low, close, n=9):
    low_n = low.rolling(n).min()
    high_n = high.rolling(n).max()
    rsv = (close - low_n) / (high_n - low_n) * 100
    k_s = rsv.ewm(com=2, adjust=False).mean()
    d_s = k_s.ewm(com=2, adjust=False).mean()
    j = 3 * k_s.iloc[-1] - 2 * d_s.iloc[-1]
    return float(k_s.iloc[-1]), float(d_s.iloc[-1]), float(j)


def _atr(high, low, close, period=14):
    tr = pd.concat(
        [(high - low), (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


# ============================================================
# 估值反向推导 + 赔率原型
# ============================================================
def valuation_reverse(
    ps, ps_peer_med, rev_growth, pe, eg, mcap, tech_bullish, bottom_signal
):
    """返回 (透支倍数, 隐含年数, 安全边际, 赔率原型)。

    ps_peer_med 缺失（无同行基准）时 overpay 为 None，不编造「未透支」结论；
    rev_growth 用于隐含年数/分类时封顶 200%，避免异常大数（如 3457%）扭曲结论。
    """
    rev_growth = rev_growth or 0.0
    eg = eg or 0.0
    pe = pe or 0.0
    overpay = ps / ps_peer_med if ps_peer_med and ps_peer_med > 0 else None
    g_math = min(rev_growth, 2.0) if rev_growth > 0 else rev_growth
    if overpay is None:
        implied_years = 0
        margin = "无同行基准"
    elif overpay > 1 and g_math > 0:
        implied_years = math.log(overpay) / math.log(1 + g_math)
    elif overpay < 1:
        implied_years = (
            -math.log(1 / overpay) / math.log(1 + max(g_math, 0.01))
            if g_math > 0
            else 0
        )
    else:
        implied_years = 0
    # 安全边际
    if overpay is None:
        pass  # margin 已置为「无同行基准」
    elif overpay < 0.8:
        margin = "充足"
    elif overpay <= 1.2:
        margin = "偏紧"
    else:
        margin = "无安全边际"
    # 赔率原型（psg 用真实增速；分类用封顶增速）
    psg = ps / (rev_growth * 100) if ps and ps > 0 and rev_growth > 0 else None
    if g_math > 0.2 and psg is not None and psg < 1.5 and tech_bullish:
        odds = "高确定性增长型"
    elif g_math > 0.2 and ((psg is not None and psg > 2) or not tech_bullish):
        odds = "催化剂驱动型"
    elif eg < 0 and pe > 50 and "底部" in bottom_signal:
        odds = "困境反转型"
    elif pe < 15 and rev_growth < 0.1 and "底部" in bottom_signal:
        odds = "周期底部型"
    else:
        odds = "混合型"
    return overpay, implied_years, margin, odds, psg


# ============================================================
# 三情景目标价
# ============================================================
def three_scenarios(
    price,
    ps,
    ps_peer_med,
    rev_growth,
    mcap,
    target_mean: float = 0.0,
    atr: float = 0.0,
    timing_state: str = "",
):
    """PS相对估值法三情景。

    - 无估值锚（无分析师目标价且 PS/同行数据缺失）时返回 None，报告显式披露数据缺口，
      而不是输出一个等于现价的伪目标价。
    - Bull/Bear 宽度由 ATR 波动率决定（约 8 倍日 ATR%，限制在 15%-45%），不再固定 ±30%。
    - 情景概率与 Timing State 联动：越不可行动，Bear 权重越高。
    """
    annual_rev = mcap / ps if ps > 0 else 0
    # Base
    if target_mean and target_mean > 0:
        base = target_mean
    elif annual_rev > 0 and ps_peer_med > 0:
        fair_mcap = annual_rev * ps_peer_med
        base = price * (fair_mcap / mcap) if mcap > 0 else price
    else:
        return None

    if atr and price > 0:
        width = min(0.45, max(0.15, (atr / price) * 8))
    else:
        width = 0.30
    prob_map = {
        "Ready": (0.30, 0.50, 0.20),
        "Wait": (0.25, 0.50, 0.25),
        "Watch": (0.20, 0.50, 0.30),
        "Avoid": (0.15, 0.45, 0.40),
    }
    prob_bull, prob_base, prob_bear = prob_map.get(timing_state, (0.25, 0.50, 0.25))

    bull = base * (1 + width)
    bear = base * (1 - width)
    weighted = bull * prob_bull + base * prob_base + bear * prob_bear
    implied_ret = (weighted / price - 1) * 100 if price > 0 else 0
    return {
        "bull": bull,
        "base": base,
        "bear": bear,
        "weighted": weighted,
        "implied_ret": implied_ret,
        "width": width,
        "probs": (prob_bull, prob_base, prob_bear),
    }


# ============================================================
# 报告数据展示：缺失指标不伪装成 0
# ============================================================
def _has_metric(value):
    """Whether a numeric fundamental metric is safe to display in the report."""
    try:
        return (
            value is not None
            and math.isfinite(float(value))
            and abs(float(value)) > 1e-12
        )
    except (TypeError, ValueError):
        return False


def _fundamental_rows(pe, pf, pb, gm, om, roe, rev_g, eg, cash, debt, debt_equity):
    """Return only available fundamental rows; Yahoo omits several A-share fields."""
    rows = []
    if _has_metric(pe):
        rows.append(
            f"| PE(TTM) | {pe:.1f} | {'偏高' if pe > 50 else ('合理' if pe < 25 else '中等')} |"
        )
    if _has_metric(pf):
        forward_note = "预期改善" if not _has_metric(pe) or pf < pe else "预期承压"
        rows.append(f"| PE(Forward) | {pf:.1f} | {forward_note} |")
    if _has_metric(pb):
        rows.append(
            f"| PB | {pb:.2f} | {'偏高' if pb > 4 else ('合理' if pb < 2 else '中等')} |"
        )
    if _has_metric(gm):
        rows.append(
            f"| 毛利率 | {gm:.1f}% | {'优秀' if gm > 40 else ('中等' if gm > 20 else '偏低')} |"
        )
    if _has_metric(om):
        rows.append(
            f"| 经营利润率 | {om:.1f}% | {'优秀' if om > 20 else ('中等' if om > 10 else '偏低')} |"
        )
    if _has_metric(roe):
        rows.append(
            f"| ROE | {roe:.1f}% | {'优秀' if roe > 15 else ('中等' if roe > 8 else '偏低')} |"
        )
    if _has_metric(rev_g):
        rows.append(
            f"| 营收增速 | {rev_g:.1f}% | {'高增长' if rev_g > 20 else ('稳健' if rev_g > 10 else '疲软')} |"
        )
    if _has_metric(eg):
        rows.append(
            f"| 盈利增速 | {eg:.1f}% | {'爆发' if eg > 50 else ('健康' if eg > 15 else '承压')} |"
        )
    if _has_metric(cash) or _has_metric(debt):
        net_cash = (cash - debt) / 1e8
        rows.append(
            f"| 净现金 | {net_cash:+.1f}亿 | {'健康' if net_cash > 0 else '负债承压'} |"
        )
    if _has_metric(debt_equity):
        # Yahoo's debtToEquity field is expressed as a percentage (e.g. 12.3 = 12.3%).
        rows.append(
            f"| 债务/权益 | {debt_equity:.1f}% | {'高杠杆' if debt_equity >= 100 else ('可控' if debt_equity < 60 else '需关注')} |"
        )
    return "\n".join(rows) or "| 可用基本面数据 | — | Yahoo 未返回可验证字段 |"


def _growth_quality_lines(rev_g, eg, gm, cash, debt):
    lines = []
    if _has_metric(rev_g):
        lines.append(
            f"- {'✅ 营收增速健康' if rev_g > 15 else '⚠️ 营收增速疲软'}（{rev_g:.1f}%）"
        )
    if _has_metric(eg) and _has_metric(rev_g):
        lines.append(
            "- ✅ 盈利增速匹配/超越营收"
            if eg > rev_g
            else "- ⚠️ 盈利增速落后于营收，利润率承压"
        )
    if (_has_metric(rev_g) and rev_g > 300) or (_has_metric(eg) and eg > 300):
        lines.append("- ⚠️ 增速异常偏高（>300%），请人工核实数据源")
    if _has_metric(cash) or _has_metric(debt):
        lines.append(
            "- ⚠️ 高负债模式，利率敏感" if cash < debt else "- ✅ 净现金充裕，抗风险强"
        )
    if _has_metric(gm):
        if gm < 15:
            lines.append("- ⚠️ 低毛利行业（物流/周期），对规模与成本控制敏感")
        elif gm > 40:
            lines.append("- ✅ 毛利率具备定价权")
    return (
        "\n".join(lines) or "- 数据源未返回足够的增长质量字段；不以 0 值代替缺失数据。"
    )


def _moat_rows(gm, mcap):
    gm_available = _has_metric(gm)
    mcap_available = _has_metric(mcap)
    tech_stars = 5 if gm > 60 else 3 if gm > 30 else 2
    scale_stars = 4 if mcap > 2e10 else 2
    return "\n".join(
        [
            f"| 技术/IP壁垒 | {'★' * tech_stars if gm_available else '—'} | {'毛利率{:.0f}%'.format(gm) + ('，强定价权' if gm > 50 else '') if gm_available else '毛利率数据未获取，暂不评级'} |",
            f"| 客户锁定 | — | 无客户结构/复购数据，暂不评级（{'行业龙头地位' if mcap_available and mcap > 1e10 else '中小盘'}，需进一步验证）|",
            f"| 规模优势 | {'★' * scale_stars if mcap_available else '—'} | {'市值¥{:.0f}亿'.format(mcap / 1e8) + ('，规模领先' if mcap > 2e10 else '') if mcap_available else '市值数据未获取，暂不评级'} |",
            f"| 品牌/转换成本 | {'★' * (4 if gm > 50 else 2) if gm_available else '—'} | {'高毛利暗示较强品牌/转换成本' if gm_available and gm > 50 else ('毛利率数据未获取，暂不评级' if not gm_available else '需结合客户黏性进一步验证')} |",
        ]
    )


def _format_multiple(value):
    """Keep sub-1 valuation multiples meaningful instead of rounding them to 0.0."""
    if not _has_metric(value):
        return "—"
    return f"{value:.2f}" if abs(value) < 1 else f"{value:.1f}"


def _format_psg(psg):
    if psg is None:
        return "—"
    return f"{psg:.2f}" if abs(psg) < 0.1 else f"{psg:.1f}"


def _valuation_details(
    name,
    ps,
    pe,
    peer,
    overpay,
    impl_years,
    margin,
    odds,
    psg,
    rev_g,
    tech_bullish,
    bottom_signal,
):
    if not (_has_metric(ps) and _has_metric(peer.get("ps_med"))):
        return """### PS同行对比
> 数据缺口：未获取可验证的本股 PS 或同行 PS 中位数，跳过相对估值、PSG 与反向推导。"""
    pe_text = _format_multiple(pe)
    peer_pe_text = _format_multiple(peer.get("pe_med"))
    psg_text = _format_psg(psg)
    psg_note = (
        ("<1 合理" if psg < 1 else ("1-2 偏高" if psg < 2 else ">2 极度高估"))
        if psg is not None
        else "营收增速缺失，无法计算"
    )
    growth_text = f"营收增速{rev_g:.0f}%" if _has_metric(rev_g) else "营收增速未获取"
    return f"""### PS同行对比
| 标的 | PS | PE |
|------|-----|-----|
| **{name}（本股）** | **{_format_multiple(ps)}** | **{pe_text}** |
| 同行中位数 | {_format_multiple(peer["ps_med"])} | {peer_pe_text} |

- **PSG** = {psg_text}（{psg_note}）

### 反向推导（当前价格假设了什么）
- **透支倍数** = {overpay:.2f}×（当前PS / 同行PS中位数）
- {"⚠️ 当前定价透支了约 {:.1f} 年的未来收入增长".format(impl_years) if impl_years > 0.5 else "✅ 当前定价未透支（合理或折价）" if overpay <= 1.2 else "当前估值略偏高但可控"}
- **安全边际**：**{margin}**

### 非对称赔率原型
- **类型**：**{odds}**
- 判断依据：{growth_text}、PSG {psg_text}、技术面{"偏多" if tech_bullish else "偏空"}、{"有底部信号" if "底部" in bottom_signal else "无底部信号"}"""


# ============================================================
# 操作格网（Fib + ATR + 道氏通道）
# ============================================================
def _entry_stop(entry, atr):
    """Return an explicit ATR invalidation level for a proposed long entry."""
    return entry - 2.5 * atr if atr > 0 else entry * 0.95


def _rr(entry, target, stop):
    """Long-side reward/risk calculated against an explicit stop, never current price."""
    if not (entry > 0 and stop > 0 and target > entry > stop):
        return None
    return round((target - entry) / (entry - stop), 1)


def trading_grid(
    price,
    period_low,
    period_high,
    atr,
    channel_lower,
    channel_upper,
    ma50,
    target,
    timing_state="",
):
    """Build entries with per-entry ATR stops and unambiguous reward/risk values."""
    fib = {
        lvl: period_high - (period_high - period_low) * lvl
        for lvl in (0.236, 0.382, 0.5, 0.618, 0.786)
    }
    current_atr_stop = _entry_stop(price, atr)
    rows = []

    def append_row(label, entry, trigger, position, keep=False):
        if entry <= 0:
            return
        stop = _entry_stop(entry, atr)
        rr = _rr(entry, target, stop)
        # 盈亏比 <1 的价位（风险大于回报）不展示，避免输出误导性加仓点；
        # 当前价信息行除外（仅作参照，不是建议买入点）
        if rr is not None and rr < 1.0 and not keep:
            return
        rows.append((label, entry, stop, trigger, position, rr))

    # Do not suggest averaging down below the current ATR risk line.  A break below
    # that level invalidates the setup rather than creating another buy level.
    deep_candidate = min(fib[0.786], (channel_lower or fib[0.786]) * 0.95)
    deep = max(deep_candidate, current_atr_stop)
    if 0 < deep < price:
        append_row(
            "🔴 深度加仓",
            deep,
            "触及78.6%回撤或道氏通道下沿-5%；跌破当前ATR风险线则取消加仓",
            "30%",
        )

    core = max(fib[0.618], channel_lower or fib[0.618])
    if 0 < core < price * 0.99:
        append_row("🟡 核心建仓", core, "回踩61.8%回撤或道氏通道下沿", "40%")

    pull = max(fib[0.5], ma50 or fib[0.5])
    if 0 < pull < price * 1.05:
        append_row("🟢 第一回调", pull, "回踩50%回撤或MA50", "20%")

    action = (
        "可追"
        if timing_state == "Ready" and target and target > price * 1.15
        else "不追"
    )
    current_trigger = (
        "时机状态 Ready 且目标价空间≥15%"
        if action == "可追"
        else f"时机状态 {timing_state or '未确认'}，不在当前价追高"
    )
    append_row("⚪ 当前价", price, current_trigger, "0-15%", keep=True)

    brk = min(fib[0.382], channel_upper or fib[0.382])
    if brk > price:
        append_row("🟢 突破加仓", brk, "突破38.2%回撤或道氏通道上沿", "15%")
    return rows


# ============================================================
# 警戒线/加仓信号自动提取
# ============================================================
def extract_alerts(p, c, f, m, rsi, price, ma20):
    """从趋势博弈分析框架四模块信号提取可观测布尔条件"""
    red, green = [], []
    # 🔴 警戒线
    if p.is_volume_spike:
        red.append(f"单日成交量 ≥ 3×20日均量 且当日收阴 → 减仓30%，疑似抢帽子出货")
    if c.neckline_signal == "颈线已跌破":
        red.append(f"收盘价持续低于通道下沿 ¥{c.lower_channel:.2f} → 清仓，衢地归空方")
    if c.top_bottom_signal == "顶部三步信号":
        red.append(f"价格出轨后回落跌破通道上沿 ¥{c.upper_channel:.2f} → 分批止盈50%")
    if f.distribution_evidence >= 70:
        red.append(
            f"连续2日高位放量滞涨（量≥2×均量且涨幅<1%）→ 减仓，主力派发证据{f.distribution_evidence:.0f}"
        )
    if rsi > 70:
        red.append(f"RSI 突破 70 → 减仓20%，超买区")
    if c.is_rubbing_upper:
        red.append(
            f"连续触碰通道上沿 ¥{c.upper_channel:.2f} 未突破≥3次 → 减仓，多方外强中干"
        )
    if f.retail_trap_risk >= 70:
        red.append(
            f"连续涨停+小市值+爆量 → 警惕散户陷阱风险{f.retail_trap_risk:.0f}，趋势博弈框架四问法"
        )
    # 🟢 加仓信号
    if p.is_flat_volume_uptrend:
        green.append(f"量比维持0.6-1.2 且20日涨幅>3% → 可加仓，平量推升筹码锁定")
    if "趋缓" in c.slope_state:
        green.append(
            f"下降通道斜率趋缓（下跌动能衰竭）+缩量至通道下沿 ¥{c.lower_channel:.2f} → 企稳确认后可试探建仓"
        )
    if c.top_bottom_signal == "底部三步信号":
        green.append(
            f"缩量筑底后放量站上通道下沿 ¥{c.lower_channel:.2f} → 可加仓，底部确认"
        )
    if f.accumulation_evidence >= 65:
        green.append(
            f"底部连续长下影线+低点抬高 → 可加仓，主力吸筹证据{f.accumulation_evidence:.0f}"
        )
    if c.neckline_signal == "颈线已突破":
        green.append(f"放量突破颈线位 → 可加仓，衢地归多方")
    if m.alignment in ("三级别共振多头", "多级别一致多头"):
        green.append(f"日/周/月多级别共振上升 → 可加仓，趋势确认")
    if rsi < 30 and f.accumulation_evidence >= 60:
        green.append(f"RSI超卖({rsi:.0f})+吸筹证据强 → 可左侧试探")
    # 默认补充
    if not red:
        red.append("跌破MA20 ¥{:.2f} 且放量 → 减仓".format(ma20))
        red.append("核心thesis被新事实证伪 → 清仓")
    if not green:
        green.append("等待量价齐升或颈线突破信号再行动")
    return red[:6], green[:6]


# ============================================================
# 技术面综合结论
# ============================================================
def _tech_conclusion(sepa_stage, wk_phase, p, c, f, m):
    """综合 SEPA/Wyckoff/趋势博弈四模块，输出技术面整体结论（一句话定性 + 要点列表）。"""
    bull, bear = 0, 0
    if "Stage 2" in sepa_stage:
        bull += 1
    elif "Stage 4" in sepa_stage:
        bear += 1
    # Wyckoff 阶段参与投票（此前参数传入但从未使用）
    wk_low = (wk_phase or "").lower()
    if any(k in wk_low for k in ("markup", "accumulation", "吸筹", "上升", "上涨")):
        bull += 1
    elif any(k in wk_low for k in ("markdown", "distribution", "派发", "下跌")):
        bear += 1
    if p.regime in ("平量推升", "量价齐升"):
        bull += 1
    elif p.regime in ("爆冲巨量", "缩量阴跌", "量价紊乱"):
        bear += 1
    if c.channel_direction == "上升":
        bull += 1
    elif c.channel_direction == "下降":
        bear += 1
    if m.alignment in ("三级别共振多头", "多级别一致多头"):
        bull += 1
    elif m.alignment in ("三级别共振空头", "多级别一致空头"):
        bear += 1

    if bull >= 3:
        verdict = "技术面整体偏多，趋势向好"
    elif bear >= 3:
        verdict = "技术面整体偏空，处于弱势"
    elif bull == bear:
        verdict = "技术面多空交织，方向不明"
    elif bull > bear:
        verdict = "技术面略偏多，但信号不完全一致"
    else:
        verdict = "技术面略偏空，等待企稳信号"
    return verdict


# ============================================================
# 术语表（静态附录）
# ============================================================
GLOSSARY = """

---

## 术语表

| 缩写 | 全称 | 含义 |
|------|------|------|
| PSG | Price-to-Sales-Growth | 市销率÷营收增速%，衡量估值相对增速的合理性（<1合理，1-2偏高，>2极度高估）|
| PS | Price-to-Sales | 市销率=市值÷年化营收 |
| PE | Price-to-Earnings | 市盈率=股价÷每股收益（TTM=过去12个月，Forward=预期）|
| PB | Price-to-Book | 市净率=股价÷每股净资产 |
| ROE | Return on Equity | 净资产收益率=净利润÷净资产，衡量资本效率（>15%优秀）|
| RSI | Relative Strength Index | 相对强弱指标（<30超卖，>70超买）|
| MACD | Moving Average Convergence Divergence | 指数平滑异同移动平均线（金叉看多，死叉看空）|
| KDJ | Stochastic Oscillator | 随机指标（K>D看多，K<D看空，J为方向敏感线）|
| MA | Moving Average | 移动平均线（MA5/20/50/120/200，多头排列=短期>长期）|
| ATR | Average True Range | 平均真实波幅，衡量波动性（用于止损计算）|
| SEPA | Specific Entry Point Analysis | 米纳维尼阶段分析（Stage 1底部/2主升/3顶部/4下跌）|
| Wyckoff | — | 威科夫方法：通过吸筹/派发/弹簧等事件识别主力意图 |
| VCP | Volatility Contraction Pattern | 波动率收缩形态，SEPA 买点确认 |
"""


# ============================================================
# Obsidian 持久化
# ============================================================
REPORT_SECTION = "趋势博弈分析框架完整分析"


def _strip_frontmatter(markdown: str) -> str:
    """移除独立报告的 YAML front matter，避免嵌入股票页时破坏页面元数据。"""
    if not markdown.startswith("---\n"):
        return markdown.strip()
    end = markdown.find("\n---", 4)
    if end == -1:
        return markdown.strip()
    return markdown[end + 4 :].lstrip()


def to_wiki_section_content(report: str) -> str:
    """将独立完整报告转换为可安全替换的股票页三级标题内容。"""
    content = _strip_frontmatter(report)
    lines = []
    for line in content.splitlines():
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            line = "#" * max(3, level + 2) + line[level:]
        lines.append(line)
    return "\n".join(lines).strip()


def persist_to_obsidian(
    symbol: str, stock_name: str, report: str, title_date: str = ""
) -> None:
    """幂等写入完整分析，不覆盖已有股票页的其他研究和历史章节。

    章节名固定为 REPORT_SECTION（每次替换）；title_date 仅保留在报告正文标题内，
    不拼入章节名，避免每天生成新章节导致 wiki 无限累积。
    """
    from memory.manager import MemoryManager

    manager = MemoryManager()
    manager.init_stock_wiki(symbol, stock_name)
    manager.replace_section(symbol, REPORT_SECTION, to_wiki_section_content(report))


# ============================================================
# 报告生成主函数
# ============================================================
def generate(
    sym,
    name,
    yf_code,
    sector,
    industry,
    biz,
    *,
    output_dir: Path | None = None,
    write_to_obsidian: bool = False,
):
    df = dm.get_historical_data(sym, period="1y")
    info = dm.get_stock_info(sym)
    fund = dm.get_fundamentals(sym)
    if df is None or len(df) < 40:
        return None
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    close, high, low, vol = df["close"], df["high"], df["low"], df["volume"]
    price = float(close.iloc[-1])
    mcap = fund.get("market_cap", 0) or 0
    rev_g = normalize_growth_rate(fund.get("revenue_growth"))
    eg = normalize_growth_rate(fund.get("earnings_growth"))
    pe = fund.get("pe_ttm", 0) or 0
    pf = fund.get("pe_forward", 0) or 0
    pb = fund.get("pb", 0) or 0
    ps = fund.get("ps", 0) or 0
    gm = (fund.get("gross_margin", 0) or 0) * 100
    om = (fund.get("operating_margin", 0) or 0) * 100
    roe = (fund.get("roe", 0) or 0) * 100
    cash = fund.get("total_cash", 0) or 0
    debt = fund.get("total_debt", 0) or 0
    net_cash = (cash - debt) / 1e8
    de_ratio = fund.get("debt_equity", 0) or 0
    target_mean = fund.get("target_mean_price", 0) or 0
    peer = PEER_BENCH.get(
        sym, {"ps_med": None, "pe_med": None, "top": "N/A", "detail": "未获取同行基准"}
    )

    # 技术指标
    rsi = _rsi(close)
    macd_v, macd_s, macd_h = _macd(close)
    boll_u, boll_m, boll_l = _boll(close)
    kdj_k, kdj_d, kdj_j = _kdj(high, low, close)
    atr = _atr(high, low, close)
    ma5 = float(close.tail(5).mean())
    ma20 = float(close.tail(20).mean())
    ma50 = float(close.tail(50).mean())
    ma120 = float(close.tail(120).mean()) if len(close) >= 120 else ma50
    ma150 = float(close.tail(150).mean()) if len(close) >= 150 else ma120
    ma200 = float(close.tail(200).mean()) if len(close) >= 200 else ma120
    vol_5d = float(vol.tail(5).mean())
    vol_20d = float(vol.tail(20).mean())
    vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1.0
    period_low = (
        float(close.tail(252).min()) if len(close) >= 252 else float(close.min())
    )
    period_high = (
        float(close.tail(252).max()) if len(close) >= 252 else float(close.max())
    )

    # SEPA Stage（Minervini 趋势模板：8 条准则中 7 条可算；第 8 条相对强度 RS 无基准数据源，未评估）
    ma200_prev = float(close.iloc[:-20].tail(200).mean()) if len(close) >= 220 else None
    sepa_checks = [
        ("价格高于 MA150 与 MA200", price > ma150 and price > ma200),
        ("MA150 高于 MA200", ma150 > ma200),
        ("MA200 较 20 个交易日前上升", (ma200 > ma200_prev) if ma200_prev else None),
        ("MA50 高于 MA150 与 MA200", ma50 > ma150 and ma50 > ma200),
        ("价格高于 MA50", price > ma50),
        ("价格高于 52 周低点 30% 以上", price >= period_low * 1.30),
        ("价格在 52 周高点 25% 以内", price >= period_high * 0.75),
    ]
    sepa_met = sum(1 for _, ok in sepa_checks if ok is True)
    if sepa_met >= 7:
        sepa_stage = "Stage 2（主升浪，买入区）"
    elif price < ma50 and ma50 < ma200:
        sepa_stage = "Stage 4（下跌，规避）"
    elif abs(price - ma200) / ma200 < 0.1:
        sepa_stage = "Stage 1（底部整理）"
    else:
        sepa_stage = "Stage 3（顶部/震荡）"

    # Wyckoff 分析（原有技术分析）
    wk = None
    try:
        wk = _wk.analyze(df.copy().reset_index(), fund)
    except Exception:
        wk = None
    # 提前提取 Wyckoff 关键变量（供技术面综合结论使用）
    wk_struct = wk.details.get("structure") if wk is not None else None
    wk_phase = wk_struct.market_phase.value if wk_struct else "N/A"
    wk_support = (
        float(wk_struct.support_level) if wk_struct and wk_struct.support_level else 0
    )
    wk_resist = (
        float(wk_struct.resistance_level)
        if wk_struct and wk_struct.resistance_level
        else 0
    )
    wk_conf = (wk_struct.confidence * 100) if wk_struct else 0

    # 趋势博弈分析框架
    vp = _va.analyze(df.copy(), fund)
    p = vp.details["profile"]
    dc = _dca.analyze(df.copy(), fund)
    c = dc.details["channel"]
    fb = _fa.analyze(df.copy(), fund)
    f = fb.details["force_balance"]
    mt = _ma.analyze(df.copy(), fund)
    m = mt.details["view"]

    # Timing
    tech_bullish = (price > ma20) and (m.daily_trend == "上升")
    md = {
        "stock_info": {"price": price, "name": name},
        "technicals": {
            "trend_short": "BULLISH" if price > ma20 else "BEARISH",
            "rsi_14": rsi,
            "vol_ratio": vol_ratio,
            "ma20": ma20,
            "ma50": ma50,
            "support_20d": float(df["low"].tail(20).min()),
        },
        "volume_profile": {"regime": p.regime, "is_volume_spike": p.is_volume_spike},
        "dow_channel": {
            "channel_direction": c.channel_direction,
            "slope_state": c.slope_state,
            "neckline_signal": c.neckline_signal,
            "top_bottom_signal": c.top_bottom_signal,
            "position_in_channel": c.position_in_channel,
            "lower_channel": c.lower_channel,
            "upper_channel": c.upper_channel,
        },
        "force_balance": {
            "bull_bear_state": f.bull_bear_state,
            "accumulation_evidence": f.accumulation_evidence,
            "distribution_evidence": f.distribution_evidence,
            "chip_lock_likelihood": f.chip_lock_likelihood,
            "retail_trap_risk": f.retail_trap_risk,
        },
        "multi_timeframe": {
            "alignment": m.alignment,
            "higher_tf_signal": m.higher_tf_signal,
            "daily_trend": m.daily_trend,
            "weekly_trend": m.weekly_trend,
            "monthly_trend": m.monthly_trend,
        },
    }
    # Wyckoff 结构传入 Timing（此前漏传导致「缺少 Wyckoff 结构」与技术章节自相矛盾）
    if wk is not None:
        md["wyckoff"] = {
            "phase": wk_phase,
            "support": wk_support,
            "resistance": wk_resist,
            "confidence": wk_conf,
        }
    # 真实 Research Score（两层联动：Research<45 时不可 Ready）；失败回退 None 而非假分
    research_value = None
    try:
        from analyzer.research_score import ResearchScoreEngine

        md_research = {
            "stock_info": {
                "price": price,
                "name": name,
                "sector": sector,
                "industry": industry,
            },
            "fundamentals": {
                "market_cap": mcap,
                "pe_ttm": pe,
                "pe_forward": pf,
                "pb": pb,
                "ps": ps,
                "gross_margin": fund.get("gross_margin"),
                "roe": fund.get("roe"),
                "revenue_growth": fund.get("revenue_growth"),
                "target_mean_price": target_mean,
            },
        }
        research_value = (
            ResearchScoreEngine().score(md_research, []).total_adjusted_score
        )
    except Exception:
        research_value = None
    ts = _te.analyze(md, research_score=research_value)
    score = ts.internal_score

    # 估值推导
    overpay, impl_years, margin, odds, psg = valuation_reverse(
        ps,
        peer["ps_med"],
        rev_g / 100 if rev_g is not None else None,
        pe,
        eg / 100 if eg is not None else None,
        mcap,
        tech_bullish,
        c.top_bottom_signal,
    )

    # 三情景（无估值锚时返回 None，报告显式披露缺口）
    scenario = three_scenarios(
        price,
        ps,
        peer["ps_med"],
        rev_g / 100 if rev_g is not None else 0,
        mcap,
        target_mean,
        atr=atr,
        timing_state=ts.state,
    )

    # 操作格网
    grid = trading_grid(
        price,
        period_low,
        period_high,
        atr,
        c.lower_channel,
        c.upper_channel,
        ma50,
        scenario["weighted"] if scenario else 0,
        ts.state,
    )

    # 警戒线
    reds, greens = extract_alerts(p, c, f, m, rsi, price, ma20)

    # 风险量化（至少3条）
    risks = []
    if p.is_volume_spike:
        risks.append(
            (
                "爆冲巨量出货风险",
                -15,
                -25,
                "高" if p.spike_followed_by_decline else "中",
            )
        )
    if c.neckline_signal == "颈线已跌破":
        risks.append(("颈线破位趋势恶化", -10, -20, "高"))
    if overpay is not None and overpay > 1.5:
        risks.append(
            (f"估值泡沫（PS {ps:.1f} vs 同行{peer['ps_med']:.1f}）", 0, -30, "中")
        )
    if net_cash < -30:
        risks.append((f"高负债（净负债{net_cash:.0f}亿）", -5, -15, "中"))
    if _has_metric(eg) and eg < 0:
        risks.append((f"盈利下滑（{eg:.0f}%）", -10, -20, "高"))
    if m.alignment in ("三级别共振空头", "多级别一致空头"):
        risks.append(("趋势共振向下", -8, -12, "中"))
    if rsi < 30:
        risks.append(("RSI超卖，可能继续下探", -5, -8, "中"))
    if _has_metric(rev_g) and rev_g < 10:
        risks.append((f"营收增速疲软（{rev_g:.0f}%）", -8, -10, "中"))
    if not tech_bullish:
        risks.append(("短期技术面偏弱，趋势未企稳", -5, -8, "中"))
    # 补满3条
    if len(risks) < 3:
        risks.append(("行业竞争加剧", -5, -10, "低"))
        risks.append(("宏观经济下行压力", -8, -12, "低"))
        risks.append(("市场系统性风险", -10, -15, "低"))
    risks = risks[:5]

    now = datetime.now()
    today, now_str = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d %H:%M")
    title_date = now.strftime("%Y.%m.%d")  # 用于标题，如 2026.07.24

    verdict = {
        "Ready": "可建仓（按仓位上限执行）",
        "Wait": "等待触发条件",
        "Watch": "观察/小仓试探",
        "Avoid": "回避",
    }.get(ts.state, "观望")
    fundamental_rows = _fundamental_rows(
        pe, pf, pb, gm, om, roe, rev_g, eg, cash, debt, de_ratio
    )
    growth_quality = _growth_quality_lines(rev_g, eg, gm, cash, debt)
    moat_rows = _moat_rows(gm, mcap)
    valuation_details = _valuation_details(
        name,
        ps,
        pe,
        peer,
        overpay,
        impl_years,
        margin,
        odds,
        psg,
        rev_g,
        tech_bullish,
        c.top_bottom_signal,
    )
    pe_yaml = f"{pe:.1f}" if _has_metric(pe) else "null"
    ps_yaml = f"{ps:.2f}" if _has_metric(ps) else "null"
    psg_yaml = _format_psg(psg) if psg is not None else "null"
    psg_description = _format_psg(psg) if psg is not None else "未获取"
    mcap_description = (
        f"市值 ¥{mcap / 1e8:.0f}亿" if _has_metric(mcap) else "市值数据未获取"
    )
    if scenario:
        target_desc = (
            f"加权目标价 ¥{scenario['weighted']:.2f}（{scenario['implied_ret']:+.0f}%）"
        )
        target_yaml = f"{scenario['weighted']:.2f}"
    else:
        target_desc = "估值锚缺失，未生成目标价"
        target_yaml = "null"

    # ---- 组装报告 ----
    L = []
    L.append(f"""---
title: "{sym} {score}/100 — {p.regime}｜{verdict}"
source: Codex
author: "Codex"
published: {today}
created: {now_str}
description: "{name}：PSG {psg_description}，{target_desc}，{margin}"
tags:
  - stock-analysis
  - {sector.lower().replace(" ", "-")}
  - dow-analysis-framework
stock_code: {sym}
score: {score}
timing_state: "{ts.state}"
current_price: {price:.2f}
target_price: {target_yaml}
pe_ttm: {pe_yaml}
ps: {ps_yaml}
psg: {psg_yaml}
moat_score: {(5 if gm > 60 else 3 if gm > 30 else 2) + (3 if roe > 15 else 1)}
odds_type: "{odds}"
margin: "{margin}"
---

# {sym} {name} — 完整版分析报告{title_date}

> 生成：{now_str} | 数据：{len(df)} 个日线交易日 + 基本面 + 同行对比 | 趋势博弈分析框架增强

---

## 一、公司与催化剂

**{name}**（{sym}），{biz}，{sector}/{industry}。现价 ¥{price:.2f}，{mcap_description}。

**触发事件**：趋势博弈分析框架扫描检测到 **{p.regime}** 信号，{("量价关系异常，需警惕" if p.is_volume_spike else "技术形态变化")}。

**供应链定位**：
- 最相关同行：{peer["top"]}
- 同行详情：{peer["detail"]}
- 竞争对手参照系：见第四节估值对比表

---

## 二、基本面与增长质量

| 指标 | 数值 | 评价 |
|------|------|------|
{fundamental_rows}

**增长质量评估**：
{growth_quality}

---

## 三、护城河分析

| 维度 | 评级 | 依据 |
|------|------|------|
{moat_rows}

**竞争威胁**：最相关同行 {peer["top"]}，需关注其份额变化。
**护城河窗口期**：{"5年以上（高毛利+强ROE）" if gm > 50 and roe > 15 else "2-3年（需持续验证）" if gm > 25 else "较弱（成本竞争为主）"}

---

## 四、估值锚点

{valuation_details}

---

## 五、技术面
""")

    # 技术面综合结论（一句话定性 + 多框架汇总表）
    tech_verdict = _tech_conclusion(sepa_stage, wk_phase, p, c, f, m)
    # 布林带位置按价格在带内分档（此前贴近下轨也可能显示「中轨」）
    if price > boll_u:
        boll_pos = "上轨外（出轨/超买）"
    elif price >= boll_m:
        boll_pos = "上半区"
    elif price >= boll_l:
        boll_pos = "下半区"
    else:
        boll_pos = "下轨外（超卖）"
    sepa_lines = "\n".join(
        f"  - {'✅' if ok is True else ('➖' if ok is None else '❌')} {label}"
        for label, ok in sepa_checks
    )

    # 财报日历：真实日期优先，缺失回退占位（政策/宏观行为通用情景）
    earnings_date = None
    try:
        from data.earnings import EarningsCalendar

        earnings_date = (EarningsCalendar().get_earnings_info(yf_code) or {}).get(
            "next_earnings_date"
        )
    except Exception:
        earnings_date = None
    earnings_row_label = earnings_date or "季报期（日期未获取）"
    rev_g_text = f"{rev_g:.0f}%" if rev_g is not None else "N/A"

    L.append(f"""
### 📊 技术面综合结论

> **{tech_verdict}**

| 维度 | 结论 |
|------|------|
| SEPA | {sepa_stage} |
| Wyckoff | {wk_phase}（置信度 {wk_conf:.0f}%）|
| 量价形态 | {p.regime} |
| 道氏通道 | {c.channel_direction}，{c.neckline_signal} |
| 多空博弈 | {f.bull_bear_state} |
| 多时间框架 | {m.alignment} |

### 传统指标
| 指标 | 数值 | 信号 |
|------|------|------|
| RSI(14) | {rsi:.0f} | {"超卖" if rsi < 30 else ("超买" if rsi > 70 else "中性")} |
| MACD | {macd_h:+.3f} | {"金叉" if macd_h > 0 else "死叉"} |
| KDJ | K{kdj_k:.0f}/D{kdj_d:.0f}/J{kdj_j:.0f} | {"看多" if kdj_k > kdj_d else "看空"} |
| 布林带 | 上{boll_u:.1f}/中{boll_m:.1f}/下{boll_l:.1f} | {boll_pos} |
| 量比(5d/20d) | {vol_ratio:.2f} | {"放量" if vol_ratio > 1.5 else ("缩量" if vol_ratio < 0.7 else "正常")} |
| MA5/20/50/120/200 | {ma5:.1f}/{ma20:.1f}/{ma50:.1f}/{ma120:.1f}/{ma200:.1f} | {"多头排列" if ma5 > ma20 > ma50 else "空头排列" if ma5 < ma20 < ma50 else "纠缠"} |

### SEPA Stage 判断
- **当前 Stage**：**{sepa_stage}**
- 趋势模板（Minervini 准则满足 {sepa_met}/7；第 8 条相对强度 RS 无基准数据源，未评估）：
{sepa_lines}""")

    # Wyckoff 分析（原有技术分析核心）— 变量已在前面提取
    if wk is not None:
        L.append(f"""
### Wyckoff 分析
- **阶段**：{wk_phase} | **支撑** ¥{wk_support:.2f} | **阻力** ¥{wk_resist:.2f} | **置信度** {wk_conf:.0f}%""")
        # 关键事件（SC/Spring/SOS/UTAD 等）
        events = wk.details.get("events", [])
        if events:
            event_names = [e.get("event", "") for e in events[:4] if e.get("event")]
            if event_names:
                L.append(f"- **关键事件**：{', '.join(event_names)}")
        for s in wk.signals[:3]:
            L.append(f"- {s}")
        for r in wk.risks[:2]:
            L.append(f"- ⚠️ {r}")
    else:
        L.append("""
### Wyckoff 分析
- 数据不足，无法识别 Wyckoff 结构""")

    L.append(f"""
### 趋势博弈分析框架 · 成交量语言
- **形态**：**{p.regime}** | 量比{p.vol_contraction_ratio:.2f} | 量价相关{p.price_vol_correlation:+.2f} | 20日涨幅{p.price_change_20d_pct:+.1f}%""")
    if p.is_volume_spike:
        L.append(
            f"  - ⚠️ **爆冲巨量**（后跌={p.spike_followed_by_decline}）：疑似抢帽子出货"
        )
    if p.is_flat_volume_uptrend:
        L.append(f"  - ✅ **平量推升**：筹码锁定，最优质走法")
    for s in vp.signals[:2]:
        L.append(f"  - {s}")

    L.append(f"""
### 趋势博弈分析框架 · 道氏通道
- **方向**：{c.channel_direction} | **斜率**：{c.slope_state} | **位置**：{c.position_in_channel:.0%}
- **通道**：¥{c.lower_channel:.2f} - ¥{c.upper_channel:.2f}（宽{c.channel_width_pct:.1f}%）
- **颈线**：{c.neckline_signal} | **顶底信号**：{c.top_bottom_signal}""")
    if c.is_rubbing_upper:
        L.append(f"  - ⚠️ 摩擦上沿：多方外强中干")
    if c.is_rubbing_lower:
        L.append(f"  - ✅ 摩擦下沿：空方衰竭")
    for s in dc.signals[:2]:
        L.append(f"  - {s}")

    L.append(f"""
### 趋势博弈分析框架 · 多空博弈
- **状态**：**{f.bull_bear_state}**
- 吸筹{f.accumulation_evidence:.0f} | 派发{f.distribution_evidence:.0f} | 锁定{f.chip_lock_likelihood:.0f} | 陷阱{f.retail_trap_risk:.0f}""")
    for s in fb.signals[:2]:
        L.append(f"  - ✅ {s}")
    for r in fb.risks[:2]:
        L.append(f"  - ⚠️ {r}")

    L.append(f"""
### 趋势博弈分析框架 · 多时间框架
- **日/周/月**：{m.daily_trend} / {m.weekly_trend} / {m.monthly_trend}
- **一致性**：{m.alignment}（{m.consistency_score:.0f}）
- **高级别信号**：{m.higher_tf_signal}""")

    L.append(f"""

---

## 六、市场结构与情绪

> 注：A股期权/做空/Reddit情绪数据暂不可用，仅显示流动性+多空博弈。""")

    # 流动性（简化）
    adv = vol_20d * price
    L.append(
        f"- **日均成交额**：¥{adv / 1e8:.1f}亿（{'流动性充裕' if adv > 5e8 else '流动性一般' if adv > 1e8 else '流动性较差'}）"
    )
    L.append(
        f"- **ATR**：¥{atr:.2f}（{atr / price * 100:.1f}%，{'高波动' if atr / price > 0.04 else '低波动'}）"
    )

    L.append(f"""

---

## 七、风险量化

| 风险 | 收入影响 | 估值影响 | 概率 |
|------|----------|----------|------|""")
    for rname, ri, rv, rp in risks:
        L.append(f"| {rname} | {ri:+d}% | {rv:+d}% | {rp} |")

    L.append("""

---

## 八、三情景目标价

""")
    if scenario:
        prob_bull, prob_base, prob_bear = scenario["probs"]
        width_pct = scenario["width"] * 100
        L.append(f"""| 情景 | 概率 | 12个月目标价 | 核心假设 |
|------|------|-------------|----------|
| 🟢 Bull | {prob_bull:.0%} | ¥{scenario["bull"]:.2f} | 估值扩张{width_pct:.0f}%（ATR 波动率自适应），增长超预期 |
| 🟡 Base | {prob_base:.0%} | ¥{scenario["base"]:.2f} | {"分析师共识" if target_mean else "PS回归同行中位数"} |
| 🔴 Bear | {prob_bear:.0%} | ¥{scenario["bear"]:.2f} | 估值收缩{width_pct:.0f}%，增长不及预期 |

- **概率加权目标价**：**¥{scenario["weighted"]:.2f}**（概率与时机状态 {ts.state} 联动）
- **隐含12个月回报**：**{scenario["implied_ret"]:+.1f}%**
- 当前价 ¥{price:.2f} vs 加权目标 ¥{scenario["weighted"]:.2f}
""")
    else:
        L.append("""> 数据缺口：缺少分析师目标价与可用的 PS/同行估值锚，本次不生成三情景目标价。
""")

    L.append(f"""

---

## 九、操作格网

| 价位 | 价格 | ATR止损 | 动作 | 仓位 | R/R（至止损） | 触发条件 |
|------|------|---------|------|------|--------------|----------|""")
    for label, lvl_price, stop, trigger, pos, rr in grid:
        rr_str = f"{rr:.1f}" if rr is not None else "—"
        L.append(
            f"| {label} | ¥{lvl_price:.2f} | ¥{stop:.2f} | {label.split(' ')[1]} | {pos} | {rr_str} | {trigger} |"
        )

    L.append(f"""
- **最大仓位上限**：{"60%（基本面优质）" if gm > 50 and roe > 15 else "40%（中等）" if gm > 25 else "20%（高风险）"}
- **当前 ATR 风险线**：¥{_entry_stop(price, atr):.2f}（当前价 - 2.5×ATR；跌破后取消未成交加仓计划）
- 注：盈亏比（R/R）<1 的价位已自动过滤（风险大于回报不出现在格网中）

---

## 十、警戒线 / 加仓信号

### 🔴 警戒线（减仓/清仓条件）""")
    for a in reds:
        L.append(f"- 如果 {a}")

    L.append(f"""
### 🟢 加仓信号""")
    for a in greens:
        L.append(f"- 如果 {a}")

    L.append(f"""

---

## 十一、催化剂日历

| 时间 | 事件 | 超预期→ | 不及预期→ |
|------|------|---------|-----------|
| {earnings_row_label} | 下次财报 | 营收增速维持{rev_g_text}+ → +10% | 增速下滑 → -15% |
| 行业政策 | {industry}政策变动（通用情景，非数据驱动） | 利好 → +8% | 收紧 → -10% |
| 宏观 | 央行利率/汇率（通用情景，非数据驱动） | 宽松 → +5% | 收紧 → -8% |

---

## 综合评估

### 时机状态：**{ts.state}**（{score}/100）→ **{verdict}**

**评分理由**：""")
    for r in ts.reasons[:6]:
        L.append(f"- {r}")
    for r in ts.risk_flags[:3]:
        L.append(f"- ⚠️ {r}")

    L.append(f"""

> **免责声明**：本分析基于 趋势博弈分析框架 + 基本面 + 同行对比，全自动生成，仅供研究参考，不构成投资建议。""")

    # 术语表附录
    L.append(GLOSSARY)

    report = "\n".join(L)

    # 报告质量检查（只打印不阻断，与 pipeline 容错原则一致）
    try:
        from analyzer.report_quality import ReportQualityEvaluator

        quality = ReportQualityEvaluator().evaluate(report, {})
        if not quality.passed:
            print(f"  ⚠️ {sym} 报告质量分 {quality.score}/100：")
            for issue in quality.issues[:5]:
                print(f"     - [{issue.severity}] {issue.code}: {issue.message}")
    except Exception:
        pass
    # 货币符号：A股 ¥ / 港股 HK$ / 美股 $（此前全文硬编码 ¥，统一在此替换）
    cur = "HK$" if sym.endswith(".HK") else ("$" if sym.endswith(".US") else "¥")
    report = report.replace("¥", cur)
    fname = sym.replace(".", "_").replace("/", "_") + ".md"
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / fname).write_text(report, encoding="utf-8")
    if write_to_obsidian:
        persist_to_obsidian(sym, name, report)
    return score, len(report)


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    default_stocks = [
        (
            "SH688035",
            "德邦科技",
            "688035.SS",
            "Basic Materials",
            "Chemicals",
            "半导体封装材料",
        ),
        (
            "SZ002468",
            "申通快递",
            "002468.SZ",
            "Industrials",
            "Integrated Freight & Logistics",
            "快递物流",
        ),
        (
            "SH688106",
            "金宏气体",
            "688106.SS",
            "Basic Materials",
            "Specialty Chemicals",
            "特种气体",
        ),
        (
            "SH688188",
            "柏楚电子",
            "688188.SS",
            "Technology",
            "Semiconductors",
            "激光控制系统/半导体设备",
        ),
    ]
    parser = argparse.ArgumentParser(
        description="生成趋势博弈分析框架增强的完整报告；默认仅输出草稿，不覆盖 Obsidian 股票页。"
    )
    parser.add_argument(
        "symbols", nargs="*", help="可选：SH688035 / 688035.SH / SZ002468 等"
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="将报告幂等更新到 Obsidian 的「趋势博弈分析框架完整分析」章节",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tmp_analysis/full_reports"),
        help="独立 Markdown 草稿输出目录",
    )
    args = parser.parse_args()

    stock_map = {stock[0]: stock for stock in default_stocks}
    stocks = []
    for raw_symbol in args.symbols:
        normalized = raw_symbol.upper().replace(".SH", "").replace(".SZ", "")
        if not normalized.startswith(("SH", "SZ")):
            normalized = (
                "SH" if raw_symbol.upper().endswith(".SH") else "SZ"
            ) + normalized
        stock = stock_map.get(normalized)
        if stock is None:
            parser.error(f"暂不支持 {raw_symbol!r}；可用标的：{', '.join(stock_map)}")
        stocks.append(stock)
    if not stocks:
        stocks = default_stocks

    destination = "Obsidian 指定章节" if args.write else str(args.output_dir)
    print(f"生成 {len(stocks)} 份趋势博弈分析框架完整报告（输出：{destination}）...")
    for sym, name, yf_code, sector, industry, biz in stocks:
        result = generate(
            sym,
            name,
            yf_code,
            sector,
            industry,
            biz,
            output_dir=args.output_dir,
            write_to_obsidian=args.write,
        )
        if result:
            score, chars = result
            print(f"  ✅ {sym} {name} → score={score} ({chars} chars)")
        else:
            print(f"  ❌ {sym} {name} → 数据不足")
    print("\n完成！")
