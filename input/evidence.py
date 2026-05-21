"""
Evidence extraction for Obsidian-native stock analysis.

Turns stock wiki context, saved materials, and Inbox snippets into typed evidence
that can support five-dimension research scoring and timing decisions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


RESEARCH_DIMENSIONS = ["行业/TAM", "护城河", "增长质量", "估值", "团队/治理"]


@dataclass
class EvidenceItem:
    """A single extracted evidence item."""

    claim: str
    evidence_type: str = "opinion"  # fact | opinion | rumor | counter_evidence
    source_type: str = "note"
    credibility: str = "medium"  # high | medium | low
    affected_dimensions: List[str] = field(default_factory=list)
    score_impact: str = "confidence_only"  # up | down | confidence_only | watch_only
    timestamp: str = ""
    source_title: str = ""
    source_path: str = ""
    note: str = ""

    def to_dict(self) -> Dict:
        return {
            "claim": self.claim,
            "evidence_type": self.evidence_type,
            "source_type": self.source_type,
            "credibility": self.credibility,
            "affected_dimensions": self.affected_dimensions,
            "score_impact": self.score_impact,
            "timestamp": self.timestamp,
            "source_title": self.source_title,
            "source_path": self.source_path,
            "note": self.note,
        }


class EvidenceExtractor:
    """Rule-based first-pass evidence extractor."""

    HIGH_CREDIBILITY_SOURCES = {
        "filing",
        "sec",
        "10-k",
        "10-q",
        "8-k",
        "earnings",
        "company_pr",
        "press_release",
        "announcement",
        "公告",
        "财报",
    }
    MEDIUM_CREDIBILITY_SOURCES = {
        "research",
        "analyst",
        "substack",
        "article",
        "news",
        "wechat",
        "pdf",
        "user_note",
        "note",
    }
    LOW_CREDIBILITY_SOURCES = {
        "twitter",
        "x",
        "kol",
        "reddit",
        "community",
        "telegram",
        "discord",
        "rumor",
    }

    FACT_PATTERNS = [
        r"\b(revenue|sales|eps|margin|gross margin|cash flow|fcf|guidance|订单|营收|收入|毛利|利润|现金流|指引|公告|财报|同比|环比)\b",
        r"[+-]?\d+(?:\.\d+)?\s?(?:%|倍|x|X|亿|万|billion|million|m|bn)",
    ]
    RUMOR_PATTERNS = [r"传闻", r"rumou?r", r"据说", r"可能进入", r"unconfirmed", r"未经确认"]
    COUNTER_PATTERNS = [r"下调", r"miss", r"不及预期", r"否认", r"延迟", r"减少", r"流失", r"风险", r"downgrade", r"cut"]
    UP_PATTERNS = [r"上调", r"beat", r"超预期", r"增长", r"扩张", r"改善", r"净买入", r"raise", r"upgrade"]

    DIMENSION_KEYWORDS = {
        "行业/TAM": ["tam", "market", "赛道", "行业", "空间", "需求", "ai", "周期", "渗透率", "政策"],
        "护城河": ["moat", "专利", "ip", "技术", "客户锁定", "切换成本", "规模", "品牌", "供应链", "竞争"],
        "增长质量": ["revenue", "growth", "margin", "fcf", "sbc", "customer", "营收", "增长", "毛利", "现金流", "客户集中", "稀释"],
        "估值": ["valuation", "ps", "p/s", "psg", "pe", "target", "multiple", "估值", "目标价", "安全边际", "倍数"],
        "团队/治理": ["ceo", "cfo", "insider", "governance", "management", "董事", "治理", "管理层", "内部人", "减持", "增持"],
        "Timing": ["breakout", "stage", "wyckoff", "rsi", "ma50", "volume", "iv", "short", "突破", "均线", "成交量", "流动性", "财报前"],
    }

    def extract(
        self,
        wiki_context: str = "",
        materials: Optional[Sequence[Dict]] = None,
        inbox_items: Optional[Sequence[object]] = None,
        max_items: int = 30,
    ) -> List[EvidenceItem]:
        evidence: List[EvidenceItem] = []

        evidence.extend(self._extract_from_wiki_prior(wiki_context, limit=8))

        for material in materials or []:
            evidence.extend(self._extract_from_material(material, limit=3))

        for item in inbox_items or []:
            evidence.extend(self._extract_from_inbox_item(item, limit=4))

        return self._dedupe(evidence)[:max_items]

    def _extract_from_wiki_prior(self, wiki_context: str, limit: int) -> List[EvidenceItem]:
        if not wiki_context:
            return []

        sections = ["综合评估", "五维打分", "不对称原型", "关键事件", "研究笔记"]
        chunks: List[str] = []
        for section in sections:
            content = self._section_content(wiki_context, section)
            if content:
                chunks.extend(self._candidate_lines(content, max_lines=limit))

        items = []
        for line in chunks[:limit]:
            items.append(self._build_item(
                claim=line,
                source_type="wiki_prior",
                source_title="Stock wiki prior",
                credibility="medium",
                note="历史 wiki 观点，作为 prior 使用；估值、技术、情绪类内容需时间衰减。",
            ))
        return items

    def _extract_from_material(self, material: Dict, limit: int) -> List[EvidenceItem]:
        source_type = material.get("source_type") or "material"
        title = material.get("title") or material.get("filepath") or "Saved material"
        text = ""
        filepath = material.get("filepath") or ""
        if filepath:
            try:
                text = Path(filepath).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                text = title
        if not text:
            text = title

        return [
            self._build_item(
                claim=line,
                source_type=source_type,
                source_title=title,
                source_path=filepath,
                timestamp=material.get("timestamp", ""),
            )
            for line in self._candidate_lines(text, max_lines=limit)
        ]

    def _extract_from_inbox_item(self, item: object, limit: int) -> List[EvidenceItem]:
        source_type = getattr(item, "source_type", "inbox") or "inbox"
        title = getattr(item, "title", "Inbox material") or "Inbox material"
        body = getattr(item, "body", "") or ""
        path = str(getattr(item, "path", "") or "")
        timestamp = ""
        try:
            timestamp = datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%Y-%m-%d") if path else ""
        except OSError:
            timestamp = ""

        lines = self._candidate_lines(f"{title}\n{body}", max_lines=limit)
        return [
            self._build_item(
                claim=line,
                source_type=source_type,
                source_title=title,
                source_path=path,
                timestamp=timestamp,
            )
            for line in lines
        ]

    def _candidate_lines(self, text: str, max_lines: int) -> List[str]:
        clean = re.sub(r"```[\s\S]*?```", " ", text)
        raw_lines = []
        for line in clean.splitlines():
            line = re.sub(r"^[#>\-\*\s|]+", "", line).strip()
            line = re.sub(r"\s+", " ", line)
            if 18 <= len(line) <= 220 and not set(line) <= {"-", "|", " "}:
                raw_lines.append(line)

        scored = sorted(raw_lines, key=self._line_score, reverse=True)
        return scored[:max_lines]

    def _line_score(self, line: str) -> int:
        lower = line.lower()
        score = 0
        for pattern in self.FACT_PATTERNS + self.COUNTER_PATTERNS + self.UP_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                score += 2
        for keywords in self.DIMENSION_KEYWORDS.values():
            if any(k.lower() in lower for k in keywords):
                score += 1
        if re.search(r"\d", line):
            score += 1
        return score

    def _build_item(
        self,
        claim: str,
        source_type: str,
        source_title: str = "",
        source_path: str = "",
        timestamp: str = "",
        credibility: Optional[str] = None,
        note: str = "",
    ) -> EvidenceItem:
        evidence_type = self._classify_evidence_type(claim, source_type)
        credibility = credibility or self._source_credibility(source_type)
        dimensions = self._affected_dimensions(claim)
        score_impact = self._score_impact(claim, evidence_type, credibility)

        if evidence_type == "opinion" and credibility == "low":
            score_impact = "watch_only"
        if evidence_type == "rumor":
            score_impact = "watch_only"

        return EvidenceItem(
            claim=claim,
            evidence_type=evidence_type,
            source_type=source_type,
            credibility=credibility,
            affected_dimensions=dimensions or ["Timing" if score_impact == "watch_only" else "行业/TAM"],
            score_impact=score_impact,
            timestamp=timestamp,
            source_title=source_title,
            source_path=source_path,
            note=note,
        )

    def _classify_evidence_type(self, claim: str, source_type: str) -> str:
        lower = claim.lower()
        if any(re.search(p, lower, re.IGNORECASE) for p in self.RUMOR_PATTERNS):
            return "rumor"
        if any(re.search(p, lower, re.IGNORECASE) for p in self.COUNTER_PATTERNS):
            return "counter_evidence"
        if self._source_credibility(source_type) == "high" or any(re.search(p, lower, re.IGNORECASE) for p in self.FACT_PATTERNS):
            return "fact"
        return "opinion"

    def _source_credibility(self, source_type: str) -> str:
        source = (source_type or "").lower()
        if self._source_matches(source, self.HIGH_CREDIBILITY_SOURCES):
            return "high"
        if self._source_matches(source, self.LOW_CREDIBILITY_SOURCES):
            return "low"
        if self._source_matches(source, self.MEDIUM_CREDIBILITY_SOURCES):
            return "medium"
        return "medium"

    def _source_matches(self, source: str, candidates: set[str]) -> bool:
        return source in candidates or any(len(candidate) > 2 and candidate in source for candidate in candidates)

    def _affected_dimensions(self, claim: str) -> List[str]:
        lower = claim.lower()
        dimensions = []
        for dimension, keywords in self.DIMENSION_KEYWORDS.items():
            if any(keyword.lower() in lower for keyword in keywords):
                dimensions.append(dimension)
        return dimensions

    def _score_impact(self, claim: str, evidence_type: str, credibility: str) -> str:
        lower = claim.lower()
        if evidence_type == "counter_evidence":
            return "down" if credibility in {"high", "medium"} else "confidence_only"
        if evidence_type == "fact" and credibility == "high":
            if any(re.search(p, lower, re.IGNORECASE) for p in self.UP_PATTERNS):
                return "up"
            if any(re.search(p, lower, re.IGNORECASE) for p in self.COUNTER_PATTERNS):
                return "down"
        if evidence_type == "fact" and credibility == "medium":
            return "confidence_only"
        return "confidence_only"

    def _section_content(self, wiki_text: str, section_name: str) -> str:
        pattern = rf"^##\s+{re.escape(section_name)}\s*$"
        match = re.search(pattern, wiki_text, flags=re.MULTILINE)
        if not match:
            return ""
        start = wiki_text.find("\n", match.start()) + 1
        next_match = re.search(r"^##[^\n#]", wiki_text[start:], flags=re.MULTILINE)
        end = start + next_match.start() if next_match else len(wiki_text)
        return wiki_text[start:end].strip()

    def _dedupe(self, items: Iterable[EvidenceItem]) -> List[EvidenceItem]:
        seen = set()
        result = []
        for item in items:
            key = re.sub(r"\W+", "", item.claim.lower())[:80]
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def to_markdown(self, evidence: Sequence[EvidenceItem]) -> str:
        lines = [
            "| 证据 | 类型 | 来源 | 可信度 | 影响维度 | 影响 | 备注 |",
            "|---|---|---|---|---|---|---|",
        ]
        if not evidence:
            lines.append("| 暂无结构化证据 | - | - | - | - | - | 需要补充材料 |")
            return "\n".join(lines)

        for item in evidence:
            claim = item.claim.replace("|", "/")[:120]
            source = item.source_title or item.source_type
            source = source.replace("|", "/")[:40]
            dims = ", ".join(item.affected_dimensions)
            note = item.note.replace("|", "/")[:60] if item.note else ""
            lines.append(
                f"| {claim} | {item.evidence_type} | {source} | {item.credibility} | {dims} | {item.score_impact} | {note} |"
            )
        return "\n".join(lines)
