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


def test_report_title_uses_stock_name_and_code():
    markdown = ReportGenerator.generate(
        "AAPL.US",
        {
            "stock_info": {
                "code": "AAPL.US",
                "name": "Apple Inc.",
                "price": 190.0,
            }
        },
    )

    assert markdown.startswith("# Apple Inc. (AAPL.US)")


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

    assert "## 三、基本面分析" not in markdown
    assert "## 四、市场情绪" not in markdown
    assert "## 五、市场结构" not in markdown
    assert "## 数据缺口" in markdown


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
