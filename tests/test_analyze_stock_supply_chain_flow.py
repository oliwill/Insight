import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer.report_generator import ReportGenerator
from analyzer.research_score import ResearchScoreEngine


def test_full_report_path_accepts_supply_chain_market_data():
    market_data = {
        "_generated_at": "2026-06-12T09:30:00",
        "stock_info": {
            "code": "MU.US",
            "name": "Micron Technology",
            "price": 120.0,
            "sector": "Technology",
            "industry": "Semiconductor Memory",
        },
        "fundamentals": {
            "pe_forward": 12.5,
            "pb": 2.1,
            "gross_margin": 0.38,
            "revenue_growth": 0.18,
            "target_mean_price": 145.0,
        },
        "technicals": {
            "trend_short": "BULLISH",
            "rsi_14": 55.0,
            "support_20d": 110.0,
            "resistance_20d": 130.0,
        },
        "liquidity": {},
        "options": {},
        "earnings": {},
        "web_search": {},
        "peers": [{"symbol": "WDC"}],
        "supply_chain": {
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
            "risks": ["存储周期波动"],
        },
    }

    research_score = ResearchScoreEngine().score(market_data, [])
    markdown = ReportGenerator.generate("MU.US", market_data, research_score=research_score)

    assert "### 产业链位置" in markdown
    assert "### 五维分析" in markdown
    assert "行业/TAM" in markdown
    assert "护城河" in markdown
    assert "## 六、操作建议" in markdown
