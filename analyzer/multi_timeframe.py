"""
多时间框架分析器 — 把 PDF 框架的大小级别交叉印证编码为可量化模块

PDF 理论映射（《应用篇 七/八/九 波浪理论在实战中的运用》）：
- "日线狗啃、月线流畅"：日线看不清往月线/周线升维
- 多时间级别交叉印证：大级别与结构最好与小级别基本一致
实现：pandas resample 生成周线/月线（不改造 LongBridgeClient）
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .base import BaseAnalyzer, AnalysisResult
from data.constants import (
    MTF_WEEKLY_MA,
    MTF_MONTHLY_MA,
    MTF_MIN_MONTHLY_ROWS,
)


@dataclass
class MultiTimeframeView:
    """多时间框架分析结果"""
    daily_trend: str = "横盘"
    weekly_trend: str = "横盘"
    monthly_trend: str = "横盘"
    alignment: str = "趋势不一致"
    consistency_score: float = 50.0
    higher_tf_signal: str = "无"
    signals: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


class MultiTimeframeAnalyzer(BaseAnalyzer):
    """多时间框架分析器"""

    @property
    def name(self) -> str:
        return "多时间框架分析"

    @property
    def description(self) -> str:
        return "基于日线/周线/月线趋势一致性检测，实现大小级别交叉印证"

    def analyze(self, data: pd.DataFrame, fundamentals: Dict) -> AnalysisResult:
        df = self._prepare_data(data)

        if len(df) < 40:
            return AnalysisResult(
                score=50,
                summary="数据不足，无法做多时间框架分析",
                details={},
                signals=["需要更多历史数据（至少 40 个交易日）"],
                risks=["多时间框架分析可靠性低"],
            )

        view = self._analyze_timeframes(df)
        score = self._calculate_score(view)
        summary = self._generate_summary(view)

        return AnalysisResult(
            score=score,
            summary=summary,
            details={
                "view": view,
                "daily_trend": view.daily_trend,
                "weekly_trend": view.weekly_trend,
                "monthly_trend": view.monthly_trend,
                "alignment": view.alignment,
                "consistency_score": round(view.consistency_score, 0),
                "higher_tf_signal": view.higher_tf_signal,
            },
            signals=view.signals,
            risks=view.risks,
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

    def _resample_ohlcv(self, df: pd.DataFrame, rule: str) -> pd.DataFrame:
        indexed = df.set_index('date') if 'date' in df.columns else df.copy()
        agg = indexed.resample(rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
        }).dropna(subset=['close'])
        return agg.reset_index()

    def _determine_trend(self, closes: pd.Series, ma_period: int) -> str:
        if len(closes) < ma_period + 2:
            return "横盘"
        ma = closes.rolling(ma_period).mean()
        current = float(closes.iloc[-1])
        ma_now = float(ma.iloc[-1])
        ma_prev = float(ma.iloc[-3])

        if pd.isna(ma_now) or pd.isna(ma_prev):
            return "横盘"

        if current > ma_now and ma_now > ma_prev:
            return "上升"
        if current < ma_now and ma_now < ma_prev:
            return "下降"
        return "横盘"

    def _analyze_timeframes(self, df: pd.DataFrame) -> MultiTimeframeView:
        daily_trend = self._determine_trend(df['close'], 20)

        weekly_df = self._resample_ohlcv(df, 'W')
        weekly_trend = self._determine_trend(weekly_df['close'], MTF_WEEKLY_MA) if len(weekly_df) >= MTF_WEEKLY_MA + 2 else "横盘"

        monthly_df = self._resample_ohlcv(df, 'ME')
        monthly_trend = "横盘"
        if len(monthly_df) >= MTF_MIN_MONTHLY_ROWS:
            monthly_trend = self._determine_trend(monthly_df['close'], MTF_MONTHLY_MA)

        trends = [daily_trend, weekly_trend, monthly_trend]
        bullish_count = trends.count("上升")
        bearish_count = trends.count("下降")

        if bullish_count == 3:
            alignment = "三级别共振多头"
            consistency = 95.0
        elif bearish_count == 3:
            alignment = "三级别共振空头"
            consistency = 90.0
        elif bullish_count == 2:
            alignment = "多级别一致多头"
            consistency = 72.0
        elif bearish_count == 2:
            alignment = "多级别一致空头"
            consistency = 68.0
        elif daily_trend != weekly_trend and daily_trend != "横盘":
            alignment = "日线与周线矛盾"
            consistency = 40.0
        else:
            alignment = "趋势不一致"
            consistency = 50.0

        higher_tf_signal = self._higher_tf_signal(daily_trend, weekly_trend, monthly_trend)

        view = MultiTimeframeView(
            daily_trend=daily_trend,
            weekly_trend=weekly_trend,
            monthly_trend=monthly_trend,
            alignment=alignment,
            consistency_score=consistency,
            higher_tf_signal=higher_tf_signal,
        )
        self._populate_signals(view)
        return view

    def _higher_tf_signal(self, daily: str, weekly: str, monthly: str) -> str:
        if monthly == "上升" and daily == "下降":
            return "月线流畅可支撑日线回踩，可借回踩布局"
        if monthly == "上升" and daily == "横盘":
            return "月线上行但日线横盘整理，等待日线方向选择"
        if monthly == "下降":
            return "月线压力未解，日线反弹需谨慎"
        if weekly == "下降" and daily == "上升":
            return "周线在调整，日线反弹可能只是次级趋势"
        if monthly == "上升" and weekly == "上升":
            return "月线周线共振上行，日线回踩即为机会"
        return "高级别信号中性"

    def _populate_signals(self, view: MultiTimeframeView) -> None:
        if view.alignment == "三级别共振多头":
            view.signals.append("日线/周线/月线三级别共振多头：最强趋势确认")
        elif view.alignment == "多级别一致多头":
            view.signals.append("多级别一致多头：大方向偏多")
        elif view.alignment == "三级别共振空头":
            view.risks.append("日线/周线/月线三级别共振空头：最强下跌确认")
        elif view.alignment == "多级别一致空头":
            view.risks.append("多级别一致空头：大方向偏空")
        elif view.alignment == "日线与周线矛盾":
            view.risks.append("日线与周线矛盾：可能处于节奏切换期，需等待方向明确")
        if "可支撑日线回踩" in view.higher_tf_signal or "共振上行" in view.higher_tf_signal:
            view.signals.append(view.higher_tf_signal)
        elif "压力" in view.higher_tf_signal or "调整" in view.higher_tf_signal:
            view.risks.append(view.higher_tf_signal)

    def _calculate_score(self, v: MultiTimeframeView) -> float:
        score = 50.0
        if v.alignment == "三级别共振多头":
            score += 14
        elif v.alignment == "多级别一致多头":
            score += 8
        elif v.alignment == "三级别共振空头":
            score -= 14
        elif v.alignment == "多级别一致空头":
            score -= 8
        elif v.alignment == "日线与周线矛盾":
            score -= 6
        return float(max(0, min(100, score)))

    def _generate_summary(self, v: MultiTimeframeView) -> str:
        return (
            f"多时间框架：日{v.daily_trend}/周{v.weekly_trend}/月{v.monthly_trend} | "
            f"{v.alignment}（一致性 {v.consistency_score:.0f}）"
        )
