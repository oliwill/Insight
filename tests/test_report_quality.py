import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer.report_generator import ReportGenerator
from analyzer.report_quality import ReportQualityEvaluator, evaluate_report_quality


def test_quality_evaluator_accepts_generated_report_with_disclosed_gaps():
    market_data = {
        "stock_info": {
            "code": "AAPL.US",
            "name": "Apple Inc.",
            "price": 190.0,
        },
        "fundamentals": {},
        "technicals": {},
        "liquidity": {},
        "options": {},
        "earnings": {},
        "web_search": {},
    }
    markdown = ReportGenerator.generate("AAPL.US", market_data)

    quality = ReportGenerator.evaluate_quality(markdown, market_data)

    assert quality.passed is True
    assert quality.issues == []


def test_quality_evaluator_flags_research_score_timing_confusion():
    markdown = ReportGenerator.generate(
        "AAPL.US",
        {
            "stock_info": {
                "code": "AAPL.US",
                "name": "Apple Inc.",
                "price": 190.0,
            }
        },
    ).replace("**Research Score**：50.0/100", "**Research Score**：Ready")

    quality = ReportQualityEvaluator().evaluate(markdown, {})

    assert quality.passed is False
    assert any(issue.code == "research_timing_mixed" for issue in quality.issues)
    assert any(issue.code == "research_score_not_numeric" for issue in quality.issues)


def test_quality_evaluator_requires_data_gap_disclosure_for_failed_modules():
    markdown = """# Apple Inc. (AAPL.US)

## 一、核心观点

**Research Score**：70/100
**Timing State**：Ready

### 证据摘要
- 有结构化证据

### 交易时机
- **状态**：Ready

## 七、操作建议
等待触发条件。

**免责声明**：本分析仅供参考，不构成投资建议。
"""

    quality = evaluate_report_quality(
        markdown,
        {
            "fundamentals_error": "Yahoo timeout",
            "technicals": {"ma20": 180.0},
            "earnings": {"next_earnings_date": "2026-08-01"},
            "liquidity": {"daily_dollar_volume": 100_000_000},
            "options": {"put_call_ratio": 0.8},
            "web_search": {"news": [{"title": "headline"}]},
        },
    )

    assert quality.passed is False
    assert any(issue.code == "data_gaps_not_disclosed" for issue in quality.issues)
