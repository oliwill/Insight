import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.manager import DataManager


class EmptyLongBridgeClient:
    def is_available(self):
        return True

    def get_history(self, symbol: str, days: int):
        return None

    def get_quote(self, symbol: str):
        return None

    def get_static_info(self, symbol: str):
        return None


class FakeYahooTicker:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.info = {
            "shortName": "Apple Inc.",
            "regularMarketPrice": 190.0,
            "regularMarketChangePercent": 1.2,
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "revenueGrowth": 0.08,
            "forwardPE": 24.5,
        }

    def history(self, period: str):
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1000, 1100],
            },
            index=pd.DatetimeIndex(["2026-01-02", "2026-01-03"], name="Date"),
        )


def test_historical_data_falls_back_to_yahoo_and_records_attempts():
    dm = DataManager(
        longbridge_client=EmptyLongBridgeClient(),
        yahoo_factory=FakeYahooTicker,
    )

    df = dm.get_historical_data("AAPL.US", period="1mo")
    attempts = dm.get_source_status()["historical_data"]

    assert len(df) == 2
    assert [attempt["source"] for attempt in attempts] == ["longbridge", "yahoo"]
    assert [attempt["status"] for attempt in attempts] == ["failed", "ok"]
    assert attempts[1]["rows"] == 2


def test_stock_info_falls_back_to_yahoo_and_keeps_canonical_symbol():
    dm = DataManager(
        longbridge_client=EmptyLongBridgeClient(),
        yahoo_factory=FakeYahooTicker,
    )

    info = dm.get_stock_info("AAPL")
    attempts = dm.get_source_status()["stock_info"]

    assert info.code == "AAPL.US"
    assert info.name == "Apple Inc."
    assert info.price == 190.0
    assert [attempt["status"] for attempt in attempts] == ["failed", "ok"]


def test_fundamentals_records_partial_source_health():
    dm = DataManager(
        longbridge_client=EmptyLongBridgeClient(),
        yahoo_factory=FakeYahooTicker,
    )

    fundamentals = dm.get_fundamentals("AAPL.US")
    attempts = dm.get_source_status()["fundamentals"]

    assert fundamentals["revenue_growth"] == 0.08
    assert fundamentals["pe_forward"] == 24.5
    assert [attempt["source"] for attempt in attempts] == ["longbridge", "yahoo"]
    assert [attempt["status"] for attempt in attempts] == ["failed", "ok"]
