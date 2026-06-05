"""
Report quality checks for generated stock analysis markdown.

The evaluator is intentionally lightweight: it validates report structure and
research/timing separation without attempting to judge the investment thesis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ReportQualityIssue:
    code: str
    severity: str
    message: str
    section: str = ""


@dataclass
class ReportQualityResult:
    score: int
    issues: List[ReportQualityIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.score >= 70 and not any(issue.severity == "error" for issue in self.issues)

    def to_markdown(self) -> str:
        lines = [
            "## 报告质量检查",
            "",
            f"- **质量分**: {self.score}/100",
            f"- **结果**: {'通过' if self.passed else '需复核'}",
            "",
        ]
        if not self.issues:
            lines.append("- 未发现结构性问题")
            return "\n".join(lines)

        lines.extend(
            [
                "| 严重性 | 代码 | 位置 | 问题 |",
                "|---|---|---|---|",
            ]
        )
        for issue in self.issues:
            section = issue.section or "-"
            message = issue.message.replace("|", "/")
            lines.append(f"| {issue.severity} | {issue.code} | {section} | {message} |")
        return "\n".join(lines)


class ReportQualityEvaluator:
    """Validate generated report structure and disclosure quality."""

    REQUIRED_MARKERS = (
        ("title", r"^# .+\(.+\)", "报告标题必须包含公司名和代码"),
        ("core_view", r"## 一、核心观点", "缺少核心观点 section"),
        ("research_score", r"\*\*Research Score\*\*", "缺少独立 Research Score 展示"),
        ("timing_state", r"\*\*Timing State\*\*", "缺少独立 Timing State 展示"),
        ("evidence", r"### 证据摘要", "缺少证据摘要"),
        ("timing_summary", r"### 交易时机", "缺少交易时机摘要"),
        ("action_plan", r"## 七、操作建议", "缺少操作建议 section"),
        ("disclaimer", r"免责声明", "缺少免责声明"),
    )
    TIMING_STATES = ("Ready", "Wait", "Watch", "Avoid")
    DATA_GAP_CHECKS = (
        ("行情/技术指标", "technicals", "technicals_error"),
        ("基本面", "fundamentals", "fundamentals_error"),
        ("财报", "earnings", "earnings_error"),
        ("流动性", "liquidity", "liquidity_error"),
        ("期权", "options", "options_error"),
        ("新闻/社交搜索", "web_search", "web_search_error"),
    )
    PENALTIES = {"error": 18, "warning": 8}

    def evaluate(self, markdown: str, market_data: Dict[str, Any] | None = None) -> ReportQualityResult:
        market_data = market_data or {}
        issues: List[ReportQualityIssue] = []
        text = markdown or ""

        for code, pattern, message in self.REQUIRED_MARKERS:
            if not re.search(pattern, text, flags=re.MULTILINE):
                issues.append(ReportQualityIssue(code, "error", message))

        issues.extend(self._check_research_timing_separation(text))
        issues.extend(self._check_data_gap_disclosure(text, market_data))

        penalty = sum(self.PENALTIES.get(issue.severity, 8) for issue in issues)
        score = max(0, 100 - penalty)
        return ReportQualityResult(score=score, issues=issues)

    def _check_research_timing_separation(self, markdown: str) -> List[ReportQualityIssue]:
        issues: List[ReportQualityIssue] = []
        lines = [line.strip() for line in markdown.splitlines()]

        research_lines = [
            line for line in lines
            if "Research Score" in line and "Timing" not in line
        ]
        timing_lines = [
            line for line in lines
            if line.startswith("**Timing State**")
        ]

        for line in research_lines:
            if any(re.search(rf"\b{state}\b", line) for state in self.TIMING_STATES):
                issues.append(
                    ReportQualityIssue(
                        "research_timing_mixed",
                        "error",
                        "Research Score 行混入了 Timing State 枚举值",
                        "核心观点",
                    )
                )
            if not re.search(r"\d+(?:\.\d+)?/100", line):
                issues.append(
                    ReportQualityIssue(
                        "research_score_not_numeric",
                        "warning",
                        "Research Score 应展示 0-100 的数值",
                        "核心观点",
                    )
                )

        for line in timing_lines:
            has_state = any(re.search(rf"\b{state}\b", line) for state in self.TIMING_STATES)
            if not has_state and "N/A" not in line:
                issues.append(
                    ReportQualityIssue(
                        "timing_state_missing_enum",
                        "warning",
                        "Timing State 应使用 Ready/Wait/Watch/Avoid 枚举",
                        "核心观点",
                    )
                )

        return issues

    def _check_data_gap_disclosure(
        self,
        markdown: str,
        market_data: Dict[str, Any],
    ) -> List[ReportQualityIssue]:
        if not market_data:
            return []

        expected_gaps = []
        for label, data_key, error_key in self.DATA_GAP_CHECKS:
            if market_data.get(error_key):
                expected_gaps.append(label)
                continue
            if not self._has_meaningful_data(market_data.get(data_key)):
                expected_gaps.append(label)

        if expected_gaps and "## 数据缺口" not in markdown:
            return [
                ReportQualityIssue(
                    "data_gaps_not_disclosed",
                    "error",
                    "存在缺失或失败的数据模块，但报告未披露数据缺口: " + "、".join(expected_gaps[:4]),
                    "数据缺口",
                )
            ]
        return []

    def _has_meaningful_data(self, value: Any) -> bool:
        if value is None:
            return False
        if value == "":
            return False
        if value == "N/A":
            return False
        if isinstance(value, dict):
            if value.get("error"):
                return False
            return any(self._has_meaningful_data(item) for item in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(self._has_meaningful_data(item) for item in value)
        return True


def evaluate_report_quality(
    markdown: str,
    market_data: Dict[str, Any] | None = None,
) -> ReportQualityResult:
    """Convenience wrapper used by scripts and tests."""
    return ReportQualityEvaluator().evaluate(markdown, market_data)
