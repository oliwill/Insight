"""Regression tests for the 2026-08 framework fixes.

Locks the behavior of:
- volume spike detection limited to the recent window (no full-history false positives)
- Dow channel top/bottom signals requiring confirmation conditions
- slope slowdown treated as momentum exhaustion, not accumulation
- TimingEngine earnings-window hard cap and chip-lock dedup
- ReportGenerator honest N/A handling when research score / analyst target is missing
- three_scenarios returning None without a valuation anchor
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer.dow_channel import DowChannelAnalyzer
from analyzer.report_generator import ReportGenerator
from analyzer.timing_engine import TimingEngine
from analyzer.volume_profile import VolumeProfileAnalyzer
from scripts import generate_full_report as full_report


def _ohlcv(rows: int, close: np.ndarray, volume: np.ndarray) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=rows)
    open_ = close + 0.1
    high = close + 1.0
    low = close - 1.0
    return pd.DataFrame(
        {
            "date": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


# ----------------------------------------------------------------------
# 成交量语言：爆量检测只统计最近 20 个交易日
# ----------------------------------------------------------------------
def test_old_volume_spike_does_not_trigger_blowoff_regime():
    rows = 120
    close = 100.0 + 0.05 * np.arange(rows)  # 平缓上行
    volume = np.full(rows, 1_000_000.0)
    # 60 天前的一次巨量 + 随后回落（相对当前已是历史事件）
    spike_pos = rows - 60
    volume[spike_pos] = 5_000_000.0
    close[spike_pos + 1 : spike_pos + 6] -= 3.0  # 巨量后回落确认
    df = _ohlcv(rows, close, volume)

    result = VolumeProfileAnalyzer().analyze(df, {})
    profile = result.details["profile"]

    assert profile.is_volume_spike is False
    assert profile.regime != "爆冲巨量"


def test_recent_volume_spike_with_decline_still_detected():
    rows = 60
    close = 100.0 + 0.05 * np.arange(rows)
    volume = np.full(rows, 1_000_000.0)
    spike_pos = rows - 10  # 最近 20 天内
    volume[spike_pos] = 5_000_000.0
    close[spike_pos + 1 :] -= 3.0
    df = _ohlcv(rows, close, volume)

    result = VolumeProfileAnalyzer().analyze(df, {})
    profile = result.details["profile"]

    assert profile.is_volume_spike is True
    assert profile.spike_followed_by_decline is True
    assert profile.regime == "爆冲巨量"


# ----------------------------------------------------------------------
# 道氏通道：顶/底信号需要确认条件
# ----------------------------------------------------------------------
def _rising_channel_at_upper() -> pd.DataFrame:
    rows = 130
    x = np.arange(rows, dtype=float)
    close = 100.0 + 0.15 * x + 1.5 * np.sin(x / 6.0)  # 稳定上升
    volume = np.full(rows, 1_000_000.0)
    df = _ohlcv(rows, close, volume)
    # 让最新收盘贴近 20 日窗口上沿（且 high 不再显著抬高上沿）
    upper_prev = float(np.asarray(df["high"].tail(20)).max())
    new_close = upper_prev + 0.5
    df.loc[df.index[-1], "close"] = new_close
    df.loc[df.index[-1], "high"] = new_close + 0.01
    return df


def test_uptrend_near_channel_top_is_only_a_warning_not_a_top_signal():
    result = DowChannelAnalyzer().analyze(_rising_channel_at_upper(), {})
    channel = result.details["channel"]

    assert channel.channel_direction == "上升"
    assert channel.position_in_channel > 0.95
    # 未跌破颈线前，不得报「顶部三步信号」
    assert channel.top_bottom_signal in {"顶部出轨警示", "无"}


def test_confirmed_top_signal_requires_neckline_break():
    df = _rising_channel_at_upper()
    # 构造出轨后跌破颈线：最后几天快速下杀跌破 30 日箱体下沿
    close = df["close"].to_numpy()
    box_low = float(pd.Series(df["low"].tail(30)).quantile(0.2))
    close[-1] = box_low * 0.97
    df["close"] = close
    df["low"] = np.minimum(df["low"], close - 0.5)

    result = DowChannelAnalyzer().analyze(df, {})
    channel = result.details["channel"]

    assert channel.neckline_signal == "颈线已跌破"
    assert channel.top_bottom_signal == "顶部三步信号"


def test_slope_slowdown_is_not_labeled_as_accumulation():
    rows = 130
    x = np.arange(rows, dtype=float)
    # 前 90 天快速下跌，最后 30 天跌速明显放缓
    close = np.concatenate(
        [200.0 - 0.8 * np.arange(100), 200.0 - 0.8 * 100 - 0.05 * np.arange(30)]
    )
    volume = np.full(rows, 1_000_000.0)
    df = _ohlcv(rows, close, volume)

    result = DowChannelAnalyzer().analyze(df, {})
    channel = result.details["channel"]

    assert "扶老太太下楼" not in channel.slope_state
    assert not any("吸筹" in s for s in channel.signals)


# ----------------------------------------------------------------------
# TimingEngine：财报窗口硬顶 + 筹码锁定去重
# ----------------------------------------------------------------------
def _base_market_data() -> dict:
    return {
        "stock_info": {"price": 100.0},
        "technicals": {
            "trend_short": "BULLISH",
            "rsi_14": 55.0,
            "vol_ratio": 1.0,
            "ma50": 98.0,
            "support_20d": 95.0,
        },
        "wyckoff": {},
        "earnings": {},
        "liquidity": {"daily_dollar_volume": 100_000_000},
        "options": {},
        "web_search": {},
        "fundamentals": {},
        "volume_profile": {"regime": "平量推升"},
        "dow_channel": {"channel_direction": "上升"},
        "force_balance": {"accumulation_evidence": 70, "chip_lock_likelihood": 70},
        "multi_timeframe": {},
    }


def test_imminent_earnings_caps_state_at_wait_even_with_high_score():
    engine = TimingEngine()
    md = _base_market_data()
    clean = engine.analyze(md, research_score=80)
    assert clean.state == "Ready"

    md["earnings"] = {"days_until_earnings": 3, "next_earnings_date": "2026-08-16"}
    capped = engine.analyze(md, research_score=80)

    assert any("极近" in flag for flag in capped.risk_flags)
    assert capped.state == "Wait"


def test_chip_lock_not_double_counted_with_flat_volume_uptrend():
    engine = TimingEngine()
    md = _base_market_data()
    combined = engine.analyze(md)

    md_no_regime = _base_market_data()
    md_no_regime["volume_profile"] = {"regime": "中性"}
    separate = engine.analyze(md_no_regime)

    # 平量推升时 chip_lock 不重复加分，所以两者分差应小于 volume(+12) + chip(+4) 的合计
    assert combined.internal_score - separate.internal_score == 12 - 4
    assert any("不重复计分" in reason for reason in combined.reasons)


def test_missing_liquidity_data_does_not_lower_timing_score():
    engine = TimingEngine()
    md = _base_market_data()
    with_data = engine.analyze(md)

    md_missing = _base_market_data()
    md_missing["liquidity"] = {"error": "no short data for CN market"}
    missing = engine.analyze(md_missing)

    assert (
        missing.internal_score == with_data.internal_score - 5
    )  # 仅失去「成交额充足」加分
    assert any("缺少流动性数据" in reason for reason in missing.reasons)


# ----------------------------------------------------------------------
# ReportGenerator：缺数据必须显式 N/A，不得编造结论
# ----------------------------------------------------------------------
def _minimal_market_data() -> dict:
    return {
        "stock_info": {"code": "AAPL.US", "name": "Apple Inc.", "price": 190.0},
        "fundamentals": {},
        "technicals": {},
        "liquidity": {},
        "options": {},
        "earnings": {},
        "web_search": {},
    }


def test_missing_research_score_shows_na_not_fabricated_50():
    markdown = ReportGenerator.generate("AAPL.US", _minimal_market_data())

    assert "| **Research Score** | N/A" in markdown
    assert "50.0/100" not in markdown
    assert "缺少研究评分" in markdown


def test_missing_analyst_target_is_not_labeled_overvalued():
    markdown = ReportGenerator.generate("AAPL.US", _minimal_market_data())

    assert "高估" not in markdown
    assert "无目标价数据" in markdown


def test_non_ready_opening_conclusion_gives_no_entry_price():
    from types import SimpleNamespace

    md = _minimal_market_data()
    md["technicals"] = {"support_20d": 180.0}
    md["fundamentals"] = {"target_mean_price": 220.0}
    timing = SimpleNamespace(state="Wait", internal_score=60)
    markdown = ReportGenerator.generate("AAPL.US", md, timing_state=timing)

    assert "建议建仓价格" not in markdown
    assert "暂不给出建仓价位" in markdown


def test_hk_stock_uses_hkd_symbol():
    md = _minimal_market_data()
    md["stock_info"] = {
        "code": "00700.HK",
        "name": "腾讯控股",
        "price": 380.0,
        "currency": "HKD",
    }
    markdown = ReportGenerator.generate("00700.HK", md)

    assert "HK$380.00" in markdown
    assert "$380.00" not in markdown.split("HK$380.00")[0]


# ----------------------------------------------------------------------
# 数据单位修复：增速归一 + A 股成交量 + 同行基准缺失
# ----------------------------------------------------------------------
def test_normalize_growth_rate_handles_decimal_and_percent():
    from data.constants import normalize_growth_rate

    assert normalize_growth_rate(0.85) == 85.0
    assert normalize_growth_rate(3.457) == 345.7  # >1 小数不再被误读为百分比
    assert normalize_growth_rate(13.685) == 1368.5  # 同一 Yahoo 源同为小数制
    assert normalize_growth_rate(-0.108) == -10.8
    assert normalize_growth_rate(None) is None
    assert normalize_growth_rate("not-a-number") is None
    assert normalize_growth_rate(9999) is None  # 疑似源错误


def test_research_percent_no_longer_misreads_decimal_above_one():
    from analyzer.research_score import ResearchScoreEngine

    engine = ResearchScoreEngine()
    assert engine._percent(3.457) == 345.7
    assert engine._percent(13.685) == 1368.5
    assert engine._percent(0.85) == 85.0


def test_cn_volume_normalized_to_shares():
    from data.manager import DataManager

    df = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-01-01", periods=3),
            "close": [10.0] * 3,
            "volume": [1000, 2000, 3000],
        }
    )
    cn = DataManager._cn_volume_to_shares(df.copy(), "SH600519")
    assert cn["volume"].tolist() == [100000, 200000, 300000]
    # US/HK 不受影响
    us = DataManager._cn_volume_to_shares(df.copy(), "MU.US")
    assert us["volume"].tolist() == [1000, 2000, 3000]
    hk = DataManager._cn_volume_to_shares(df.copy(), "00700.HK")
    assert hk["volume"].tolist() == [1000, 2000, 3000]


def test_peer_fallback_is_explicitly_missing_not_self():
    import scripts.generate_full_report as gfr

    assert gfr.PEER_BENCH.get("SH603087") is None  # 未注册标的不再硬编码
    peer = gfr.PEER_BENCH.get(
        "MU.US",
        {"ps_med": None, "pe_med": None, "top": "N/A", "detail": "未获取同行基准"},
    )
    assert peer["ps_med"] is None
    assert peer["pe_med"] is None


def test_valuation_reverse_without_peer_returns_none_overpay():
    import scripts.generate_full_report as gfr

    overpay, years, margin, odds, psg = gfr.valuation_reverse(
        10.0, None, 0.3, 20.0, 0.5, 1e9, True, "无"
    )
    assert overpay is None
    assert margin == "无同行基准"
    assert years == 0


def test_valuation_details_shows_gap_when_peer_missing():
    import scripts.generate_full_report as gfr

    text = gfr._valuation_details(
        "X",
        10.0,
        20.0,
        {"ps_med": None, "pe_med": None},
        1.0,
        0,
        "无同行基准",
        "混合型",
        None,
        30.0,
        True,
        "无",
    )
    assert "数据缺口" in text


def test_growth_classification_caps_absurd_values():
    import scripts.generate_full_report as gfr

    # 增速 3457%（小数 34.57）在分类/隐含年数上与 200% 等价，避免异常大数扭曲结论
    overpay, years, margin, odds, psg = gfr.valuation_reverse(
        8.0, 8.0, 34.57, 20.0, 0.5, 1e9, True, "无"
    )
    assert odds in {"高确定性增长型", "催化剂驱动型"}
    capped_years = gfr.valuation_reverse(16.0, 8.0, 2.0, 20.0, 0.5, 1e9, True, "无")[1]
    absurd_years = gfr.valuation_reverse(16.0, 8.0, 34.57, 20.0, 0.5, 1e9, True, "无")[
        1
    ]
    assert abs(absurd_years - capped_years) < 1e-9


def test_three_scenarios_returns_none_without_anchor():
    result = full_report.three_scenarios(
        price=100.0,
        ps=0.0,
        ps_peer_med=0.0,
        rev_growth=0.1,
        mcap=0.0,
        target_mean=0,
    )
    assert result is None


def test_three_scenarios_width_and_probs_follow_atr_and_timing():
    common = dict(price=100.0, ps=5.0, ps_peer_med=5.0, rev_growth=0.1, mcap=1e10)

    calm = full_report.three_scenarios(**common, atr=1.0, timing_state="Ready")
    wild = full_report.three_scenarios(**common, atr=6.0, timing_state="Avoid")
    fallback = full_report.three_scenarios(**common, atr=0.0, timing_state="")

    assert calm is not None and wild is not None and fallback is not None
    assert calm["width"] < wild["width"]
    assert calm["probs"][0] > wild["probs"][0]  # Ready 的 Bull 概率更高
    assert calm["bull"] > calm["base"] > calm["bear"]
    # 无 ATR 时回退到默认 30% 宽度
    assert abs(fallback["width"] - 0.30) < 1e-9


def test_timing_currency_symbol_falls_back_to_code():
    from analyzer.timing_engine import TimingEngine

    engine = TimingEngine()
    assert engine._currency_symbol({"currency": "CNY"}) == "¥"
    assert engine._currency_symbol({"currency": "HKD"}) == "HK$"
    # currency 缺失/未知时按 code 推断
    assert engine._currency_symbol({"code": "SH603087"}) == "¥"
    assert engine._currency_symbol({"code": "09988.HK"}) == "HK$"
    assert engine._currency_symbol({"code": "MU.US"}) == "$"


def test_liquidity_risk_uses_currency_symbol():
    from analyzer.timing_engine import TimingEngine

    engine = TimingEngine()
    flags = []
    engine._liquidity_score({"daily_dollar_volume": 5_000_000}, [], flags, ccy="¥")
    assert flags
    assert any("¥" in f and "$" not in f for f in flags)
