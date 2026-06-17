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


def test_research_score_preserves_behavior_with_moat_stress_test_field():
    market_data = deepcopy(BASE_MARKET_DATA)
    market_data["fundamentals"]["moat_stress_test"] = {
        "version": "1.0",
        "method": "deterministic_template",
        "confirmed_facts": [],
        "reasonable_inferences": [],
        "assumptions_to_verify": [],
        "perspectives": {},
    }

    score = ResearchScoreEngine().score(market_data, [])

    assert score.total_base_score > 0
    assert score.total_adjusted_score > 0
    assert "护城河" in score.dimensions
