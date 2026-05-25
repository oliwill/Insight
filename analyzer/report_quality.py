"""Quality checks for generated stock analysis reports."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Sequence


REQUIRED_H2_SECTIONS = (
    "一、核心观点",
    "二、技术分析",
    "三、基本面分析",
    "四、市场情绪",
    "五、市场结构",
    "六、催化因素",
    "七、操作建议",
)


@dataclass
class ReportQualityIssue:
    severity: str
    code: str
    message: str


@dataclass
class ReportQualityResult:
    issues: List[ReportQualityIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_markdown(self) -> str:
        if not self.issues:
            return "- 报告质量检查通过"
        return "\n".join(
            f"- [{issue.severity}] {issue.code}: {issue.message}"
            for issue in self.issues
        )


class ReportQualityEvaluator:
    """Checks generated reports for structure and score/timing separation."""

    def evaluate(self, markdown: str, required_sections: Sequence[str] = REQUIRED_H2_SECTIONS) -> ReportQualityResult:
        issues: List[ReportQualityIssue] = []
        headings = self._h2_headings(markdown)

        self._check_required_sections(headings, required_sections, issues)
        self._check_duplicate_ordinals(headings, issues)
        self._check_research_timing_separation(markdown, issues)

        return ReportQualityResult(issues=issues)

    def _h2_headings(self, markdown: str) -> List[str]:
        return [match.group(1).strip() for match in re.finditer(r"^##\s+(.+?)\s*$", markdown, re.MULTILINE)]

    def _check_required_sections(
        self,
        headings: Sequence[str],
        required_sections: Sequence[str],
        issues: List[ReportQualityIssue],
    ) -> None:
        missing = [section for section in required_sections if section not in headings]
        if missing:
            issues.append(
                ReportQualityIssue(
                    severity="error",
                    code="missing_sections",
                    message="缺少关键章节: " + ", ".join(missing),
                )
            )

    def _check_duplicate_ordinals(self, headings: Sequence[str], issues: List[ReportQualityIssue]) -> None:
        ordinals = []
        for heading in headings:
            match = re.match(r"([一二三四五六七八九十]+)、", heading)
            if match:
                ordinals.append(match.group(1))

        duplicates = sorted({ordinal for ordinal in ordinals if ordinals.count(ordinal) > 1})
        if duplicates:
            issues.append(
                ReportQualityIssue(
                    severity="error",
                    code="duplicate_section_ordinals",
                    message="章节编号重复: " + ", ".join(duplicates),
                )
            )

    def _check_research_timing_separation(self, markdown: str, issues: List[ReportQualityIssue]) -> None:
        has_research = bool(re.search(r"Research\s+Score|五维打分", markdown, re.IGNORECASE))
        has_timing = bool(re.search(r"Timing\s+State|交易时机", markdown, re.IGNORECASE))
        if not has_research or not has_timing:
            missing = []
            if not has_research:
                missing.append("Research Score")
            if not has_timing:
                missing.append("Timing State")
            issues.append(
                ReportQualityIssue(
                    severity="error",
                    code="missing_score_or_timing",
                    message="报告必须同时展示 " + " 和 ".join(missing),
                )
            )
            return

        action_section = self._section(markdown, "七、操作建议")
        if not action_section:
            return

        has_action = bool(re.search(r"建仓|买入|可行动|等待|观察|回避", action_section))
        action_has_research = bool(re.search(r"Research\s+Score", action_section, re.IGNORECASE))
        action_has_timing = bool(re.search(r"Timing\s+State|Timing\s+", action_section, re.IGNORECASE))
        if has_action and (not action_has_research or not action_has_timing):
            issues.append(
                ReportQualityIssue(
                    severity="warning",
                    code="action_without_score_timing",
                    message="操作建议应同时引用 Research Score 和 Timing State，避免把公司质量与入场时机合并成单一结论。",
                )
            )

    def _section(self, markdown: str, section_name: str) -> str:
        pattern = rf"^##\s+{re.escape(section_name)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
        match = re.search(pattern, markdown, re.MULTILINE)
        return match.group(1).strip() if match else ""
