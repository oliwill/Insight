#!/usr/bin/env python3
"""
统一分析报告生成器

整合所有数据模块，生成格式化的 Markdown 分析报告
"""
from typing import Dict, Any, Sequence
from datetime import datetime


class ReportGenerator:
    """分析报告生成器"""

    # Emoji 映射
    EMOJI = {
        "bullish": "📈",
        "bearish": "📉",
        "neutral": "🟡",
        "positive": "🟢",
        "negative": "🔴",
        "warning": "⚠️",
        "rocket": "🚀",
        "chart": "📊",
        "target": "🎯",
        "fire": "🔥",
    }

    @classmethod
    def generate(cls, stock_code: str, market_data: Dict[str, Any], research_score=None, timing_state=None, evidence: Sequence = None) -> str:
        """
        生成完整的分析报告

        Args:
            stock_code: 股票代码
            market_data: 来自 analysis_pipeline 的完整数据

        Returns:
            格式化的 Markdown 报告
        """
        # 提取数据
        stock_info = market_data.get('stock_info', {})
        fundamentals = market_data.get('fundamentals', {})
        technicals = market_data.get('technicals', {})
        wyckoff = market_data.get('wyckoff', {})
        liquidity = market_data.get('liquidity', {})
        options = market_data.get('options', {})
        earnings = market_data.get('earnings', {})
        web_search = market_data.get('web_search', {})

        # 生成各章节
        sections = []

        sections.append(cls._section_1_overview(stock_code, stock_info, technicals, fundamentals, liquidity, options, wyckoff, earnings, web_search, research_score, timing_state, evidence or []))
        sections.append(cls._section_2_technical(technicals, wyckoff))
        sections.append(cls._section_3_fundamental(fundamentals))
        sections.append(cls._section_4_market_structure(liquidity, options, web_search))
        sections.append(cls._section_5_catalysts(fundamentals, earnings, web_search))
        sections.append(cls._section_6_trading_plan(stock_info, technicals, fundamentals, wyckoff))

        return "\n\n".join(sections)

    @classmethod
    def _section_1_overview(cls, stock_code: str, stock_info: Dict, technicals: Dict, fundamentals: Dict, liquidity: Dict, options: Dict, wyckoff: Dict, earnings: Dict, web_search: Dict, research_score=None, timing_state=None, evidence: Sequence = ()) -> str:
        """第一部分：核心观点"""
        name = stock_info.get('name', 'Unknown')
        sector = stock_info.get('sector', '-')
        industry = stock_info.get('industry', '-')
        price = stock_info.get('price') or 0
        change_pct = stock_info.get('change_pct') or 0
        pe_forward = fundamentals.get('pe_forward') or 0
        target_mean = fundamentals.get('target_mean_price') or 0
        target_low = fundamentals.get('target_low_price') or 0
        target_high = fundamentals.get('target_high_price') or 0
        analyst_count = fundamentals.get('analyst_count') or 0
        recommendation = (fundamentals.get('recommendation_key') or '-').upper()
        short_percent_float = liquidity.get('short_percent_float') or 0
        days_to_cover = liquidity.get('days_to_cover') or 0
        institutional_ownership = liquidity.get('institutional_ownership') or 0
        daily_dollar_volume = liquidity.get('daily_dollar_volume') or 0

        def fmt_money(value):
            return f"${value:,.2f}" if value else "N/A"

        def fmt_num(value, digits=2):
            return f"{value:.{digits}f}" if value is not None else "N/A"

        def fmt_pct(value, digits=1, signed=False):
            if value is None:
                return "N/A"
            sign = "+" if signed else ""
            return f"{value:{sign}.{digits}f}%"

        # 评分
        research_value = getattr(research_score, 'total_adjusted_score', None)
        if research_value is None:
            research_value = market_score = fundamentals.get('wyckoff_score', 50)
        else:
            market_score = research_value
        score_emoji = cls._get_score_emoji(research_value)
        timing_label = getattr(timing_state, 'state', 'N/A')
        timing_internal = getattr(timing_state, 'internal_score', None)

        # 估值信号
        potential = (target_mean / price - 1) * 100 if price > 0 and target_mean > 0 else 0

        # 趋势信号
        trend_short = technicals.get('trend_short', 'NEUTRAL')
        rsi = technicals.get('rsi_14', 50)
        put_call_ratio = options.get('put_call_ratio')
        put_call_display = f"{put_call_ratio:.2f}" if put_call_ratio is not None else "N/A"
        max_pain = options.get('max_pain')
        max_pain_display = f"${max_pain:.2f}" if max_pain is not None else "N/A"

        return f"""## 一、核心观点

**Research Score**：{research_value:.1f}/100 {score_emoji}
**Timing State**：{timing_label}{f"（内部时机分 {timing_internal}/100）" if timing_internal is not None else ""}

**股票信息**：{name} ({stock_code}) | {sector} / {industry}
**当前价格**：{fmt_money(price)} ({fmt_pct(change_pct, 2, signed=True)})

### {cls.EMOJI['chart']} 快速评估

| 维度 | 数值 | 评级 |
|------|------|------|
| 估值 | PE(Forward) {fmt_num(pe_forward)} | {cls._get_valuation_signal(potential)} |
| 潜在涨幅 | {fmt_pct(potential, 1, signed=True)} | {cls._get_potential_emoji(potential)} |
| 趋势 | {trend_short} | {cls._get_trend_emoji(trend_short)} |
| RSI | {fmt_num(rsi, 1)} | {cls._get_rsi_signal(rsi)} |
| 做空比例 | {fmt_pct(short_percent_float * 100, 1)} | {cls._get_short_signal(short_percent_float * 100)} |

### 证据摘要
{cls._format_evidence_summary(evidence)}

### 交易时机
{cls._format_timing_summary(timing_state)}

### {cls.EMOJI['target']} 分析师预期
- **目标价均值**：{fmt_money(target_mean)} ({fmt_pct(potential, 1, signed=True)})
- **目标价区间**：{fmt_money(target_low)} - {fmt_money(target_high)}
- **评级**：{recommendation} ({analyst_count} 位分析师)

---

## 二、技术分析

### 价格位置
- **当前价格**：{fmt_money(price)}
- **52周区间**：{fmt_money(technicals.get('period_low'))} - {fmt_money(technicals.get('period_high'))}
- **距高点**：{fmt_pct(technicals.get('pct_from_high'), 1, signed=True)} | **距低点**：{fmt_pct(technicals.get('pct_from_low'), 1, signed=True)}

### 趋势分析
- **短期**：{trend_short} (MA5: {fmt_money(technicals.get('ma5'))} vs MA20: {fmt_money(technicals.get('ma20'))}) {cls._get_trend_emoji(trend_short)}
- **中期**：{technicals.get('trend_mid', 'NEUTRAL')} (MA20 vs MA50: {fmt_money(technicals.get('ma50'))})

### 技术指标
| 指标 | 数值 | 信号 |
|------|------|------|
| RSI(14) | {fmt_num(rsi, 2)} | {cls._get_rsi_signal(rsi)} |
| MACD | {fmt_num(technicals.get('macd'), 3)} | {cls._get_macd_signal(technicals.get('macd_hist'))} |
| KDJ_K | {fmt_num(technicals.get('kdj_k'), 2)} | {cls._get_kdj_signal(technicals.get('kdj_k'), technicals.get('kdj_d'))} |

### 支撑/阻力
- **阻力**：{fmt_money(technicals.get('resistance_20d'))} (20日)
- **支撑**：{fmt_money(technicals.get('support_20d'))} (20日)

### Wyckoff 分析
- **阶段**：{wyckoff.get('phase', 'N/A')}
- **区间**：{fmt_money(wyckoff.get('support'))} - {fmt_money(wyckoff.get('resistance'))}
- **置信度**：{fmt_pct(wyckoff.get('confidence'), 0)}

### Wyckoff 图表
![Wyckoff分析](../Charts/{stock_code.replace('.', '_')}_wyckoff.png)

---

## 三、基本面分析

### 护城河分析

{cls._format_moat_analysis(fundamentals)}

### 估值水平
| 指标 | 数值 | 评价 |
|------|------|------|
| PE (Forward) | {fmt_num(fundamentals.get('pe_forward'))} | {cls._get_pe_signal(fundamentals.get('pe_forward'))} |
| PB | {fmt_num(fundamentals.get('pb'))} | {cls._get_pb_signal(fundamentals.get('pb'))} |
| PS | {fmt_num(fundamentals.get('ps'))} | {cls._get_ps_signal(fundamentals.get('ps'))} |

### 盈利能力
| 指标 | 数值 | 评价 |
|------|------|------|
| ROE | {fmt_pct(cls._percent_value(fundamentals.get('roe')), 2)} | {cls._get_roe_signal(cls._percent_value(fundamentals.get('roe')))} |
| ROA | {fmt_pct(cls._percent_value(fundamentals.get('roa')), 2)} | {cls._get_roa_signal(cls._percent_value(fundamentals.get('roa')))} |
| 毛利率 | {fmt_pct(cls._percent_value(fundamentals.get('gross_margin')), 2)} | {cls._get_margin_signal(cls._percent_value(fundamentals.get('gross_margin')))} |
| 净利率 | {fmt_pct(cls._percent_value(fundamentals.get('profit_margin')), 2)} | {cls._get_margin_signal(cls._percent_value(fundamentals.get('profit_margin')))} |

### 成长性
- **营收增长**：{fmt_pct(cls._percent_value(fundamentals.get('revenue_growth')), 1, signed=True)} YoY {cls._get_growth_emoji(cls._percent_value(fundamentals.get('revenue_growth')))}

### 财务健康
- **流动比率**：{fmt_num(fundamentals.get('current_ratio'))} {cls._get_current_ratio_signal(fundamentals.get('current_ratio'))}
- **债务权益比**：{fmt_num(fundamentals.get('debt_equity'), 1)}
- **现金**：{cls._format_large_money(fundamentals.get('total_cash'))} | **债务**：{cls._format_large_money(fundamentals.get('total_debt'))}
- **自由现金流**：{cls._format_large_money(fundamentals.get('free_cashflow'))} {cls._get_fcf_signal(fundamentals.get('free_cashflow'))}

---

## 四、市场情绪

{cls._get_sentiment_analysis(web_search)}

---

## 五、市场结构

### 流动性分析
| 指标 | 数值 | 评价 |
|------|------|------|
| 做空比例 | {fmt_pct(short_percent_float * 100, 1)} | {cls._get_short_signal(short_percent_float * 100)} |
| Days to Cover | {fmt_num(days_to_cover, 1)}天 | {cls._get_days_to_cover_signal(days_to_cover)} |
| 机构持仓 | {fmt_pct(institutional_ownership * 100, 1)} | - |
| 日均成交额 | {cls._format_large_money(daily_dollar_volume)} | {cls._get_volume_signal(daily_dollar_volume / 1_000_000 if daily_dollar_volume else None)} |

### 期权市场
- **Put/Call Ratio**：{put_call_display} {cls._get_putcall_signal(put_call_ratio)}
- **Max Pain**：{max_pain_display}

---

## 五、催化因素

### {cls.EMOJI['positive']} 向上催化
{cls._get_positive_catalysts(fundamentals, earnings, price)}

### {cls.EMOJI['negative']} 下行风险
{cls._get_negative_risks(fundamentals, liquidity)}

---

## 六、操作建议

### 当前状态
{cls._get_timing_action(timing_label)} | Research Score {research_value:.1f}/100 | Timing {timing_label}

### 交易网格
{cls._get_trading_grid(stock_info, technicals, fundamentals, wyckoff)}

### 仓位管理
- **建议仓位**：{cls._get_timing_position(timing_label, research_value)}
- **止损位**：基于 ATR 2.5x 或 {fmt_money(technicals.get('support_20d'))}

---

**免责声明**：本分析仅供参考，不构成投资建议。
"""

    @classmethod
    def _section_2_technical(cls, technicals: Dict, wyckoff: Dict) -> str:
        """第二部分：技术分析（已合并到第一部分）"""
        return ""

    @classmethod
    def _section_3_fundamental(cls, fundamentals: Dict) -> str:
        """第三部分：基本面分析（已合并到第一部分）"""
        return ""

    @classmethod
    def _section_4_market_structure(cls, liquidity: Dict, options: Dict, web_search: Dict = None) -> str:
        """第四部分：市场结构（已合并到第一部分）"""
        return ""

    @classmethod
    def _section_5_catalysts(cls, fundamentals: Dict, earnings: Dict, web_search: Dict) -> str:
        """第五部分：催化因素（已合并到第一部分）"""
        return ""

    @classmethod
    def _section_6_trading_plan(cls, stock_info: Dict, technicals: Dict, fundamentals: Dict, wyckoff: Dict) -> str:
        """第六部分：操作建议（已合并到第一部分）"""
        return ""

    # ========== 辅助方法：信号判定 ==========

    @classmethod
    def _format_evidence_summary(cls, evidence: Sequence) -> str:
        if not evidence:
            return "- 暂无结构化 Obsidian 证据"
        lines = []
        for item in list(evidence)[:5]:
            claim = getattr(item, 'claim', '')[:100]
            evidence_type = getattr(item, 'evidence_type', '-')
            credibility = getattr(item, 'credibility', '-')
            impact = getattr(item, 'score_impact', '-')
            lines.append(f"- [{evidence_type}/{credibility}/{impact}] {claim}")
        return "\n".join(lines)

    @classmethod
    def _format_timing_summary(cls, timing_state) -> str:
        if not timing_state:
            return "- Timing State 暂不可用"
        lines = [f"- **状态**：{getattr(timing_state, 'state', 'N/A')}"]
        reasons = getattr(timing_state, 'reasons', []) or []
        triggers = getattr(timing_state, 'entry_triggers', []) or []
        if reasons:
            lines.append(f"- **主因**：{reasons[0]}")
        if triggers:
            lines.append(f"- **首要触发条件**：{triggers[0]}")
        return "\n".join(lines)

    @classmethod
    def _get_score_emoji(cls, score: float) -> str:
        score = score or 0
        return cls.EMOJI['positive'] if score >= 70 else cls.EMOJI['neutral'] if score >= 50 else cls.EMOJI['negative']

    @classmethod
    def _get_valuation_signal(cls, potential: float) -> str:
        return f"{cls.EMOJI['positive']} 低估" if potential > 50 else f"{cls.EMOJI['neutral']} 合理" if potential > 0 else f"{cls.EMOJI['negative']} 高估"

    @classmethod
    def _get_potential_emoji(cls, potential: float) -> str:
        return f"{cls.EMOJI['rocket']}" if potential > 50 else f"➡️" if potential > 0 else f"{cls.EMOJI['warning']}"

    @classmethod
    def _get_trend_emoji(cls, trend: str) -> str:
        return f"{cls.EMOJI['bullish']} 看多" if trend == "BULLISH" else f"{cls.EMOJI['bearish']} 看空"

    @classmethod
    def _get_rsi_signal(cls, rsi: float) -> str:
        if rsi is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['positive']} 超卖" if rsi < 30 else f"{cls.EMOJI['negative']} 超买" if rsi > 70 else f"{cls.EMOJI['neutral']} 中性"

    @classmethod
    def _get_short_signal(cls, short_pct: float) -> str:
        return f"{cls.EMOJI['warning']} 高" if short_pct > 10 else f"{cls.EMOJI['positive']} 正常"

    @classmethod
    def _get_macd_signal(cls, macd_hist: float) -> str:
        if macd_hist is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['positive']} 金叉" if macd_hist > 0 else f"{cls.EMOJI['negative']} 死叉"

    @classmethod
    def _get_kdj_signal(cls, k: float, d: float) -> str:
        if k is None or d is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['positive']}" if k > d else f"{cls.EMOJI['negative']}"

    @classmethod
    def _get_pe_signal(cls, pe: float) -> str:
        if pe is None or pe == 0:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['warning']} 亏损" if pe < 0 else f"{cls.EMOJI['positive']} 合理" if pe < 20 else f"{cls.EMOJI['neutral']} 偏高"

    @classmethod
    def _get_pb_signal(cls, pb: float) -> str:
        if pb is None or pb == 0:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['positive']} 低" if pb < 1 else f"{cls.EMOJI['neutral']} 中等" if pb < 3 else f"{cls.EMOJI['negative']} 高"

    @classmethod
    def _get_ps_signal(cls, ps: float) -> str:
        if ps is None or ps == 0:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['positive']} 低" if ps < 1 else f"{cls.EMOJI['neutral']} 中等" if ps < 3 else f"{cls.EMOJI['negative']} 高"

    @classmethod
    def _get_roe_signal(cls, roe: float) -> str:
        if roe is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['positive']} 优秀" if roe > 15 else f"{cls.EMOJI['neutral']} 一般" if roe > 0 else f"{cls.EMOJI['negative']} 亏损"

    @classmethod
    def _get_roa_signal(cls, roa: float) -> str:
        if roa is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['positive']} 优秀" if roa > 10 else f"{cls.EMOJI['neutral']} 一般" if roa > 0 else f"{cls.EMOJI['negative']} 亏损"

    @classmethod
    def _get_margin_signal(cls, margin: float) -> str:
        if margin is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['positive']} 高" if margin > 40 else f"{cls.EMOJI['neutral']} 中等" if margin > 20 else f"{cls.EMOJI['negative']} 低"

    @classmethod
    def _get_growth_emoji(cls, growth: float) -> str:
        if growth is None:
            return f"{cls.EMOJI['neutral']}"
        return f"{cls.EMOJI['rocket']}" if growth > 20 else f"➡️" if growth > 0 else f"{cls.EMOJI['warning']}"

    @classmethod
    def _get_current_ratio_signal(cls, ratio: float) -> str:
        if ratio is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['positive']} 健康" if ratio > 1.5 else f"{cls.EMOJI['neutral']} 一般" if ratio > 1 else f"{cls.EMOJI['negative']} 紧张"

    @classmethod
    def _get_fcf_signal(cls, fcf: float) -> str:
        if fcf is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['positive']} 正向" if fcf > 0 else f"{cls.EMOJI['negative']} 烧钱"

    @classmethod
    def _get_days_to_cover_signal(cls, days: float) -> str:
        if days is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['warning']} 流动性差" if days > 5 else f"{cls.EMOJI['positive']} 正常"

    @classmethod
    def _get_volume_signal(cls, volume: float) -> str:
        if volume is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['warning']} 低" if volume < 2 else f"{cls.EMOJI['positive']} 正常"

    @classmethod
    def _get_putcall_signal(cls, ratio: float) -> str:
        if ratio is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['negative']} 极度看空" if ratio > 10 else f"{cls.EMOJI['neutral']} 看空" if ratio > 1 else f"{cls.EMOJI['positive']} 看多"

    @classmethod
    def _percent_value(cls, value):
        if value is None:
            return None
        value = float(value)
        return value * 100 if abs(value) <= 1 else value

    @classmethod
    def _format_large_money(cls, value) -> str:
        if value is None:
            return "N/A"
        return f"${float(value) / 1_000_000:.1f}M"

    @classmethod
    def _get_positive_catalysts(cls, fundamentals: Dict, earnings: Dict, price: float = 0) -> str:
        """生成向上催化因素"""
        catalysts = []

        # 财报
        history = earnings.get('history', [])
        if history:
            catalysts.append(f"1. **财报超预期**：下次财报 {history[0].get('date', 'N/A')}")

        # 分析师目标价
        target_mean = fundamentals.get('target_mean_price') or 0
        if target_mean > 0 and price and price > 0:
            potential = (target_mean / price - 1) * 100
            catalysts.append(f"2. **分析师上调**：目标价均值 ${target_mean:.2f} 暗示 {potential:+.1f}% 空间")

        return "\n".join(catalysts) if catalysts else "暂无"

    @classmethod
    def _get_negative_risks(cls, fundamentals: Dict, liquidity: Dict) -> str:
        """生成下行风险"""
        risks = []

        # 流动性
        daily_volume = (liquidity.get('daily_dollar_volume') or 0) / 1_000_000
        if daily_volume < 2:
            risks.append(f"1. **流动性风险**：日均成交额 ${daily_volume:.1f}M 较低")

        # 做空
        short_pct = (liquidity.get('short_percent_float') or 0) * 100
        if short_pct > 5:
            risks.append(f"2. **做空挤压风险**")

        # 现金流
        fcf = (fundamentals.get('free_cashflow') or 0) / 1_000_000
        if fcf < 0:
            risks.append(f"3. **现金流压力**：自由现金流 ${fcf:.1f}M")

        return "\n".join(risks) if risks else "暂无"

    @classmethod
    def _get_action_emoji(cls, score: float) -> str:
        return f"{cls.EMOJI['positive']} 建仓" if score >= 60 else f"{cls.EMOJI['neutral']} 观望" if score >= 40 else f"{cls.EMOJI['negative']} 回避"

    @classmethod
    def _get_timing_action(cls, timing_label: str) -> str:
        mapping = {
            "Ready": f"{cls.EMOJI['positive']} 可行动",
            "Wait": f"{cls.EMOJI['neutral']} 等待",
            "Watch": f"{cls.EMOJI['neutral']} 观察",
            "Avoid": f"{cls.EMOJI['negative']} 回避",
        }
        return mapping.get(timing_label, f"{cls.EMOJI['neutral']} 未知")

    @classmethod
    def _get_timing_position(cls, timing_label: str, research_score: float) -> str:
        if timing_label == "Ready":
            if research_score >= 75:
                return "3-5%"
            if research_score >= 60:
                return "2-3%"
            return "≤1%"
        if timing_label == "Wait":
            return "0%，等待触发条件"
        if timing_label == "Watch":
            return "0-1%，仅观察/小仓试探"
        return "0%"

    @classmethod
    def _get_action_text(cls, score: float) -> str:
        return "建仓" if score >= 60 else "观望" if score >= 40 else "回避"

    @classmethod
    def _get_position_size(cls, score: float) -> str:
        return "2-3%" if score >= 60 else "1-2%" if score >= 40 else "0%"

    @classmethod
    def _get_sentiment_analysis(cls, web_search: Dict) -> str:
        """生成情绪分析"""
        try:
            from data.sentiment_analyzer import SentimentAnalyzer
            analyzer = SentimentAnalyzer()
            result = analyzer.analyze(web_search)
            return analyzer.format_result(result)
        except Exception as e:
            return f"情绪分析暂不可用: {e}"

    @classmethod
    def _get_trading_grid(
        cls,
        stock_info: Dict,
        technicals: Dict,
        fundamentals: Dict,
        wyckoff: Dict
    ) -> str:
        """生成交易网格"""
        try:
            from analyzer.trading_grid import TradingGridGenerator
            generator = TradingGridGenerator()
            levels = generator.generate(stock_info, technicals, fundamentals, wyckoff)
            return generator.format_grid(levels)
        except Exception as e:
            return f"交易网格生成失败: {e}"

    @classmethod
    def _format_moat_analysis(cls, fundamentals: Dict) -> str:
        """格式化护城河分析"""
        moat = fundamentals.get("moat")
        if not moat:
            return "> 护城河分析暂不可用"

        # 处理 dataclass 或 dict 格式
        if hasattr(moat, 'dimensions'):
            # Dataclass 对象
            dimensions = moat.dimensions
            overall_score = moat.overall_score
            overall_rating = moat.overall_rating
            summary = moat.summary
        else:
            # Dict 格式
            dimensions = moat.get("dimensions", [])
            overall_score = moat.get("overall_score", 0)
            overall_rating = moat.get("overall_rating", "-")
            summary = moat.get("summary", "")

        if not dimensions:
            return "> 护城河分析暂不可用"

        # 构建评分表格
        lines = [
            f"**综合评分**: {overall_score}/10 ({overall_rating})",
            "",
            "| 维度 | 评分 | 评级 | 关键证据 |",
            "|------|------|------|----------|",
        ]

        for d in dimensions:
            if hasattr(d, 'score'):
                name, score, rating, evidence = d.name, d.score, d.rating, d.evidence
            else:
                name = d.get("name", "-")
                score = d.get("score", 0)
                rating = d.get("rating", "-")
                evidence = d.get("evidence", "-")

            emoji = "🟢" if score >= 7 else "🟡" if score >= 5 else "🔴"
            lines.append(
                f"| {name} | {emoji} {score:.1f} | {rating} | {evidence} |"
            )

        lines.append("")
        lines.append(f"**总结**: {summary}")

        return "\n".join(lines)
