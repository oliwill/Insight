"""
多空博弈分析器 — 把 趋势博弈分析框架的九地形态、抢帽子、筹码锁定论编码为可量化模块

趋势博弈分析框架映射（《应用篇 五 道氏理论在实战中的运用》）：
- 九地形态：散地/争地/重地/圮地/交地/围地/死地
- 抢帽子：连续涨停+巨量 = 主力派发，散户陷阱
- 筹码锁定论：平量推升 = 基石仓位锁定
- 引友杀敌：突破阻力后回落（假突破）
采用"可观测代理变量"映射趋势博弈分析框架的定性概念。
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .base import BaseAnalyzer, AnalysisResult
from data.constants import (
    FORCE_LONG_SHADOW_RATIO,
    FORCE_UPPER_SHADOW_RATIO,
    FORCE_LIMIT_UP_THRESHOLD,
    FORCE_SMALL_CAP_THRESHOLD,
    VOLUME_MID_PERIOD,
    VOLUME_SPIKE_MULTIPLIER,
)


@dataclass
class ForceBalance:
    """多空博弈分析结果"""

    bull_bear_state: str = "僵持(散地)"
    accumulation_evidence: float = 50.0
    distribution_evidence: float = 50.0
    chip_lock_likelihood: float = 50.0
    retail_trap_risk: float = 50.0
    force_balance_score: float = 50.0
    signals: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


class ForceBalanceAnalyzer(BaseAnalyzer):
    """多空博弈分析器"""

    @property
    def name(self) -> str:
        return "多空博弈分析"

    @property
    def description(self) -> str:
        return "基于九地形态、抢帽子、筹码锁定论判定多空力量与散户陷阱"

    def analyze(self, data: pd.DataFrame, fundamentals: Dict) -> AnalysisResult:
        df = self._prepare_data(data)

        if len(df) < VOLUME_MID_PERIOD + 5:
            return AnalysisResult(
                score=50,
                summary="数据不足，无法分析多空博弈",
                details={},
                signals=["需要更多历史数据"],
                risks=["博弈分析可靠性低"],
            )

        fb = self._assess_force_balance(df, fundamentals)
        score = self._calculate_score(fb)
        summary = self._generate_summary(fb)

        return AnalysisResult(
            score=score,
            summary=summary,
            details={
                "force_balance": fb,
                "bull_bear_state": fb.bull_bear_state,
                "accumulation_evidence": round(fb.accumulation_evidence, 0),
                "distribution_evidence": round(fb.distribution_evidence, 0),
                "chip_lock_likelihood": round(fb.chip_lock_likelihood, 0),
                "retail_trap_risk": round(fb.retail_trap_risk, 0),
            },
            signals=fb.signals,
            risks=fb.risks,
        )

    def _prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        column_mapping = {
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Date": "date",
            "Datetime": "date",
        }
        df = df.rename(
            columns={k: v for k, v in column_mapping.items() if k in df.columns}
        )
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
        for col in ("open", "high", "low", "close", "volume"):
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df

    def _assess_force_balance(
        self, df: pd.DataFrame, fundamentals: Dict
    ) -> ForceBalance:
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]
        n = len(df)
        current_price = float(close.iloc[-1])

        market_cap = (
            fundamentals.get("market_cap") or fundamentals.get("marketCap") or 0
        )
        is_small_cap = 0 < market_cap < FORCE_SMALL_CAP_THRESHOLD

        # === 主力吸筹证据（重地）===
        acc = 50.0
        vol_5d = volume.tail(5).mean()
        vol_20d = volume.tail(VOLUME_MID_PERIOD).mean()
        if vol_20d > 0 and vol_5d < vol_20d * 0.85:
            acc += 12
        recent = df.tail(VOLUME_MID_PERIOD)
        long_lower_shadows = 0
        for _, row in recent.iterrows():
            body = abs(row["close"] - row["open"])
            lower_shadow = min(row["open"], row["close"]) - row["low"]
            if body > 0 and lower_shadow > FORCE_LONG_SHADOW_RATIO * body:
                long_lower_shadows += 1
        if long_lower_shadows >= 3:
            acc += 15
        elif long_lower_shadows >= 1:
            acc += 5
        if n >= 60:
            low_20 = float(low.tail(20).min())
            low_60 = float(low.tail(60).min())
            if low_60 > 0 and low_20 >= low_60 * 1.02:
                acc += 10
        acc = min(100.0, acc)

        # === 主力派发证据（顶部）===
        dist = 50.0
        vol_20d_full = volume.rolling(VOLUME_MID_PERIOD).mean()
        recent_vol = volume.tail(10)
        valid_vol = vol_20d_full.notna() & (vol_20d_full > 0)
        high_vol_mask = (recent_vol >= 2.0 * vol_20d_full.tail(10)) & valid_vol.tail(10)
        high_vol_stall = False
        if high_vol_mask.any():
            for idx in recent_vol[high_vol_mask.fillna(False)].index:
                pos = df.index.get_loc(idx)
                day_return = (
                    abs((close.iloc[pos] / close.iloc[pos - 1] - 1) * 100)
                    if pos > 0
                    else 0
                )
                if day_return < 1.0:
                    high_vol_stall = True
                    break
        if high_vol_stall:
            dist += 15
        long_upper_shadows = 0
        for _, row in recent.iterrows():
            body = abs(row["close"] - row["open"])
            upper_shadow = row["high"] - max(row["open"], row["close"])
            if body > 0 and upper_shadow > FORCE_UPPER_SHADOW_RATIO * body:
                long_upper_shadows += 1
        if long_upper_shadows >= 3:
            dist += 12
        elif long_upper_shadows >= 1:
            dist += 4
        # 高于 60 日均价 10% 本身不是派发证据（强势股常态）；只有同时跌破 20 日均价
        # （高位滞涨/动能转弱）才计为派发信号，避免把趋势强势误判为出货。
        if n >= 60:
            ma60 = float(close.tail(60).mean())
            ma20 = float(close.tail(VOLUME_MID_PERIOD).mean())
            if current_price > ma60 * 1.10 and current_price < ma20:
                dist += 8
        dist = min(100.0, dist)

        # === 筹码锁定可能性 ===
        chip = 50.0
        if vol_20d > 0:
            ratio = vol_5d / vol_20d
            price_20d_change = 0.0
            if n >= 21:
                price_20d_change = (close.iloc[-1] / close.iloc[-21] - 1) * 100
            if 0.6 <= ratio <= 1.2 and price_20d_change > 3.0:
                chip += 25
                chip = min(100.0, chip)
            elif ratio > 0.9 and price_20d_change > 0:
                chip += 10
            elif ratio > 1.8:
                chip -= 15

        # === 散户陷阱风险（抢帽子）===
        trap = 50.0
        recent_returns = close.tail(6).pct_change().dropna() * 100
        limit_up_days = int((recent_returns > FORCE_LIMIT_UP_THRESHOLD).sum())
        if limit_up_days >= 2:
            trap += 20
        elif limit_up_days >= 1:
            trap += 8
        if is_small_cap:
            trap += 12
        spike_mask = (volume >= VOLUME_SPIKE_MULTIPLIER * vol_20d_full) & valid_vol
        if spike_mask.tail(10).any():
            trap += 15
        trap = min(100.0, trap)

        fb = ForceBalance(
            accumulation_evidence=acc,
            distribution_evidence=dist,
            chip_lock_likelihood=chip,
            retail_trap_risk=trap,
        )
        fb.bull_bear_state = self._determine_state(fb)
        self._populate_signals(fb)
        return fb

    def _determine_state(self, fb: ForceBalance) -> str:
        if fb.retail_trap_risk >= 70:
            return "空方包围(围地)"
        if fb.distribution_evidence >= 70:
            return "空方主导"
        if fb.accumulation_evidence >= 65 and fb.chip_lock_likelihood >= 60:
            return "多方主导"
        if fb.accumulation_evidence >= 65:
            return "多方集结(圮地)"
        if fb.accumulation_evidence < 55 and fb.distribution_evidence < 55:
            return "僵持(散地)"
        if fb.distribution_evidence > fb.accumulation_evidence:
            return "空方主导"
        return "多方主导"

    def _populate_signals(self, fb: ForceBalance) -> None:
        if fb.accumulation_evidence >= 65:
            fb.signals.append(
                f"主力吸筹证据较强（{fb.accumulation_evidence:.0f}）：底部缩量+长下影线+低点抬高"
            )
        if fb.chip_lock_likelihood >= 65:
            fb.signals.append(
                f"筹码锁定可能性高（{fb.chip_lock_likelihood:.0f}）：平量推升=基石仓位，趋势博弈框架下的最优质走法"
            )
        if fb.distribution_evidence >= 65:
            fb.risks.append(
                f"主力派发证据较强（{fb.distribution_evidence:.0f}）：高位爆量滞涨+上影线"
            )
        if fb.retail_trap_risk >= 65:
            fb.risks.append(
                f"散户陷阱风险高（{fb.retail_trap_risk:.0f}）：疑似抢帽子游戏，趋势博弈框架四问法审视"
            )

    def _calculate_score(self, fb: ForceBalance) -> float:
        score = 50.0
        if fb.accumulation_evidence >= 65:
            score += 8
        if fb.chip_lock_likelihood >= 65:
            score += 6
        if fb.distribution_evidence >= 70:
            score -= 10
        if fb.retail_trap_risk >= 70:
            score -= 8
        elif fb.retail_trap_risk >= 60:
            score -= 4
        return float(max(0, min(100, score)))

    def _generate_summary(self, fb: ForceBalance) -> str:
        return (
            f"多空博弈：{fb.bull_bear_state} | "
            f"吸筹{fb.accumulation_evidence:.0f} 派发{fb.distribution_evidence:.0f} "
            f"锁定{fb.chip_lock_likelihood:.0f} 陷阱{fb.retail_trap_risk:.0f}"
        )
