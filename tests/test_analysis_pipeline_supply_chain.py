import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data.analysis_pipeline as pipeline


class FakeDataManager:
    def get_stock_info(self, code):
        return SimpleNamespace(
            code=code,
            name="Micron Technology",
            market="US",
            price=120.0,
            change_pct=1.2,
            currency="USD",
            sector="Technology",
            industry="Semiconductors",
        )

    def get_fundamentals(self, code):
        return {
            "business_summary": "Micron makes DRAM, NAND and high bandwidth memory.",
            "pe_forward": 12.5,
            "pb": 2.1,
            "ps": 3.0,
        }

    def get_historical_data(self, code, period="1y"):
        return None

    def get_source_status(self):
        return {"fake": "ok"}


class FakeMemoryManager:
    def __init__(self, base_dir=None):
        self.base_dir = base_dir

    def get_stock_context(self, code):
        return ""


def test_generate_analysis_adds_supply_chain_without_breaking_existing_keys(monkeypatch):
    monkeypatch.setattr(pipeline, "DataManager", lambda: FakeDataManager())
    monkeypatch.setattr(pipeline, "MemoryManager", lambda base_dir=None: FakeMemoryManager(base_dir))

    result = pipeline.generate_analysis("MU.US")

    assert result["stock_info"]["name"] == "Micron Technology"
    assert "fundamentals" in result
    assert "supply_chain" in result
    assert result["supply_chain"]["topic"] == "hbm"
    assert result["fundamentals"]["supply_chain"]["topic"] == "hbm"


def test_generate_analysis_records_supply_chain_error_and_continues(monkeypatch):
    class FailingStockChainAnalyzer:
        def analyze(self, code, stock_info=None, fundamentals=None):
            raise ValueError("boom")

    monkeypatch.setattr(pipeline, "DataManager", lambda: FakeDataManager())
    monkeypatch.setattr(pipeline, "MemoryManager", lambda base_dir=None: FakeMemoryManager(base_dir))
    monkeypatch.setattr("data.supply_chain.StockChainAnalyzer", lambda: FailingStockChainAnalyzer())

    result = pipeline.generate_analysis("MU.US")

    assert result["stock_info"]["name"] == "Micron Technology"
    assert result["fundamentals"]["pe_forward"] == 12.5
    assert "supply_chain_error" in result
    assert "boom" in result["supply_chain_error"]
