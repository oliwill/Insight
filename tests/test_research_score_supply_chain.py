import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer.research_score import ResearchScoreEngine


BASE_MARKET_DATA = {
    "stock_info": {
        "sector": "Technology",
        "industry": "Semiconductors",
        "price": 100.0,
    },
    "fundamentals": {
        "gross_margin": 0.45,
        "roe": 0.18,
        "revenue_growth": 0.12,
        "pe_forward": 18.0,
        "ps": 3.0,
        "target_mean_price": 120.0,
    },
    "peers": [{"symbol": "AMD"}],
    "web_search": {},
    "liquidity": {},
}


def test_research_score_is_unchanged_without_supply_chain_data():
    engine = ResearchScoreEngine()

    before = engine.score(deepcopy(BASE_MARKET_DATA), [])
    after = engine.score(deepcopy(BASE_MARKET_DATA), [])

    assert after.total_base_score == before.total_base_score
    assert after.total_adjusted_score == before.total_adjusted_score
    assert after.dimensions["行业/TAM"].data_evidence == before.dimensions["行业/TAM"].data_evidence
    assert after.dimensions["护城河"].data_evidence == before.dimensions["护城河"].data_evidence


def test_research_score_adds_supply_chain_evidence_when_available():
    market_data = deepcopy(BASE_MARKET_DATA)
    market_data["supply_chain"] = {
        "status": "available",
        "topic": "hbm",
        "position": "位于 HBM 产业链芯片/器件层。",
        "bottleneck_score": 6,
        "bottleneck_level": "中等瓶颈",
        "target_layer": {
            "name": "芯片/器件（核心元件）",
            "bottleneck_score": 6,
            "bottleneck_level": "中等瓶颈",
            "supply_demand": "tight",
            "expansion_difficulty": "high",
        },
        "opportunities": ["AI GPU 对 HBM 需求增长"],
    }

    score = ResearchScoreEngine().score(market_data, [])

    tam_evidence = "；".join(score.dimensions["行业/TAM"].data_evidence)
    moat_evidence = "；".join(score.dimensions["护城河"].data_evidence)
    growth_evidence = "；".join(score.dimensions["增长质量"].data_evidence)

    assert "产业链" in tam_evidence
    assert "HBM" in tam_evidence or "hbm" in tam_evidence
    assert "瓶颈" in moat_evidence
    assert "HBM" in growth_evidence or "hbm" in growth_evidence or "产业链" in growth_evidence
    assert score.dimensions["行业/TAM"].base_score >= 5.0
    assert score.dimensions["护城河"].base_score >= 5.0
