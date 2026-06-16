"""Batch A focused tests for evidence extraction and core scoring/timing APIs.

这些测试只覆盖 Batch A 新增模块的可导入性与最小运行行为，
避免依赖 Obsidian 路径、外部网络、yfinance 或 wiki 写入逻辑。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from input.evidence import EvidenceExtractor, EvidenceItem
from analyzer.research_score import ResearchScoreEngine
from analyzer.timing_engine import TimingEngine


EXPECTED_TIMING_STATES = {"Ready", "Wait", "Watch", "Avoid"}


def _minimal_market_data():
    """构造最小可运行的市场数据，专门供核心评分/时机引擎测试使用。"""
    return {
        "stock_info": {
            "price": 100.0,
            "sector": "Technology",
            "industry": "Software",
        },
        "fundamentals": {
            "revenue_growth": 0.20,
            "earnings_growth": 0.18,
            "gross_margin": 0.55,
            "free_cashflow": 1_000_000,
            "ps": 3.0,
            "pe_forward": 18.0,
            "target_mean_price": 130.0,
            "insider_signal": "neutral",
            "sbc_ratio": 0.08,
        },
        "peers": [{"symbol": "PEER1"}],
        "liquidity": {
            "daily_dollar_volume": 60_000_000,
            "insider_ownership": 0.12,
        },
        "technicals": {
            "trend_short": "BULLISH",
            "trend_mid": "BULLISH",
            "rsi_14": 55.0,
            "vol_ratio": 1.0,
            "ma20": 98.0,
            "ma50": 96.0,
            "support_20d": 97.0,
            "pct_from_high": -12.0,
        },
        "wyckoff": {
            "phase": "Markup",
            "support": 95.0,
            "resistance": 110.0,
            "confidence": 80,
        },
        "earnings": {},
        "options": {},
        "web_search": {},
    }


def test_batch_a_exports_import():
    """验证 Batch A 对外暴露的类可以从轻量模块直接导入。"""
    assert EvidenceExtractor.__name__ == "EvidenceExtractor"
    assert EvidenceItem.__name__ == "EvidenceItem"
    assert ResearchScoreEngine.__name__ == "ResearchScoreEngine"
    assert TimingEngine.__name__ == "TimingEngine"



def test_package_roots_do_not_eagerly_import_unrelated_modules():
    """验证包入口不会为核心评分能力提前加载无关重依赖。"""
    import importlib

    for module_name in [
        "input",
        "input.ingest",
        "analyzer",
        "analyzer.fundamental",
        "analyzer.comprehensive",
        "analyzer.wyckoff",
    ]:
        sys.modules.pop(module_name, None)

    input_package = importlib.import_module("input")
    analyzer_package = importlib.import_module("analyzer")

    assert input_package.EvidenceExtractor.__name__ == "EvidenceExtractor"
    assert analyzer_package.ResearchScoreEngine.__name__ == "ResearchScoreEngine"
    assert "input.ingest" not in sys.modules
    assert "analyzer.fundamental" not in sys.modules
    assert "analyzer.comprehensive" not in sys.modules
    assert "analyzer.wyckoff" not in sys.modules



def test_evidence_item_to_dict_returns_expected_keys():
    """验证 EvidenceItem.to_dict() 的字段集合稳定，便于后续序列化消费。"""
    item = EvidenceItem(
        claim="Valuation multiple is compressing while growth stays above 20%.",
        evidence_type="fact",
        source_type="filing",
        credibility="high",
        affected_dimensions=["估值"],
        score_impact="up",
        timestamp="2026-05-21",
        source_title="10-Q",
        source_path="/tmp/mock-10q.md",
        note="Test note",
    )

    data = item.to_dict()

    assert set(data) == {
        "claim",
        "evidence_type",
        "source_type",
        "credibility",
        "affected_dimensions",
        "score_impact",
        "timestamp",
        "source_title",
        "source_path",
        "note",
    }
    assert data["claim"] == item.claim
    assert data["affected_dimensions"] == ["估值"]
    assert data["score_impact"] == "up"



def test_research_score_applies_evidence_adjustment_to_named_dimension():
    """验证 ResearchScoreEngine 会把结构化证据作用到指定维度，而不是只返回静态基础分。"""
    engine = ResearchScoreEngine()
    market_data = _minimal_market_data()

    positive_item = EvidenceItem(
        claim="Valuation reset improves margin of safety.",
        credibility="high",
        affected_dimensions=["估值"],
        score_impact="up",
    )
    negative_item = EvidenceItem(
        claim="Valuation remains stretched versus peers.",
        credibility="high",
        affected_dimensions=["估值"],
        score_impact="down",
    )

    positive_result = engine.score(market_data, [positive_item])
    negative_result = engine.score(market_data, [negative_item])

    positive_dimension = positive_result.dimensions["估值"]
    negative_dimension = negative_result.dimensions["估值"]

    assert positive_dimension.base_score == negative_dimension.base_score
    assert positive_dimension.adjusted_score > positive_dimension.base_score
    assert negative_dimension.adjusted_score < negative_dimension.base_score
    assert "Valuation reset improves margin of safety." in positive_dimension.obsidian_evidence
    assert "上调" in positive_dimension.adjustment_reason
    assert "下调" in negative_dimension.adjustment_reason



def test_timing_engine_analyze_returns_supported_state():
    """验证 TimingEngine.analyze() 在最小输入下可运行，并返回预期状态集合中的值。"""
    engine = TimingEngine()

    result = engine.analyze(_minimal_market_data(), research_score=70)

    assert hasattr(result, "state")
    assert result.state in EXPECTED_TIMING_STATES
    assert isinstance(result.internal_score, int)
    assert isinstance(result.reasons, list)
    assert isinstance(result.entry_triggers, list)
    assert isinstance(result.invalidation_triggers, list)
