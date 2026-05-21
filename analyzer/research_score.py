"""
Five-dimension research scoring for obsidiantrader.

The research score measures thesis/company quality. It is intentionally separate
from trading timing so technical setup does not pollute the main research score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from input.evidence import EvidenceItem


DIMENSION_WEIGHTS = {
    "行业/TAM": 0.20,
    "护城河": 0.20,
    "增长质量": 0.20,
    "估值": 0.25,
    "团队/治理": 0.15,
}


@dataclass
class ResearchDimensionScore:
    name: str
    weight: float
    base_score: float = 5.0  # 0-10
    adjusted_score: float = 5.0  # 0-10
    data_evidence: List[str] = field(default_factory=list)
    obsidian_evidence: List[str] = field(default_factory=list)
    adjustment_reason: str = ""
    confidence: str = "medium"

    @property
    def weighted_score(self) -> float:
        return self.adjusted_score * self.weight * 10


@dataclass
class ResearchScore:
    dimensions: Dict[str, ResearchDimensionScore]
    total_base_score: float
    total_adjusted_score: float
    confidence: str
    missing_evidence: List[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        score = self.total_adjusted_score
        if score >= 75:
            return "高信心"
        if score >= 60:
            return "标准建仓候选"
        if score >= 45:
            return "观察"
        return "Pass"


class ResearchScoreEngine:
    """Builds the existing five-dimension score as structured data."""

    def score(self, market_data: Dict, evidence: Optional[Sequence[EvidenceItem]] = None) -> ResearchScore:
        evidence = list(evidence or [])
        fundamentals = market_data.get("fundamentals", {}) or {}
        stock_info = market_data.get("stock_info", {}) or {}
        peers = market_data.get("peers", []) or []
        web_search = market_data.get("web_search", {}) or {}

        dimensions = {
            "行业/TAM": self._industry_score(stock_info, peers, web_search),
            "护城河": self._moat_score(fundamentals, peers),
            "增长质量": self._growth_score(fundamentals),
            "估值": self._valuation_score(fundamentals, stock_info, peers),
            "团队/治理": self._team_score(fundamentals, market_data.get("liquidity", {}) or {}),
        }

        for item in evidence:
            self._apply_evidence(dimensions, item)

        for dim in dimensions.values():
            dim.adjusted_score = self._clamp(dim.adjusted_score)
            dim.base_score = self._clamp(dim.base_score)
            dim.confidence = self._dimension_confidence(dim)

        total_base = self._weighted_total(dimensions, adjusted=False)
        total_adjusted = self._weighted_total(dimensions, adjusted=True)
        missing = self._missing_evidence(dimensions, fundamentals, peers, evidence)
        confidence = self._overall_confidence(dimensions, missing)

        return ResearchScore(
            dimensions=dimensions,
            total_base_score=round(total_base, 1),
            total_adjusted_score=round(total_adjusted, 1),
            confidence=confidence,
            missing_evidence=missing,
        )

    def _industry_score(self, stock_info: Dict, peers: List[Dict], web_search: Dict) -> ResearchDimensionScore:
        score = 5.0
        evidence = []
        sector = (stock_info.get("sector") or "").lower()
        industry = (stock_info.get("industry") or "").lower()
        growth_sectors = ["technology", "semiconductor", "software", "healthcare", "biotechnology", "ai"]

        if any(s in sector or s in industry for s in growth_sectors):
            score += 1.2
            evidence.append(f"成长型赛道: {stock_info.get('sector', '-')}/{stock_info.get('industry', '-')}")
        if peers:
            score += min(1.0, len(peers) * 0.15)
            evidence.append(f"找到 {len(peers)} 个相关同行/交叉资产")
        if web_search.get("reddit") or web_search.get("polymarket"):
            evidence.append("存在社交/预测市场关注度")

        return ResearchDimensionScore("行业/TAM", DIMENSION_WEIGHTS["行业/TAM"], score, score, data_evidence=evidence)

    def _moat_score(self, fundamentals: Dict, peers: List[Dict]) -> ResearchDimensionScore:
        moat = fundamentals.get("moat")
        evidence = []
        if moat:
            if hasattr(moat, "overall_score"):
                score = float(moat.overall_score)
                evidence.append(getattr(moat, "summary", "护城河分析可用"))
            else:
                score = float(moat.get("overall_score", 5.0) or 5.0)
                summary = moat.get("summary")
                if summary:
                    evidence.append(summary)
        else:
            gross_margin = self._percent(fundamentals.get("gross_margin"))
            roe = self._percent(fundamentals.get("roe"))
            score = 5.0
            if gross_margin and gross_margin > 40:
                score += 1.0
                evidence.append(f"毛利率 {gross_margin:.1f}% 支撑一定定价权")
            if roe and roe > 15:
                score += 0.8
                evidence.append(f"ROE {roe:.1f}% 显示资本效率较好")
        if peers:
            evidence.append("同行对比可用于验证竞争优势")
        return ResearchDimensionScore("护城河", DIMENSION_WEIGHTS["护城河"], score, score, data_evidence=evidence)

    def _growth_score(self, fundamentals: Dict) -> ResearchDimensionScore:
        score = 5.0
        evidence = []
        revenue_growth = self._percent(fundamentals.get("revenue_growth"))
        earnings_growth = self._percent(fundamentals.get("earnings_growth"))
        gross_margin = self._percent(fundamentals.get("gross_margin"))
        free_cashflow = fundamentals.get("free_cashflow") or 0

        if revenue_growth is not None:
            evidence.append(f"营收增长 {revenue_growth:+.1f}%")
            if revenue_growth > 30:
                score += 2.2
            elif revenue_growth > 15:
                score += 1.4
            elif revenue_growth > 5:
                score += 0.6
            elif revenue_growth < 0:
                score -= 1.5
        if earnings_growth is not None and earnings_growth > 15:
            score += 0.8
            evidence.append(f"盈利增长 {earnings_growth:+.1f}%")
        if gross_margin is not None and gross_margin > 45:
            score += 0.5
            evidence.append(f"毛利率 {gross_margin:.1f}%")
        if free_cashflow:
            if free_cashflow > 0:
                score += 0.5
                evidence.append("自由现金流为正")
            else:
                score -= 0.8
                evidence.append("自由现金流为负")

        return ResearchDimensionScore("增长质量", DIMENSION_WEIGHTS["增长质量"], score, score, data_evidence=evidence)

    def _valuation_score(self, fundamentals: Dict, stock_info: Dict, peers: List[Dict]) -> ResearchDimensionScore:
        score = 5.0
        evidence = []
        ps = fundamentals.get("ps") or fundamentals.get("price_to_sales")
        pe_forward = fundamentals.get("pe_forward")
        target_mean = fundamentals.get("target_mean_price") or 0
        price = stock_info.get("price") or 0
        revenue_growth = self._percent(fundamentals.get("revenue_growth"))

        if ps:
            evidence.append(f"P/S {ps:.2f}")
            if revenue_growth and revenue_growth > 0:
                psg = ps / revenue_growth
                evidence.append(f"PSG {psg:.2f}")
                if psg < 0.5:
                    score += 2.5
                elif psg < 1:
                    score += 1.5
                elif psg < 2:
                    score += 0.2
                else:
                    score -= 2.0
            elif ps < 3:
                score += 0.8
            elif ps > 10:
                score -= 1.5
        if pe_forward:
            evidence.append(f"Forward PE {pe_forward:.2f}")
            if 0 < pe_forward < 20:
                score += 0.8
            elif pe_forward > 60:
                score -= 0.8
        if price and target_mean:
            potential = (target_mean / price - 1) * 100
            evidence.append(f"分析师目标价隐含 {potential:+.1f}%")
            if potential > 30:
                score += 1.0
            elif potential < -10:
                score -= 1.0
        if peers:
            evidence.append("具备同行估值对照")

        return ResearchDimensionScore("估值", DIMENSION_WEIGHTS["估值"], score, score, data_evidence=evidence)

    def _team_score(self, fundamentals: Dict, liquidity: Dict) -> ResearchDimensionScore:
        score = 5.0
        evidence = []
        insider_ownership = liquidity.get("insider_ownership")
        insider_signal = fundamentals.get("insider_signal")
        sbc_ratio = fundamentals.get("sbc_ratio") or fundamentals.get("stock_based_compensation_ratio")

        if insider_ownership is not None:
            pct = insider_ownership * 100 if insider_ownership <= 1 else insider_ownership
            evidence.append(f"内部人持股 {pct:.1f}%")
            if pct > 10:
                score += 1.0
            elif pct < 1:
                score -= 0.3
        if insider_signal:
            evidence.append(f"内部人信号: {insider_signal}")
            signal = str(insider_signal).lower()
            if "positive" in signal or "买入" in signal or "增持" in signal:
                score += 1.0
            if "negative" in signal or "卖出" in signal or "减持" in signal:
                score -= 1.0
        if sbc_ratio:
            pct = sbc_ratio * 100 if sbc_ratio <= 1 else sbc_ratio
            evidence.append(f"SBC/Revenue {pct:.1f}%")
            if pct > 30:
                score -= 1.5
            elif pct < 10:
                score += 0.4

        return ResearchDimensionScore("团队/治理", DIMENSION_WEIGHTS["团队/治理"], score, score, data_evidence=evidence)

    def _apply_evidence(self, dimensions: Dict[str, ResearchDimensionScore], item: EvidenceItem) -> None:
        credibility_delta = {"high": 0.6, "medium": 0.35, "low": 0.15}.get(getattr(item, "credibility", "medium"), 0.25)
        impact = getattr(item, "score_impact", "confidence_only")
        if impact not in {"up", "down"}:
            delta = 0.0
        else:
            delta = credibility_delta if impact == "up" else -credibility_delta

        for dim_name in getattr(item, "affected_dimensions", []) or []:
            if dim_name not in dimensions:
                continue
            dim = dimensions[dim_name]
            dim.obsidian_evidence.append(getattr(item, "claim", "")[:160])
            if delta:
                dim.adjusted_score += delta
                direction = "上调" if delta > 0 else "下调"
                reason = f"{direction}{abs(delta):.1f}: {getattr(item, 'claim', '')[:80]}"
                dim.adjustment_reason = f"{dim.adjustment_reason}; {reason}" if dim.adjustment_reason else reason

    def _missing_evidence(
        self,
        dimensions: Dict[str, ResearchDimensionScore],
        fundamentals: Dict,
        peers: List[Dict],
        evidence: Sequence[EvidenceItem],
    ) -> List[str]:
        missing = []
        if not evidence:
            missing.append("缺少 Obsidian 材料证据")
        if not peers:
            missing.append("缺少同行/相关性对比")
        if not fundamentals.get("revenue_growth"):
            missing.append("缺少明确营收增长数据")
        if not fundamentals.get("ps") and not fundamentals.get("pe_forward"):
            missing.append("缺少估值锚点")
        for name, dim in dimensions.items():
            if not dim.data_evidence and not dim.obsidian_evidence:
                missing.append(f"{name} 证据不足")
        return missing

    def _overall_confidence(self, dimensions: Dict[str, ResearchDimensionScore], missing: List[str]) -> str:
        low_count = sum(1 for dim in dimensions.values() if dim.confidence == "low")
        if len(missing) >= 4 or low_count >= 2:
            return "low"
        if len(missing) >= 2 or low_count == 1:
            return "medium"
        return "high"

    def _dimension_confidence(self, dim: ResearchDimensionScore) -> str:
        evidence_count = len(dim.data_evidence) + len(dim.obsidian_evidence)
        if evidence_count >= 3:
            return "high"
        if evidence_count >= 1:
            return "medium"
        return "low"

    def _weighted_total(self, dimensions: Dict[str, ResearchDimensionScore], adjusted: bool) -> float:
        total = 0.0
        for dim in dimensions.values():
            score = dim.adjusted_score if adjusted else dim.base_score
            total += score * dim.weight * 10
        return total

    def _percent(self, value) -> Optional[float]:
        if value is None:
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        if abs(value) <= 1:
            return value * 100
        return value

    def _clamp(self, value: float) -> float:
        return round(max(0.0, min(10.0, float(value))), 1)

    def to_markdown(self, score: ResearchScore) -> str:
        lines = [
            "| 维度 | Base | Adjusted | 权重 | 加权分 | 证据/调整理由 | 置信度 |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
        for dim in score.dimensions.values():
            evidence = dim.adjustment_reason or "; ".join((dim.data_evidence + dim.obsidian_evidence)[:2]) or "证据不足"
            evidence = evidence.replace("|", "/")[:120]
            lines.append(
                f"| {dim.name} | {dim.base_score:.1f} | {dim.adjusted_score:.1f} | {dim.weight:.0%} | {dim.weighted_score:.1f} | {evidence} | {dim.confidence} |"
            )
        lines.append(
            f"| **综合** | **{score.total_base_score:.1f}** | **{score.total_adjusted_score:.1f}** | **100%** | **{score.total_adjusted_score:.1f}** | **{score.verdict}** | **{score.confidence}** |"
        )
        if score.missing_evidence:
            lines.append("")
            lines.append("**缺失证据:** " + "；".join(score.missing_evidence[:5]))
        return "\n".join(lines)
