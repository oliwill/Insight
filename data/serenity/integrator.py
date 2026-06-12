"""
SerenityIntegrator — 将产业链扫描结果融入现有分析框架。

将 Serenity 产业链分析的结构化数据映射到 Obsidian Wiki 的各个 section：
- 综合评估：行业/TAM 维度
- 五维打分：基于瓶颈分析和供需判断
- 证据表：候选公司作为证据条目
- 研究笔记：完整产业链分析（保留原有行为）
- 交叉引用：产业链相关公司
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .reference import EVIDENCE_LEVELS


class SerenityIntegrator:
    """将 Serenity 产业链分析结果写入 Obsidian Wiki 的多个 section。"""

    def integrate(
        self,
        stock_code: str,
        serenity_data: Dict[str, Any],
        memory_manager: Any,
    ) -> List[str]:
        """
        将产业链分析结果融入现有 wiki 框架。

        Returns:
            已更新的 section 名称列表
        """
        updated = []
        mm = memory_manager

        # 确保 wiki 页面存在
        mm.init_stock_wiki(stock_code, stock_code)

        # 1. 找到目标公司在产业链中的位置
        target_layer, target_company = self._find_company_position(
            stock_code, serenity_data
        )

        # 2. 更新综合评估 — 行业/TAM 维度
        tam_judgment = self._build_tam_judgment(serenity_data, target_layer)
        if tam_judgment:
            mm.update_evaluation_table(stock_code, stock_code, "行业/TAM", tam_judgment)
            updated.append("综合评估")

        # 3. 更新五维打分
        score_md = self._build_five_dimension_scores(
            serenity_data, target_layer, target_company
        )
        if score_md:
            mm.replace_section(stock_code, "五维打分", score_md)
            updated.append("五维打分")

        # 4. 更新证据表 — 添加产业链候选公司
        evidence_md = self._build_evidence_table(serenity_data, stock_code)
        if evidence_md:
            mm.replace_section(stock_code, "证据表", evidence_md)
            updated.append("证据表")

        # 5. 更新交叉引用
        xref_md = self._build_cross_references(serenity_data, stock_code)
        if xref_md:
            mm.replace_section(stock_code, "交叉引用", xref_md)
            updated.append("交叉引用")

        # 6. 追加完整产业链分析到研究笔记（保留原有行为）
        from .report_builder import ReportBuilder
        builder = ReportBuilder()
        chain_md = builder.build(serenity_data)
        mm.append_to_section(stock_code, "研究笔记", "\n" + chain_md + "\n")
        updated.append("研究笔记")

        # 7. 追加分析时间线
        topic = serenity_data.get("topic", stock_code)
        layer_info = f"位于「{target_layer['name']}」" if target_layer else "产业链分析完成"
        timeline_entry = (
            f"- **{datetime.now().strftime('%Y-%m-%d %H:%M')}** | "
            f"类型: Serenity 产业链扫描 ({topic})\n"
            f"  - {layer_info}"
        )
        mm.append_to_section(stock_code, "分析时间线", timeline_entry)
        updated.append("分析时间线")

        return updated

    def _find_company_position(
        self, stock_code: str, data: Dict[str, Any]
    ) -> tuple:
        """在产业链中找到目标公司所在的层级和公司信息。"""
        candidates = data.get("candidates", [])
        layers = data.get("layers", [])

        # 尝试匹配：stock_code 在候选公司中
        code_upper = stock_code.upper().replace(".US", "").replace(".HK", "")
        for c in candidates:
            company_name = c.get("company", "").upper()
            if code_upper in company_name or company_name in code_upper:
                layer_name = c.get("layer", "")
                for layer in layers:
                    if layer["name"] == layer_name:
                        return layer, c

        # 如果没找到精确匹配，用第一个候选公司
        if candidates:
            first = candidates[0]
            layer_name = first.get("layer", "")
            for layer in layers:
                if layer["name"] == layer_name:
                    return layer, first

        # 都没有，返回最高瓶颈层级
        scored_layers = [l for l in layers if l.get("bottleneck_score", 0) > 0]
        if scored_layers:
            scored_layers.sort(key=lambda l: l["bottleneck_score"], reverse=True)
            return scored_layers[0], None

        return None, None

    def _build_tam_judgment(
        self, data: Dict[str, Any], target_layer: Optional[Dict]
    ) -> str:
        """构建行业/TAM 维度的综合评估文本。"""
        summary = data.get("summary", {})
        desc = summary.get("description", "")
        driver = summary.get("demand_driver", "")

        parts = []
        if desc:
            parts.append(desc[:60])

        if target_layer:
            sd = target_layer.get("supply_demand", "unknown")
            sd_map = {
                "tight": "供需紧张",
                "balanced": "供需平衡",
                "loose": "供过于求",
                "unknown": "供需待确认",
            }
            parts.append(f"{target_layer['name'][:10]}{sd_map.get(sd, '待确认')}")
            bn = target_layer.get("bottleneck_score", 0)
            if bn >= 5:
                parts.append(f"瓶颈分{bn}/10")

        if driver:
            parts.append(f"驱动: {driver[:40]}")

        return " | ".join(parts) if parts else ""

    def _build_five_dimension_scores(
        self,
        data: Dict[str, Any],
        target_layer: Optional[Dict],
        target_company: Optional[Dict],
    ) -> str:
        """基于产业链分析构建五维打分表。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 行业/TAM 评分
        tam_score, tam_detail = self._score_industry_tam(data, target_layer)
        # 护城河评分 — 基于所在层级的瓶颈程度
        moat_score, moat_detail = self._score_moat(target_layer, target_company)
        # 增长质量 — 基于需求驱动清晰度
        growth_score, growth_detail = self._score_growth(data, target_layer)

        lines = [
            "| 维度 | 得分 | 子维度评分 | 更新时间 |",
            "|------|------|-----------|----------|",
            f"| 行业/TAM | {tam_score}/10 | 赛道方向:{self._trend_label(data)}, TAM规模:{self._tam_scale_label(data)}, 资金流向:- | {now} |",
            f"| 护城河 | {moat_score}/10 | {moat_detail} | {now} |",
            f"| 增长质量 | {growth_score}/10 | {growth_detail} | {now} |",
            "| 估值 | - | PSG:-, 同行溢价:-, 安全边际:- | - |",
            "| 团队/治理 | - | CEO:-, 董事会:-, 内部人:-, SBC:- | - |",
            f"| **综合** | {self._overall_label(tam_score, moat_score, growth_score)} | 判定:Serenity产业链分析 | {now} |",
        ]
        return "\n".join(lines)

    def _score_industry_tam(
        self, data: Dict[str, Any], target_layer: Optional[Dict]
    ) -> tuple:
        """行业/TAM 维度评分 (0-10)。"""
        score = 5  # 基础分
        layers = data.get("layers", [])

        # 供需紧张度加分
        tight_count = sum(
            1 for l in layers if (l.get("supply_demand") or "").lower() == "tight"
        )
        if tight_count >= 4:
            score += 2
        elif tight_count >= 2:
            score += 1

        # 目标层级在瓶颈位置加分
        if target_layer:
            bn = target_layer.get("bottleneck_score", 0)
            if bn >= 5:
                score += 1
            if (target_layer.get("supply_demand") or "").lower() == "tight":
                score += 1

        return min(score, 10), f"赛道方向:{self._trend_label(data)}, 供需紧张层级:{tight_count}/{len(layers)}"

    def _score_moat(
        self, target_layer: Optional[Dict], target_company: Optional[Dict]
    ) -> tuple:
        """护城河维度评分 (0-10) — 基于瓶颈程度。"""
        if not target_layer:
            return 0, "技术/IP:-, 客户锁定:-, 规模:-"

        bn = target_layer.get("bottleneck_score", 0)
        # 瓶颈分越高，护城河越强（供应端壁垒）
        moat = min(bn, 10)

        parts = []
        # 技术/IP
        if bn >= 5:
            parts.append(f"技术/IP:{bn}/10")
        else:
            parts.append("技术/IP:-")
        # 客户锁定
        if target_layer.get("certification_barrier"):
            parts.append("客户锁定:强")
        else:
            parts.append("客户锁定:-")
        # 规模
        sd = (target_layer.get("supply_demand") or "").lower()
        if sd == "tight":
            parts.append("规模:稀缺")
        else:
            parts.append("规模:-")

        return moat, ", ".join(parts)

    def _score_growth(
        self, data: Dict[str, Any], target_layer: Optional[Dict]
    ) -> tuple:
        """增长质量评分 (0-10) — 基于需求驱动清晰度。"""
        summary = data.get("summary", {})
        driver = summary.get("demand_driver", "")

        score = 5  # 基础分
        if driver and len(driver) > 30:
            score += 2  # 需求驱动描述清晰
        if target_layer:
            if (target_layer.get("supply_demand") or "").lower() == "tight":
                score += 1
            if target_layer.get("expansion_difficulty", "").lower() == "high":
                score += 1  # 扩产困难意味着需求持续

        score = min(score, 10)
        detail = f"需求驱动:{'清晰' if len(driver) > 30 else '待补充'}, 供需:{(target_layer or {}).get('supply_demand', '待确认')}"
        return score, detail

    def _trend_label(self, data: Dict[str, Any]) -> str:
        """赛道方向标签。"""
        layers = data.get("layers", [])
        tight = sum(1 for l in layers if (l.get("supply_demand") or "").lower() == "tight")
        if tight >= 4:
            return "强上行"
        if tight >= 2:
            return "上行"
        return "待确认"

    def _tam_scale_label(self, data: Dict[str, Any]) -> str:
        """TAM 规模标签。"""
        layers = data.get("layers", [])
        has_players = sum(
            1 for l in layers
            if len(l.get("key_companies_global", [])) + len(l.get("key_companies_cn", [])) >= 3
        )
        if has_players >= 4:
            return "大"
        if has_players >= 2:
            return "中"
        return "待确认"

    def _overall_label(self, tam: int, moat: int, growth: int) -> str:
        """综合判定标签。"""
        avg = (tam + moat + growth) / 3
        if avg >= 7:
            return f"{avg:.1f}/10 产业链位置优越"
        if avg >= 5:
            return f"{avg:.1f}/10 产业链位置中等"
        return f"{avg:.1f}/10 产业链位置偏弱"

    def _build_evidence_table(
        self, data: Dict[str, Any], stock_code: str
    ) -> str:
        """构建证据表 — 将候选公司作为证据条目。"""
        candidates = data.get("candidates", [])
        if not candidates:
            return ""

        lines = [
            "| 证据 | 类型 | 来源 | 可信度 | 影响维度 | 影响 | 备注 |",
            "|---|---|---|---|---|---|---|",
        ]

        code_upper = stock_code.upper().replace(".US", "").replace(".HK", "")

        for c in candidates:
            company = c.get("company", "?")
            layer = c.get("layer", "?")
            rationale = c.get("rationale", "")[:60]
            evidence_type = c.get("evidence", "none")
            evidence_label = EVIDENCE_LEVELS.get(evidence_type, evidence_type)
            risks = "、".join(c.get("risks", [])[:2]) or "待确认"

            # 判断是否是目标公司
            is_target = code_upper in company.upper() or company.upper() in code_upper
            impact_dim = "行业/TAM, 护城河" if is_target else "交叉引用"
            impact = f"+{3 if c.get('priority', 5) <= 2 else 1}"

            lines.append(
                f"| {company}({layer}): {rationale} | 产业链 | {evidence_label} | "
                f"{'高' if evidence_type in ('financial', 'order') else '中'} | "
                f"{impact_dim} | {impact} | 风险:{risks} |"
            )

        return "\n".join(lines)

    def _build_cross_references(
        self, data: Dict[str, Any], stock_code: str
    ) -> str:
        """构建交叉引用 — 产业链中的相关公司。"""
        candidates = data.get("candidates", [])
        layers = data.get("layers", [])

        if not candidates and not layers:
            return ""

        lines = ["> Serenity 产业链扫描自动生成的交叉引用", ""]

        # 候选公司
        if candidates:
            lines.append("### 产业链候选公司")
            lines.append("")
            for c in candidates:
                company = c.get("company", "?")
                layer = c.get("layer", "?")
                lines.append(f"- **{company}** — {layer}")
            lines.append("")

        # 各层级关键公司
        lines.append("### 产业链关键玩家")
        lines.append("")
        for layer in layers:
            cn = layer.get("key_companies_cn", [])
            gl = layer.get("key_companies_global", [])
            all_companies = cn + gl
            if all_companies:
                lines.append(f"- **{layer['name']}**: {', '.join(all_companies[:5])}")

        return "\n".join(lines)
