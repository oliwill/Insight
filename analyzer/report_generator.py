#!/usr/bin/env python3
"""
统一分析报告生成器

整合所有数据模块，生成格式化的 Markdown 分析报告
"""

import os
from pathlib import Path
from typing import Dict, Any, Sequence
from datetime import datetime

from config import Config
from data.constants import normalize_margin_ratio


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
    def generate(
        cls,
        stock_code: str,
        market_data: Dict[str, Any],
        research_score=None,
        timing_state=None,
        evidence: Sequence = (),
        wiki_base=None,
    ) -> str:
        """
        生成完整的分析报告

        Args:
            stock_code: 股票代码
            market_data: 来自 analysis_pipeline 的完整数据

        Returns:
            格式化的 Markdown 报告
        """
        # 提取数据
        stock_info = market_data.get("stock_info", {})
        fundamentals = market_data.get("fundamentals", {})
        technicals = market_data.get("technicals", {})
        wyckoff = market_data.get("wyckoff", {})
        liquidity = market_data.get("liquidity", {})
        options = market_data.get("options", {})
        earnings = market_data.get("earnings", {})
        web_search = market_data.get("web_search", {})
        supply_chain = market_data.get("supply_chain", {}) or fundamentals.get(
            "supply_chain", {}
        )

        sections = [
            cls._format_report_header(stock_code, stock_info, market_data),
            cls._section_1_overview(
                stock_code,
                stock_info,
                technicals,
                fundamentals,
                liquidity,
                options,
                wyckoff,
                earnings,
                web_search,
                research_score,
                timing_state,
                evidence or [],
                market_data,
                wiki_base=wiki_base,
            ),
        ]

        return "\n\n".join(
            section for section in sections if section and section.strip()
        )

    @classmethod
    def evaluate_quality(cls, markdown: str, market_data: Dict[str, Any] = None):
        from analyzer.report_quality import ReportQualityEvaluator

        return ReportQualityEvaluator().evaluate(markdown, market_data or {})

    @classmethod
    def _section_1_overview(
        cls,
        stock_code: str,
        stock_info: Dict,
        technicals: Dict,
        fundamentals: Dict,
        liquidity: Dict,
        options: Dict,
        wyckoff: Dict,
        earnings: Dict,
        web_search: Dict,
        research_score=None,
        timing_state=None,
        evidence: Sequence = (),
        market_data: Dict = None,
        wiki_base=None,
    ) -> str:
        """Main report body ordered for top-down reading."""
        market_data = market_data or {}
        name = stock_info.get("name") or stock_code
        sector = stock_info.get("sector", "-")
        industry = stock_info.get("industry", "-")
        price = stock_info.get("price") or 0
        change_pct = stock_info.get("change_pct") or 0
        pe_forward = fundamentals.get("pe_forward") or 0
        target_mean = fundamentals.get("target_mean_price") or 0
        target_low = fundamentals.get("target_low_price") or 0
        target_high = fundamentals.get("target_high_price") or 0
        analyst_count = fundamentals.get("analyst_count") or 0
        recommendation = (fundamentals.get("recommendation_key") or "-").upper()
        short_percent_float = liquidity.get("short_percent_float") or 0
        days_to_cover = liquidity.get("days_to_cover") or 0
        institutional_ownership = liquidity.get("institutional_ownership") or 0
        daily_dollar_volume = liquidity.get("daily_dollar_volume") or 0

        ccy = cls._currency_symbol(stock_code, stock_info)

        def fmt_money(value):
            return f"{ccy}{value:,.2f}" if value else "N/A"

        def fmt_num(value, digits=2):
            return f"{value:.{digits}f}" if value is not None else "N/A"

        def fmt_pct(value, digits=1, signed=False):
            if value is None:
                return "N/A"
            sign = "+" if signed else ""
            return f"{value:{sign}.{digits}f}%"

        # 评分
        # Research Score 缺失时保持 None 并显式展示 N/A；
        # 绝不用技术指标分（如 Wyckoff）冒充研究质量分——两层必须分离。
        research_value = getattr(research_score, "total_adjusted_score", None)
        research_display = (
            f"{research_value:.1f}/100" if research_value is not None else "N/A"
        )
        score_emoji = cls._get_score_emoji(research_value)
        timing_label = getattr(timing_state, "state", "N/A")
        timing_internal = getattr(timing_state, "internal_score", None)

        # 估值信号（无分析师目标价时保持 None，不得把缺数据显示成「高估」）
        potential = (
            (target_mean / price - 1) * 100 if price > 0 and target_mean > 0 else None
        )

        # 趋势信号
        trend_short = technicals.get("trend_short", "NEUTRAL")
        rsi = technicals.get("rsi_14", 50)
        put_call_ratio = options.get("put_call_ratio")
        put_call_display = (
            f"{put_call_ratio:.2f}" if put_call_ratio is not None else "N/A"
        )
        max_pain = options.get("max_pain")
        max_pain_display = f"{ccy}{max_pain:.2f}" if max_pain is not None else "N/A"

        supply_chain = market_data.get("supply_chain", {}) or fundamentals.get(
            "supply_chain", {}
        )
        moat_stress_test = (
            market_data.get("moat_stress_test")
            or fundamentals.get("moat_stress_test")
            or {}
        )
        moat_stress_md = cls._format_moat_stress_test(moat_stress_test)
        summary_lines = [
            "## 一、本次分析总结",
            "",
            cls._format_opening_conclusion(
                stock_code,
                stock_info,
                fundamentals,
                technicals,
                research_score,
                timing_state,
            ),
            "",
            f"**一句话判断**：{cls._get_one_line_summary(research_value, timing_label, potential, technicals, fundamentals)}",
            "",
            "| 项目 | 结论 |",
            "|---|---|",
            f"| **Research Score** | {research_display} {score_emoji} |",
            f"| **Timing State** | {timing_label}{f'（内部时机分 {timing_internal}/100）' if timing_internal is not None else ''} |",
            f"| 当前动作 | {cls._get_current_action(timing_label, research_value, potential, technicals)} |",
            f"| 主要矛盾 | {cls._get_main_tension(research_value, timing_label, potential, technicals, fundamentals)} |",
            f"| 最大风险 | {cls._get_primary_risk(potential, technicals, fundamentals, liquidity)} |",
            "",
        ]

        key_judgments = cls._format_key_judgments(
            price=price,
            potential=potential,
            technicals=technicals,
            fundamentals=fundamentals,
            liquidity=liquidity,
            options=options,
        )
        if key_judgments:
            summary_lines.extend(["### 关键判断", key_judgments, ""])

        data_quality = cls._format_data_quality_summary(
            market_data,
            fundamentals,
            technicals,
            liquidity,
            options,
            earnings,
            web_search,
        )
        if data_quality:
            summary_lines.extend(["### 数据质量提醒", data_quality, ""])

        sections = ["\n".join(summary_lines).strip()]

        evidence_and_score = [
            f"""---

## 二、公司与证据概览

**股票信息**：{name} ({stock_code}) | {sector} / {industry}
**当前价格**：{fmt_money(price)} ({fmt_pct(change_pct, 2, signed=True)})

### 证据摘要
{cls._format_evidence_summary(evidence)}

### {cls.EMOJI["chart"]} 快速评估

| 维度 | 数值 | 评级 |
|------|------|------|
| 估值 | PE(Forward) {fmt_num(pe_forward)} | {cls._get_valuation_signal(potential)} |
| 潜在涨幅 | {fmt_pct(potential, 1, signed=True)} | {cls._get_potential_emoji(potential)} |
| 趋势 | {trend_short} | {cls._get_trend_emoji(trend_short)} |
| RSI | {fmt_num(rsi, 1)} | {cls._get_rsi_signal(rsi)} |
| 做空比例 | {fmt_pct(short_percent_float * 100, 1)} | {cls._get_short_signal(short_percent_float * 100)} |
"""
        ]

        if cls._has_any_value(
            fundamentals,
            [
                "target_mean_price",
                "target_low_price",
                "target_high_price",
                "analyst_count",
                "recommendation_key",
            ],
        ):
            evidence_and_score.append(f"""### {cls.EMOJI["target"]} 分析师预期
- **目标价均值**：{fmt_money(target_mean)} ({fmt_pct(potential, 1, signed=True)})
- **目标价区间**：{fmt_money(target_low)} - {fmt_money(target_high)}
- **评级**：{recommendation} ({analyst_count} 位分析师)
""")
        sections.append(
            "\n\n".join(
                item.strip() for item in evidence_and_score if item and item.strip()
            )
        )

        supply_chain_md = cls._format_supply_chain_analysis(supply_chain)
        if cls._has_meaningful_data(fundamentals) or supply_chain_md:
            sections.append(f"""---

## 三、基本面与估值
{supply_chain_md + chr(10) + chr(10) if supply_chain_md else ""}### 护城河分析

{cls._format_moat_analysis(fundamentals)}

{moat_stress_md}

### 估值水平
| 指标 | 数值 | 评价 |
|------|------|------|
| PE (Forward) | {fmt_num(fundamentals.get("pe_forward"))} | {cls._get_pe_signal(fundamentals.get("pe_forward"))} |
| PB | {fmt_num(fundamentals.get("pb"))} | {cls._get_pb_signal(fundamentals.get("pb"))} |
| PS | {fmt_num(fundamentals.get("ps"))} | {cls._get_ps_signal(fundamentals.get("ps"))} |

### 盈利能力
| 指标 | 数值 | 评价 |
|------|------|------|
| ROE | {fmt_pct(cls._percent_value(fundamentals.get("roe")), 2)} | {cls._get_roe_signal(cls._percent_value(fundamentals.get("roe")))} |
| ROA | {fmt_pct(cls._percent_value(fundamentals.get("roa")), 2)} | {cls._get_roa_signal(cls._percent_value(fundamentals.get("roa")))} |
| 毛利率 | {fmt_pct(cls._percent_value(fundamentals.get("gross_margin")), 2)} | {cls._get_margin_signal(cls._percent_value(fundamentals.get("gross_margin")))} |
| 净利率 | {fmt_pct(cls._percent_value(fundamentals.get("profit_margin")), 2)} | {cls._get_margin_signal(cls._percent_value(fundamentals.get("profit_margin")))} |

### 成长性
- **营收增长**：{fmt_pct(cls._percent_value(fundamentals.get("revenue_growth")), 1, signed=True)} YoY {cls._get_growth_emoji(cls._percent_value(fundamentals.get("revenue_growth")))}

### 财务健康
- **流动比率**：{fmt_num(fundamentals.get("current_ratio"))} {cls._get_current_ratio_signal(fundamentals.get("current_ratio"))}
- **债务权益比**：{fmt_num(fundamentals.get("debt_equity"), 1)}
- **现金**：{cls._format_large_money(fundamentals.get("total_cash"))} | **债务**：{cls._format_large_money(fundamentals.get("total_debt"))}
- **自由现金流**：{cls._format_large_money(fundamentals.get("free_cashflow"))} {cls._get_fcf_signal(fundamentals.get("free_cashflow"))}
""")

        if cls._has_meaningful_data(technicals) or cls._has_meaningful_data(wyckoff):
            chart_gallery = cls._format_chart_gallery(
                stock_code, market_data, wiki_base
            )
            sections.append(f"""---

## 四、技术结构与五维分析
{cls._format_research_score_summary(research_score)}

### 交易时机
{cls._format_timing_summary(timing_state)}

### 价格位置
- **当前价格**：{fmt_money(price)}
- **52周区间**：{fmt_money(technicals.get("period_low"))} - {fmt_money(technicals.get("period_high"))}
- **距高点**：{fmt_pct(technicals.get("pct_from_high"), 1, signed=True)} | **距低点**：{fmt_pct(technicals.get("pct_from_low"), 1, signed=True)}

### 趋势分析
- **短期**：{trend_short} (MA5: {fmt_money(technicals.get("ma5"))} vs MA20: {fmt_money(technicals.get("ma20"))}) {cls._get_trend_emoji(trend_short)}
- **中期**：{technicals.get("trend_mid", "NEUTRAL")} (MA20 vs MA50: {fmt_money(technicals.get("ma50"))})

### 技术指标
| 指标 | 数值 | 信号 |
|------|------|------|
| RSI(14) | {fmt_num(rsi, 2)} | {cls._get_rsi_signal(rsi)} |
| MACD | {fmt_num(technicals.get("macd"), 3)} | {cls._get_macd_signal(technicals.get("macd_hist"))} |
| KDJ_K | {fmt_num(technicals.get("kdj_k"), 2)} | {cls._get_kdj_signal(technicals.get("kdj_k"), technicals.get("kdj_d"))} |

### 支撑/阻力
- **阻力**：{fmt_money(technicals.get("resistance_20d"))} (20日)
- **支撑**：{fmt_money(technicals.get("support_20d"))} (20日)

### Wyckoff 分析
- **阶段**：{wyckoff.get("phase", "N/A")}
- **区间**：{fmt_money(wyckoff.get("support"))} - {fmt_money(wyckoff.get("resistance"))}
- **置信度**：{fmt_pct(wyckoff.get("confidence"), 0)}
{chart_gallery}
""")

        if cls._has_meaningful_data(liquidity) or cls._has_meaningful_data(options):
            market_lines = ["---", "", "## 五、市场结构"]

            if cls._has_meaningful_data(liquidity):
                market_lines.append(f"""
### 流动性分析
| 指标 | 数值 | 评价 |
|------|------|------|
| 做空比例 | {fmt_pct(short_percent_float * 100, 1)} | {cls._get_short_signal(short_percent_float * 100)} |
| Days to Cover | {fmt_num(days_to_cover, 1)}天 | {cls._get_days_to_cover_signal(days_to_cover)} |
| 机构持仓 | {fmt_pct(institutional_ownership * 100, 1)} | - |
| 日均成交额 | {cls._format_large_money(daily_dollar_volume)} | {cls._get_volume_signal(daily_dollar_volume / 1_000_000 if daily_dollar_volume else None)} |
""")

            if cls._has_meaningful_data(options):
                market_lines.append(f"""
### 期权市场
- **Put/Call Ratio**：{put_call_display} {cls._get_putcall_signal(put_call_ratio)}
- **Max Pain**：{max_pain_display}
""")
            sections.append("\n".join(market_lines))

        sections.append(f"""---

## 六、操作建议
### 当前状态
{cls._get_timing_action(timing_label)} | Research Score {research_display} | Timing {timing_label}

### 交易网格
{cls._get_trading_grid(stock_info, technicals, fundamentals, wyckoff)}

### 仓位管理
- **建议仓位**：{cls._get_timing_position(timing_label, research_value)}
- **止损位**：基于 ATR 2.5x 或 {fmt_money(technicals.get("support_20d"))}
""")

        if (
            cls._has_meaningful_data(earnings)
            or cls._has_any_value(fundamentals, ["target_mean_price", "free_cashflow"])
            or cls._has_meaningful_data(liquidity)
        ):
            sections.append(f"""---

## 七、催化与风险
### {cls.EMOJI["positive"]} 向上催化
{cls._get_positive_catalysts(fundamentals, earnings, price)}

### {cls.EMOJI["negative"]} 下行风险
{cls._get_negative_risks(fundamentals, liquidity)}
""")

        if cls._has_meaningful_data(web_search):
            sections.append(f"""---

## 八、市场情绪
{cls._get_sentiment_analysis(web_search)}
""")

        gaps = cls._format_data_gaps(
            market_data,
            fundamentals,
            technicals,
            liquidity,
            options,
            earnings,
            web_search,
        )
        if gaps:
            sections.append(f"""---

## 数据缺口
{gaps}
""")

        sections.append("**免责声明**：本分析仅供参考，不构成投资建议。")
        return "\n\n".join(
            section.strip() for section in sections if section and section.strip()
        )

    @classmethod
    def _format_report_header(
        cls, stock_code: str, stock_info: Dict, market_data: Dict
    ) -> str:
        title = cls._format_report_title(stock_code, stock_info)
        data_time = cls._format_data_time(stock_info, market_data)
        return f"{title}\n\n**数据时间**：{data_time}"

    @classmethod
    def _format_report_title(cls, stock_code: str, stock_info: Dict) -> str:
        name = stock_info.get("name") or stock_code
        code = stock_info.get("code") or stock_code
        if name == code:
            return f"# {code}"
        return f"# {code} {name}"

    @classmethod
    def _format_data_time(cls, stock_info: Dict, market_data: Dict) -> str:
        raw_time = (
            market_data.get("_generated_at")
            or market_data.get("timestamp")
            or market_data.get("as_of")
            or stock_info.get("timestamp")
            or stock_info.get("last_updated")
        )
        if raw_time:
            return cls._format_timestamp(raw_time)
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    @classmethod
    def _format_timestamp(cls, value) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        text = str(value).strip()
        if not text:
            return datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
        return parsed.strftime("%Y-%m-%d %H:%M")

    @classmethod
    def _has_any_value(cls, data: Dict, keys: Sequence[str]) -> bool:
        if not isinstance(data, dict):
            return False
        for key in keys:
            value = data.get(key)
            if cls._is_meaningful_value(value):
                return True
        return False

    @classmethod
    def _has_meaningful_data(cls, data) -> bool:
        if not data:
            return False
        if isinstance(data, dict):
            if data.get("error"):
                return False
            return any(cls._is_meaningful_value(value) for value in data.values())
        if isinstance(data, (list, tuple, set)):
            return any(cls._is_meaningful_value(value) for value in data)
        return cls._is_meaningful_value(data)

    @classmethod
    def _is_meaningful_value(cls, value) -> bool:
        if value is None:
            return False
        if value == "":
            return False
        if value == "N/A":
            return False
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return True

    @classmethod
    def _format_data_gaps(
        cls,
        market_data: Dict,
        fundamentals: Dict,
        technicals: Dict,
        liquidity: Dict,
        options: Dict,
        earnings: Dict,
        web_search: Dict,
    ) -> str:
        gaps = []
        checks = [
            ("行情/技术指标", technicals, "technicals_error"),
            ("财报", earnings, "earnings_error"),
            ("流动性", liquidity, "liquidity_error"),
            ("期权", options, "options_error"),
            ("新闻/社交搜索", web_search, "web_search_error"),
        ]
        for label, data, error_key in checks:
            error = market_data.get(error_key)
            if error:
                gaps.append(f"- **{label}**：{error}")
            elif not cls._has_meaningful_data(data):
                gaps.append(f"- **{label}**：本次未取得有效数据，已从正文模块中省略")
        if market_data.get("fundamentals_error"):
            gaps.append(f"- **基本面**：{market_data.get('fundamentals_error')}")
        elif not cls._has_core_fundamental_data(fundamentals):
            gaps.append(
                "- **基本面**：本次未取得有效财务估值数据，产业链信息仅作为基本面补充"
            )
        return "\n".join(gaps)

    @classmethod
    def _has_core_fundamental_data(cls, fundamentals: Dict) -> bool:
        """只用财务/估值字段判断基本面是否有效，避免 supply_chain 掩盖数据缺口。"""
        return cls._has_any_value(
            fundamentals,
            [
                "pe_forward",
                "pe_ttm",
                "trailing_pe",
                "pb",
                "ps",
                "price_to_sales",
                "gross_margin",
                "profit_margin",
                "roe",
                "roa",
                "revenue_growth",
                "earnings_growth",
                "free_cashflow",
                "target_mean_price",
                "target_low_price",
                "target_high_price",
            ],
        )

    @classmethod
    def _get_one_line_summary(
        cls,
        research_value,
        timing_label: str,
        potential,
        technicals: Dict,
        fundamentals: Dict,
    ) -> str:
        trend_short = technicals.get("trend_short")
        rsi = technicals.get("rsi_14")
        pe_forward = fundamentals.get("pe_forward")
        ps = fundamentals.get("ps")

        if research_value is None:
            return "本次缺少研究评分数据，优先补齐证据与数据缺口后再形成结论。"
        if timing_label == "Ready" and research_value >= 60:
            return "研究质量和买点状态同时支持行动，但仍需按仓位和失效条件控制风险。"
        if timing_label == "Avoid" or research_value < 45:
            return "本次分析不支持高信心行动，优先识别风险和缺失证据。"
        if timing_label == "Wait":
            return "投资 thesis 可以继续跟踪，但当前缺少足够清晰的行动触发条件。"
        if timing_label == "Watch":
            return "本次更适合观察和补充证据，不宜直接放大仓位。"
        if trend_short == "BULLISH" and rsi is not None and rsi >= 70:
            return "趋势表现较强，但短线已经过热，本次更适合等待回调或确认新催化。"
        if potential and potential < 5 and (pe_forward or ps):
            return "目标价空间有限且估值已有压力，本次更适合审慎跟踪而非追高。"
        if research_value >= 60:
            return "公司质量具备继续研究价值，下一步重点看买点触发和关键风险。"
        return "本次结论偏中性，先看关键判断和数据缺口，再决定是否继续深挖。"

    @classmethod
    def _get_current_action(
        cls,
        timing_label: str,
        research_value,
        potential,
        technicals: Dict,
    ) -> str:
        rsi = technicals.get("rsi_14")
        if timing_label == "Ready":
            return "可行动，但按仓位上限和失效条件执行"
        if timing_label == "Wait":
            return "等待触发条件，不急于开新仓"
        if timing_label == "Watch":
            return "观察或小仓试探，优先补证据"
        if timing_label == "Avoid":
            return "回避，除非核心假设明显改善"
        if rsi is not None and rsi >= 70:
            return "不追高，等待过热缓解"
        if potential and potential < 5:
            return "目标价空间不足，等待更好风险收益"
        if research_value is not None and research_value >= 60:
            return "继续研究，等待 Timing 明确"
        return "补充数据后再判断"

    @classmethod
    def _get_main_tension(
        cls,
        research_value,
        timing_label: str,
        potential,
        technicals: Dict,
        fundamentals: Dict,
    ) -> str:
        trend_short = technicals.get("trend_short")
        rsi = technicals.get("rsi_14")
        ps = fundamentals.get("ps")
        pe_forward = fundamentals.get("pe_forward")
        revenue_growth = cls._percent_value(fundamentals.get("revenue_growth"))

        if (
            research_value is not None
            and research_value >= 60
            and timing_label in {"Wait", "Watch"}
        ):
            return "公司质量尚可，但买点质量不足"
        if trend_short == "BULLISH" and (rsi is not None and rsi >= 70):
            return "趋势强，但短线过热"
        if (
            revenue_growth
            and revenue_growth > 15
            and ((ps and ps > 10) or (pe_forward and pe_forward > 35))
        ):
            return "成长性较好，但估值压力偏高"
        if potential and potential < 5:
            return "市场预期偏乐观，但目标价空间不足"
        if timing_label == "N/A":
            return "数据可读，但 Timing 结论尚未形成"
        return "研究质量、买点和数据完整性需要一起验证"

    @classmethod
    def _get_primary_risk(
        cls,
        potential,
        technicals: Dict,
        fundamentals: Dict,
        liquidity: Dict,
    ) -> str:
        rsi = technicals.get("rsi_14")
        pct_from_high = technicals.get("pct_from_high")
        ps = fundamentals.get("ps")
        pe_forward = fundamentals.get("pe_forward")
        free_cashflow = fundamentals.get("free_cashflow")
        short_pct = liquidity.get("short_percent_float")

        if rsi is not None and rsi >= 70:
            return "高位追涨和短线回撤"
        if pct_from_high is not None and pct_from_high > -5:
            return "接近区间高位，安全边际不足"
        if (ps and ps > 10) or (pe_forward and pe_forward > 50):
            return "估值压缩"
        if free_cashflow is not None and free_cashflow < 0:
            return "自由现金流压力"
        if short_pct and short_pct * 100 > 10:
            return "高做空比例带来的波动"
        if potential and potential < 5:
            return "目标价空间不足"
        return "核心 thesis 被新事实证伪"

    @classmethod
    def _format_key_judgments(
        cls,
        price: float,
        potential,
        technicals: Dict,
        fundamentals: Dict,
        liquidity: Dict,
        options: Dict,
    ) -> str:
        judgments = []
        trend_short = technicals.get("trend_short")
        trend_mid = technicals.get("trend_mid")
        rsi = technicals.get("rsi_14")
        pct_from_high = technicals.get("pct_from_high")
        revenue_growth = cls._percent_value(fundamentals.get("revenue_growth"))
        gross_margin = cls._percent_value(fundamentals.get("gross_margin"))
        free_cashflow = fundamentals.get("free_cashflow")
        ps = fundamentals.get("ps")
        pe_forward = fundamentals.get("pe_forward")
        daily_dollar_volume = liquidity.get("daily_dollar_volume")
        short_pct = liquidity.get("short_percent_float")
        put_call = options.get("put_call_ratio")

        if trend_short == "BULLISH" and trend_mid == "BULLISH":
            if rsi is not None and rsi >= 70:
                judgments.append(
                    f"趋势较强，但 RSI {rsi:.1f} 已过热，短线不适合直接追高。"
                )
            else:
                judgments.append("短期和中期趋势均偏多，买点质量取决于回调和触发条件。")
        elif trend_short == "BEARISH" and trend_mid == "BULLISH":
            judgments.append("中期趋势仍偏多，但短期走弱，适合等待企稳信号。")

        if potential:
            if potential < 5:
                judgments.append(
                    f"目标价隐含空间仅 {potential:+.1f}%，当前风险收益不够宽。"
                )
            elif potential > 25:
                judgments.append(
                    f"目标价隐含空间 {potential:+.1f}%，估值预期仍有上行余地。"
                )

        if (
            revenue_growth is not None
            or gross_margin is not None
            or free_cashflow is not None
        ):
            quality_parts = []
            if revenue_growth is not None:
                quality_parts.append(f"营收增长 {revenue_growth:+.1f}%")
            if gross_margin is not None:
                quality_parts.append(f"毛利率 {gross_margin:.1f}%")
            if free_cashflow is not None:
                quality_parts.append(
                    "自由现金流为正" if free_cashflow > 0 else "自由现金流为负"
                )
            if quality_parts:
                judgments.append(
                    "基本面质量信号：" + "，".join(quality_parts[:3]) + "。"
                )

        if (ps and ps > 10) or (pe_forward and pe_forward > 35):
            valuation_parts = []
            if pe_forward:
                valuation_parts.append(f"Forward PE {pe_forward:.1f}")
            if ps:
                valuation_parts.append(f"PS {ps:.1f}")
            judgments.append("估值压力偏高：" + "，".join(valuation_parts) + "。")

        if daily_dollar_volume:
            if daily_dollar_volume >= 50_000_000:
                judgments.append(
                    f"流动性充足，日均成交额约 {cls._format_large_money(daily_dollar_volume)}。"
                )
            elif daily_dollar_volume < 10_000_000:
                judgments.append(
                    f"流动性偏弱，日均成交额约 {cls._format_large_money(daily_dollar_volume)}。"
                )

        if short_pct and short_pct * 100 > 10:
            judgments.append(f"做空比例 {short_pct * 100:.1f}%，波动风险需要单独管理。")
        if put_call and put_call > 2:
            judgments.append(f"Put/Call {put_call:.2f} 偏空，期权情绪不支持激进追多。")

        deduped = []
        for item in judgments:
            if item not in deduped:
                deduped.append(item)
        return "\n".join(f"- {item}" for item in deduped[:4])

    @classmethod
    def _format_data_quality_summary(
        cls,
        market_data: Dict,
        fundamentals: Dict,
        technicals: Dict,
        liquidity: Dict,
        options: Dict,
        earnings: Dict,
        web_search: Dict,
    ) -> str:
        gaps = cls._format_data_gaps(
            market_data,
            fundamentals,
            technicals,
            liquidity,
            options,
            earnings,
            web_search,
        )
        if not gaps:
            return ""
        lines = gaps.splitlines()
        return "\n".join(lines[:3])

    @classmethod
    def _format_chart_gallery(
        cls, stock_code: str, market_data: Dict, wiki_base=None
    ) -> str:
        charts = []
        wyckoff_chart = cls._format_wyckoff_chart(stock_code, wiki_base)
        if wyckoff_chart:
            charts.append(wyckoff_chart)

        for item in market_data.get("charts", []) or []:
            if isinstance(item, dict):
                path = item.get("path") or item.get("file")
                title = item.get("title") or "图表"
                alt = item.get("alt") or title
            else:
                path = str(item)
                title = Path(path).stem
                alt = title

            markdown_path = cls._chart_markdown_path(path, wiki_base)
            if markdown_path:
                charts.append(f"\n### {title}\n![{alt}]({markdown_path})")

        if not charts:
            return ""
        return "\n\n".join(charts)

    @classmethod
    def _format_opening_conclusion(
        cls,
        stock_code: str,
        stock_info: Dict,
        fundamentals: Dict,
        technicals: Dict,
        research_score=None,
        timing_state=None,
    ) -> str:
        name = stock_info.get("name") or stock_code
        industry = stock_info.get("industry") or stock_info.get("sector") or "业务"
        price = stock_info.get("price") or 0
        pe = (
            fundamentals.get("pe_forward")
            or fundamentals.get("pe_ttm")
            or fundamentals.get("trailing_pe")
        )
        pb = fundamentals.get("pb")
        target = fundamentals.get("target_mean_price") or 0
        support = technicals.get("support_20d") or 0
        potential = (target / price - 1) * 100 if price and target else 0
        ccy = cls._currency_symbol(stock_code, stock_info)

        timing_label = getattr(timing_state, "state", "N/A")
        research_value = getattr(research_score, "total_adjusted_score", None)
        if timing_label == "Ready":
            action_word = "建仓"
        elif timing_label in {"Wait", "Watch", "N/A"}:
            action_word = "观望"
        elif timing_label == "Avoid":
            action_word = "回避"
        elif potential > 0 or (research_value is not None and research_value >= 45):
            action_word = "观望"
        else:
            action_word = "回避"

        price_text = f"{ccy}{price:,.2f}" if price else "N/A"
        pe_text = f"{float(pe):.2f} 倍" if pe else "N/A"
        pb_text = f"{float(pb):.2f} 倍" if pb else "N/A"
        entry_text = f"{ccy}{support:,.2f}" if support else "等待技术触发"
        target_text = f"{ccy}{target:,.2f}" if target else "待分析师目标价/估值模型确认"

        if action_word == "建仓":
            # 只有 Timing=Ready 时才给出具体价位；目标价明确标注来自分析师共识
            tail = f"建议建仓价格 {entry_text}，目标价格（分析师共识）{target_text}。"
        else:
            tail = "暂不给出建仓价位，等待触发条件确认后再评估。"

        return (
            f"{name} 是一家{industry}公司，当前股价 {price_text}，"
            f"PE {pe_text}，PB {pb_text}，经过分析建议{action_word}，{tail}"
        )

    @classmethod
    def _format_supply_chain_analysis(cls, supply_chain: Dict) -> str:
        if not isinstance(supply_chain, dict):
            return ""
        if supply_chain.get("status") not in {"available", "fallback"}:
            return ""

        target_layer = supply_chain.get("target_layer") or {}
        lines = [
            "### 产业链位置",
            "",
            f"- **主题**：{supply_chain.get('topic', '-')}",
            f"- **公司位置**：{supply_chain.get('position') or '-'}",
            f"- **所在层级**：{target_layer.get('name', '-')}",
            f"- **瓶颈强度**：{target_layer.get('bottleneck_score', supply_chain.get('bottleneck_score', 0))}/10（{target_layer.get('bottleneck_level', supply_chain.get('bottleneck_level', '-'))}）",
            f"- **供需判断**：{target_layer.get('supply_demand', '-')}",
        ]
        opportunities = supply_chain.get("opportunities") or []
        risks = supply_chain.get("risks") or []
        if opportunities:
            lines.append("- **上行逻辑**：" + "；".join(opportunities[:3]))
        if risks:
            lines.append("- **核心风险**：" + "；".join(risks[:3]))
        return "\n".join(lines)

    @classmethod
    def _format_research_score_summary(cls, research_score) -> str:
        if not research_score:
            return "- 五维分析暂不可用"
        lines = [
            "### 五维分析",
            "",
            "| 维度 | 得分 | 证据 |",
            "|---|---:|---|",
        ]
        for dim in research_score.dimensions.values():
            evidence = (
                "; ".join((dim.data_evidence + dim.obsidian_evidence)[:2])
                or dim.adjustment_reason
                or "证据不足"
            )
            lines.append(
                f"| {dim.name} | {dim.adjusted_score:.1f}/10 | {evidence.replace('|', '/')[:80]} |"
            )
        lines.append(
            f"| **综合** | **{research_score.total_adjusted_score:.1f}/100** | **{research_score.verdict} / {research_score.confidence}** |"
        )
        return "\n".join(lines)

    # ========== 辅助方法：信号判定 ==========

    @classmethod
    def _format_wyckoff_chart(cls, stock_code: str, wiki_base=None) -> str:
        chart_name = f"{stock_code.replace('.', '_')}_wyckoff.png"
        base = Path(wiki_base) if wiki_base else Config.WIKI_BASE_DIR
        chart_path = base / "Charts" / chart_name
        if not chart_path.exists():
            return ""
        markdown_path = cls._chart_markdown_path(chart_path, wiki_base)
        if not markdown_path:
            return ""
        return f"\n### Wyckoff 图表\n![Wyckoff分析]({markdown_path})"

    @classmethod
    def _chart_markdown_path(cls, chart_path, wiki_base=None) -> str:
        if not chart_path:
            return ""
        chart_path = Path(chart_path)
        if not chart_path.is_absolute():
            base = Path(wiki_base) if wiki_base else Config.WIKI_BASE_DIR
            chart_path = base / chart_path
        if not chart_path.exists():
            return ""
        wiki_dir = (
            Path(wiki_base) if wiki_base else Config.WIKI_BASE_DIR
        ) / Config.WIKI_SUBDIR
        rel_path = Path(os.path.relpath(chart_path, wiki_dir))
        return rel_path.as_posix()

    @classmethod
    def _format_evidence_summary(cls, evidence: Sequence) -> str:
        if not evidence:
            return "- 暂无结构化 Obsidian 证据"
        lines = []
        for item in list(evidence)[:5]:
            claim = getattr(item, "claim", "")[:100]
            evidence_type = getattr(item, "evidence_type", "-")
            credibility = getattr(item, "credibility", "-")
            impact = getattr(item, "score_impact", "-")
            lines.append(f"- [{evidence_type}/{credibility}/{impact}] {claim}")
        return "\n".join(lines)

    @classmethod
    def _format_timing_summary(cls, timing_state) -> str:
        if not timing_state:
            return "- Timing State 暂不可用"
        lines = [f"- **状态**：{getattr(timing_state, 'state', 'N/A')}"]
        reasons = getattr(timing_state, "reasons", []) or []
        triggers = getattr(timing_state, "entry_triggers", []) or []
        if reasons:
            lines.append(f"- **主因**：{reasons[0]}")
        if triggers:
            lines.append(f"- **首要触发条件**：{triggers[0]}")
        return "\n".join(lines)

    @classmethod
    def _get_score_emoji(cls, score: float) -> str:
        if score is None:
            return "⚪"
        # 与 verdict 阈值对齐：≥75 高信心 / 45-75 中间 / <45 Pass
        return (
            cls.EMOJI["positive"]
            if score >= 75
            else cls.EMOJI["neutral"]
            if score >= 45
            else cls.EMOJI["negative"]
        )

    @classmethod
    def _get_valuation_signal(cls, potential) -> str:
        if potential is None:
            return f"{cls.EMOJI['neutral']} 无目标价数据"
        # 仅为「现价 vs 分析师共识目标价」的相对位置，不是内在价值判断，不过度声称
        return (
            f"{cls.EMOJI['positive']} 低于分析师共识"
            if potential > 50
            else f"{cls.EMOJI['neutral']} 接近分析师共识"
            if potential > 0
            else f"{cls.EMOJI['negative']} 高于分析师共识"
        )

    @classmethod
    def _get_potential_emoji(cls, potential) -> str:
        if potential is None:
            return "⚪"
        return (
            f"{cls.EMOJI['rocket']}"
            if potential > 50
            else f"➡️"
            if potential > 0
            else f"{cls.EMOJI['warning']}"
        )

    @classmethod
    def _get_trend_emoji(cls, trend: str) -> str:
        if trend == "BULLISH":
            return f"{cls.EMOJI['bullish']} 看多"
        if trend == "BEARISH":
            return f"{cls.EMOJI['bearish']} 看空"
        return f"{cls.EMOJI['neutral']} 中性"

    @classmethod
    def _get_rsi_signal(cls, rsi: float) -> str:
        if rsi is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['positive']} 超卖"
            if rsi < 30
            else f"{cls.EMOJI['negative']} 超买"
            if rsi > 70
            else f"{cls.EMOJI['neutral']} 中性"
        )

    @classmethod
    def _get_short_signal(cls, short_pct: float) -> str:
        return (
            f"{cls.EMOJI['warning']} 高"
            if short_pct > 10
            else f"{cls.EMOJI['positive']} 正常"
        )

    @classmethod
    def _get_macd_signal(cls, macd_hist: float) -> str:
        if macd_hist is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['positive']} 金叉"
            if macd_hist > 0
            else f"{cls.EMOJI['negative']} 死叉"
        )

    @classmethod
    def _get_kdj_signal(cls, k: float, d: float) -> str:
        if k is None or d is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return f"{cls.EMOJI['positive']}" if k > d else f"{cls.EMOJI['negative']}"

    @classmethod
    def _get_pe_signal(cls, pe: float) -> str:
        if pe is None or pe == 0:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['warning']} 亏损"
            if pe < 0
            else f"{cls.EMOJI['positive']} 合理"
            if pe < 20
            else f"{cls.EMOJI['neutral']} 偏高"
        )

    @classmethod
    def _get_pb_signal(cls, pb: float) -> str:
        if pb is None or pb == 0:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['positive']} 低"
            if pb < 1
            else f"{cls.EMOJI['neutral']} 中等"
            if pb < 3
            else f"{cls.EMOJI['negative']} 高"
        )

    @classmethod
    def _get_ps_signal(cls, ps: float) -> str:
        if ps is None or ps == 0:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['positive']} 低"
            if ps < 1
            else f"{cls.EMOJI['neutral']} 中等"
            if ps < 3
            else f"{cls.EMOJI['negative']} 高"
        )

    @classmethod
    def _get_roe_signal(cls, roe: float) -> str:
        if roe is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['positive']} 优秀"
            if roe > 15
            else f"{cls.EMOJI['neutral']} 一般"
            if roe > 0
            else f"{cls.EMOJI['negative']} 亏损"
        )

    @classmethod
    def _get_roa_signal(cls, roa: float) -> str:
        if roa is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['positive']} 优秀"
            if roa > 10
            else f"{cls.EMOJI['neutral']} 一般"
            if roa > 0
            else f"{cls.EMOJI['negative']} 亏损"
        )

    @classmethod
    def _get_margin_signal(cls, margin: float) -> str:
        if margin is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['positive']} 高"
            if margin > 40
            else f"{cls.EMOJI['neutral']} 中等"
            if margin > 20
            else f"{cls.EMOJI['negative']} 低"
        )

    @classmethod
    def _get_growth_emoji(cls, growth: float) -> str:
        if growth is None:
            return f"{cls.EMOJI['neutral']}"
        return (
            f"{cls.EMOJI['rocket']}"
            if growth > 20
            else f"➡️"
            if growth > 0
            else f"{cls.EMOJI['warning']}"
        )

    @classmethod
    def _get_current_ratio_signal(cls, ratio: float) -> str:
        if ratio is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['positive']} 健康"
            if ratio > 1.5
            else f"{cls.EMOJI['neutral']} 一般"
            if ratio > 1
            else f"{cls.EMOJI['negative']} 紧张"
        )

    @classmethod
    def _get_fcf_signal(cls, fcf: float) -> str:
        if fcf is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['positive']} 正向"
            if fcf > 0
            else f"{cls.EMOJI['negative']} 烧钱"
        )

    @classmethod
    def _get_days_to_cover_signal(cls, days: float) -> str:
        if days is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['warning']} 流动性差"
            if days > 5
            else f"{cls.EMOJI['positive']} 正常"
        )

    @classmethod
    def _get_volume_signal(cls, volume: float) -> str:
        if volume is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['warning']} 低"
            if volume < 2
            else f"{cls.EMOJI['positive']} 正常"
        )

    @classmethod
    def _get_putcall_signal(cls, ratio: float) -> str:
        if ratio is None:
            return f"{cls.EMOJI['neutral']} 无数据"
        return (
            f"{cls.EMOJI['negative']} 极度看空"
            if ratio > 10
            else f"{cls.EMOJI['neutral']} 看空"
            if ratio > 1
            else f"{cls.EMOJI['positive']} 看多"
        )

    @classmethod
    def _currency_symbol(cls, stock_code: str, stock_info: Dict) -> str:
        """按市场返回货币符号：USD→$、HKD→HK$、CNY/CNH→¥，避免 HK/CN 标的显示成美元。"""
        currency = str((stock_info or {}).get("currency") or "").upper()
        mapping = {"USD": "$", "HKD": "HK$", "CNY": "¥", "CNH": "¥"}
        if currency in mapping:
            return mapping[currency]
        code = (stock_code or "").upper()
        if code.endswith(".HK"):
            return "HK$"
        if code.startswith(("SH", "SZ")) or code.endswith((".SH", ".SZ", ".SS")):
            return "¥"
        return "$"

    @classmethod
    def _percent_value(cls, value):
        # 委托共享归一化：小数制 ×100，已是百分比原样（口径与 feishu_bot/full_report 一致）
        return normalize_margin_ratio(value)

    @classmethod
    def _format_large_money(cls, value) -> str:
        if value is None:
            return "N/A"
        v = float(value)
        if abs(v) >= 1e12:
            return f"${v / 1e12:.2f}T"
        if abs(v) >= 1e9:
            return f"${v / 1e9:.1f}B"
        return f"${v / 1e6:.1f}M"

    @classmethod
    def _get_positive_catalysts(
        cls, fundamentals: Dict, earnings: Dict, price: float = 0
    ) -> str:
        """生成向上催化因素"""
        catalysts = []

        # 财报
        history = earnings.get("history", [])
        if history:
            catalysts.append(
                f"1. **财报超预期**：下次财报 {history[0].get('date', 'N/A')}"
            )

        # 分析师目标价
        target_mean = fundamentals.get("target_mean_price") or 0
        if target_mean > 0 and price and price > 0:
            potential = (target_mean / price - 1) * 100
            catalysts.append(
                f"2. **分析师上调**：目标价均值 ${target_mean:.2f} 暗示 {potential:+.1f}% 空间"
            )

        return "\n".join(catalysts) if catalysts else "暂无"

    @classmethod
    def _get_negative_risks(cls, fundamentals: Dict, liquidity: Dict) -> str:
        """生成下行风险"""
        risks = []

        # 流动性
        daily_volume = (liquidity.get("daily_dollar_volume") or 0) / 1_000_000
        if daily_volume < 2:
            risks.append(f"**流动性风险**：日均成交额 ${daily_volume:.1f}M 较低")

        # 做空
        short_pct = (liquidity.get("short_percent_float") or 0) * 100
        if short_pct > 5:
            risks.append(f"**做空比例偏高 ({short_pct:.1f}%)**：双向波动可能加剧")

        # 现金流
        fcf = (fundamentals.get("free_cashflow") or 0) / 1_000_000
        if fcf < 0:
            risks.append(f"**现金流压力**：自由现金流 ${fcf:.1f}M")

        return (
            "\n".join(f"{i}. {risk}" for i, risk in enumerate(risks, 1))
            if risks
            else "暂无"
        )

    @classmethod
    def _get_action_emoji(cls, score: float) -> str:
        return (
            f"{cls.EMOJI['positive']} 建仓"
            if score >= 60
            else f"{cls.EMOJI['neutral']} 观望"
            if score >= 40
            else f"{cls.EMOJI['negative']} 回避"
        )

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
    def _get_timing_position(cls, timing_label: str, research_score) -> str:
        if timing_label == "Ready":
            if research_score is not None and research_score >= 75:
                return "3-5%"
            if research_score is not None and research_score >= 60:
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
        cls, stock_info: Dict, technicals: Dict, fundamentals: Dict, wyckoff: Dict
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
    def _format_moat_stress_test(cls, stress_test: Dict) -> str:
        """格式化护城河压力测试。"""
        if not isinstance(stress_test, dict) or not stress_test:
            return ""

        def _render_list(items, limit=4, key="claim"):
            lines = []
            for item in list(items or [])[:limit]:
                if isinstance(item, dict):
                    text = (
                        item.get(key)
                        or item.get("claim")
                        or item.get("hypothesis")
                        or item.get("basis")
                        or item.get("prompt_role")
                        or ""
                    )
                    if key == "claim" and item.get("source"):
                        text = (
                            f"{text}（{item.get('source')}）"
                            if text
                            else str(item.get("source"))
                        )
                else:
                    text = str(item)
                text = text.strip()
                if text:
                    lines.append(f"- {text}")
            return lines

        subject = stress_test.get("subject") or {}
        perspectives = stress_test.get("perspectives") or {}
        conclusion = stress_test.get("conclusion") or {}
        metadata = stress_test.get("metadata") or {}

        lines = ["### 护城河压力测试", ""]

        business_model = subject.get("business_model") or "-"
        company = subject.get("company") or metadata.get("company") or "-"
        sector = subject.get("sector") or "-"
        industry = subject.get("industry") or "-"
        peer_count = subject.get("peer_count")

        lines.append(
            f"- **业务边界**：{company} 主要按 {business_model} 理解，处于 {sector} / {industry} 语境。"
        )
        if peer_count is not None:
            lines.append(f"- **同行样本**：{peer_count} 家")

        if conclusion:
            business = conclusion.get("one_line_business")
            moat = conclusion.get("one_line_moat")
            hardest = conclusion.get("one_line_hardest_to_copy")
            fear = conclusion.get("one_line_market_fear")
            verify = conclusion.get("one_line_verification")
            verdict = conclusion.get("classification")
            rationale = conclusion.get("rationale")
            if business:
                lines.append(f"- **真正的生意**：{business}")
            if moat:
                lines.append(f"- **核心护城河**：{moat}")
            if hardest:
                lines.append(f"- **最难复制**：{hardest}")
            if fear:
                lines.append(f"- **市场担心**：{fear}")
            if verify:
                lines.append(f"- **未来最值得验证**：{verify}")
            if verdict:
                lines.append(
                    f"- **最终判断**：{verdict}"
                    + (f"（{rationale}）" if rationale else "")
                )
            cyclical_caveat = conclusion.get("cyclical_caveat")
            if cyclical_caveat:
                lines.append(f"- **周期性提示**：{cyclical_caveat}")

        confirmed_facts = stress_test.get("confirmed_facts") or []
        if confirmed_facts:
            lines.extend(["", "#### 已确认事实"])
            lines.extend(_render_list(confirmed_facts, limit=5, key="claim"))

        # 同行相对强弱（仅当可比字段存在时渲染）
        peer_strength = stress_test.get("peer_relative_strength") or {}
        if peer_strength.get("available") and peer_strength.get("comparisons"):
            lines.extend(["", "#### 同行相对强弱"])
            if peer_strength.get("summary"):
                lines.append(f"- {peer_strength['summary']}")
            label_map = {
                "market_cap": "市值",
                "gross_margin": "毛利率",
                "revenue_growth": "营收增速",
                "roe": "ROE",
            }
            for comp in peer_strength.get("comparisons", [])[:4]:
                metric_label = label_map.get(comp.get("metric"), comp.get("metric", ""))
                direction = "高于" if comp.get("direction") == "above" else "低于"
                if comp.get("metric") == "market_cap":
                    lines.append(
                        f"- {metric_label}{direction}同行中位数，约 {comp.get('ratio_vs_peer_median')}x"
                    )
                else:
                    lines.append(
                        f"- {metric_label}{direction}同行中位数约 {abs(comp.get('diff_percentage_points', 0)):.1f} 个百分点"
                    )

        # 三档预算攻击模拟（仅当市值可得时渲染）
        budget_tiers = stress_test.get("attack_budget_tiers") or {}
        if budget_tiers.get("available") and budget_tiers.get("tiers"):
            lines.extend(["", "#### 竞争对手攻击模拟（三档预算）"])
            tier_labels = {"low": "低预算", "mid": "中预算", "high": "高预算"}
            for tier_key in ("low", "mid", "high"):
                tier = (budget_tiers.get("tiers") or {}).get(tier_key) or {}
                if not tier:
                    continue
                lines.append(
                    f"- **{tier_labels.get(tier_key, tier_key)}**：约 ${tier.get('budget', 0) / 1e6:.0f}M"
                )
                lines.append(f"  - 首年：{tier.get('first_year_focus', '')}")
                lines.append(f"  - 三年可达：{tier.get('realistic_3_year_reach', '')}")
                lines.append(f"  - 建议姿态：{tier.get('recommended_angle', '')}")

        reasonable_inferences = stress_test.get("reasonable_inferences") or []
        if reasonable_inferences:
            lines.extend(["", "#### 合理推断"])
            lines.extend(_render_list(reasonable_inferences, limit=5, key="claim"))

        assumptions = stress_test.get("assumptions_to_verify") or []
        if assumptions:
            lines.extend(["", "#### 需要验证的假设"])
            # 按优先级排序：high → medium → low
            priority_order = {"high": 0, "medium": 1, "low": 2}
            sorted_assumptions = sorted(
                (a for a in assumptions if isinstance(a, dict)),
                key=lambda a: priority_order.get(a.get("priority"), 1),
            )
            priority_label = {"high": "高", "medium": "中", "low": "低"}
            for item in sorted_assumptions[:5]:
                hypothesis = item.get("hypothesis") or item.get("claim") or ""
                verification = item.get("verification_path") or ""
                risk = item.get("risk_if_false") or ""
                priority = item.get("priority")
                text = hypothesis
                if priority in priority_label:
                    text = f"[{priority_label[priority]}] {text}"
                if verification:
                    text += f"｜验证路径：{verification}"
                if risk:
                    text += f"｜若为假：{risk}"
                if text:
                    lines.append(f"- {text}")

        for title, key in [
            ("创业者/竞争对手视角", "founder_competitor"),
            ("产业研究员视角", "industry_researcher"),
            ("长期投资者视角", "long_term_investor"),
        ]:
            section = perspectives.get(key) or {}
            if not section:
                continue
            lines.extend(["", f"#### {title}"])
            if key == "founder_competitor":
                lines.extend(_render_list(section.get("attack_vectors"), limit=4))
                lines.extend(_render_list(section.get("defense_signals"), limit=4))
            elif key == "industry_researcher":
                lines.extend(
                    _render_list(section.get("structure_observations"), limit=4)
                )
                lines.extend(
                    _render_list(
                        section.get("profit_pool_hypotheses"), limit=3, key="claim"
                    )
                )
            else:
                lines.extend(_render_list(section.get("durability_signals"), limit=4))
                lines.extend(_render_list(section.get("fragility_signals"), limit=4))
            lines.extend(_render_list(section.get("unknowns"), limit=3))
            if section.get("conclusion"):
                lines.append(f"- **视角结论**：{section.get('conclusion')}")

        return "\n".join(line for line in lines if line is not None).strip()

    @classmethod
    def _format_moat_analysis(cls, fundamentals: Dict) -> str:
        """格式化护城河分析"""
        moat = fundamentals.get("moat")
        if not moat:
            return "> 护城河分析暂不可用"

        # 处理 dataclass 或 dict 格式
        if hasattr(moat, "dimensions"):
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
            if hasattr(d, "score"):
                name, score, rating, evidence = d.name, d.score, d.rating, d.evidence
            else:
                name = d.get("name", "-")
                score = d.get("score", 0)
                rating = d.get("rating", "-")
                evidence = d.get("evidence", "-")

            emoji = "🟢" if score >= 7 else "🟡" if score >= 5 else "🔴"
            lines.append(f"| {name} | {emoji} {score:.1f} | {rating} | {evidence} |")

        lines.append("")
        lines.append(f"**总结**: {summary}")

        return "\n".join(lines)
