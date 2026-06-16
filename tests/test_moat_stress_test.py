"""build_moat_stress_test 阶段一强化逻辑的单元测试。

覆盖：
- 同行相对强弱（含字段缺失安全降级）
- 三档预算攻击模拟（含市值缺失降级、微型股下限保护）
- 假设行业化优先级
- 周期性公司识别
- 结论分类稳定性
"""
import math

from analyzer.fundamental import (
    build_moat_stress_test,
    _peer_relative_strength,
    _attack_budget_tiers,
    _assumption_priority,
    _detect_cyclical,
)


# ========== 同行相对强弱 ==========

def test_peer_relative_strength_with_full_peer_financials():
    peers = [
        {"name": "A", "gross_margin": 0.30, "revenue_growth": 0.10, "market_cap": 50e9},
        {"name": "B", "gross_margin": 0.28, "revenue_growth": 0.08, "market_cap": 40e9},
        {"name": "C", "gross_margin": 0.32, "revenue_growth": 0.12, "market_cap": 60e9},
    ]
    target = {"gross_margin": 0.45, "revenue_growth": 0.25, "market_cap": 100e9, "roe": 0.18}
    result = _peer_relative_strength(target, peers)
    assert result.get("available") is True
    comparisons = result.get("comparisons") or []
    metrics = {c["metric"] for c in comparisons}
    # roe 在 peers 中缺失，应被跳过；其余三个应出现
    assert "gross_margin" in metrics
    assert "revenue_growth" in metrics
    assert "market_cap" in metrics
    assert "roe" not in metrics
    # 目标全面高于中位数
    assert all(c["direction"] == "above" for c in comparisons)


def test_peer_relative_strength_degrades_when_peer_financials_missing():
    # peers 只有 ticker（生产数据源真实形态），无财务字段
    peers = [{"ticker": "A"}, {"ticker": "B"}, {"ticker": "C"}]
    target = {"gross_margin": 0.45, "revenue_growth": 0.25}
    result = _peer_relative_strength(target, peers)
    # 所有字段样本不足，整体降级
    assert result == {}


def test_peer_relative_strength_degrades_when_single_peer():
    # 只有 1 家 peer，不满足 <2 的阈值
    peers = [{"name": "A", "gross_margin": 0.30}]
    target = {"gross_margin": 0.45}
    result = _peer_relative_strength(target, peers)
    assert result == {}


def test_peer_relative_strength_handles_nan_peer_values():
    peers = [
        {"name": "A", "gross_margin": float("nan"), "revenue_growth": 0.10},
        {"name": "B", "gross_margin": 0.28, "revenue_growth": 0.08},
    ]
    target = {"revenue_growth": 0.25}
    result = _peer_relative_strength(target, peers)
    # revenue_growth 可比（2 家有值），gross_margin 因 nan 被排除后只剩 1 家有效值也跳过
    comparisons = result.get("comparisons") or []
    metrics = {c["metric"] for c in comparisons}
    assert "revenue_growth" in metrics
    assert "gross_margin" not in metrics


# ========== 三档预算攻击模拟 ==========

def test_attack_budget_tiers_scales_with_market_cap():
    large = _attack_budget_tiers(100e9, None)
    small = _attack_budget_tiers(1e9, None)
    assert large["tiers"]["high"]["budget"] > small["tiers"]["high"]["budget"]
    assert large["tiers"]["low"]["budget"] > small["tiers"]["low"]["budget"]
    # 比例关系：low≈1%, mid≈5%, high≈20%
    mc = 100e9
    assert math.isclose(large["tiers"]["low"]["budget"], mc * 0.01, rel_tol=0.01)
    assert math.isclose(large["tiers"]["mid"]["budget"], mc * 0.05, rel_tol=0.01)
    assert math.isclose(large["tiers"]["high"]["budget"], mc * 0.20, rel_tol=0.01)


def test_attack_budget_tiers_floor_protection_for_micro_cap():
    # 微型股市值极低，三档预算应被下限保护
    result = _attack_budget_tiers(1e6, None)
    assert result["tiers"]["low"]["budget"] >= 10e6
    assert result["tiers"]["mid"]["budget"] >= 50e6
    assert result["tiers"]["high"]["budget"] >= 200e6


def test_attack_budget_tiers_degrades_without_market_cap():
    assert _attack_budget_tiers(None, None) == {}
    assert _attack_budget_tiers(0, None) == {}
    assert _attack_budget_tiers(-1, None) == {}
    assert _attack_budget_tiers(float("nan"), None) == {}


def test_attack_budget_tiers_bottleneck_affects_high_tier_reach():
    with_bottleneck = _attack_budget_tiers(50e9, 7)
    without_bottleneck = _attack_budget_tiers(50e9, 3)
    # 有供应瓶颈时，高预算的三年可达应提到"产能/认证"类壁垒
    assert "产能" in with_bottleneck["tiers"]["high"]["realistic_3_year_reach"]
    assert "网络效应" in without_bottleneck["tiers"]["high"]["realistic_3_year_reach"]


