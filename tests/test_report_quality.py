import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer.report_generator import ReportGenerator
from analyzer.report_quality import ReportQualityEvaluator


def _minimal_market_data():
    return {
        "stock_info": {"price": 100.0, "sector": "Technology", "industry": "Software"},
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


def test_report_quality_flags_missing_sections_and_duplicate_ordinals():
    result = ReportQualityEvaluator().evaluate(
        "## 一、核心观点\n\nResearch Score：70/100\nTiming State：Ready\n\n"
        "## 一、重复章节\n\n正文\n"
    )

    codes = {issue.code for issue in result.issues}
    assert not result.passed
    assert "missing_sections" in codes
    assert "duplicate_section_ordinals" in codes


def test_report_quality_warns_when_action_omits_score_timing_split():
    markdown = "\n\n".join([
        "## 一、核心观点\n\nResearch Score：70/100\nTiming State：Ready",
        "## 二、技术分析\n\n正文",
        "## 三、基本面分析\n\n正文",
        "## 四、市场情绪\n\n正文",
        "## 五、市场结构\n\n正文",
        "## 六、催化因素\n\n正文",
        "## 七、操作建议\n\n建议买入，但没有拆分公司质量与入场时机。",
    ])

    result = ReportQualityEvaluator().evaluate(markdown)

    assert result.passed
    assert {issue.code for issue in result.issues} == {"action_without_score_timing"}


def test_generated_report_passes_report_quality_checks():
    report = ReportGenerator.generate("TEST.US", _minimal_market_data())

    result = ReportQualityEvaluator().evaluate(report)

    assert result.passed, result.to_markdown()
