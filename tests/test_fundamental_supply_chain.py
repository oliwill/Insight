import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from analyzer.fundamental import FundamentalAnalyzer


def test_fundamental_analyzer_includes_supply_chain_details_when_available():
    result = FundamentalAnalyzer().analyze(
        pd.DataFrame(),
        {
            "sector": "Technology",
            "industry": "Semiconductors",
            "market_cap": 100_000_000_000,
            "gross_margin": 0.38,
            "roe": 0.12,
            "supply_chain": {
                "status": "available",
                "topic": "hbm",
                "position": "位于 HBM 产业链芯片/器件层。",
                "target_layer": {
                    "name": "芯片/器件（核心元件）",
                    "bottleneck_score": 6,
                    "bottleneck_level": "中等瓶颈",
                    "supply_demand": "tight",
                },
                "opportunities": ["AI GPU 对 HBM 需求增长"],
                "risks": ["存储周期波动"],
            },
        },
    )

    assert "supply_chain" in result.details
    assert result.details["supply_chain"]["topic"] == "hbm"
    assert result.details["supply_chain"]["bottleneck_score"] == 6
    assert "HBM" in result.details["supply_chain"]["position"]


def test_fundamental_analyzer_omits_supply_chain_details_when_missing():
    result = FundamentalAnalyzer().analyze(
        pd.DataFrame(),
        {
            "sector": "Technology",
            "industry": "Software",
            "market_cap": 10_000_000_000,
        },
    )

    assert "supply_chain" not in result.details
