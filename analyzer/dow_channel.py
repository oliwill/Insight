"""
道氏通道分析器 — 把 PDF 框架的通道/趋势轨迹分析编码为可量化模块

PDF 理论映射（《应用篇 四 道氏理论在实战中的运用》）：
- 通道内四种变化：摩擦型、通道里的通道（宽幅箱体）、斜率延缓（扶老太太下楼）、跳空刺破
- 顶/底三步信号：出轨→颈线→通道下沿（顶）；通道破→缩量筑底→上破回踩（底）
- 颈线 = 交地/衢地：颈线得失是趋势确认关键
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .base import BaseAnalyzer, AnalysisResult
from data.constants import (
    CHANNEL_LOOKBACK_DAYS,
    CHANNEL_SLOPE_RECENT_DAYS,
    CHANNEL_SLOPE_BASELINE_DAYS,
    CHANNEL_SLOPE_SLOWDOWN_THRESHOLD,
    CHANNEL_RUBBING_LOOKBACK,
    CHANNEL_RUBBING_MIN_TOUCHES,
    CHANNEL_RANGE_RATIO_THRESHOLD,
)


@dataclass
class DowChannel:
    """道氏通道分析结果"""
    channel_direction: str = "不明"
    upper_channel: float = 0.0
    lower_channel: float = 0.0
    channel_width_pct: float = 0.0
    position_in_channel: float = 0.5
    slope: float = 0.0
    slope_state: str = "稳定"
    is_rubbing_upper: bool = False
    is_rubbing_lower: bool = False
    neckline_signal: str = "无"
    top_bottom_signal: str = "无"
    signals: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


class DowChannelAnalyzer(BaseAnalyzer):
    """道氏通道分析器"""

    @property
    def name(self) -> str:
        return "道氏通道分析"

    @property
    def description(self) -> str:
        return "基于道氏理论的通道、斜率、摩擦、颈线判定趋势轨迹与顶底信号"

    def analyze(self, data: pd.DataFrame, fundamentals: Dict) -> AnalysisResult:
        df = self._prepare_data(data)

        if len(df) < CHANNEL_SLOPE_BASELINE_DAYS + 5:
            return AnalysisResult(
                score=50,
                summary="数据不足，无法分析道氏通道",
                details={},
                signals=["需要更多历史数据"],
                risks=["通道分析可靠性低"],
            )

        channel = self._identify_channel(df)
        score = self._calculate_score(channel)
        summary = self._generate_summary(channel)

        return AnalysisResult(
            score=score,
            summary=summary,
            details={
                "channel": channel,
                "channel_direction": channel.channel_direction,
                "upper_channel": round(channel.upper_channel, 2),
                "lower_channel": round(channel.lower_channel, 2),
                "channel_width_pct": round(channel.channel_width_pct, 1),
                "position_in_channel": round(channel.position_in_channel, 2),
                "slope_state": channel.slope_state,
                "is_rubbing_upper": channel.is_rubbing_upper,
                "is_rubbing_lower": channel.is_rubbing_lower,
                "neckline_signal": channel.neckline_signal,
                "top_bottom_signal": channel.top_bottom_signal,
            },
            signals=channel.signals,
            risks=channel.risks,
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

    def _identify_channel(self, df: pd.DataFrame) -> DowChannel:
        lookback = min(CHANNEL_LOOKBACK_DAYS, len(df))
        window = df.tail(lookback).reset_index(drop=True)
        close = window['close']
        current_price = float(close.iloc[-1])

        bound_lookback = min(20, len(window))
        recent_window = window.tail(bound_lookback)
        upper_end = float(recent_window['high'].max())
        lower_end = float(recent_window['low'].min())
        if lower_end >= upper_end:
            spread = max(current_price * 0.02, 0.01)
            upper_end = current_price + spread
            lower_end = current_price - spread

        avg_price = float(close.mean())
        x = np.arange(len(window), dtype=float)
        close_slope, _ = self._linear_regression(x, close.values)
        norm_slope_pct = close_slope / avg_price * 100 if avg_price > 0 else 0.0

        if norm_slope_pct > 0.03:
            direction = "上升"
        elif norm_slope_pct < -0.03:
            direction = "下降"
        else:
            direction = "横盘"

        channel_width_pct = (upper_end - lower_end) / avg_price * 100 if avg_price > 0 else 0.0
        position = (current_price - lower_end) / (upper_end - lower_end)
        position = float(max(0.0, min(1.0, position)))

        slope_state = self._assess_slope(window, direction)
        rubbing_upper, rubbing_lower = self._detect_rubbing(window, upper_end, lower_end)
        neckline_signal = self._assess_neckline(window)
        top_bottom_signal = self._detect_top_bottom(window, direction, position)

        channel = DowChannel(
            channel_direction=direction,
            upper_channel=upper_end,
            lower_channel=lower_end,
            channel_width_pct=channel_width_pct,
            position_in_channel=position,
            slope=norm_slope_pct,
            slope_state=slope_state,
            is_rubbing_upper=rubbing_upper,
            is_rubbing_lower=rubbing_lower,
            neckline_signal=neckline_signal,
            top_bottom_signal=top_bottom_signal,
        )
        self._populate_signals(channel, df)
        return channel

    def _linear_regression(self, x: np.ndarray, y: np.ndarray) -> tuple:
        n = len(x)
        if n < 2:
            return 0.0, float(y[0]) if len(y) > 0 else 0.0
        x_mean = x.mean()
        y_mean = y.mean()
        denom = ((x - x_mean) ** 2).sum()
        if denom == 0:
            return 0.0, float(y_mean)
        slope = float(((x - x_mean) * (y - y_mean)).sum() / denom)
        intercept = float(y_mean - slope * x_mean)
        return slope, intercept

    def _assess_slope(self, window: pd.DataFrame, direction: str) -> str:
        close = window['close']
        n = len(window)
        recent_n = min(CHANNEL_SLOPE_RECENT_DAYS, n)
        base_n = min(CHANNEL_SLOPE_BASELINE_DAYS, n)
        if recent_n < 5:
            return "稳定"

        recent = close.tail(recent_n).values
        base = close.tail(base_n).values
        x_recent = np.arange(recent_n, dtype=float)
        x_base = np.arange(base_n, dtype=float)
        recent_slope, _ = self._linear_regression(x_recent, recent)
        base_slope, _ = self._linear_regression(x_base, base)

        if base_slope == 0:
            return "稳定"

        if direction == "下降":
            slowdown = abs(recent_slope) / abs(base_slope) if abs(base_slope) > 0 else 1.0
            if slowdown < (1 - CHANNEL_SLOPE_SLOWDOWN_THRESHOLD):
                return "趋缓(扶老太太下楼)"

        if base_slope != 0 and abs(recent_slope) > abs(base_slope) * 1.5:
            if (recent_slope > 0) == (base_slope > 0) and abs(recent_slope / (close.iloc[-1] or 1)) > 0.001:
                return "加速"

        if abs(recent_slope) < abs(base_slope) * 0.3 and abs(base_slope) > 0:
            return "走平"

        return "稳定"

    def _detect_rubbing(self, window: pd.DataFrame, upper: float, lower: float) -> tuple:
        lookback = min(CHANNEL_RUBBING_LOOKBACK, len(window))
        recent = window.tail(lookback)
        tolerance = (upper - lower) * 0.02 if upper > lower else 0.0

        upper_touches = 0
        lower_touches = 0
        for _, row in recent.iterrows():
            if row['high'] >= upper - tolerance and row['close'] < upper:
                upper_touches += 1
            if row['low'] <= lower + tolerance and row['close'] > lower:
                lower_touches += 1

        return (
            upper_touches >= CHANNEL_RUBBING_MIN_TOUCHES,
            lower_touches >= CHANNEL_RUBBING_MIN_TOUCHES,
        )

    def _assess_neckline(self, window: pd.DataFrame) -> str:
        box = window.tail(min(30, len(window)))
        box_high = float(box['high'].quantile(0.8))
        box_low = float(box['low'].quantile(0.2))
        box_range_ratio = (box_high - box_low) / box['close'].mean() if box['close'].mean() > 0 else 1.0

        if box_range_ratio > CHANNEL_RANGE_RATIO_THRESHOLD * 2:
            return "无"

        current = float(window['close'].iloc[-1])
        if current > box_high * 1.01:
            return "颈线已突破"
        elif current < box_low * 0.99:
            return "颈线已跌破"
        elif box_range_ratio < CHANNEL_RANGE_RATIO_THRESHOLD:
            return "颈线争夺中"
        return "无"

    def _detect_top_bottom(self, window: pd.DataFrame, direction: str, position: float) -> str:
        if direction == "上升" and position > 0.95:
            return "顶部三步信号"
        if direction == "下降":
            if position < 0.30:
                return "底部三步信号"
        return "无"

    def _populate_signals(self, channel: DowChannel, df: pd.DataFrame) -> None:
        if channel.top_bottom_signal == "顶部三步信号":
            channel.risks.append("顶部三步信号：出轨→颈线→通道下沿，注意止盈")
        if channel.top_bottom_signal == "底部三步信号":
            channel.signals.append("底部三步信号：下降通道趋缓+筑底，潜在反转（切忌心急）")
        if channel.slope_state == "趋缓(扶老太太下楼)":
            channel.signals.append("斜率趋缓（扶老太太下楼）：主力温和吸筹，值得重点关注")
        if channel.is_rubbing_upper:
            channel.risks.append("摩擦上沿：多次触碰上沿未突破，多方力量外强中干")
        if channel.is_rubbing_lower:
            channel.signals.append("摩擦下沿：多次测试下沿不破，空方力量衰竭")
        if channel.neckline_signal == "颈线已突破":
            channel.signals.append("颈线已突破（衢地归多方），技术派跟风资金可能介入")
        elif channel.neckline_signal == "颈线已跌破":
            channel.risks.append("颈线已跌破（衢地归空方），技术派资金可能出逃")
        elif channel.neckline_signal == "颈线争夺中":
            channel.signals.append("颈线争夺中（交地），多空双方必战之地")

    def _calculate_score(self, c: DowChannel) -> float:
        score = 50.0
        if c.channel_direction == "上升":
            score += 10
        elif c.channel_direction == "下降":
            score -= 8

        if c.slope_state == "趋缓(扶老太太下楼)":
            score += 8
        elif c.slope_state == "加速" and c.channel_direction == "上升":
            score += 4

        if c.top_bottom_signal == "底部三步信号":
            score += 10
        elif c.top_bottom_signal == "顶部三步信号":
            score -= 12

        if c.is_rubbing_lower:
            score += 4
        if c.is_rubbing_upper:
            score -= 4

        if c.neckline_signal == "颈线已突破":
            score += 6
        elif c.neckline_signal == "颈线已跌破":
            score -= 6

        if c.position_in_channel < 0.25:
            score += 4
        elif c.position_in_channel > 0.85:
            score -= 4

        return float(max(0, min(100, score)))

    def _generate_summary(self, c: DowChannel) -> str:
        return (
            f"道氏通道：{c.channel_direction} | 斜率{c.slope_state} | "
            f"位置 {c.position_in_channel:.0%} | 颈线{c.neckline_signal}"
        )
