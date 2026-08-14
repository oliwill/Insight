"""
Trading timing engine for obsidiantrader.

Produces a state machine for entry quality while keeping timing separate from
the five-dimension research score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TimingState:
    state: str
    internal_score: int
    reasons: List[str] = field(default_factory=list)
    entry_triggers: List[str] = field(default_factory=list)
    invalidation_triggers: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)


class TimingEngine:
    """Build Ready/Wait/Watch/Avoid timing state from market context."""

    def analyze(
        self, market_data: Dict, research_score: Optional[float] = None
    ) -> TimingState:
        stock_info = market_data.get("stock_info", {}) or {}
        technicals = market_data.get("technicals", {}) or {}
        wyckoff = market_data.get("wyckoff", {}) or {}
        earnings = market_data.get("earnings", {}) or {}
        liquidity = market_data.get("liquidity", {}) or {}
        options = market_data.get("options", {}) or {}
        web_search = market_data.get("web_search", {}) or {}
        fundamentals = market_data.get("fundamentals", {}) or {}
        # 趋势博弈分析框架技术分析模块
        volume_profile = market_data.get("volume_profile", {}) or {}
        dow_channel = market_data.get("dow_channel", {}) or {}
        force_balance = market_data.get("force_balance", {}) or {}
        multi_timeframe = market_data.get("multi_timeframe", {}) or {}

        score = 50
        reasons: List[str] = []
        entry_triggers: List[str] = []
        invalidation_triggers: List[str] = []
        risk_flags: List[str] = []
        ccy = self._currency_symbol(stock_info)

        score += self._trend_score(technicals, reasons, entry_triggers)
        score += self._wyckoff_score(
            wyckoff, reasons, entry_triggers, invalidation_triggers, ccy
        )
        score += self._volume_score(volume_profile, reasons, risk_flags)
        score += self._channel_score(
            dow_channel, reasons, entry_triggers, risk_flags, ccy
        )
        score += self._force_balance_score(
            force_balance, reasons, risk_flags, volume_profile.get("regime", "")
        )
        score += self._timeframe_score(multi_timeframe, reasons, risk_flags)
        score += self._price_quality_score(
            stock_info, technicals, fundamentals, reasons, entry_triggers, ccy
        )
        score += self._catalyst_score(earnings, reasons, risk_flags)
        score += self._liquidity_score(liquidity, reasons, risk_flags, ccy)
        score += self._sentiment_score(
            web_search, options, liquidity, reasons, risk_flags
        )

        if research_score is not None:
            if research_score >= 75:
                score += 4
                reasons.append("Research Score 高，允许更积极等待低风险买点")
            elif research_score < 45:
                score -= 12
                risk_flags.append("Research Score 低，交易时机再好也只适合短线或放弃")

        score = int(max(0, min(100, score)))
        state = self._state_from_score(score, risk_flags, research_score)

        if not entry_triggers:
            entry_triggers.append("等待价格、催化剂或趋势结构给出更明确触发条件")
        if not invalidation_triggers:
            support = technicals.get("support_20d")
            if support:
                invalidation_triggers.append(
                    f"跌破 20 日支撑 {ccy}{support:.2f} 且放量"
                )
            else:
                invalidation_triggers.append("核心 thesis 被新事实证伪或风险收益转负")

        return TimingState(
            state=state,
            internal_score=score,
            reasons=reasons[:8],
            entry_triggers=entry_triggers[:6],
            invalidation_triggers=invalidation_triggers[:6],
            risk_flags=risk_flags[:6],
        )

    @staticmethod
    def _currency_symbol(stock_info: Dict) -> str:
        """按市场返回货币符号，避免 HK/CN 标的的价位显示成美元。

        优先用 stock_info.currency；缺失或未知时按 code 后缀/前缀推断。
        """
        currency = str(stock_info.get("currency") or "").upper()
        symbol = {"USD": "$", "HKD": "HK$", "CNY": "¥", "CNH": "¥"}.get(currency)
        if symbol:
            return symbol
        code = str(stock_info.get("code") or "").upper()
        if code.endswith(".HK"):
            return "HK$"
        if code.startswith(("SH", "SZ")):
            return "¥"
        return "$"

    def _trend_score(
        self, technicals: Dict, reasons: List[str], entry_triggers: List[str]
    ) -> int:
        score = 0
        trend_short = technicals.get("trend_short")
        trend_mid = technicals.get("trend_mid")
        rsi = technicals.get("rsi_14")
        vol_ratio = technicals.get("vol_ratio")

        if trend_short == "BULLISH":
            score += 6
            reasons.append("短期趋势多头")
        elif trend_short == "BEARISH":
            score -= 5
            reasons.append("短期趋势偏弱")

        if trend_mid == "BULLISH":
            score += 6
            reasons.append("中期趋势多头")
        elif trend_mid == "BEARISH":
            score -= 5

        if rsi is not None:
            if 40 <= rsi <= 65:
                score += 5
                reasons.append(f"RSI {rsi:.1f} 位于健康区间")
            elif rsi > 75:
                score -= 8
                reasons.append(f"RSI {rsi:.1f} 过热，追高风险上升")
                entry_triggers.append("等待 RSI 从过热区回落后再评估")
            elif rsi < 30:
                score -= 2
                entry_triggers.append("若超卖后重新站回关键均线，可转为试探机会")

        if vol_ratio is not None:
            if 0.7 <= vol_ratio <= 1.5:
                score += 2
            elif vol_ratio > 2:
                score -= 3
                reasons.append("短期成交量显著放大，需判断是否情绪拥挤")

        return score

    def _wyckoff_score(
        self,
        wyckoff: Dict,
        reasons: List[str],
        entry_triggers: List[str],
        invalidation_triggers: List[str],
        ccy: str = "$",
    ) -> int:
        if not wyckoff:
            # 数据缺失只降低置信度，不把「数据不可得」当作「时机差」扣分
            reasons.append("缺少 Wyckoff 结构，Timing 置信度下降")
            return 0

        phase = str(wyckoff.get("phase", "")).lower()
        support = wyckoff.get("support")
        resistance = wyckoff.get("resistance")
        confidence = wyckoff.get("confidence") or 0
        score = 0

        if (
            "markup" in phase
            or "accumulation" in phase
            or "吸筹" in phase
            or "上升" in phase
        ):
            score += 10
            reasons.append(f"Wyckoff 阶段偏正面: {wyckoff.get('phase')}")
        elif (
            "distribution" in phase
            or "markdown" in phase
            or "派发" in phase
            or "下跌" in phase
        ):
            score -= 12
            reasons.append(f"Wyckoff 阶段偏负面: {wyckoff.get('phase')}")

        if confidence >= 70:
            score += 3
        elif confidence and confidence < 45:
            score -= 2

        if support:
            entry_triggers.append(
                f"回调接近 Wyckoff 支撑 {ccy}{support:.2f} 且不放量跌破"
            )
            invalidation_triggers.append(f"有效跌破 Wyckoff 支撑 {ccy}{support:.2f}")
        if resistance:
            entry_triggers.append(
                f"放量突破 Wyckoff 阻力 {ccy}{resistance:.2f} 后回踩确认"
            )

        return score

    # ------------------------------------------------------------------
    # 趋势博弈分析框架子分：成交量语言 / 道氏通道 / 多空博弈 / 多时间框架
    # ------------------------------------------------------------------
    def _volume_score(
        self, volume_profile: Dict, reasons: List[str], risk_flags: List[str]
    ) -> int:
        """成交量语言子分（趋势博弈分析框架：平量推升/量价齐升/量价紊乱/爆冲巨量）"""
        if not volume_profile:
            return 0
        regime = volume_profile.get("regime", "")
        score = 0
        if regime == "平量推升":
            score += 12
            reasons.append("平量推升：筹码锁定，最优质量价形态")
        elif regime == "量价齐升":
            score += 6
            reasons.append("量价齐升，确定性较高")
        elif regime == "爆冲巨量":
            score -= 10
            reasons.append("爆冲巨量疑似抢帽子出货")
            risk_flags.append(
                "爆冲巨量骗局风险：趋势博弈框架四问法审视，等量能平静后再看"
            )
        elif regime == "量价紊乱":
            score -= 4
            reasons.append("量价紊乱，等待缩量后标志K线")
        elif regime == "缩量阴跌":
            score -= 6
            reasons.append("缩量阴跌，动能衰竭")
        return score

    def _channel_score(
        self,
        dow_channel: Dict,
        reasons: List[str],
        entry_triggers: List[str],
        risk_flags: List[str],
        ccy: str = "$",
    ) -> int:
        """道氏通道子分（趋势博弈分析框架：通道/斜率/颈线/顶底信号）"""
        if not dow_channel:
            return 0
        score = 0
        direction = dow_channel.get("channel_direction", "")
        slope_state = dow_channel.get("slope_state", "")
        neckline = dow_channel.get("neckline_signal", "")
        top_bottom = dow_channel.get("top_bottom_signal", "")
        position = dow_channel.get("position_in_channel", 0.5)
        lower = dow_channel.get("lower_channel")

        if direction == "上升":
            score += 4
        elif direction == "下降":
            score -= 4
        if "趋缓" in slope_state:
            score += 2
            reasons.append("下跌斜率趋缓：下跌动能衰竭，需底部确认后才可行动")
        if top_bottom == "底部三步信号":
            score += 6
            reasons.append("道氏底部三步信号：通道趋缓+筑底")
            if lower:
                entry_triggers.append(
                    f"道氏通道下沿 {ccy}{lower:.2f} 附近为潜在底部建仓区"
                )
        elif top_bottom == "下跌减速观察":
            score += 1
            reasons.append("下降通道低位但减速未确认，不接飞刀")
        elif top_bottom == "顶部出轨警示":
            score -= 3
            reasons.append("价格出轨通道上沿，警惕假突破回落（顶部未确认）")
        elif top_bottom == "顶部三步信号":
            score -= 8
            reasons.append("道氏顶部三步信号确认：出轨后跌破颈线")
            risk_flags.append("顶部信号确认：注意分批止盈")
        if neckline == "颈线已突破":
            score += 4
            reasons.append("颈线已突破，技术派跟风资金可能介入")
        elif neckline == "颈线已跌破":
            score -= 4
            reasons.append("颈线已跌破，技术派资金可能出逃")
        if position < 0.25:
            score += 2
        elif position > 0.85:
            score -= 2
        return score

    def _force_balance_score(
        self,
        force_balance: Dict,
        reasons: List[str],
        risk_flags: List[str],
        volume_regime: str = "",
    ) -> int:
        """多空博弈子分（趋势博弈分析框架：九地形态/抢帽子/筹码锁定）"""
        if not force_balance:
            return 0
        score = 0
        acc = force_balance.get("accumulation_evidence", 50)
        chip = force_balance.get("chip_lock_likelihood", 50)
        dist = force_balance.get("distribution_evidence", 50)
        trap = force_balance.get("retail_trap_risk", 50)

        if acc and acc >= 65:
            score += 5
            reasons.append(f"主力吸筹证据较强（{acc:.0f}）")
        if chip and chip >= 65:
            if volume_regime == "平量推升":
                # 与成交量语言的「平量推升」同源（量比+涨幅），不重复计分
                reasons.append(
                    f"筹码锁定可能性高（{chip:.0f}）：与平量推升同源，不重复计分"
                )
            else:
                score += 4
                reasons.append(f"筹码锁定可能性高（{chip:.0f}）：基石仓位")
        if dist and dist >= 70:
            score -= 6
            reasons.append(f"主力派发证据较强（{dist:.0f}）")
        if trap and trap >= 70:
            score -= 5
            risk_flags.append(f"散户陷阱风险高（{trap:.0f}）：疑似抢帽子游戏")
            reasons.append("散户陷阱风险高，趋势博弈框架四问法审视")
        elif trap and trap >= 60:
            score -= 2
        return score

    def _timeframe_score(
        self, multi_timeframe: Dict, reasons: List[str], risk_flags: List[str]
    ) -> int:
        """多时间框架子分（趋势博弈分析框架：大小级别交叉印证）"""
        if not multi_timeframe:
            return 0
        score = 0
        alignment = multi_timeframe.get("alignment", "")
        higher_signal = multi_timeframe.get("higher_tf_signal", "")

        if alignment == "三级别共振多头":
            score += 6
            reasons.append("日/周/月三级别共振多头")
        elif alignment == "多级别一致多头":
            score += 3
            reasons.append("多级别一致多头")
        elif alignment == "三级别共振空头":
            score -= 6
            reasons.append("日/周/月三级别共振空头")
            risk_flags.append("三级别共振空头，趋势确认向下")
        elif alignment == "多级别一致空头":
            score -= 3
        elif alignment == "日线与周线矛盾":
            score -= 4
            reasons.append("日线与周线矛盾，可能处于节奏切换期")

        if "可支撑日线回踩" in higher_signal or "共振上行" in higher_signal:
            reasons.append(higher_signal)
        elif "压力" in higher_signal or "调整" in higher_signal:
            risk_flags.append(higher_signal)
        return score

    def _price_quality_score(
        self,
        stock_info: Dict,
        technicals: Dict,
        fundamentals: Dict,
        reasons: List[str],
        entry_triggers: List[str],
        ccy: str = "$",
    ) -> int:
        price = stock_info.get("price") or 0
        target = fundamentals.get("target_mean_price") or 0
        ma20 = technicals.get("ma20")
        ma50 = technicals.get("ma50")
        support = technicals.get("support_20d")
        pct_from_high = technicals.get("pct_from_high")
        score = 0

        if price and target:
            potential = (target / price - 1) * 100
            if potential > 25:
                score += 7
                reasons.append(f"分析师目标价隐含 {potential:+.1f}% 空间")
            elif potential < 0:
                score -= 6
                reasons.append(f"目标价低于现价，风险收益偏弱 ({potential:+.1f}%)")

        if price and ma50:
            distance = (price / ma50 - 1) * 100
            if -3 <= distance <= 8:
                score += 6
                reasons.append("价格接近 MA50，买点质量较好")
            elif distance > 20:
                score -= 6
                entry_triggers.append(f"等待回调接近 MA50 {ccy}{ma50:.2f}")

        if pct_from_high is not None:
            if pct_from_high > -8:
                score -= 2
                reasons.append("价格接近区间高位，追高需谨慎")
            elif -30 <= pct_from_high <= -10:
                score += 3

        if support and price:
            entry_triggers.append(
                f"若回调到 20 日支撑 {ccy}{support:.2f} 附近企稳，可重新评估"
            )
        elif ma20:
            entry_triggers.append(
                f"若回调到 MA20 {ccy}{ma20:.2f} 附近缩量企稳，可重新评估"
            )

        return score

    def _catalyst_score(
        self, earnings: Dict, reasons: List[str], risk_flags: List[str]
    ) -> int:
        if not earnings or earnings.get("error"):
            return 0
        score = 0
        days = earnings.get("days_until_earnings")
        if days is not None:
            if 0 <= days <= 10:
                score -= 6
                risk_flags.append("财报窗口极近，隔夜跳空风险高")
            elif 10 < days <= 30:
                score -= 2
                reasons.append("财报窗口 30 天内，需要情景预判")
            elif days > 30:
                score += 1
        if earnings.get("next_earnings_date"):
            reasons.append(f"下次财报: {earnings.get('next_earnings_date')}")
        return score

    def _liquidity_score(
        self, liquidity: Dict, reasons: List[str], risk_flags: List[str], ccy: str = "$"
    ) -> int:
        if not liquidity or liquidity.get("error"):
            # 数据缺失只降低置信度，不把「数据不可得」当作「时机差」扣分
            reasons.append("缺少流动性数据，Timing 置信度下降")
            return 0
        score = 0
        dollar_vol = liquidity.get("daily_dollar_volume") or 0
        short_pct = liquidity.get("short_percent_float")
        days_cover = liquidity.get("days_to_cover")

        if dollar_vol:
            if dollar_vol >= 50_000_000:
                score += 5
                reasons.append("日均成交额充足")
            elif dollar_vol < 10_000_000:
                score -= 8
                risk_flags.append(
                    f"日均成交额偏低 ({ccy}{dollar_vol / 1e6:.1f}M)，仓位需受限"
                )
        if short_pct:
            pct = short_pct * 100
            if pct > 20:
                score -= 4
                risk_flags.append(f"做空比例极高 ({pct:.1f}%)，波动风险大")
            elif pct > 10:
                score -= 2
                reasons.append(
                    f"做空比例较高 ({pct:.1f}%)，可能带来 squeeze 也带来波动"
                )
        if days_cover and days_cover > 5:
            score -= 3
            risk_flags.append(f"Days to Cover {days_cover:.1f}，流动性压力较高")
        for flag in liquidity.get("risk_flags", [])[:2]:
            risk_flags.append(flag)

        return score

    def _sentiment_score(
        self,
        web_search: Dict,
        options: Dict,
        liquidity: Dict,
        reasons: List[str],
        risk_flags: List[str],
    ) -> int:
        score = 0
        reddit_count = len(web_search.get("reddit", []) or []) if web_search else 0
        poly_count = len(web_search.get("polymarket", []) or []) if web_search else 0
        put_call = options.get("put_call_ratio") if options else None

        if reddit_count >= 5:
            score -= 2
            risk_flags.append("Reddit 讨论较多，需警惕情绪拥挤")
        elif reddit_count > 0:
            reasons.append("存在社区讨论，可作为情绪观察")
        if poly_count > 0:
            reasons.append("存在 Polymarket 相关事件，可辅助判断催化剂")
        if put_call:
            if put_call > 2:
                score -= 3
                risk_flags.append(f"Put/Call {put_call:.2f} 偏空")
            elif 0.5 <= put_call <= 1.2:
                score += 1

        return score

    def _state_from_score(
        self, score: int, risk_flags: List[str], research_score: Optional[float]
    ) -> str:
        if research_score is not None and research_score < 45:
            return "Avoid" if score < 70 else "Watch"
        # 财报窗口极近（≤10 天）是硬性风险：无论分数多高都不给 Ready，隔夜跳空不可控
        if any("极近" in flag for flag in risk_flags):
            if score >= 55:
                return "Wait"
            if score >= 40:
                return "Watch"
            return "Avoid"
        if any("偏低" in flag for flag in risk_flags) and score < 75:
            return "Wait"
        if score >= 75:
            return "Ready"
        if score >= 55:
            return "Wait"
        if score >= 40:
            return "Watch"
        return "Avoid"

    def to_markdown(self, timing: TimingState) -> str:
        lines = [
            f"状态：**{timing.state}**",
            f"内部时机分：约 **{timing.internal_score}/100**",
            "",
            "### 主要原因",
        ]
        lines.extend([f"- {reason}" for reason in timing.reasons] or ["- 暂无明确原因"])
        lines.append("")
        if timing.risk_flags:
            lines.append("### 风险标记")
            lines.extend(f"- {flag}" for flag in timing.risk_flags)
            lines.append("")
        lines.append("### 触发条件")
        lines.extend(f"- {trigger}" for trigger in timing.entry_triggers)
        lines.append("")
        lines.append("### 失效条件")
        lines.extend(f"- {trigger}" for trigger in timing.invalidation_triggers)
        return "\n".join(lines)
