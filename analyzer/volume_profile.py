"""
成交量语言分析器 — 把 PDF 框架的量价三段论编码为可量化模块

PDF 理论映射（《应用篇 六 道氏理论在实战中的运用》）：
- 量价齐升：确定性最高，但最连贯的一段往往在天量之前（接近末端）
- 量价紊乱：紊乱后等待缩量，缩量后出现标志性 K 线组合才是买点
- 平量推升（最优质走法）：基石仓位锁定 + 温和供需，无法造假
- 爆冲巨量（骗局）：连续涨停 + 巨量往往是抢帽子游戏、主力派发
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .base import BaseAnalyzer, AnalysisResult
from data.constants import (
    VOLUME_SHORT_PERIOD,
    VOLUME_MID_PERIOD,
    VOLUME_SPIKE_MULTIPLIER,
    FLAT_VOLUME_RATIO_MIN,
    FLAT_VOLUME_RATIO_MAX,
    FLAT_VOLUME_GAIN_THRESHOLD,
    PRICE_VOL_CORR_LOOKBACK,
)


@dataclass
class VolumeProfile:
    """成交量语言分析结果"""
    regime: str = "中性"
    score: float = 50.0
    vol_contraction_ratio: float = 1.0
    price_vol_correlation: float = 0.0
    price_change_20d_pct: float = 0.0
    is_volume_spike: bool = False
    is_flat_volume_uptrend: bool = False
    spike_followed_by_decline: bool = False
    signals: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


class VolumeProfileAnalyzer(BaseAnalyzer):
    """成交量语言分析器"""

    @property
    def name(self) -> str:
        return "成交量语言分析"

    @property
    def description(self) -> str:
        return "基于量价三段论（平量推升/量价齐升/量价紊乱/爆冲巨量）判定成交量形态"

    def analyze(self, data: pd.DataFrame, fundamentals: Dict) -> AnalysisResult:
        df = self._prepare_data(data)

        if len(df) < VOLUME_MID_PERIOD + 5:
            return AnalysisResult(
                score=50,
                summary="数据不足，无法分析成交量语言",
                details={},
                signals=["需要更多历史数据"],
                risks=["成交量分析可靠性低"],
            )

        profile = self._classify_regime(df)
        score = self._calculate_score(profile)
        summary = self._generate_summary(profile)

        return AnalysisResult(
            score=score,
            summary=summary,
            details={
                "profile": profile,
                "regime": profile.regime,
                "vol_ratio": round(profile.vol_contraction_ratio, 2),
                "price_vol_correlation": round(profile.price_vol_correlation, 2),
                "price_change_20d_pct": round(profile.price_change_20d_pct, 1),
                "is_volume_spike": profile.is_volume_spike,
                "is_flat_volume_uptrend": profile.is_flat_volume_uptrend,
                "spike_followed_by_decline": profile.spike_followed_by_decline,
            },
            signals=profile.signals,
            risks=profile.risks,
        )

    def _prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        column_mapping = {
            'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close',
            'Volume': 'volume', 'Date': 'date', 'Datetime': 'date',
        }
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
        for col in ("open", "high", "low", "close", "volume"):
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df

    def _classify_regime(self, df: pd.DataFrame) -> VolumeProfile:
        close = df['close']
        volume = df['volume']

        vol_5d = volume.tail(VOLUME_SHORT_PERIOD).mean()
        vol_20d = volume.tail(VOLUME_MID_PERIOD).mean()
        vol_ratio = float(vol_5d / vol_20d) if vol_20d > 0 else 1.0

        if len(close) >= VOLUME_MID_PERIOD + 1:
            price_change_20d = float((close.iloc[-1] / close.iloc[-1 - VOLUME_MID_PERIOD] - 1) * 100)
        else:
            price_change_20d = 0.0

        lookback = min(PRICE_VOL_CORR_LOOKBACK, len(df) - 1)
        recent_close = close.tail(lookback + 1)
        daily_returns = recent_close.pct_change().dropna()
        recent_vol = volume.tail(lookback)
        vol_ma = volume.rolling(VOLUME_MID_PERIOD).mean().tail(lookback)
        valid = (vol_ma > 0) & recent_vol.notna() & daily_returns.notna()
        if valid.sum() >= 8:
            norm_vol = (recent_vol[valid] / vol_ma[valid])
            rets = daily_returns[valid]
            if norm_vol.std() > 0 and rets.std() > 0:
                price_vol_corr = float(np.corrcoef(rets, norm_vol)[0, 1])
                if np.isnan(price_vol_corr):
                    price_vol_corr = 0.0
            else:
                price_vol_corr = 0.0
        else:
            price_vol_corr = 0.0

        intraday_range = (df['high'] - df['low']) / close
        recent_volatility = float(intraday_range.tail(VOLUME_MID_PERIOD).mean())
        baseline_volatility = float(intraday_range.mean()) if len(intraday_range) > 0 else recent_volatility

        vol_20d_full = volume.rolling(VOLUME_MID_PERIOD).mean()
        valid_vol = vol_20d_full.notna() & (vol_20d_full > 0)
        spike_mask = (volume >= VOLUME_SPIKE_MULTIPLIER * vol_20d_full) & valid_vol
        is_volume_spike = bool(spike_mask.any())

        spike_followed_by_decline = False
        if is_volume_spike:
            for idx in volume[spike_mask.fillna(False)].index:
                pos = df.index.get_loc(idx)
                if pos + 3 < len(df):
                    after_return = (close.iloc[pos + 3] / close.iloc[pos] - 1) * 100
                    if after_return < -2.0:
                        spike_followed_by_decline = True
                        break

        is_flat = (
            price_change_20d > FLAT_VOLUME_GAIN_THRESHOLD
            and FLAT_VOLUME_RATIO_MIN <= vol_ratio <= FLAT_VOLUME_RATIO_MAX
            and recent_volatility <= baseline_volatility * 1.1
        )

        profile = VolumeProfile(
            vol_contraction_ratio=vol_ratio,
            price_vol_correlation=price_vol_corr,
            price_change_20d_pct=price_change_20d,
            is_volume_spike=is_volume_spike,
            is_flat_volume_uptrend=is_flat,
            spike_followed_by_decline=spike_followed_by_decline,
        )

        if is_volume_spike and spike_followed_by_decline:
            profile.regime = "爆冲巨量"
            profile.risks.append("爆冲巨量后走阴跌，疑似抢帽子出货/主力派发（PDF 四问法：等量能平静后再看）")
        elif is_flat:
            profile.regime = "平量推升"
            profile.signals.append("平量推升：筹码锁定，最优质走法（PDF：好东西大家都不舍得送给别人）")
        elif price_change_20d > 3.0 and vol_ratio > 1.2 and price_vol_corr > 0:
            profile.regime = "量价齐升"
            profile.signals.append("量价齐升，确定性较高（注意：最连贯的一段往往在天量之前）")
        elif price_change_20d > 0 and price_vol_corr < 0:
            profile.regime = "量价紊乱"
            profile.signals.append("量价紊乱：价升量缩，等待缩量后标志性 K 线再入手")
        elif price_change_20d < -3.0 and vol_ratio < 0.8:
            profile.regime = "缩量阴跌"
            profile.risks.append("缩量阴跌，动能衰竭但尚未企稳")
        else:
            profile.regime = "中性"

        return profile

    def _calculate_score(self, p: VolumeProfile) -> float:
        score = 50.0
        if p.regime == "平量推升":
            score += 20
        elif p.regime == "量价齐升":
            score += 12
        elif p.regime == "爆冲巨量":
            score -= 18
        elif p.regime == "量价紊乱":
            score -= 8
        elif p.regime == "缩量阴跌":
            score -= 12
        return float(max(0, min(100, score)))

    def _generate_summary(self, p: VolumeProfile) -> str:
        return (
            f"成交量形态：{p.regime} | 量比 {p.vol_contraction_ratio:.2f} | "
            f"20日涨幅 {p.price_change_20d_pct:+.1f}% | 量价相关 {p.price_vol_correlation:+.2f}"
        )
