"""
基本面分析器 - 专业股票分析师框架

分析维度：
1. 业务模式与核心竞争力
2. 财务健康与盈利能力
3. 估值分析（横向+纵向对比）
4. 成长性与估值匹配度
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from .base import BaseAnalyzer, AnalysisResult


class Rating(Enum):
    """评级枚举"""
    EXCELLENT = "优秀"
    GOOD = "良好"
    FAIR = "一般"
    POOR = "较差"
    UNKNOWN = "未知"


@dataclass
class FinancialMetrics:
    """财务指标"""
    # 盈利能力
    gross_margin: float = 0
    operating_margin: float = 0
    profit_margin: float = 0
    roe: float = 0
    roa: float = 0
    
    # 成长性
    revenue_growth: float = 0
    earnings_growth: float = 0
    
    # 估值
    pe_ttm: float = 0
    pe_forward: float = 0
    pb: float = 0
    ps: float = 0
    ev_ebitda: float = 0
    
    # 财务健康
    current_ratio: float = 0
    debt_equity: float = 0
    free_cashflow: float = 0


@dataclass
class ValuationContext:
    """估值上下文"""
    industry_avg_pe: float = 15
    industry_avg_pb: float = 2
    historical_pe_low: float = 10
    historical_pe_high: float = 30
    historical_pb_low: float = 1
    historical_pb_high: float = 5


@dataclass
class MoatDimension:
    """护城河维度评分"""
    name: str
    score: float  # 0-10
    rating: str
    evidence: str


@dataclass
class MoatAnalysis:
    """护城河分析结果"""
    overall_score: float  # 0-10
    overall_rating: str
    dimensions: List[MoatDimension]
    summary: str


MOAT_STRESS_TEST_PROMPT_TEMPLATE = """我想研究【{company}】所在的【{industry}】。

请你不要直接评价这家公司好不好，而是假设我是一个资金充足、执行力很强的新进入者，准备从 0 开始做同样的生意，并在【3-10 年】内挑战【{company}】。

请你站在三个视角分析：

创业者/竞争对手视角：如果我要从 0 做起来，我会被卡在哪里？
产业研究员视角：这个行业真正的关键资源和利润来源是什么？
长期投资者视角：这家公司是否具备可持续护城河，是否值得长期跟踪或持有？

在回答前，请先做 3 件事：

A. 明确业务边界
请先说明【{company}】到底靠哪些业务赚钱，不要把公司简单等同于一个行业。
例如：它是产品公司、平台公司、渠道公司、基础设施公司、资源型公司，还是多种模式叠加？

B. 区分事实、推断和假设
请在分析中明确标注：
已确认事实
基于事实的合理推断
需要进一步验证的假设

C. 如果信息不足，请不要编造
请直接说明哪些信息需要查年报、财报电话会、投资者日、行业报告、监管文件或客户/供应链数据验证。
请按以下框架拆解：

一、行业从 0 做起来的完整流程

假设我是新进入者，从 0 开始做这个行业，请拆解完整流程：
我要先解决什么问题？

需要做出什么产品或服务？

需要哪些核心技术？

需要哪些供应链资源？

需要哪些基础设施？
需要哪些人才和组织能力？
需要哪些销售渠道和客户关系？
需要多少资金，资金主要花在哪里？
需要哪些监管、牌照、认证或政策支持？
从启动到商业化，大概需要多久？
请不要只列清单，要说明每一步为什么重要。

二、进入这个行业最难的 5-7 个环节
请找出这个行业最难突破的 5-7 个关键环节。
每个环节请说明：

难在哪里

需要多少钱

需要多长时间

需要哪些稀缺资源

新进入者最容易死在哪里
有钱能不能解决
如果不能完全靠钱解决，真正缺的是什么

三、目标公司在关键环节里的位置
请分析【{company}】在上述关键环节里分别占据什么优势。
请区分以下类型：
技术优势
产品优势
成本优势
规模优势
客户关系
渠道优势
数据优势
生态优势
品牌信任
监管/牌照优势
资本开支和融资能力
供应链卡位
基础设施卡位
时间窗口和先发优势
请进一步判断：
这些优势是“强护城河”“阶段性优势”，还是“容易被竞争对手追平的优势”？

四、竞争对手攻击模拟
假设我是竞争对手，分别给我三档预算：
低预算：【金额】
中预算：【金额】
高预算：【金额】

请分别告诉我：

第一年度我应该做什么？

三年内我能追上【{company}】哪些部分？
哪些部分即使有钱也很难追上？
我最现实的切入点在哪里？

我应该正面进攻，还是绕开它？

如果绕开它，最好的细分市场是什么？
如果正面进攻，最大风险是什么？
我最终有多大概率撼动它的核心地位？

五、护城河压力测试
请不要泛泛而谈“品牌、技术、规模”。
请判断【{company}】真正的护城河是什么，并回答：
这个护城河来自哪里？
它是技术壁垒、客户锁定、成本优势、网络效应、监管优势、供应链优势，还是资本密集带来的进入门槛？

这个护城河能不能转化为利润？

它能不能提高毛利率、经营利润率、自由现金流或 ROIC？

它能持续多久？

它会不会被新技术、新商业模式或政策变化绕开？
什么情况下这个护城河会失效？
如果我是竞争对手，攻击这个护城河最有效的方法是什么？

六、财务和商业模式验证
请从投资角度进一步分析：
这家公司的收入增长来自哪里？
增长是靠行业扩张、价格提升、份额提升，还是并购/资本开支驱动？
毛利率和经营利润率是否能稳定或提升？

自由现金流质量如何？

资本开支是维护性投入，还是扩张性投入？

资产负债表是否能支撑长期扩张？
公司增长是否依赖少数大客户？
如果公司现在大幅投资，未来能否形成更高利润和现金流？
这个商业模式更像轻资产软件、重资产基础设施、周期品，还是平台型生意？

七、长期持有判断
请不要直接给“买/卖”建议，而是判断它是否具备长期跟踪或长期持有的条件。
请输出：
长期看好的核心逻辑
短期市场担心什么

哪些担心是合理的

哪些担心可能是市场过度反应

未来 3 年最重要的 5 个验证指标

一旦出现哪些信号，说明投资逻辑变了
什么情况下可以安心持有
什么情况下必须重新评估
这家公司适合什么类型的投资者，不适合什么类型的投资者

八、最后请给出一个结论
请用以下格式总结：
一句话判断这家公司真正的生意是什么。
一句话判断它最核心的护城河是什么。
一句话判断竞争对手最难复制的地方是什么。

一句话判断市场目前最担心什么。

一句话判断未来最值得验证的指标是什么。

