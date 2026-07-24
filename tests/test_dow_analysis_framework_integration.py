"""Integration tests for the four-module Dow analysis framework."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer.timing_engine import TimingEngine
from scripts import generate_full_report as full_report


def _market_data() -> dict:
    return {
        "stock_info": {},
        "technicals": {},
        "wyckoff": {},
        "earnings": {},
        "liquidity": {},
        "options": {},
        "web_search": {},
        "fundamentals": {},
    }


def test_dow_framework_changes_timing_score_and_surfaces_reasons():
    engine = TimingEngine()
    neutral = engine.analyze(_market_data())

    bullish = _market_data()
    bullish.update(
        {
            "volume_profile": {"regime": "平量推升"},
            "dow_channel": {
                "channel_direction": "上升",
                "slope_state": "趋缓",
                "neckline_signal": "颈线已突破",
                "top_bottom_signal": "底部三步信号",
                "position_in_channel": 0.20,
                "lower_channel": 10.0,
            },
            "force_balance": {
                "accumulation_evidence": 70,
                "distribution_evidence": 35,
                "chip_lock_likelihood": 72,
                "retail_trap_risk": 25,
            },
            "multi_timeframe": {
                "alignment": "三级别共振多头",
                "higher_tf_signal": "周线可支撑日线回踩",
            },
        }
    )

    result = engine.analyze(bullish)

    assert result.internal_score > neutral.internal_score
    assert any("平量推升" in reason for reason in result.reasons)
    assert any("三级别共振多头" in reason for reason in result.reasons)
    assert any("道氏通道下沿" in trigger for trigger in result.entry_triggers)
    assert "PDF" not in "\n".join(result.reasons + result.risk_flags)


def test_bearish_dow_framework_signals_reduce_timing_score_and_raise_risks():
    engine = TimingEngine()
    neutral = engine.analyze(_market_data())

    bearish = _market_data()
    bearish.update(
        {
            "volume_profile": {"regime": "爆冲巨量"},
            "dow_channel": {
                "channel_direction": "下降",
                "slope_state": "加速",
                "neckline_signal": "颈线已跌破",
                "top_bottom_signal": "顶部三步信号",
                "position_in_channel": 0.92,
            },
            "force_balance": {
                "accumulation_evidence": 15,
                "distribution_evidence": 78,
                "chip_lock_likelihood": 20,
                "retail_trap_risk": 75,
            },
            "multi_timeframe": {
                "alignment": "三级别共振空头",
                "higher_tf_signal": "高周期调整压力未解除",
            },
        }
    )

    result = engine.analyze(bearish)

    assert result.internal_score < neutral.internal_score
    assert any("顶部信号" in risk for risk in result.risk_flags)
    assert any("三级别共振空头" in risk for risk in result.risk_flags)
    assert all("PDF" not in item for item in result.reasons + result.risk_flags)


def test_full_report_content_is_safe_to_embed_in_existing_wiki_page():
    standalone = """---
title: Test report
---

# SH688035 德邦科技 — 完整版分析报告

## 一、公司与催化剂

### 子结论
"""

    content = full_report.to_wiki_section_content(standalone)

    assert "title: Test report" not in content
    assert content.startswith("### SH688035 德邦科技")
    assert "#### 一、公司与催化剂" in content
    assert "##### 子结论" in content
    assert not any(line.startswith("## ") for line in content.splitlines())


def test_persist_report_replaces_only_dedicated_section(monkeypatch):
    calls = []

    class FakeMemoryManager:
        def init_stock_wiki(self, symbol, stock_name):
            calls.append(("init", symbol, stock_name))

        def replace_section(self, symbol, section_name, content):
            calls.append(("replace", symbol, section_name, content))

    import memory.manager

    monkeypatch.setattr(memory.manager, "MemoryManager", FakeMemoryManager)
    full_report.persist_to_obsidian(
        "SH688035",
        "德邦科技",
        "---\ntitle: ignored\n---\n\n# 标题\n\n## 技术面\n",
    )

    assert calls[:1] == [("init", "SH688035", "德邦科技")]
    operation, symbol, section, content = calls[1]
    assert operation == "replace"
    assert symbol == "SH688035"
    assert section == full_report.REPORT_SECTION
    assert "title: ignored" not in content
    assert "### 标题" in content
    assert "#### 技术面" in content


def test_trading_grid_uses_explicit_atr_stops_for_reward_risk():
    price = 100.0
    atr = 4.0
    grid = full_report.trading_grid(
        price=price,
        period_low=60.0,
        period_high=120.0,
        atr=atr,
        channel_lower=72.0,
        channel_upper=118.0,
        ma50=92.0,
        target=140.0,
    )

    assert grid
    assert all(len(row) == 6 for row in grid)
    assert all(entry > stop > 0 for _, entry, stop, _, _, _ in grid)
    assert all(rr is None or rr > 0 for *_, rr in grid)
    # The deep-buy entry may not be below the current ATR invalidation level.
    deep = next(row for row in grid if row[0] == '🔴 深度加仓')
    assert deep[1] >= full_report._entry_stop(price, atr)
    assert full_report._rr(100.0, 150.0, 90.0) == 5.0
    assert full_report._rr(100.0, 90.0, 95.0) is None


def test_full_report_omits_missing_fundamentals_instead_of_presenting_zeroes():
    rows = full_report._fundamental_rows(
        pe=75.1,
        pf=0.0,
        pb=3.69,
        gm=27.0,
        om=12.4,
        roe=4.9,
        rev_g=0.285,
        eg=26.3,
        cash=882_080_768.0,
        debt=294_895_872.0,
        debt_equity=12.327,
    )
    growth = full_report._growth_quality_lines(0.285, 26.3, 27.0, 882_080_768.0, 294_895_872.0)

    assert 'PE(Forward)' not in rows
    assert '债务/权益 | 12.3% | 可控' in rows
    assert not growth.rstrip().endswith('-')

    missing_valuation = full_report._valuation_details(
        '测试公司', 0.0, 0.0, {'ps_med': 7.1, 'pe_med': 75.7},
        1.0, 0.0, '—', '混合型', None, 0.0, False, '无',
    )
    assert '数据缺口' in missing_valuation
    assert 'PSG 0.0' not in missing_valuation


def test_trading_grid_requires_ready_timing_state_before_current_price_chase():
    common = dict(
        price=100.0, period_low=60.0, period_high=120.0, atr=4.0,
        channel_lower=72.0, channel_upper=118.0, ma50=92.0, target=140.0,
    )
    avoid_current = next(row for row in full_report.trading_grid(**common, timing_state='Avoid') if row[0] == '⚪ 当前价')
    ready_current = next(row for row in full_report.trading_grid(**common, timing_state='Ready') if row[0] == '⚪ 当前价')

    assert '不在当前价追高' in avoid_current[3]
    assert '目标价空间≥15%' in ready_current[3]