# ========== 假设行业化优先级 ==========

def test_assumption_priority_for_product_company():
    # 产品公司：客户集中度、切换成本、价格竞争应为 high
    assert _assumption_priority("customer_concentration", "产品公司", "Technology", "Software") == "high"
    assert _assumption_priority("switching_cost", "产品公司", "Technology", "Software") == "high"
    assert _assumption_priority("price_competition", "产品公司", "Technology", "Software") == "high"


def test_assumption_priority_for_platform_company():
    # 平台公司：客户集中度 high，价格竞争 medium，供应链 low
    assert _assumption_priority("customer_concentration", "平台公司", "Technology", "Internet") == "high"
    assert _assumption_priority("price_competition", "平台公司", "Technology", "Internet") == "medium"
    assert _assumption_priority("supply_chain", "平台公司", "Technology", "Internet") == "low"


def test_assumption_priority_for_infra_company():
    # 基础设施公司：capex、监管、供应链应为 high
    assert _assumption_priority("capex_roi", "基础设施公司", "Industrials", "Datacenter") == "high"
    assert _assumption_priority("regulatory", "基础设施公司", "Industrials", "Datacenter") == "high"
    assert _assumption_priority("supply_chain", "基础设施公司", "Industrials", "Datacenter") == "high"


def test_assumption_priority_for_cyclical_sector():
    # 周期性行业（半导体）即使业务模式不含"基础设施"，capex_roi 也应为 high
    assert _assumption_priority("capex_roi", "产品公司", "Technology", "Semiconductor") == "high"


# ========== 周期性公司识别 ==========

def test_detect_cyclical_semiconductor():
    result = _detect_cyclical({}, "Technology", "Semiconductor Memory")
    assert result.get("is_cyclical") is True
    assert "周期" in result["caveat"]


def test_detect_cyclical_energy():
    result = _detect_cyclical({}, "Energy", "Oil & Gas")
    assert result.get("is_cyclical") is True


def test_detect_cyclical_non_cyclical():
    result = _detect_cyclical({}, "Consumer", "Beverages")
    assert result == {}


def test_detect_cyclical_via_business_summary():
    # business_summary 含周期性关键词应触发
    result = _detect_cyclical({"business_summary": "半导体存储器制造"}, "Technology", "Tech")
    assert result.get("is_cyclical") is True
    # business_summary 不含任何周期性关键词则不触发
    result2 = _detect_cyclical({"business_summary": "生产存储芯片"}, "Technology", "Tech")
    assert result2 == {}


# ========== build_moat_stress_test 集成 ==========

def test_build_moat_stress_test_full_rich_output():
    result = build_moat_stress_test(
        {"name": "Micron", "code": "MU.US", "sector": "Technology", "industry": "Semiconductor Memory"},
        {
            "market_cap": 120e9, "gross_margin": 0.38, "operating_margin": 0.18,
            "revenue_growth": 0.25, "roe": 0.16, "pe_forward": 14, "ps": 3, "free_cashflow": 5e9,
        },
        [
            {"name": "WDC", "gross_margin": 0.30, "revenue_growth": 0.10, "pe_forward": 12},
            {"name": "SNDK", "gross_margin": 0.28, "revenue_growth": 0.08, "pe_forward": 11},
        ],
    )
    # 新增字段存在
    assert result["peer_relative_strength"]["available"] is True
    assert result["attack_budget_tiers"]["available"] is True
    # 周期性识别触发
    assert result["conclusion"].get("cyclical_caveat") is not None
    # 假设都有 priority
    for assumption in result["assumptions_to_verify"]:
        assert "priority" in assumption
        assert assumption["priority"] in {"high", "medium", "low"}
    # peer_relative_strength 推进到 inferences
    inferences_basis = [i.get("basis") for i in result["reasonable_inferences"]]
    assert "peer_relative_strength" in inferences_basis


def test_build_moat_stress_test_full_degradation_with_empty_inputs():
    result = build_moat_stress_test(
        {"name": "X", "sector": "Consumer"},
        {},
        [{"ticker": "A"}, {"ticker": "B"}],
    )
    # 全部降级
    assert result["peer_relative_strength"] == {}
    assert result["attack_budget_tiers"] == {}
    assert "cyclical_caveat" not in result["conclusion"]
    # 核心字段仍存在
    assert "confirmed_facts" in result
    assert "assumptions_to_verify" in result
    assert "prompt" in result


def test_build_moat_stress_test_priority_sortable_and_complete():
    result = build_moat_stress_test(
        {"name": "P", "sector": "Technology", "industry": "Software"},
        {"market_cap": 10e9, "gross_margin": 0.7, "business_summary": "SaaS platform"},
        [],
    )
    # 平台类业务应识别出来
    priorities = {a["key"]: a["priority"] for a in result["assumptions_to_verify"]}
    assert priorities["customer_concentration"] == "high"
    assert priorities["price_competition"] == "medium"
