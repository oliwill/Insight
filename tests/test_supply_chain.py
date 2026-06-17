import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.supply_chain import StockChainAnalyzer


def test_stock_chain_analyzer_maps_micron_to_hbm_without_cache(tmp_path):
    analyzer = StockChainAnalyzer(cache_dir=tmp_path)

    result = analyzer.analyze(
        "MU.US",
        stock_info={
            "code": "MU.US",
            "name": "Micron Technology",
            "sector": "Technology",
            "industry": "Semiconductors",
        },
        fundamentals={
            "business_summary": "Micron makes DRAM, NAND and high bandwidth memory products."
        },
    )

    assert result["status"] == "available"
    assert result["source"] == "knowledge_base"
    assert result["topic"] == "hbm"
    assert result["target_layer"]["name"] == "芯片/器件（核心元件）"
    assert result["bottleneck_score"] >= 5
    assert "Micron" in " ".join(result["key_peers"])
    assert result["position"]


def test_stock_chain_analyzer_returns_unknown_skeleton_for_unmapped_company(tmp_path):
    analyzer = StockChainAnalyzer(cache_dir=tmp_path)

    result = analyzer.analyze(
        "ZZZZ.US",
        stock_info={
            "code": "ZZZZ.US",
            "name": "Unknown Widgets",
            "sector": "Industrials",
            "industry": "Specialty Widgets",
        },
        fundamentals={"business_summary": "Makes specialty widgets."},
    )

    assert result["status"] in {"unknown", "fallback"}
    assert result["source"] == "deterministic_fallback"
    assert result["topic"] in {"specialty widgets", "industrials", "ZZZZ.US"}
    assert isinstance(result["layers"], list)
    assert "error" not in result


def test_stock_chain_analyzer_uses_cache_topic_override(tmp_path):
    cache_dir = tmp_path
    cache_dir.mkdir(exist_ok=True)
    (cache_dir / "TEST_US.json").write_text(
        """
        {
          "topic": "gpu",
          "company_aliases": ["TEST"],
          "target_layer_name": "芯片/器件（核心元件）",
          "opportunities": ["缓存中的上行机会"],
          "risks": ["缓存中的风险"]
        }
        """,
        encoding="utf-8",
    )
    analyzer = StockChainAnalyzer(cache_dir=cache_dir)

    result = analyzer.analyze(
        "TEST.US",
        stock_info={"code": "TEST.US", "name": "Test GPU Co"},
        fundamentals={},
    )

    assert result["status"] == "available"
    assert result["source"] == "cache"
    assert result["topic"] == "gpu"
    assert result["target_layer"]["name"] == "芯片/器件（核心元件）"
    assert "缓存中的上行机会" in result["opportunities"]
    assert "缓存中的风险" in result["risks"]


def test_stock_chain_analyzer_never_requires_external_llm_or_network(tmp_path, monkeypatch):
    analyzer = StockChainAnalyzer(cache_dir=tmp_path)
    monkeypatch.setattr(analyzer, "_load_cache", lambda code: None)

    result = analyzer.analyze(
        "NVDA.US",
        stock_info={"code": "NVDA.US", "name": "NVIDIA", "industry": "Semiconductors"},
        fundamentals={"business_summary": "GPU accelerators for AI."},
    )

    assert result["topic"] == "gpu"
    assert result["status"] == "available"


def test_stock_chain_analyzer_matches_layer_key_companies_before_bottleneck_fallback(tmp_path):
    analyzer = StockChainAnalyzer(cache_dir=tmp_path)

    result = analyzer.analyze(
        "ASML.US",
        stock_info={"code": "ASML.US", "name": "ASML", "industry": "Semiconductor Equipment"},
        fundamentals={"business_summary": "ASML supplies lithography systems for semiconductor manufacturing."},
    )

    assert result["topic"] == "ai 半导体"
    assert result["target_layer"]["name"] == "设备（制造设备/测试设备）"
    assert "ASML" in " ".join(result["key_peers"])
