"""个股供应链卡位分析。

该模块把现有 Serenity 主题扫描能力包装成“个股 → 产业链位置”的确定性分析器。
第一版不调用外部 LLM/API：优先读本地缓存，其次用内置知识库和规则映射，最后给出
可解释的 fallback 结果，避免影响主分析流水线。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from data.serenity.bottleneck_scorer import BottleneckScorer
from data.serenity.chain_analyzer import ChainAnalyzer


class StockChainAnalyzer:
    """将股票映射到 Serenity 产业链主题，并返回个股卡位摘要。"""

    TICKER_TOPIC_MAP = {
        "MU": "hbm",
        "MICRON": "hbm",
        "MICRON TECHNOLOGY": "hbm",
        "NVDA": "gpu",
        "NVIDIA": "gpu",
        "AMD": "gpu",
        "ASML": "ai 半导体",
        "MRAM": "mram",
        "EVERSPIN": "mram",
        "MNTS": "space infrastructure",
        "MOMENTUS": "space infrastructure",
    }

    KEYWORD_TOPIC_MAP = [
        (("hbm", "dram", "nand", "memory", "high bandwidth memory", "存储"), "hbm"),
        (("gpu", "graphics", "accelerator", "加速器"), "gpu"),
        (("optical", "photonics", "co-packaged", "datacenter interconnect", "光模块", "硅光"), "cpo"),
        (("space", "satellite", "orbital", "in-orbit", "太空", "卫星"), "space infrastructure"),
        (("semiconductor", "chip", "wafer", "foundry", "半导体", "芯片"), "ai 半导体"),
    ]

    def __init__(self, cache_dir: Optional[Path | str] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).resolve().parent / "cache" / "supply_chain"
        self.chain_analyzer = ChainAnalyzer()
        self.scorer = BottleneckScorer()

    def analyze(
        self,
        code: str,
        stock_info: Optional[Dict[str, Any]] = None,
        fundamentals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """分析个股在产业链中的位置。"""
        stock_info = stock_info or {}
        fundamentals = fundamentals or {}
        cache = self._load_cache(code)
        topic, source = self._resolve_topic(code, stock_info, fundamentals, cache)

        data = self.chain_analyzer.analyze(topic, "normal")
        layers = data.get("layers", []) or []
        candidates = data.get("candidates", []) or []
        self.scorer.score_layers(layers)
        self.scorer.rank_candidates(candidates)

        return self._compact_result(code, stock_info, data, source, cache)

    def _normalize_code(self, code: str) -> str:
        """把股票代码转成稳定缓存文件名。"""
        return (code or "").upper().replace(".", "_").replace("/", "_")

    def _load_cache(self, code: str) -> Optional[Dict[str, Any]]:
        """读取人工/Claude Code 写入的缓存；不存在或格式错误时返回 None。"""
        cache_path = self.cache_dir / f"{self._normalize_code(code)}.json"
        if not cache_path.exists():
            return None
        try:
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return loaded if isinstance(loaded, dict) else None

    def _resolve_topic(
        self,
        code: str,
        stock_info: Dict[str, Any],
        fundamentals: Dict[str, Any],
        cache: Optional[Dict[str, Any]],
    ) -> Tuple[str, str]:
        """按缓存、ticker、关键词、fallback 顺序解析 Serenity 主题。"""
        if cache and cache.get("topic"):
            return str(cache["topic"]), "cache"

        aliases = [code, stock_info.get("code", ""), stock_info.get("name", "")]
        normalized_aliases = {self._clean_alias(alias) for alias in aliases if alias}
        for alias in normalized_aliases:
            if alias in self.TICKER_TOPIC_MAP:
                return self.TICKER_TOPIC_MAP[alias], "knowledge_base"

        text = " ".join(
            str(part or "")
            for part in [
                stock_info.get("sector"),
                stock_info.get("industry"),
                fundamentals.get("business_summary"),
            ]
        ).lower()
        for keywords, topic in self.KEYWORD_TOPIC_MAP:
            if any(keyword.lower() in text for keyword in keywords):
                return topic, "knowledge_base"

        fallback = (stock_info.get("industry") or stock_info.get("sector") or code or "unknown").lower()
        return fallback, "deterministic_fallback"

    def _clean_alias(self, value: str) -> str:
        """规范化 ticker/company alias，便于映射。"""
        text = str(value or "").upper().strip()
        for suffix in (".US", ".HK", ".SH", ".SZ"):
            if text.endswith(suffix):
                text = text[: -len(suffix)]
        return text

    def _compact_result(
        self,
        code: str,
        stock_info: Dict[str, Any],
        data: Dict[str, Any],
        source: str,
        cache: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """把主题扫描结果压缩为个股基本面可消费的数据契约。"""
        layers = data.get("layers", []) or []
        candidates = data.get("candidates", []) or []
        target_layer = self._find_target_layer(code, stock_info, layers, candidates, cache)
        topic = data.get("topic") or (cache or {}).get("topic") or code
        status = "unknown" if source == "deterministic_fallback" else "available"

        bottleneck_score = target_layer.get("bottleneck_score", 0) if target_layer else 0
        bottleneck_level = target_layer.get("bottleneck_level") or target_layer.get("bottleneck_class") or "待确认" if target_layer else "待确认"
        peer_companies = self._extract_companies(target_layer) if target_layer else []
        company = stock_info.get("name") or stock_info.get("code") or code
        layer_name = target_layer.get("name", "待确认") if target_layer else "待确认"

        opportunities = list((cache or {}).get("opportunities", [])) or self._default_opportunities(data, target_layer)
        risks = list((cache or {}).get("risks", [])) or self._default_risks(target_layer)

        return {
            "status": status,
            "source": source,
            "topic": topic,
            "company": company,
            "company_code": stock_info.get("code") or code,
            "summary": data.get("summary", {}) or {},
            "target_layer": target_layer or {},
            "position": f"位于 {topic} 产业链的{layer_name}。",
            "bottleneck_score": bottleneck_score,
            "bottleneck_level": bottleneck_level,
            "key_customers_or_downstream": self._companies_from_layer(layers, 0),
            "key_upstream_or_inputs": self._companies_from_layer(layers, -1),
            "key_peers": peer_companies,
            "opportunities": opportunities[:3],
            "risks": risks[:3],
            "evidence": [f"知识库: {topic}" if source != "deterministic_fallback" else "确定性 fallback: 行业/主题待补充"],
            "layers": layers,
            "candidates": candidates,
        }

    def _find_target_layer(
        self,
        code: str,
        stock_info: Dict[str, Any],
        layers: list[Dict[str, Any]],
        candidates: list[Dict[str, Any]],
        cache: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """定位目标公司所在层级；找不到时返回瓶颈分最高的层级。"""
        target_layer_name = (cache or {}).get("target_layer_name")
        if target_layer_name:
            for layer in layers:
                if layer.get("name") == target_layer_name:
                    return layer

        aliases = {self._clean_alias(code), self._clean_alias(stock_info.get("code", "")), self._clean_alias(stock_info.get("name", ""))}
        for candidate in candidates:
            company_alias = self._clean_alias(candidate.get("company", ""))
            if any(alias and (alias in company_alias or company_alias in alias) for alias in aliases):
                layer_name = candidate.get("layer", "")
                for layer in layers:
                    if layer.get("name") == layer_name:
                        return layer

        # 候选清单不一定覆盖所有关键公司；继续在每个层级的关键玩家列表中匹配。
        for layer in layers:
            layer_companies = (layer.get("key_companies_global", []) or []) + (layer.get("key_companies_cn", []) or [])
            for company in layer_companies:
                company_alias = self._clean_alias(company)
                if any(alias and (alias in company_alias or company_alias in alias) for alias in aliases):
                    return layer

        scored = [layer for layer in layers if layer.get("bottleneck_score", 0) > 0]
        if scored:
            return sorted(scored, key=lambda layer: layer.get("bottleneck_score", 0), reverse=True)[0]
        return layers[0] if layers else {}

    def _extract_companies(self, layer: Dict[str, Any]) -> list[str]:
        return self._dedupe((layer.get("key_companies_global", []) or []) + (layer.get("key_companies_cn", []) or []))

    def _companies_from_layer(self, layers: list[Dict[str, Any]], index: int) -> list[str]:
        if not layers:
            return []
        try:
            layer = layers[index]
        except IndexError:
            return []
        return self._extract_companies(layer)[:5]

    def _default_opportunities(self, data: Dict[str, Any], target_layer: Dict[str, Any]) -> list[str]:
        driver = (data.get("summary", {}) or {}).get("demand_driver")
        if driver:
            return [driver]
        if target_layer and target_layer.get("supply_demand") == "tight":
            return ["所在层级供需偏紧，具备进一步验证的产业链线索"]
        return []

    def _default_risks(self, target_layer: Dict[str, Any]) -> list[str]:
        risks = []
        if target_layer and target_layer.get("expansion_difficulty") == "high":
            risks.append("扩产周期长，供给释放和资本开支节奏需验证")
        if target_layer and target_layer.get("certification_barrier"):
            risks.append("客户认证严格，订单兑现节奏存在不确定性")
        return risks or ["产业链映射仍需公告、财报和客户证据交叉验证"]

    def _dedupe(self, values: list[str]) -> list[str]:
        seen = set()
        result = []
        for value in values:
            if value and value not in seen:
                result.append(value)
                seen.add(value)
        return result
