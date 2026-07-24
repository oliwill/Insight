import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer import (
    DowChannelAnalyzer,
    ForceBalanceAnalyzer,
    MultiTimeframeAnalyzer,
    VolumeProfileAnalyzer,
)
from analyzer.comprehensive import ComprehensiveAnalyzer
from analyzer.models import get_analyzer, list_analyzers
from data.constants import CHANNEL_SLOPE_BASELINE_DAYS, VOLUME_MID_PERIOD


ANALYZER_CASES = [
    ("dow_channel", DowChannelAnalyzer, CHANNEL_SLOPE_BASELINE_DAYS + 5),
    ("volume_profile", VolumeProfileAnalyzer, VOLUME_MID_PERIOD + 5),
    ("multi_timeframe", MultiTimeframeAnalyzer, 40),
    ("force_balance", ForceBalanceAnalyzer, VOLUME_MID_PERIOD + 5),
]


def make_ohlcv(rows: int, *, uppercase: bool = False, flat: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=rows)
    x = np.arange(rows, dtype=float)
    close = np.full(rows, 100.0) if flat else 100.0 + 0.12 * x + 2.0 * np.sin(x / 8.0)
    open_ = close if flat else close + 0.25 * np.sin(x / 5.0)
    high = np.maximum(open_, close) + 1.0
    low = np.minimum(open_, close) - 1.0
    volume = np.zeros(rows) if flat else 1_000_000.0 * (1.0 + 0.1 * np.sin(x / 6.0))
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )
    if uppercase:
        frame = frame.rename(
            columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )
    return frame


def test_registry_exposes_all_four_technical_framework_analyzers():
    expected = {key: cls for key, cls, _ in ANALYZER_CASES}

    listed = {item["key"]: item for item in list_analyzers()}

    assert expected.keys() <= listed.keys()
    for key, analyzer_cls in expected.items():
        analyzer = get_analyzer(key)
        assert isinstance(analyzer, analyzer_cls)
        assert listed[key]["name"] == analyzer.name
        assert listed[key]["description"] == analyzer.description


def test_unknown_registry_key_preserves_comprehensive_fallback():
    assert isinstance(get_analyzer("not-a-real-analyzer"), ComprehensiveAnalyzer)


@pytest.mark.parametrize("key,analyzer_cls,min_rows", ANALYZER_CASES)
def test_analyzers_return_neutral_result_below_minimum_rows(key, analyzer_cls, min_rows):
    analyzer = get_analyzer(key)

    result = analyzer.analyze(make_ohlcv(min_rows - 1), {})

    assert isinstance(analyzer, analyzer_cls)
    assert result.score == 50
    assert result.details == {}
    assert "数据不足" in result.summary
    assert result.risks


@pytest.mark.parametrize("key,analyzer_cls,min_rows", ANALYZER_CASES)
def test_analyzers_run_at_their_minimum_supported_row_count(key, analyzer_cls, min_rows):
    result = get_analyzer(key).analyze(
        make_ohlcv(min_rows, uppercase=True),
        {"marketCap": 3_000_000_000},
    )

    assert isinstance(result.score, (int, float))
    assert math.isfinite(float(result.score))
    assert 0 <= float(result.score) <= 100
    assert result.details
    assert result.summary


@pytest.mark.parametrize("key,_,min_rows", ANALYZER_CASES)
def test_analyzers_handle_flat_price_and_zero_volume_without_nan(key, _, min_rows):
    rows = max(220, min_rows)

    result = get_analyzer(key).analyze(
        make_ohlcv(rows, flat=True),
        {"market_cap": 0},
    )

    assert math.isfinite(float(result.score))
    assert 0 <= float(result.score) <= 100
    assert result.summary
    assert all("nan" not in str(value).lower() for value in result.details.values())
