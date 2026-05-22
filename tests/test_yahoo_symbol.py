import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from data.correlation import CorrelationAnalyzer
from data.earnings import EarningsCalendar
from data.etf import ETFAnalyzer
from data.liquidity import LiquidityAnalyzer
from data.manager import DataManager
from data.options import OptionsAnalyzer
from data.search import StockSearchEngine


@pytest.mark.parametrize(
    "symbol,expected",
    [
        ("03986.HK", "3986.HK"),
        ("00700.HK", "0700.HK"),
        ("00388.HK", "0388.HK"),
    ],
)
def test_yf_symbol_converts_five_digit_hk_code_to_yahoo_four_digit_format(symbol, expected):
    helpers = [
        DataManager._yf_symbol,
        EarningsCalendar()._yf_symbol,
        LiquidityAnalyzer()._yf_symbol,
        OptionsAnalyzer()._yf_symbol,
        CorrelationAnalyzer()._yf_symbol,
        ETFAnalyzer()._yf_symbol,
        StockSearchEngine()._yf_symbol,
    ]

    for helper in helpers:
        assert helper(symbol) == expected


def test_yf_symbol_keeps_us_and_cn_conventions():
    assert DataManager._yf_symbol("AAPL.US") == "AAPL"
    assert DataManager._yf_symbol("SH603906") == "603906.SS"
    assert DataManager._yf_symbol("SZ000001") == "000001.SZ"
