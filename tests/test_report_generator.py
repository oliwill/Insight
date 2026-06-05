import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer.report_generator import ReportGenerator
from config import Config


def test_wyckoff_chart_link_uses_configured_charts_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "WIKI_BASE_DIR", tmp_path)
    monkeypatch.setattr(Config, "WIKI_SUBDIR", "4_Trader/Analysis")
    charts_dir = tmp_path / "Charts"
    charts_dir.mkdir()
    (charts_dir / "01060_HK_wyckoff.png").write_bytes(b"fake image")

    markdown = ReportGenerator._format_wyckoff_chart("01060.HK")

    assert "../../Charts/01060_HK_wyckoff.png" in markdown


def test_wyckoff_chart_link_is_omitted_when_chart_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "WIKI_BASE_DIR", tmp_path)
    monkeypatch.setattr(Config, "WIKI_SUBDIR", "4_Trader/Analysis")

    markdown = ReportGenerator._format_wyckoff_chart("01060.HK")

    assert markdown == ""


def test_report_title_uses_code_then_stock_name():
    markdown = ReportGenerator.generate(
        "AAPL.US",
        {
            "_generated_at": "2026-06-02T14:42:31.574199",
            "stock_info": {
                "code": "AAPL.US",
                "name": "Apple Inc.",
                "price": 190.0,
            }
        },
    )

    assert markdown.startswith("# AAPL.US Apple Inc.\n\n**数据时间**：2026-06-02 14:42")


def test_report_omits_empty_optional_modules():
    markdown = ReportGenerator.generate(
        "EMPTY.US",
        {
            "stock_info": {
                "code": "EMPTY.US",
                "name": "Empty Co",
                "price": 10.0,
            },
            "fundamentals": {},
            "technicals": {},
            "liquidity": {},
            "options": {},
            "web_search": {},
        },
    )

    assert "## 三、基本面与估值" not in markdown
    assert "## 八、市场情绪" not in markdown
    assert "## 五、市场结构" not in markdown
    assert "## 数据缺口" in markdown


def test_report_summary_prioritizes_interpretation_before_details():
    markdown = ReportGenerator.generate(
        "MRVL.US",
        {
            "_generated_at": "2026-06-02T14:42:31.574199",
            "stock_info": {
                "code": "MRVL.US",
                "name": "Marvell Technology",
                "price": 219.43,
                "change_pct": 7.04,
            },
            "fundamentals": {
                "pe_forward": 35.9,
                "ps": 22.0,
                "revenue_growth": 0.276,
                "gross_margin": 0.515,
                "free_cashflow": 2_269_700_096,
                "target_mean_price": 222.55,
            },
            "technicals": {
                "trend_short": "BULLISH",
                "trend_mid": "BULLISH",
                "rsi_14": 72.56,
                "pct_from_high": -2.54,
            },
            "liquidity": {"daily_dollar_volume": 6_051_634_735.55},
            "options": {},
            "earnings": {},
            "web_search": {},
        },
    )

    assert "## 一、本次分析总结" in markdown
    assert "**一句话判断**" in markdown
    assert "### 关键判断" in markdown
    assert "趋势较强，但 RSI 72.6 已过热" in markdown
    assert markdown.index("**数据时间**") < markdown.index("## 一、本次分析总结")
    assert markdown.index("## 三、基本面与估值") < markdown.index("## 四、买点与技术结构")
    assert markdown.index("## 六、交易计划") < markdown.index("## 七、催化与风险")


def test_chart_gallery_includes_extra_chart(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "WIKI_BASE_DIR", tmp_path)
    monkeypatch.setattr(Config, "WIKI_SUBDIR", "4_Trader/Analysis")
    charts_dir = tmp_path / "Charts"
    charts_dir.mkdir()
    chart_path = charts_dir / "AAPL_US_price.png"
    chart_path.write_bytes(b"fake image")

    markdown = ReportGenerator.generate(
        "AAPL.US",
        {
            "stock_info": {"code": "AAPL.US", "name": "Apple Inc.", "price": 190.0},
            "technicals": {"ma20": 180.0},
            "charts": [{"title": "价格走势", "path": chart_path}],
        },
    )

    assert "### 价格走势" in markdown
    assert "![价格走势](../../Charts/AAPL_US_price.png)" in markdown
