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
    from types import SimpleNamespace

    research_stub = SimpleNamespace(
        total_adjusted_score=50.0,
        dimensions={},
        verdict="观察",
        confidence="low",
    )
    markdown = ReportGenerator.generate(
        "AAPL.US",
        {
            "stock_info": {
                "code": "AAPL.US",
                "name": "Apple Inc.",
                "price": 190.0,
            }
        },
        research_score=research_stub,
    ).replace("| **Research Score** | 50.0/100 🟡 |", "| **Research Score** | Ready |")

    assert "| **Research Score** | Ready |" in markdown

    quality = ReportQualityEvaluator().evaluate(markdown, {})

    assert quality.passed is False
    assert any(issue.code == "research_timing_mixed" for issue in quality.issues)
    assert any(issue.code == "research_score_not_numeric" for issue in quality.issues)


def test_quality_evaluator_requires_data_gap_disclosure_for_failed_modules():
    markdown = """# AAPL.US Apple Inc.

**数据时间**：2026-06-02 14:42

## 一、本次分析总结

| 项目 | 结论 |
|---|---|
| **Research Score** | 70/100 |
| **Timing State** | Ready |

### 证据摘要
- 有结构化证据

## 六、交易计划
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


FULL_REPORT_SAMPLE = """# SH688035 德邦科技 — 完整版分析报告2026.08.18

## 一、公司与催化剂
## 二、基本面与增长质量
## 五、技术面
## 九、操作格网
## 十一、催化剂日历
## 综合评估
> **免责声明**：仅供研究参考。
"""


def test_full_report_markers_pass_on_11_section_format():
    from analyzer.report_quality import ReportQualityEvaluator

    result = ReportQualityEvaluator().evaluate(FULL_REPORT_SAMPLE, {})
    assert result.passed, [i.message for i in result.issues]


def test_full_report_missing_catalyst_section_flagged():
    from analyzer.report_quality import ReportQualityEvaluator

    broken = FULL_REPORT_SAMPLE.replace("## 十一、催化剂日历", "## 十一、占位")
    result = ReportQualityEvaluator().evaluate(broken, {})
    assert not result.passed
    assert any(i.code == "catalyst_section" for i in result.issues)
