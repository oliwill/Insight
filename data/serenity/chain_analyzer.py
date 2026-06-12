"""热点解析 + 产业链拆解 — LLM 知识驱动模块。

_build_from_knowledge() 直接使用 LLM 训练知识构建产业链 JSON。
不依赖外部 API 调用，适用于 normal depth。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .reference import LAYER_TEMPLATE, SERENITY_PROMPT, LAYER_MAP, INDUSTRY_KNOWLEDGE


class ChainAnalyzer:
    """将热点主题拆解为结构化产业链分析。"""

    def analyze(self, topic: str, depth: str = "normal") -> Dict[str, Any]:
        """主入口。normal 深度直接使用 LLM 知识构建 JSON。"""
        topic_clean = topic.strip().lower()
        # 先尝试知识库精确匹配
        result = self._build_from_knowledge(topic_clean)
        result["depth"] = depth
        return result

    def _build_from_knowledge(self, topic: str) -> Dict[str, Any]:
        """基于 LLM 训练知识输出结构化产业链 JSON。"""
        # 尝试匹配已知产业主题
        matched = INDUSTRY_KNOWLEDGE.get(topic)
        if matched is not None:
            return self._apply_knowledge(topic, matched)

        # 模糊匹配：关键词包含
        for key, knowledge in INDUSTRY_KNOWLEDGE.items():
            if key in topic or topic in key:
                return self._apply_knowledge(topic, knowledge)

        # 匹配 LAYER_MAP 中的别名
        canonical = LAYER_MAP.get(topic, topic)
        matched2 = INDUSTRY_KNOWLEDGE.get(canonical)
        if matched2 is not None:
            return self._apply_knowledge(canonical, matched2)

        # 无匹配，返回骨架结构
        return self._skeleton(topic)

    def _skeleton(self, topic: str) -> Dict[str, Any]:
        """返回空骨架结构。"""
        return {
            "topic": topic,
            "depth": "normal",
            "summary": {"description": "（待 LLM 解析）" + topic, "demand_driver": "（待补充）"},
            "layers": [
                {
                    "name": layer,
                    "key_companies_cn": [],
                    "key_companies_global": [],
                    "supply_demand": "unknown",
                    "expansion_difficulty": "unknown",
                    "certification_barrier": False,
                    "scarcity": "unknown",
                }
                for layer in LAYER_TEMPLATE
            ],
            "candidates": [],
        }

    def _apply_knowledge(self, topic: str, k: dict) -> Dict[str, Any]:
        """将知识库条目应用到标准产业链格式。"""
        summary = k.get("summary", {"description": topic, "demand_driver": "（待补充）"})
        raw_layers = k.get("layers", [])
        raw_candidates = k.get("candidates", [])

        # 用知识库层级覆盖默认层级模板
        name_map = {l["name"]: l for l in raw_layers}
        layers = []
        for template_layer in LAYER_TEMPLATE:
            # 尝试精确匹配，再尝试部分匹配
            matched_layer = name_map.get(template_layer)
            if matched_layer is None:
                # 部分匹配：知识库层名包含模板层名 或 模板层名包含知识库层名
                for kname, klayer in name_map.items():
                    if kname in template_layer or template_layer in kname:
                        matched_layer = klayer
                        break
            if matched_layer is not None:
                layers.append(dict(matched_layer))
            else:
                layers.append({
                    "name": template_layer,
                    "key_companies_cn": [],
                    "key_companies_global": [],
                    "supply_demand": "unknown",
                    "expansion_difficulty": "unknown",
                    "certification_barrier": False,
                    "scarcity": "unknown",
                })

        return {
            "topic": topic,
            "depth": "normal",
            "summary": summary,
            "layers": layers,
            "candidates": list(raw_candidates),
        }

    def parse_llm_json(self, raw: str) -> Optional[Dict[str, Any]]:
        """将 LLM 返回的 JSON 字符串解析为结构化 dict。"""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