最后给出一个结论：这家公司是“短期被高估的叙事”，还是“正在把投入转化为长期壁垒的公司”？请说明理由。"""


def _compact_text(value: Any, limit: int = 140) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    if not text:
        return ""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _format_metric(value: Any, suffix: str = "", digits: int = 1) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if suffix == "%":
            return f"{float(value) * 100:.{digits}f}%" if abs(float(value)) <= 1 else f"{float(value):.{digits}f}%"
        if suffix == "x":
            return f"{float(value):.{digits}f}x"
        return f"{float(value):.{digits}f}{suffix}"
    return f"{value}{suffix}"


def _first_sentence(text: str) -> str:
    if not text:
        return ""
    for sep in ("。", ".", "！", "!", "；", ";", "\n"):
        if sep in text:
            return text.split(sep, 1)[0].strip()
    return text.strip()


def _infer_business_model(stock_info: Dict[str, Any], fundamentals: Dict[str, Any]) -> str:
    summary = " ".join(
        str(part)
        for part in [
            stock_info.get("business_summary"),
            fundamentals.get("business_summary"),
            stock_info.get("sector"),
            stock_info.get("industry"),
            fundamentals.get("sector"),
            fundamentals.get("industry"),
        ]
        if part
    ).lower()

    if any(keyword in summary for keyword in ("platform", "marketplace", "ecosystem", "network", "平台", "生态")):
        return "平台公司"
    if any(keyword in summary for keyword in ("channel", "distribution", "dealer", "retail", "渠道", "经销")):
        return "渠道公司"
    if any(keyword in summary for keyword in ("infrastructure", "cloud", "datacenter", "data center", "power", "equipment", "foundry", "fab", "基础设施", "设备")):
        return "基础设施公司"
    if any(keyword in summary for keyword in ("resource", "mining", "oil", "gas", "commodity", "矿", "资源")):
        return "资源型公司"
    if any(keyword in summary for keyword in ("software", "saas", "subscription", "应用", "软件")):
        return "产品/订阅型公司"
    if "and" in summary or "叠加" in summary or "hybrid" in summary:
        return "多种模式叠加"
    return "产品公司"


def _company_peer_names(peers: Any) -> List[str]:
    names: List[str] = []
    for peer in peers or []:
        if isinstance(peer, dict):
            candidate = peer.get("name") or peer.get("symbol") or peer.get("code")
        else:
            candidate = str(peer)
        candidate = _compact_text(candidate, 40)
        if candidate and candidate not in names:
            names.append(candidate)
    return names


def _metric_fact(label: str, value: Any, suffix: str = "", digits: int = 1) -> Dict[str, str] | None:
    formatted = _format_metric(value, suffix=suffix, digits=digits)
    if not formatted:
        return None
    return {"claim": f"{label}为 {formatted}", "source": label, "confidence": "confirmed"}


# ========== 阶段一：确定性脚手架强化辅助函数 ==========

# 同行横向对比关注的财务字段
_PEER_METRIC_KEYS = ["market_cap", "gross_margin", "revenue_growth", "roe"]
_PEER_METRIC_LABELS = {
    "market_cap": "市值",
    "gross_margin": "毛利率",
    "revenue_growth": "营收增速",
    "roe": "ROE",
}


def _peer_metric_values(peers: Any, key: str) -> List[float]:
    """从 peers 列表提取指定财务字段的合法数值（nan 被排除）。"""
    values: List[float] = []
    for peer in peers or []:
        if not isinstance(peer, dict):
            continue
        value = peer.get(key)
        # value == value 排除 nan（nan != nan）
        if isinstance(value, (int, float)) and value == value:
            values.append(float(value))
    return values


def _peer_relative_strength(
    target_metrics: Dict[str, Any],
    peers: Any,
) -> Dict[str, Any]:
    """计算目标公司相对同行中位数的偏离，产出横向强弱信号。

    只消费 peer dict 里已存在的财务字段；某字段样本不足（<2 家含该字段）时跳过该字段。
    若所有字段都不可比，整体降级返回空 dict（不报错）。
    """
    comparisons: List[Dict[str, Any]] = []
    sample_sizes: List[int] = []
    for key in _PEER_METRIC_KEYS:
        peer_vals = _peer_metric_values(peers, key)
        if len(peer_vals) < 2:
            continue
        target_val = target_metrics.get(key)
        if not isinstance(target_val, (int, float)) or target_val != target_val:
            continue
        peer_median = float(np.median(peer_vals))
        direction = "above" if target_val > peer_median else "below"
        if key == "market_cap":
            if peer_median <= 0:
                continue
            comparisons.append({
                "metric": key,
                "target": target_val,
                "peer_median": peer_median,
                "ratio_vs_peer_median": round(target_val / peer_median, 2),
                "direction": direction,
            })
        else:
            comparisons.append({
                "metric": key,
                "target": round(target_val, 4),
                "peer_median": round(peer_median, 4),
                "diff_percentage_points": round((target_val - peer_median) * 100, 1),
                "direction": direction,
            })
        sample_sizes.append(len(peer_vals))

    if not comparisons:
        return {}

    summary_parts = []
    for comp in comparisons:
        label = _PEER_METRIC_LABELS.get(comp["metric"], comp["metric"])
        if comp["metric"] == "market_cap":
            summary_parts.append(f"{label}约为同行中位数的 {comp['ratio_vs_peer_median']}x")
        else:
            sign = "高" if comp["direction"] == "above" else "低"
            summary_parts.append(
                f"{label}{sign}于同行中位数约 {abs(comp['diff_percentage_points']):.1f} 个百分点"
            )
    return {
        "available": True,
        "peer_sample_size": min(sample_sizes) if sample_sizes else 0,
        "comparisons": comparisons,
        "summary": "；".join(summary_parts) + "。" if summary_parts else "",
    }


def _attack_budget_tiers(
    market_cap: Any,
    supply_chain_bottleneck: Any,
) -> Dict[str, Any]:
    """基于目标公司市值推断攻击者三档预算量级及对应攻击建议。

    微型股做下限保护；供应瓶颈强度影响正面进攻的现实性判断。
    market_cap 不可用时整体降级返回空。
    """
    if not isinstance(market_cap, (int, float)) or market_cap != market_cap or market_cap <= 0:
        return {}

    mc = float(market_cap)
    low = max(mc * 0.01, 10e6)
    mid = max(mc * 0.05, 50e6)
    high = max(mc * 0.20, 200e6)
    bottleneck = isinstance(supply_chain_bottleneck, (int, float)) and supply_chain_bottleneck >= 6

    def _tier(amount: float, focus: str, reach: str, angle: str) -> Dict[str, Any]:
        return {
            "budget": round(amount, 0),
            "first_year_focus": focus,
            "realistic_3_year_reach": reach,
            "recommended_angle": angle,
        }

    tiers = {
        "low": _tier(
            low,
            "复制最易标准化的产品功能或渠道流程，单点切入被忽视的细分场景。",
            "最多追平目标公司的非核心产品线或边缘渠道。",
            "绕开核心市场，主攻细分场景。",
        ),
        "mid": _tier(
            mid,
            "建立最小可行产能、启动关键认证、锁定首批头部客户。",
            "可追上目标公司的中等产品线或区域市场，但核心壁垒仍难撼动。"
            if bottleneck
            else "可追上目标公司部分产品线和渠道份额。",
            "绕开为主，局部正面试探。",
        ),
        "high": _tier(
            high,
            "全链路复制：产能、认证、渠道、品牌同时投入，正面竞争。",
            "可正面争夺核心市场份额，但"
            + ("产能/认证类壁垒仍需额外 2-3 年。" if bottleneck else "网络效应/客户锁定类壁垒仍难完全突破。"),
            "可正面进攻核心市场。",
        ),
    }
    return {
        "available": True,
        "target_market_cap": round(mc, 0),
        "tiers": tiers,
        "note": "预算量级基于目标公司市值推断，仅作为攻击模拟的参照基准。",
    }


# 假设键 → 业务模式/行业下的优先级映射表
def _assumption_priority(key: str, business_model: str, sector: str, industry: str) -> str:
    """根据业务模式和行业，给假设分配优先级 high/medium/low。"""
    s = " ".join(str(x).lower() for x in [sector, industry])
    is_cyclical = any(
        k in s
        for k in ("energy", "semiconductor", "commodity", "mining", "oil", "gas", "周期", "半导体", "能源", "矿业")
    )
    is_platform = "平台" in business_model
    is_infra = "基础设施" in business_model
    is_resource = "资源" in business_model
    is_product = "产品" in business_model and not is_platform

    table = {
        "customer_concentration": "high" if (is_product or is_platform) else "medium",
        "switching_cost": "high" if (is_platform or is_product) else "medium",
        "price_competition": "high" if is_product else ("medium" if is_platform else "low"),
        "capex_roi": "high" if (is_infra or is_resource or is_cyclical) else "medium",
        "regulatory": "high" if (is_infra or is_resource or "金融" in s or "financial" in s) else "medium",
        "supply_chain": "high" if (is_infra or is_resource or is_product) else ("low" if is_platform else "medium"),
        "substitute_tech": "high" if (is_product or is_platform) else "medium",
    }
    return table.get(key, "medium")


def _detect_cyclical(fundamentals: Dict[str, Any], sector: str, industry: str) -> Dict[str, Any]:
    """识别周期性行业公司，返回周期性警示（非周期则返回空）。"""
    s = " ".join(
        str(x).lower()
        for x in [sector, industry, fundamentals.get("business_summary") or ""]
    )
    cyclical_keywords = (
        "energy", "semiconductor", "commodity", "mining", "oil", "gas",
        "steel", "chemical", "shipping", "周期", "半导体", "能源", "矿业", "钢铁", "化工", "航运",
    )
    if any(k in s for k in cyclical_keywords):
        return {
            "is_cyclical": True,
            "caveat": (
                "该公司处于周期性行业，当前的高利润率或低估值可能反映周期位置而非稳态盈利能力，"
                "需结合产能周期、库存周期和产品价格周期交叉验证。"
            ),
        }
    return {}


def build_moat_stress_test(stock_info: Dict[str, Any], fundamentals: Dict[str, Any], peers: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    stock_info = stock_info or {}
    fundamentals = fundamentals or {}
    peers = peers or []

    company = stock_info.get("name") or stock_info.get("code") or "未知公司"
    code = stock_info.get("code") or fundamentals.get("code") or ""
    sector = stock_info.get("sector") or fundamentals.get("sector") or "未知行业"
    industry = stock_info.get("industry") or fundamentals.get("industry") or sector
    business_model = _infer_business_model(stock_info, fundamentals)
    business_summary = _compact_text(stock_info.get("business_summary") or fundamentals.get("business_summary"), 220)
    peer_names = _company_peer_names(peers)

    moat = fundamentals.get("moat")
    moat_overall_score = None
    moat_summary = ""
    moat_dims: List[str] = []
    if moat:
        if hasattr(moat, "overall_score"):
            moat_overall_score = getattr(moat, "overall_score", None)
            moat_summary = getattr(moat, "summary", "") or ""
            moat_dims = [getattr(d, "name", "") for d in getattr(moat, "dimensions", []) if getattr(d, "name", "")]
        else:
            moat_overall_score = moat.get("overall_score") if isinstance(moat, dict) else None
            moat_summary = (moat.get("summary", "") if isinstance(moat, dict) else "") or ""
            moat_dims = [d.get("name", "") for d in moat.get("dimensions", []) if isinstance(d, dict) and d.get("name")] if isinstance(moat, dict) else []

    supply_chain = fundamentals.get("supply_chain")
    supply_chain_topic = ""
    supply_chain_position = ""
    supply_chain_bottleneck = None
    supply_chain_level = ""
    if isinstance(supply_chain, dict) and supply_chain.get("status") in {"available", "fallback"}:
        supply_chain_topic = str(supply_chain.get("topic") or "")
        supply_chain_position = str(supply_chain.get("position") or "")
        supply_chain_bottleneck = supply_chain.get("bottleneck_score") or (supply_chain.get("target_layer") or {}).get("bottleneck_score")
        supply_chain_level = str(supply_chain.get("bottleneck_level") or (supply_chain.get("target_layer") or {}).get("bottleneck_level") or "")

    gross_margin = fundamentals.get("gross_margin")
    operating_margin = fundamentals.get("operating_margin")
    profit_margin = fundamentals.get("profit_margin")
    roe = fundamentals.get("roe")
    roa = fundamentals.get("roa")
    revenue_growth = fundamentals.get("revenue_growth")
    earnings_growth = fundamentals.get("earnings_growth")
    free_cashflow = fundamentals.get("free_cashflow")
    current_ratio = fundamentals.get("current_ratio")
    debt_equity = fundamentals.get("debt_equity")
    market_cap = fundamentals.get("market_cap")
    pe_forward = fundamentals.get("pe_forward")
    ps = fundamentals.get("ps")

    # 阶段一：同行相对强弱 + 三档预算攻击模拟 + 周期性识别
    target_metrics_for_peers = {
        "market_cap": market_cap,
        "gross_margin": gross_margin,
        "revenue_growth": revenue_growth,
        "roe": roe,
    }
    peer_relative_strength = _peer_relative_strength(target_metrics_for_peers, peers)
    attack_budget_tiers = _attack_budget_tiers(market_cap, supply_chain_bottleneck)
    cyclical = _detect_cyclical(fundamentals, sector, industry)

    confirmed_facts = [
        {"claim": f"研究对象为 {company}（{code or '代码未填'}）", "source": "stock_info.name/code", "confidence": "confirmed"},
        {"claim": f"业务语境为 {sector} / {industry}", "source": "stock_info.sector/industry", "confidence": "confirmed"},
        {"claim": f"业务模式暂归类为 {business_model}", "source": "business_summary + sector + industry", "confidence": "confirmed"},
    ]
    if business_summary:
        confirmed_facts.append({"claim": f"公开业务摘要：{_first_sentence(business_summary)}", "source": "fundamentals.business_summary", "confidence": "confirmed"})
    for label, value, suffix, digits in [
        ("gross_margin", gross_margin, "%", 1),
        ("operating_margin", operating_margin, "%", 1),
        ("profit_margin", profit_margin, "%", 1),
        ("roe", roe, "%", 1),
        ("roa", roa, "%", 1),
        ("revenue_growth", revenue_growth, "%", 1),
        ("earnings_growth", earnings_growth, "%", 1),
        ("free_cashflow", free_cashflow, "", 1),
        ("current_ratio", current_ratio, "x", 2),
        ("debt_equity", debt_equity, "x", 2),
        ("market_cap", market_cap, "", 0),
        ("pe_forward", pe_forward, "x", 2),
        ("ps", ps, "x", 2),
    ]:
        fact = _metric_fact(label, value, suffix=suffix, digits=digits)
        if fact:
            confirmed_facts.append(fact)
    if peer_names:
        confirmed_facts.append({"claim": f"当前同行对照样本包括 {', '.join(peer_names[:5])}", "source": "peers", "confidence": "confirmed"})
    if supply_chain_position or supply_chain_topic:
        confirmed_facts.append({"claim": f"供应链/产业链上下文：{supply_chain_position or supply_chain_topic}", "source": "fundamentals.supply_chain", "confidence": "confirmed"})
    if moat_summary:
        confirmed_facts.append({"claim": f"现有护城河摘要：{moat_summary}", "source": "fundamentals.moat.summary", "confidence": "confirmed"})

    reasonable_inferences: List[Dict[str, str]] = []
    if isinstance(gross_margin, (int, float)) and gross_margin >= 0.4:
        reasonable_inferences.append({"claim": f"毛利率约 {_format_metric(gross_margin, '%', 1)}，说明定价权或产品差异化至少已经部分成立。", "basis": "gross_margin", "confidence": "inferred"})
    if isinstance(operating_margin, (int, float)) and operating_margin >= 0.15:
        reasonable_inferences.append({"claim": f"经营利润率约 {_format_metric(operating_margin, '%', 1)}，说明规模化后利润池可能存在。", "basis": "operating_margin", "confidence": "inferred"})
    if isinstance(revenue_growth, (int, float)) and revenue_growth >= 0.15:
        reasonable_inferences.append({"claim": f"营收增长约 {_format_metric(revenue_growth, '%', 1)}，行业扩张或份额提升仍在发生。", "basis": "revenue_growth", "confidence": "inferred"})
    if isinstance(free_cashflow, (int, float)) and free_cashflow > 0:
        reasonable_inferences.append({"claim": "自由现金流为正，增长开始转化为现金而不只是规模。", "basis": "free_cashflow", "confidence": "inferred"})
    if isinstance(supply_chain_bottleneck, (int, float)) and supply_chain_bottleneck >= 6:
        reasonable_inferences.append({"claim": f"供应链/产业链瓶颈分约 {supply_chain_bottleneck:.0f}/10，进入该环节不仅要花钱，还要花时间、认证和产能。", "basis": "supply_chain.bottleneck_score", "confidence": "inferred"})
    if isinstance(moat_overall_score, (int, float)) and moat_overall_score >= 7:
        reasonable_inferences.append({"claim": f"现有护城河综合评分约 {moat_overall_score:.1f}/10，当前优势不只是短期叙事。", "basis": "fundamentals.moat.overall_score", "confidence": "inferred"})
    if len(peer_names) >= 3:
        reasonable_inferences.append({"claim": f"同行样本至少 {len(peer_names)} 家，说明竞争并不稀薄，必须用份额、成本和渠道数据验证优势。", "basis": "peers", "confidence": "inferred"})
    if peer_relative_strength and peer_relative_strength.get("summary"):
        reasonable_inferences.append({"claim": peer_relative_strength["summary"], "basis": "peer_relative_strength", "confidence": "inferred"})

    assumptions_to_verify = [
        {"key": "customer_concentration", "hypothesis": "客户集中度是否过高", "verification_path": "查年报、10-K/20-F、财报电话会、客户名单与应收账款说明", "risk_if_false": "少数客户一旦流失，收入和毛利率会同时承压"},
        {"key": "switching_cost", "hypothesis": "切换成本是否足够高", "verification_path": "查客户案例、实施周期、系统集成深度、合同年限、续约条款", "risk_if_false": "竞争对手可用更低价格快速抢单"},
        {"key": "price_competition", "hypothesis": "价格竞争是否会快速侵蚀毛利", "verification_path": "查毛利率趋势、ASP、行业报告、电话会对定价的描述", "risk_if_false": "高增长可能只是换来的低质量收入"},
        {"key": "capex_roi", "hypothesis": "资本开支是否真的转化为更高利润池", "verification_path": "查 capex 指引、投资者日、产能利用率、ROIC/FCF 趋势", "risk_if_false": "投入回报不足，壁垒无法兑现"},
        {"key": "regulatory", "hypothesis": "监管/牌照/认证门槛是否存在", "verification_path": "查监管文件、牌照清单、认证周期、客户准入标准", "risk_if_false": "资金更充足的对手可以直接复制"},
        {"key": "supply_chain", "hypothesis": "供应链卡位是否真实", "verification_path": "查上游采购、产能扩张周期、供应商集中度、交付周期", "risk_if_false": "瓶颈只是阶段性的，不是长期壁垒"},
        {"key": "substitute_tech", "hypothesis": "替代技术是否正在出现", "verification_path": "查行业报告、专利、产品路线图、竞品发布", "risk_if_false": "当前护城河会被新技术绕开"},
    ]
    # 按业务模式/行业赋予优先级
    for assumption in assumptions_to_verify:
        assumption["priority"] = _assumption_priority(
            assumption.get("key", ""), business_model, sector, industry
        )

    competitor_attack_vectors = []
    defense_signals = []
    unknowns = []
    if isinstance(gross_margin, (int, float)) and gross_margin < 0.35:
        competitor_attack_vectors.append("先打价格和渠道，用更低毛利快速抢份额。")
    else:
        competitor_attack_vectors.append("先复制最容易标准化的功能/流程，再用更低成本或更快交付切入。")
    if isinstance(supply_chain_bottleneck, (int, float)) and supply_chain_bottleneck >= 6:
        competitor_attack_vectors.append("若要正面进攻，优先攻击产能、认证和关键供应链节点，而不是只拼销售。")
    if peer_names:
        competitor_attack_vectors.append(f"重点比较并争夺 {peer_names[0]} 等可替代客户/场景。")
    defense_signals.extend([
        f"{company} 已经有公开业务定位和基本财务数据，可不是空壳叙事。",
        f"当前毛利率/增长/现金流数据至少能看出利润池线索。" if any(isinstance(v, (int, float)) for v in [gross_margin, revenue_growth, free_cashflow]) else "公开财务数据尚不足以判断利润池质量。",
    ])
    if moat_summary:
        defense_signals.append(f"现有护城河摘要指向：{moat_summary}")
    if supply_chain_position:
        defense_signals.append(f"产业链位置显示：{supply_chain_position}")
    if isinstance(free_cashflow, (int, float)):
        defense_signals.append("自由现金流为正" if free_cashflow > 0 else "自由现金流仍承压")
    if isinstance(moat_overall_score, (int, float)):
        defense_signals.append(f"护城河综合评分约 {moat_overall_score:.1f}/10")
    unknowns.extend([
        "客户集中度是否足够分散",
        "真实切换成本是否高到足以阻止价格战",
        "是否存在监管/牌照/认证门槛",
        "是否存在未披露的供应链卡位或产能锁定",
    ])

    structure_observations = [
        f"利润池要先看 {business_model} 的价值分配，而不是只看行业名字。",
        "竞争强度必须结合产品同质化、客户议价权和渠道结构判断。",
    ]
    if supply_chain_position:
        structure_observations.append(f"产业链位置：{supply_chain_position}")
    if isinstance(supply_chain_bottleneck, (int, float)):
        structure_observations.append(f"瓶颈强度：{supply_chain_bottleneck:.0f}/10（{supply_chain_level or '未细分'}）")
    if peer_names:
        structure_observations.append(f"同业比较样本：{', '.join(peer_names[:5])}")

    durability_signals = [
        f"业务模式暂归类为 {business_model}，若该分类成立，长期护城河更可能来自规模/流程/渠道/平台而非一次性故事。",
    ]
    if isinstance(moat_overall_score, (int, float)):
        durability_signals.append(f"现有 moat 综合评分约 {moat_overall_score:.1f}/10。")
    if isinstance(gross_margin, (int, float)):
        durability_signals.append(f"毛利率约 {_format_metric(gross_margin, '%', 1)}，可观察是否稳定。")
    if isinstance(free_cashflow, (int, float)):
        durability_signals.append("自由现金流为正，长期复利才有现金底座。" if free_cashflow > 0 else "自由现金流尚未稳定，长期壁垒需要更多验证。")
    if supply_chain_position:
        durability_signals.append(f"供应链位置偏向：{supply_chain_position}")

    fragility_signals = []
    if isinstance(pe_forward, (int, float)) and pe_forward >= 35:
        fragility_signals.append(f"Forward PE {pe_forward:.1f}x 偏高，市场已经提前定价。")
    if isinstance(ps, (int, float)) and ps >= 10:
        fragility_signals.append(f"PS {ps:.1f}x 偏高，估值对叙事依赖强。")
    if isinstance(free_cashflow, (int, float)) and free_cashflow <= 0:
        fragility_signals.append("自由现金流尚未转正，投入未必已转成壁垒。")
    if isinstance(operating_margin, (int, float)) and operating_margin < 0.1:
        fragility_signals.append("经营利润率不高，说明竞争压力或成本结构仍偏脆弱。")
    if len(peer_names) >= 3:
        fragility_signals.append("同业样本较多，说明复制/替代风险不低。")
    if isinstance(supply_chain_bottleneck, (int, float)) and supply_chain_bottleneck < 5:
        fragility_signals.append("供应链瓶颈分不高，卡位优势可能偏阶段性。")
    # 同业相对估值：若同行市盈率可得且显著低于目标公司，提示高估风险
    if peer_relative_strength and isinstance(pe_forward, (int, float)) and pe_forward > 0:
        peer_pe_vals = _peer_metric_values(peers, "pe_forward")
        if peer_pe_vals and len(peer_pe_vals) >= 2:
            peer_pe_median = float(np.median(peer_pe_vals))
            if peer_pe_median > 0 and pe_forward > peer_pe_median * 1.3:
                fragility_signals.append(
                    f"Forward PE {pe_forward:.1f}x 显著高于同行中位数约 {peer_pe_median:.1f}x，相对估值偏高。"
                )
    # 周期性公司的脆弱性提示
    if cyclical.get("is_cyclical"):
        fragility_signals.append("处于周期性行业，当前利润率/估值可能反映周期位置而非稳态。")

    market_fear = "市场担心估值先于壁垒兑现。"
    if fragility_signals:
        market_fear = fragility_signals[0]

    if isinstance(moat_overall_score, (int, float)) and moat_overall_score >= 7 and (isinstance(free_cashflow, (int, float)) and free_cashflow > 0) and (not isinstance(ps, (int, float)) or ps < 12):
        classification = "正在把投入转化为长期壁垒的公司"
        rationale = "护城河、现金流和利润率至少有两项同时指向可持续性。"
    elif isinstance(pe_forward, (int, float)) and pe_forward >= 35 and (isinstance(free_cashflow, (int, float)) and free_cashflow <= 0 or (isinstance(moat_overall_score, (int, float)) and moat_overall_score < 6)):
        classification = "短期被高估的叙事"
        rationale = "估值已经很高，但壁垒或现金流还没有同步验证。"
    else:
        classification = "需要进一步验证"
        rationale = "公开数据还不足以把叙事和壁垒彻底分开。"

    conclusion = {
        "one_line_business": f"{company} 的真正生意是 {business_model}，而不是简单的行业标签。",
        "one_line_moat": f"最核心的护城河目前更像是 {moat_summary or (', '.join(moat_dims[:3]) if moat_dims else '尚未完全验证的结构性优势')}。",
        "one_line_hardest_to_copy": f"竞争对手最难复制的地方是 {supply_chain_position or ('规模化后的客户关系和执行节奏' if business_model else '尚未充分验证')}。",
        "one_line_market_fear": market_fear,
        "one_line_verification": assumptions_to_verify[0]["hypothesis"],
        "classification": classification,
        "rationale": rationale,
    }
    if cyclical.get("is_cyclical"):
        conclusion["cyclical_caveat"] = cyclical["caveat"]

    prompt = MOAT_STRESS_TEST_PROMPT_TEMPLATE.format(company=company, industry=industry)

    return {
        "version": "1.0",
        "method": "deterministic_template",
        "prompt": prompt,
        "subject": {
            "company": company,
            "code": code,
            "sector": sector,
            "industry": industry,
            "business_model": business_model,
            "peer_count": len(peer_names),
        },
        "confirmed_facts": confirmed_facts,
        "reasonable_inferences": reasonable_inferences,
        "assumptions_to_verify": assumptions_to_verify,
        "peer_relative_strength": peer_relative_strength,
        "attack_budget_tiers": attack_budget_tiers,
        "perspectives": {
            "founder_competitor": {
                "prompt_role": "创业者/竞争对手",
                "attack_vectors": competitor_attack_vectors,
                "defense_signals": defense_signals,
                "unknowns": unknowns,
            },
            "industry_researcher": {
                "prompt_role": "产业研究员",
                "structure_observations": structure_observations,
                "profit_pool_hypotheses": [
                    "真正的利润池通常在瓶颈、标准、渠道控制、产能和客户认证更强的一侧。",
                    "如果毛利率高且现金流稳定，利润池更可能来自定价权或规模效应。",
                ],
                "unknowns": unknowns,
            },
            "long_term_investor": {
                "prompt_role": "长期投资者",
                "durability_signals": durability_signals,
                "fragility_signals": fragility_signals,
                "unknowns": unknowns,
                "conclusion": classification,
            },
        },
        "conclusion": conclusion,
        "metadata": {
            "business_summary": business_summary,
            "moat_overall_score": moat_overall_score,
            "moat_summary": moat_summary,
            "supply_chain_topic": supply_chain_topic,
            "supply_chain_position": supply_chain_position,
            "supply_chain_bottleneck_score": supply_chain_bottleneck,
        },
    }


class FundamentalAnalyzer(BaseAnalyzer):
    """
    基本面分析器
    
    角色：经验丰富的股票分析师、研究员
    """
    
    @property
    def name(self) -> str:
        return "基本面深度分析"
    
    @property
    def description(self) -> str:
        return "多维度财务分析与估值评估"
    
    def analyze(self, data: pd.DataFrame, fundamentals: Dict) -> AnalysisResult:
        """
        执行基本面分析
        
        Args:
            data: 历史行情数据（用于计算历史估值区间）
            fundamentals: 基本面数据字典
        """
        # 清洗 None 值
        fundamentals = {k: (v if v is not None else 0) for k, v in fundamentals.items()}
        # 文本字段特殊处理
        for k in ["sector", "industry", "website", "business_summary"]:
            if k in fundamentals and fundamentals[k] == 0:
                fundamentals[k] = ""
        # 解析财务指标
        metrics = self._parse_metrics(fundamentals)
        supply_chain_analysis = self._analyze_supply_chain_position(fundamentals)

        # 获取估值上下文（行业对比和历史区间）
        context = self._get_valuation_context(data, fundamentals)

        # 执行各维度分析
        business_analysis = self._analyze_business_model(fundamentals)
        financial_analysis = self._analyze_financial_health(metrics)
        valuation_analysis = self._analyze_valuation(metrics, context)
        growth_analysis = self._analyze_growth(metrics)

        # 综合评分
        score = self._calculate_overall_score(
            business_analysis,
            financial_analysis,
            valuation_analysis,
            growth_analysis
        )

        # 生成投资建议
        recommendation = self._generate_recommendation(
            score, metrics, valuation_analysis
        )

        details = {
            "business": business_analysis,
            "financial": financial_analysis,
            "valuation": valuation_analysis,
            "growth": growth_analysis,
            "metrics": metrics,
            "context": context,
        }
        if supply_chain_analysis:
            details["supply_chain"] = supply_chain_analysis

        return AnalysisResult(
            score=score,
            summary=recommendation["summary"],
            details=details,
            signals=recommendation["signals"],
            risks=recommendation["risks"]
        )
    
    def _analyze_supply_chain_position(self, fundamentals: Dict) -> Dict:
        """提取个股产业链卡位摘要，作为基本面分析的补充信息。"""
        supply_chain = fundamentals.get("supply_chain") or {}
        if not isinstance(supply_chain, dict):
            return {}
        if supply_chain.get("status") not in {"available", "fallback"}:
            return {}

        target_layer = supply_chain.get("target_layer") or {}
        return {
            "topic": supply_chain.get("topic", ""),
            "position": supply_chain.get("position", ""),
            "layer": target_layer.get("name", ""),
            "bottleneck_score": target_layer.get("bottleneck_score", supply_chain.get("bottleneck_score", 0)),
            "bottleneck_level": target_layer.get("bottleneck_level", supply_chain.get("bottleneck_level", "")),
            "supply_demand": target_layer.get("supply_demand", ""),
            "opportunities": list(supply_chain.get("opportunities", [])[:3]),
            "risks": list(supply_chain.get("risks", [])[:3]),
        }

    def _parse_metrics(self, fundamentals: Dict) -> FinancialMetrics:
        """解析财务指标"""
        return FinancialMetrics(
            gross_margin=self._safe_get(fundamentals, "gross_margin", 0) * 100,
            operating_margin=self._safe_get(fundamentals, "operating_margin", 0) * 100,
            profit_margin=self._safe_get(fundamentals, "profit_margin", 0) * 100,
            roe=self._safe_get(fundamentals, "roe", 0) * 100,
            roa=self._safe_get(fundamentals, "roa", 0) * 100,
            revenue_growth=self._safe_get(fundamentals, "revenue_growth", 0) * 100,
            earnings_growth=self._safe_get(fundamentals, "earnings_growth", 0) * 100,
            pe_ttm=self._safe_get(fundamentals, "pe_ttm", 0),
            pe_forward=self._safe_get(fundamentals, "pe_forward", 0),
            pb=self._safe_get(fundamentals, "pb", 0),
            ps=self._safe_get(fundamentals, "ps", 0),
            ev_ebitda=self._safe_get(fundamentals, "ev_ebitda", 0),
            current_ratio=self._safe_get(fundamentals, "current_ratio", 0),
            debt_equity=self._safe_get(fundamentals, "debt_equity", 0),
            free_cashflow=self._safe_get(fundamentals, "free_cashflow", 0)
        )
    
    def _safe_get(self, d: Dict, key: str, default: Any) -> Any:
        """安全获取字典值"""
        value = d.get(key, default)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return default
        return value
    
    def _get_valuation_context(
        self,
        data: pd.DataFrame,
        fundamentals: Dict
    ) -> ValuationContext:
        """获取估值上下文"""
        context = ValuationContext()
        
        # 根据行业设置基准
        sector = (fundamentals.get("sector") or "").lower()
        industry = (fundamentals.get("industry") or "").lower()
        
        # 不同行业的典型估值区间
        sector_multiples = {
            "technology": {"pe": 25, "pb": 4},
            "healthcare": {"pe": 20, "pb": 3},
            "financial": {"pe": 12, "pb": 1.2},
            "energy": {"pe": 10, "pb": 1.5},
            "consumer": {"pe": 18, "pb": 2.5},
            "industrials": {"pe": 16, "pb": 2}
        }
        
        for key, multiples in sector_multiples.items():
            if key in sector or key in industry:
                context.industry_avg_pe = multiples["pe"]
                context.industry_avg_pb = multiples["pb"]
                break
        
        # 历史估值区间（简化处理）
        context.historical_pe_low = context.industry_avg_pe * 0.6
        context.historical_pe_high = context.industry_avg_pe * 1.8
        context.historical_pb_low = context.industry_avg_pb * 0.5
        context.historical_pb_high = context.industry_avg_pb * 2
        
        return context
    
    def _analyze_business_model(self, fundamentals: Dict) -> Dict:
        """分析业务模式与核心竞争力"""
        summary = fundamentals.get("business_summary", "")
        sector = fundamentals.get("sector", "未知")
        industry = fundamentals.get("industry", "未知")
        market_cap = fundamentals.get("market_cap", 0)
        employees = fundamentals.get("employees", 0)
        
        # 市值规模分类
        if market_cap > 200e9:
            size = "大型蓝筹"
            size_rating = Rating.EXCELLENT
        elif market_cap > 10e9:
            size = "中型成长"
            size_rating = Rating.GOOD
        elif market_cap > 2e9:
            size = "小型潜力"
            size_rating = Rating.FAIR
        else:
            size = "微型风险"
            size_rating = Rating.POOR
        
        # 执行护城河深度分析
        moat_analysis = self._assess_moat(fundamentals)

        return {
            "sector": sector,
            "industry": industry,
            "market_cap_tier": size,
            "market_cap_rating": size_rating.value,
            "employees": employees,
            "business_summary": summary[:500] if summary else "暂无",
            "moat": moat_analysis,
            "moat_indicators": [d.name for d in moat_analysis.dimensions if d.score >= 6]
        }
    
    def _assess_moat(self, fundamentals: Dict) -> MoatAnalysis:
        """
        评估护城河 - 6维度量化评分系统

        维度：
        1. 技术壁垒 (Tech Barrier) - R&D投入、专利密度
        2. 品牌优势 (Brand Strength) - 毛利率溢价、ROE
        3. 规模效应 (Scale Advantage) - 市值、营收规模
        4. 网络效应 (Network Effect) - 用户增长、平台属性
        5. 客户锁定 (Customer Lock-in) - 转换成本、复购率
        6. 可持续性 (Sustainability) - 现金流稳定性、增长持续性
        """
        dimensions = []

        # 1. 技术壁垒评分
        tech_score = self._rate_tech_barrier(fundamentals)
        dimensions.append(MoatDimension(
            name="技术壁垒",
            score=tech_score,
            rating=self._score_to_rating(tech_score),
            evidence=self._tech_evidence(fundamentals, tech_score)
        ))

        # 2. 品牌优势评分
        brand_score = self._rate_brand_strength(fundamentals)
        dimensions.append(MoatDimension(
            name="品牌优势",
            score=brand_score,
            rating=self._score_to_rating(brand_score),
            evidence=self._brand_evidence(fundamentals, brand_score)
        ))

        # 3. 规模效应评分
        scale_score = self._rate_scale_advantage(fundamentals)
        dimensions.append(MoatDimension(
            name="规模效应",
            score=scale_score,
            rating=self._score_to_rating(scale_score),
            evidence=self._scale_evidence(fundamentals, scale_score)
        ))

        # 4. 网络效应评分
        network_score = self._rate_network_effect(fundamentals)
        dimensions.append(MoatDimension(
            name="网络效应",
            score=network_score,
            rating=self._score_to_rating(network_score),
            evidence=self._network_evidence(fundamentals, network_score)
        ))

        # 5. 客户锁定评分
        lockin_score = self._rate_customer_lockin(fundamentals)
        dimensions.append(MoatDimension(
            name="客户锁定",
            score=lockin_score,
            rating=self._score_to_rating(lockin_score),
            evidence=self._lockin_evidence(fundamentals, lockin_score)
        ))

        # 6. 可持续性评分
        sustain_score = self._rate_sustainability(fundamentals)
        dimensions.append(MoatDimension(
            name="可持续性",
            score=sustain_score,
            rating=self._score_to_rating(sustain_score),
            evidence=self._sustain_evidence(fundamentals, sustain_score)
        ))

        # 计算综合评分 (加权平均)
        weights = {
            "技术壁垒": 0.20,
            "品牌优势": 0.20,
            "规模效应": 0.15,
            "网络效应": 0.15,
            "客户锁定": 0.15,
            "可持续性": 0.15,
        }

        overall_score = sum(
            d.score * weights.get(d.name, 1/6)
            for d in dimensions
        )

        overall_rating = self._score_to_rating(overall_score)

        # 生成总结
        strong_dims = [d.name for d in dimensions if d.score >= 7]
        weak_dims = [d.name for d in dimensions if d.score < 4]

        if overall_score >= 7:
            summary = f"护城河深厚，核心优势：{'、'.join(strong_dims)}"
        elif overall_score >= 5:
            summary = f"护城河中等，{'、'.join(strong_dims) if strong_dims else '有一定竞争优势'}"
        elif overall_score >= 3:
            summary = f"护城河较弱，需关注：{'、'.join(weak_dims) if weak_dims else '竞争力可持续性'}"
        else:
            summary = "护城河薄弱，竞争优势不明显"

        return MoatAnalysis(
            overall_score=round(overall_score, 1),
            overall_rating=overall_rating,
            dimensions=dimensions,
            summary=summary
        )

    # ========== 护城河各维度评分方法 ==========

    def _rate_tech_barrier(self, fundamentals: Dict) -> float:
        """技术壁垒评分 (0-10)"""
        score = 5.0  # 基础分

        # R&D投入比例 (如果数据可用)
        rd_ratio = fundamentals.get("rd_ratio", 0)
        if rd_ratio > 0.15:
            score += 2.5
        elif rd_ratio > 0.08:
            score += 1.5
        elif rd_ratio > 0.03:
            score += 0.5

        # 毛利率高通常意味着技术溢价
        gross_margin = fundamentals.get("gross_margin", 0)
        if gross_margin > 0.6:
            score += 2.0
        elif gross_margin > 0.4:
            score += 1.0

        # 高ROE可能来自技术壁垒
        roe = fundamentals.get("roe", 0)
        if roe > 0.20:
            score += 0.5

        return min(10.0, score)

    def _rate_brand_strength(self, fundamentals: Dict) -> float:
        """品牌优势评分 (0-10)"""
        score = 5.0

        # 毛利率是品牌溢价的直接体现
        gross_margin = fundamentals.get("gross_margin", 0)
        if gross_margin > 0.5:
            score += 3.0
        elif gross_margin > 0.35:
            score += 2.0
        elif gross_margin > 0.20:
            score += 1.0

        # 净利率反映品牌带来的定价权
        profit_margin = fundamentals.get("profit_margin", 0)
        if profit_margin > 0.15:
            score += 1.5
        elif profit_margin > 0.08:
            score += 0.5

        # 市值规模 (大品牌通常市值更大)
        market_cap = fundamentals.get("market_cap", 0)
        if market_cap > 100e9:
            score += 0.5

        return min(10.0, score)

    def _rate_scale_advantage(self, fundamentals: Dict) -> float:
        """规模效应评分 (0-10)"""
        score = 5.0

        # 市值规模
        market_cap = fundamentals.get("market_cap", 0)
        if market_cap > 500e9:
            score += 3.0
        elif market_cap > 100e9:
            score += 2.0
        elif market_cap > 10e9:
            score += 1.0

        # 营收规模 (如果数据可用)
        revenue = fundamentals.get("revenue", 0)
        if revenue > 50e9:
            score += 1.5
        elif revenue > 10e9:
            score += 0.5

        # 运营利润率反映规模效应
        operating_margin = fundamentals.get("operating_margin", 0)
        if operating_margin > 0.20:
            score += 1.0

        return min(10.0, score)

    def _rate_network_effect(self, fundamentals: Dict) -> float:
        """网络效应评分 (0-10)"""
        score = 5.0

        # 行业判断 (科技/平台类公司更可能有网络效应)
        sector = (fundamentals.get("sector") or "").lower()
        industry = (fundamentals.get("industry") or "").lower()

        network_sectors = ["technology", "communication", "software", "platform", "internet"]
        is_network_sector = any(s in sector or s in industry for s in network_sectors)

        if is_network_sector:
            score += 2.0

        # 营收增长快可能暗示网络效应
        revenue_growth = fundamentals.get("revenue_growth", 0)
        if revenue_growth > 0.30:
            score += 2.0
        elif revenue_growth > 0.15:
            score += 1.0

        # 高毛利率 + 高增长 = 可能的网络效应
        gross_margin = fundamentals.get("gross_margin", 0)
        if gross_margin > 0.5 and revenue_growth > 0.20:
            score += 1.0

        return min(10.0, score)

    def _rate_customer_lockin(self, fundamentals: Dict) -> float:
        """客户锁定评分 (0-10)"""
        score = 5.0

        # 高毛利率 + 稳定收入 = 客户锁定
        gross_margin = fundamentals.get("gross_margin", 0)
        revenue_growth = fundamentals.get("revenue_growth", 0)

        if gross_margin > 0.4:
            score += 1.5

        # 稳定的增长意味着客户留存好
        if 0.05 < revenue_growth < 0.25:
            score += 1.0

        # 高ROE可能来自客户粘性
        roe = fundamentals.get("roe", 0)
        if roe > 0.15:
            score += 1.5
        elif roe > 0.10:
            score += 0.5

        # 低负债 + 高现金流 = 商业模式健康
        debt_equity = fundamentals.get("debt_equity", 0)
        if debt_equity < 50:
            score += 1.0

        return min(10.0, score)

    def _rate_sustainability(self, fundamentals: Dict) -> float:
        """可持续性评分 (0-10)"""
        score = 5.0

        # 现金流稳定性
        free_cashflow = fundamentals.get("free_cashflow", 0)
        if free_cashflow > 1e9:
            score += 2.5
        elif free_cashflow > 0:
            score += 1.5

        # 健康的财务结构
        current_ratio = fundamentals.get("current_ratio", 0)
        if current_ratio > 2:
            score += 1.5
        elif current_ratio > 1.5:
            score += 0.5

        debt_equity = fundamentals.get("debt_equity", 0)
        if debt_equity < 30:
            score += 1.5
        elif debt_equity < 60:
            score += 0.5

        # 持续的增长能力
        revenue_growth = fundamentals.get("revenue_growth", 0)
        earnings_growth = fundamentals.get("earnings_growth", 0)
        if revenue_growth > 0.10 and earnings_growth > 0.10:
            score += 1.0

        return min(10.0, score)

    # ========== 评分辅助方法 ==========

    def _score_to_rating(self, score: float) -> str:
        """分数转评级"""
        if score >= 8: return "优秀"
        elif score >= 6: return "良好"
        elif score >= 4: return "一般"
        elif score >= 2: return "较弱"
        return "薄弱"

    def _tech_evidence(self, fundamentals: Dict, score: float) -> str:
        """技术壁垒证据说明"""
        rd_ratio = fundamentals.get("rd_ratio", 0)
        gm = fundamentals.get("gross_margin", 0)
        if score >= 7:
            return f"R&D投入{rd_ratio*100:.1f}%，毛利率{gm*100:.1f}%，技术溢价显著"
        elif score >= 5:
            return f"有一定技术积累，毛利率{gm*100:.1f}%"
        return "技术壁垒不明显，产品同质化风险"

    def _brand_evidence(self, fundamentals: Dict, score: float) -> str:
        """品牌优势证据说明"""
        gm = fundamentals.get("gross_margin", 0)
        pm = fundamentals.get("profit_margin", 0)
        if score >= 7:
            return f"强品牌定价权，毛利率{gm*100:.1f}%，净利率{pm*100:.1f}%"
        elif score >= 5:
            return f"品牌有一定认知度，毛利率{gm*100:.1f}%"
        return "品牌溢价能力有限，价格竞争激烈"

    def _scale_evidence(self, fundamentals: Dict, score: float) -> str:
        """规模效应证据说明"""
        mc = fundamentals.get("market_cap", 0) / 1e9
        if score >= 7:
            return f"行业龙头，市值${mc:.0f}B，规模优势明显"
        elif score >= 5:
            return f"中等规模，市值${mc:.0f}B"
        return "规模较小，成本优势有限"

    def _network_evidence(self, fundamentals: Dict, score: float) -> str:
        """网络效应证据说明"""
        rg = fundamentals.get("revenue_growth", 0)
        if score >= 7:
            return f"强网络效应，营收增长{rg*100:.1f}%，用户自驱动增长"
        elif score >= 5:
            return f"有一定平台属性，营收增长{rg*100:.1f}%"
        return "网络效应不明显，线性增长模式"

    def _lockin_evidence(self, fundamentals: Dict, score: float) -> str:
        """客户锁定证据说明"""
        roe = fundamentals.get("roe", 0)
        if score >= 7:
            return f"高客户粘性，ROE {roe*100:.1f}%，转换成本高"
        elif score >= 5:
            return f"客户留存尚可，ROE {roe*100:.1f}%"
        return "客户忠诚度一般，易被替代"

    def _sustain_evidence(self, fundamentals: Dict, score: float) -> str:
        """可持续性证据说明"""
        fcf = fundamentals.get("free_cashflow", 0) / 1e6
        de = fundamentals.get("debt_equity", 0)
        if score >= 7:
            return f"商业模式稳健，FCF ${fcf:.0f}M，负债率{de:.1f}%"
        elif score >= 5:
            return f"经营基本稳定，FCF ${fcf:.0f}M"
        return "现金跑道有限，需关注融资能力"
    
    def _analyze_financial_health(self, metrics: FinancialMetrics) -> Dict:
        """分析财务健康与盈利能力"""
        # 盈利能力评级
        profitability_score = self._rate_profitability(metrics)
        
        # 财务结构评级
        structure_score = self._rate_financial_structure(metrics)
        
        # 现金流健康度
        cashflow_rating = self._rate_cashflow(metrics)
        
        return {
            "profitability": {
                "score": profitability_score,
                "gross_margin": {"value": metrics.gross_margin, "rating": self._rate_margin(metrics.gross_margin, 30, 50)},
                "operating_margin": {"value": metrics.operating_margin, "rating": self._rate_margin(metrics.operating_margin, 10, 20)},
                "profit_margin": {"value": metrics.profit_margin, "rating": self._rate_margin(metrics.profit_margin, 8, 15)},
                "roe": {"value": metrics.roe, "rating": self._rate_roe(metrics.roe)},
                "roa": {"value": metrics.roa, "rating": self._rate_roa(metrics.roa)}
            },
            "financial_structure": {
                "score": structure_score,
                "current_ratio": {"value": metrics.current_ratio, "rating": self._rate_current_ratio(metrics.current_ratio)},
                "debt_equity": {"value": metrics.debt_equity, "rating": self._rate_debt_equity(metrics.debt_equity)}
            },
            "cashflow": cashflow_rating
        }
    
    def _rate_profitability(self, metrics: FinancialMetrics) -> int:
        """盈利能力评分"""
        score = 0
        if metrics.gross_margin > 40: score += 20
        elif metrics.gross_margin > 25: score += 15
        elif metrics.gross_margin > 15: score += 10
        
        if metrics.profit_margin > 15: score += 20
        elif metrics.profit_margin > 8: score += 15
        elif metrics.profit_margin > 3: score += 10
        
        if metrics.roe > 20: score += 20
        elif metrics.roe > 15: score += 15
        elif metrics.roe > 10: score += 10
        elif metrics.roe > 5: score += 5
        
        return min(score, 60)
    
    def _rate_margin(self, value: float, good: float, excellent: float) -> str:
        if value > excellent: return Rating.EXCELLENT.value
        elif value > good: return Rating.GOOD.value
        elif value > 0: return Rating.FAIR.value
        return Rating.POOR.value
    
    def _rate_roe(self, roe: float) -> str:
        if roe > 20: return Rating.EXCELLENT.value
        elif roe > 15: return Rating.GOOD.value
        elif roe > 10: return Rating.FAIR.value
        elif roe > 0: return Rating.POOR.value
        return Rating.UNKNOWN.value
    
    def _rate_roa(self, roa: float) -> str:
        if roa > 10: return Rating.EXCELLENT.value
        elif roa > 6: return Rating.GOOD.value
        elif roa > 3: return Rating.FAIR.value
        elif roa > 0: return Rating.POOR.value
        return Rating.UNKNOWN.value
    
    def _rate_financial_structure(self, metrics: FinancialMetrics) -> int:
        """财务结构评分"""
        score = 0
        if metrics.current_ratio > 2: score += 20
        elif metrics.current_ratio > 1.5: score += 15
        elif metrics.current_ratio > 1: score += 10
        
        if metrics.debt_equity < 50: score += 20
        elif metrics.debt_equity < 100: score += 15
        elif metrics.debt_equity < 200: score += 10
        
        return score
    
    def _rate_current_ratio(self, ratio: float) -> str:
        if ratio > 2: return Rating.EXCELLENT.value
        elif ratio > 1.5: return Rating.GOOD.value
        elif ratio > 1: return Rating.FAIR.value
        return Rating.POOR.value
    
    def _rate_debt_equity(self, de: float) -> str:
        if de < 50: return Rating.EXCELLENT.value
        elif de < 100: return Rating.GOOD.value
        elif de < 200: return Rating.FAIR.value
        return Rating.POOR.value
    
    def _rate_cashflow(self, metrics: FinancialMetrics) -> str:
        if metrics.free_cashflow > 1e9: return Rating.EXCELLENT.value
        elif metrics.free_cashflow > 0: return Rating.GOOD.value
        return Rating.POOR.value
    
    def _analyze_valuation(
        self,
        metrics: FinancialMetrics,
        context: ValuationContext
    ) -> Dict:
        """估值分析 - 横向+纵向对比"""
        # 横向对比（行业对比）
        pe_vs_industry = self._compare_pe(metrics.pe_ttm, context.industry_avg_pe)
        pb_vs_industry = self._compare_pb(metrics.pb, context.industry_avg_pb)
        
        # 纵向对比（历史区间）
        pe_percentile = self._calculate_percentile(
            metrics.pe_ttm,
            context.historical_pe_low,
            context.historical_pe_high
        )
        pb_percentile = self._calculate_percentile(
            metrics.pb,
            context.historical_pb_low,
            context.historical_pb_high
        )
        
        # 综合估值评级
        valuation_rating = self._rate_overall_valuation(
            pe_vs_industry, pb_vs_industry, pe_percentile, pb_percentile
        )
        
        return {
            "pe_analysis": {
                "current": round(metrics.pe_ttm, 2),
                "industry_avg": context.industry_avg_pe,
                "vs_industry": pe_vs_industry,
                "historical_percentile": round(pe_percentile * 100, 1)
            },
            "pb_analysis": {
                "current": round(metrics.pb, 2),
                "industry_avg": context.industry_avg_pb,
                "vs_industry": pb_vs_industry,
                "historical_percentile": round(pb_percentile * 100, 1)
            },
            "other_metrics": {
                "ps": round(metrics.ps, 2),
                "ev_ebitda": round(metrics.ev_ebitda, 2),
                "forward_pe": round(metrics.pe_forward, 2)
            },
            "overall_rating": valuation_rating,
            "margin_of_safety": self._calculate_safety_margin(
                pe_percentile, pb_percentile
            )
        }
    
    def _compare_pe(self, pe: float, industry_avg: float) -> str:
        if pe <= 0 or industry_avg <= 0:
            return "无法比较"
        ratio = pe / industry_avg
        if ratio < 0.7: return "显著低估"
        elif ratio < 0.9: return "相对低估"
        elif ratio < 1.1: return "估值合理"
        elif ratio < 1.3: return "相对高估"
        return "显著高估"
    
    def _compare_pb(self, pb: float, industry_avg: float) -> str:
        if pb <= 0 or industry_avg <= 0:
            return "无法比较"
        ratio = pb / industry_avg
        if ratio < 0.7: return "显著低估"
        elif ratio < 0.9: return "相对低估"
        elif ratio < 1.1: return "估值合理"
        elif ratio < 1.3: return "相对高估"
        return "显著高估"
    
    def _calculate_percentile(self, value: float, low: float, high: float) -> float:
        """计算在历史区间的百分位"""
        if value <= 0 or high <= low:
            return 0.5
        percentile = (value - low) / (high - low)
        return max(0, min(1, percentile))
    
    def _rate_overall_valuation(self, pe_vs: str, pb_vs: str, pe_p: float, pb_p: float) -> str:
        """综合估值评级"""
        if "低估" in pe_vs and "低估" in pb_vs:
            return "低估"
        elif "高估" in pe_vs or "高估" in pb_vs:
            if pe_p > 0.8 or pb_p > 0.8:
                return "显著高估"
            return "相对高估"
        elif pe_p < 0.3 and pb_p < 0.3:
            return "低估区间"
        elif pe_p > 0.7 and pb_p > 0.7:
            return "高估区间"
        return "估值合理"
    
    def _calculate_safety_margin(self, pe_p: float, pb_p: float) -> str:
        """计算安全边际"""
        avg_p = (pe_p + pb_p) / 2
        if avg_p < 0.25: return "高安全边际"
        elif avg_p < 0.4: return "中等安全边际"
        elif avg_p < 0.6: return "安全边际一般"
        elif avg_p < 0.75: return "安全边际较低"
        return "安全边际不足"
    
    def _analyze_growth(self, metrics: FinancialMetrics) -> Dict:
        """成长性分析"""
        # 收入增长评级
        revenue_rating = self._rate_growth(metrics.revenue_growth)
        earnings_rating = self._rate_growth(metrics.earnings_growth)
        
        # PEG 估值
        peg = self._calculate_peg(metrics.pe_ttm, metrics.earnings_growth)
        
        return {
            "revenue_growth": {
                "value": round(metrics.revenue_growth, 2),
                "rating": revenue_rating
            },
            "earnings_growth": {
                "value": round(metrics.earnings_growth, 2),
                "rating": earnings_rating
            },
            "peg_ratio": round(peg, 2) if peg else None,
            "peg_rating": self._rate_peg(peg)
        }
    
    def _rate_growth(self, growth: float) -> str:
        if growth > 30: return Rating.EXCELLENT.value
        elif growth > 15: return Rating.GOOD.value
        elif growth > 5: return Rating.FAIR.value
        elif growth > 0: return "低增长"
        return "负增长"
    
    def _calculate_peg(self, pe: float, growth: float) -> float:
        """计算PEG比率"""
        if pe <= 0 or growth <= 0:
            return None
        return pe / growth
    
    def _rate_peg(self, peg: float) -> str:
        if peg is None:
            return "无法计算"
        if peg < 1: return "显著低估"
        elif peg < 1.5: return "相对低估"
        elif peg < 2: return "估值合理"
        return "相对高估"
    
    def _calculate_overall_score(
        self,
        business: Dict,
        financial: Dict,
        valuation: Dict,
        growth: Dict
    ) -> float:
        """计算综合评分"""
        # 盈利能力权重 30%
        profitability_score = financial["profitability"]["score"]
        
        # 估值合理性权重 25%
        valuation_score = self._valuation_to_score(valuation["overall_rating"])
        
        # 成长性权重 20%
        growth_score = self._growth_to_score(growth)
        
        # 财务结构权重 15%
        structure_score = financial["financial_structure"]["score"]
        
        # 业务质量权重 10% - 使用护城河综合评分
        moat = business.get("moat")
        if moat:
            business_score = moat.overall_score * 10  # 0-10分 -> 0-100分
        else:
            business_score = 50 if business["market_cap_rating"] == "优秀" else 40
        
        total = (profitability_score * 0.3 +
                valuation_score * 0.25 +
                growth_score * 0.2 +
                structure_score * 0.15 +
                business_score * 0.1)
        
        return round(total, 1)
    
    def _valuation_to_score(self, rating: str) -> float:
        scores = {
            "低估": 90,
            "显著低估": 95,
            "相对低估": 80,
            "估值合理": 60,
            "相对高估": 40,
            "显著高估": 25,
            "高估区间": 35
        }
        return scores.get(rating, 50)
    
    def _growth_to_score(self, growth: Dict) -> float:
        earnings = growth.get("earnings_growth", {}).get("value", 0)
        revenue = growth.get("revenue_growth", {}).get("value", 0)
        avg_growth = (earnings + revenue) / 2 if earnings and revenue else max(earnings, revenue)
        
        if avg_growth > 30: return 90
        elif avg_growth > 20: return 80
        elif avg_growth > 10: return 65
        elif avg_growth > 5: return 50
        elif avg_growth > 0: return 35
        return 20
    
    def _generate_recommendation(
        self,
        score: float,
        metrics: FinancialMetrics,
        valuation: Dict
    ) -> Dict:
        """生成投资建议"""
        signals = []
        risks = []
        
        # 根据评分生成观点
        if score >= 80:
            view = "看好"
            summary = f"基本面优秀，估值{valuation['overall_rating']}，值得重点关注"
        elif score >= 65:
            view = "谨慎看好"
            summary = f"基本面良好，估值{valuation['overall_rating']}，可考虑分批建仓"
        elif score >= 50:
            view = "中性"
            summary = "基本面一般，建议观望或等待更好时机"
        else:
            view = "看空"
            summary = "基本面存在明显问题，建议规避"
        
        # 交易信号
        if valuation["overall_rating"] in ["低估", "显著低估"]:
            signals.append(f"估值处于{valuation['margin_of_safety']}区间，中长期配置价值显现")
        
        if metrics.roe > 15 and metrics.profit_margin > 10:
            signals.append("ROE与净利率双高，盈利能力强劲")
        
        if metrics.revenue_growth > 20:
            signals.append("营收高速增长，成长动能充足")
        
        # 风险警示
        if metrics.debt_equity > 150:
            risks.append("负债率偏高，财务杠杆风险需关注")
        
        if metrics.current_ratio < 1:
            risks.append("流动比率低于1，短期偿债压力较大")
        
        if valuation["overall_rating"] in ["高估", "显著高估"]:
            risks.append("当前估值偏高，存在回调风险")
        
        if metrics.earnings_growth < 0:
            risks.append("盈利负增长，基本面承压")
        
        if not risks:
            risks.append("市场整体波动风险")
        
        return {
            "view": view,
            "summary": summary,
            "signals": signals,
            "risks": risks
        }