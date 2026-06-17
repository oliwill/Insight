"""Markdown 生成 + Obsidian 写入。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from .reference import EVIDENCE_LEVELS


class ReportBuilder:
    """将结构化产业链扫描结果转为 Markdown，可选写入 Obsidian。"""

    def build(self, data: Dict[str, Any]) -> str:
        """生成完整 Markdown。"""
        parts = [self._header(data), ""]
        parts.append(self._summary_section(data))
        parts.append("")
        parts.append(self._chain_section(data))
        parts.append("")
        parts.append(self._bottleneck_section(data))
        parts.append("")
        parts.append(self._candidates_section(data))
        parts.append("")
        parts.append(self._checklist_section(data))
        return "\n".join(parts)

    def _header(self, data: Dict[str, Any]) -> str:
        topic = data.get("topic", "未知主题")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"### [{now}] 产业链扫描：{topic}"

    def _summary_section(self, data: Dict[str, Any]) -> str:
        summary = data.get("summary", {})
        desc = summary.get("description", "（待补充）")
        driver = summary.get("demand_driver", "（待补充）")
        return f"""### 一、主题定位

**描述**：{desc}

**真实需求驱动**：{driver}"""

    def _chain_section(self, data: Dict[str, Any]) -> str:
        layers = data.get("layers", [])
        if not layers:
            return "### 二、产业链拆解\n\n暂无数据。"
        lines = [
            "### 二、产业链拆解",
            "",
            "| 层级 | 中国公司 | 海外公司 | 供需判断 |",
            "|---|---|---|---|",
        ]
        for layer in layers:
            cn = "、".join(layer.get("key_companies_cn", [])[:3]) or "-"
            gl = "、".join(layer.get("key_companies_global", [])[:3]) or "-"
            sd = layer.get("supply_demand", "unknown")
            lines.append(f"| {layer['name']} | {cn} | {gl} | {sd} |")
        return "\n".join(lines)

    def _bottleneck_section(self, data: Dict[str, Any]) -> str:
        layers = data.get("layers", [])
        scored = [l for l in layers if l.get("bottleneck_score") is not None]
        if not scored:
            return "### 三、瓶颈判断\n\n暂无数据。"
        scored.sort(key=lambda l: l["bottleneck_score"], reverse=True)
        lines = ["### 三、瓶颈判断", "", "| 层级 | 瓶颈分 | 等级 | 核心卡点 |", "|---|---|---|---|"]
        for layer in scored:
            score = layer["bottleneck_score"]
            level = layer.get("bottleneck_level", "-")
            triggers = self._bottleneck_triggers(layer)
            lines.append(f"| {layer['name']} | {score}/10 | {level} | {triggers} |")
        return "\n".join(lines)

    def _bottleneck_triggers(self, layer: Dict[str, Any]) -> str:
        parts = []
        if (layer.get("supply_demand") or "").lower() == "tight": parts.append("供应紧张")
        if (layer.get("expansion_difficulty") or "").lower() == "high": parts.append("扩产困难")
        if layer.get("certification_barrier"): parts.append("认证壁垒")
        if (layer.get("scarcity") or "").lower() == "high": parts.append("稀缺性")
        return "、".join(parts) if parts else "待确认"

    def _candidates_section(self, data: Dict[str, Any]) -> str:
        candidates = data.get("candidates", [])
        if not candidates:
            return "### 四、优先研究清单\n\n暂无候选。"
        sc = sorted(candidates, key=lambda c: c.get("priority", 99))
        lines = ["### 四、优先研究清单", ""]
        for c in sc:
            company = c.get("company", "?")
            layer = c.get("layer", "?")
            rationale = c.get("rationale", "")
            evidence = EVIDENCE_LEVELS.get(c.get("evidence", "none"), c.get("evidence", "无"))
            risks = "、".join(c.get("risks", [])[:3]) or "待确认"
            lines.append(f"1. **{company}** — **{layer}**")
            if rationale: lines.append(f"   - 逻辑：{rationale}")
            lines.append(f"   - 证据：{evidence}")
            lines.append(f"   - 风险：{risks}")
            lines.append("")
        return "\n".join(lines)

    def _checklist_section(self, data: Dict[str, Any]) -> str:
        candidates = data.get("candidates", [])
        lines = ["### 五、下一步检查清单", ""]
        has_items = False
        for c in candidates[:5]:
            company = c.get("company", "?")
            evidence = c.get("evidence", "none")
            if evidence in ("media", "none"):
                lines.append(f"- [ ] 查 {company} 最新财报确认 {c.get('layer', '')} 收入和毛利率")
                has_items = True
            if c.get("risks"):
                lines.append(f"- [ ] 核验 {company} 的主要风险：{c['risks'][0]}")
                has_items = True
        if not has_items:
            lines.append("- [ ] 补充公司证据后更新研究优先级")
        return "\n".join(lines)

    def write_to_obsidian(self, stock_code: str, markdown: str, memory_manager: Any) -> None:
        """通过 MemoryManager 写入 Obsidian 研究笔记。"""
        memory_manager.init_stock_wiki(stock_code, stock_code)
        memory_manager.append_to_section(stock_code, "研究笔记", "\n" + markdown + "\n")
