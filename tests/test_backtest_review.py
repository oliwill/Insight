import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer.base import AnalysisResult
from backtest.core import BacktestEngine
from backtest.runner import BacktestRunner
from scripts.run_review import _parse_summary_counts


class DecimalPriceDataManager:
    def get_historical_data(self, ticker: str, period: str):
        return pd.DataFrame(
            {
                "date": ["2026-01-02", "2026-01-03"],
                "open": [Decimal("10"), Decimal("11")],
                "high": [Decimal("10"), Decimal("11")],
                "low": [Decimal("10"), Decimal("11")],
                "close": [Decimal("10"), Decimal("11")],
                "volume": [1000, 1000],
            }
        )


def test_ticker_from_wiki_stem_restores_common_codes():
    assert BacktestRunner._ticker_from_wiki_stem("AAPL_US") == "AAPL.US"
    assert BacktestRunner._ticker_from_wiki_stem("03986_HK") == "03986.HK"
    assert BacktestRunner._ticker_from_wiki_stem("SH603906") == "SH603906"


def test_normalize_discovered_ticker_accepts_wiki_links_and_paths():
    assert BacktestRunner._normalize_discovered_ticker("[[OKLO_US]]") == "OKLO.US"
    assert BacktestRunner._normalize_discovered_ticker("[[4_Trader/Analysis/ASX_US]]") == "ASX.US"
    assert BacktestRunner._normalize_discovered_ticker("03986_HK") == "03986.HK"
    assert BacktestRunner._normalize_discovered_ticker("600487.SH") == "600487.SH"


def test_normalize_discovered_ticker_rejects_non_stock_labels():
    assert BacktestRunner._normalize_discovered_ticker("名称") is None
    assert BacktestRunner._normalize_discovered_ticker("主题") is None
    assert BacktestRunner._normalize_discovered_ticker("[[Serenity]]") is None
    assert BacktestRunner._normalize_discovered_ticker("[[AI CAPEX超级周期]]") is None


def test_dedupe_tickers_preserves_order():
    assert BacktestRunner._dedupe_tickers(["AAPL.US", "AAPL.US", "NVDA.US"]) == [
        "AAPL.US",
        "NVDA.US",
    ]


def test_parse_summary_counts():
    summary = "覆盖 3 只股票，验证 12 条信号。\n总体胜率 **58.3%**"

    assert _parse_summary_counts(summary) == (3, 12)


def test_backtest_handles_decimal_price_series():
    engine = BacktestEngine(data_manager=DecimalPriceDataManager())
    result = engine.backtest_analysis(
        "HIMS.US",
        AnalysisResult(score=70, summary="BUY setup", signals=["BUY"], risks=[]),
        "2026-01-02",
        days_after=1,
    )

    assert result.signals[0].verified is True
    assert result.signals[0].return_pct == pytest.approx(10.0)
