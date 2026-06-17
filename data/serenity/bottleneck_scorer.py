"""瓶颈评分 + 候选公司筛选 — 纯逻辑模块。"""
from __future__ import annotations

from typing import Any, Dict, List

from .reference import BOTTLENECK_RULES


class BottleneckScorer:
    """对产业链各层级做瓶颈评分，对候选公司排序。"""

    def score_layers(self, layers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """给每个层级计算瓶颈得分，原地修改。"""
        for layer in layers:
            score = self._compute_layer_score(layer)
            layer["bottleneck_score"] = score
            layer["bottleneck_level"] = self._classify(score)
        return layers

    def rank_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按 priority -> valuation_pressure 排序后返回。"""
        sorted_list = sorted(
            candidates,
            key=lambda c: (c.get("priority", 5), self._pressure_sort_key(c.get("valuation_pressure", "high"))),
        )
        for i, c in enumerate(sorted_list, 1):
            c["priority"] = i
        return sorted_list

    def _compute_layer_score(self, layer: Dict[str, Any]) -> int:
        score = 0
        sd = (layer.get("supply_demand") or "").lower()
        if sd == "tight":
            score += BOTTLENECK_RULES["low_supplier_count"]["score"]
        exp = (layer.get("expansion_difficulty") or "").lower()
        if exp == "high":
            score += BOTTLENECK_RULES["hard_expansion"]["score"]
        if layer.get("certification_barrier"):
            score += BOTTLENECK_RULES["strict_certification"]["score"]
        sc = (layer.get("scarcity") or "").lower()
        if sc == "high":
            score += BOTTLENECK_RULES["material_scarcity"]["score"]
        return min(score, 10)

    @staticmethod
    def _classify(score: int) -> str:
        if score >= 7: return "强瓶颈"
        if score >= 5: return "中等瓶颈"
        return "弱瓶颈"

    @staticmethod
    def _pressure_sort_key(pressure: str) -> int:
        m = {"low": 0, "medium": 1, "high": 2}
        return m.get(pressure.lower(), 2)
