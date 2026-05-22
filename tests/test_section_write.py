import re
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_analysis
import memory.manager as memory_manager
from memory.section_parser import _append_to_section, _get_section_content


def test_strip_section_heading_removes_matching_h2_heading():
    markdown = "## 流动性分析\n\n- **机构持仓**: 34.5%\n"
    strip_heading = getattr(run_analysis, "_strip_section_heading", None)

    assert strip_heading is not None
    assert strip_heading(markdown, "流动性分析") == "- **机构持仓**: 34.5%"


def test_strip_section_heading_keeps_body_without_matching_h2():
    markdown = "- **机构持仓**: 34.5%\n"
    strip_heading = getattr(run_analysis, "_strip_section_heading", None)

    assert strip_heading is not None
    assert strip_heading(markdown, "流动性分析") == "- **机构持仓**: 34.5%"


def test_demote_markdown_headings_keeps_notes_inside_parent_section():
    markdown = "## 一、核心观点\n\n### 交易时机\n\n正文"
    demote_headings = getattr(run_analysis, "_demote_markdown_headings", None)

    assert demote_headings is not None
    assert demote_headings(markdown).startswith("### 一、核心观点")
    assert "\n#### 交易时机" in demote_headings(markdown)


def test_demote_markdown_headings_converts_h1_to_h3():
    markdown = "# 手工分析\n\n正文"
    demote_headings = getattr(run_analysis, "_demote_markdown_headings", None)

    assert demote_headings is not None
    assert demote_headings(markdown).startswith("### 手工分析")


def test_module_section_append_does_not_create_duplicate_top_level_heading():
    wiki = "# TEST\n\n## 流动性分析\n\n（暂无）\n\n## 研究笔记\n\n（暂无）\n"
    entry = run_analysis._strip_section_heading(
        "## 流动性分析\n\n- **机构持仓**: 34.5%\n",
        "流动性分析",
    )

    updated = _append_to_section(wiki, "流动性分析", entry)

    assert len(re.findall(r"^##\s+流动性分析\s*$", updated, re.MULTILINE)) == 1
    assert "- **机构持仓**: 34.5%" in _get_section_content(updated, "流动性分析")


def test_research_note_append_keeps_full_report_inside_research_section():
    wiki = "# TEST\n\n## 研究笔记\n\n（暂无）\n\n## 交叉引用\n\n（暂无）\n"
    report = run_analysis._demote_markdown_headings("# 手工分析\n\n## 一、核心观点\n\n正文")

    updated = _append_to_section(wiki, "研究笔记", report)
    content = _get_section_content(updated, "研究笔记")

    assert "### 手工分析" in content
    assert "### 一、核心观点" in content
    assert not re.search(r"^##\s+手工分析\s*$", content, re.MULTILINE)


class FakeMemoryManager:
    instances = []

    def __init__(self):
        self.calls = []
        FakeMemoryManager.instances.append(self)

    def init_stock_wiki(self, stock_code, stock_name):
        self.calls.append(("init_stock_wiki", stock_code, stock_name))

    def update_evaluation_table(self, **kwargs):
        self.calls.append(("update_evaluation_table", kwargs))

    def update_cockpit_sections(self, **kwargs):
        self.calls.append(("update_cockpit_sections", kwargs))

    def append_to_timeline(self, **kwargs):
        self.calls.append(("append_to_timeline", kwargs))

    def append_to_section(self, stock_code, section_name, content):
        self.calls.append(("append_to_section", stock_code, section_name, content))

    def update_index(self, stock_code, stock_name, score):
        self.calls.append(("update_index", stock_code, stock_name, score))


def test_write_analysis_uses_research_score_for_index_when_available():
    FakeMemoryManager.instances = []

    with patch.object(run_analysis, "MemoryManager", FakeMemoryManager):
        run_analysis.write_analysis_to_obsidian(
            stock_code="TEST.US",
            stock_name="Test Inc",
            analysis_text="## 结论\n\n正文",
            score=40,
            core_view="研究分更可信",
            price=12.5,
            research_score=72,
            timing_state="Ready",
        )

    mm = FakeMemoryManager.instances[0]
    index_calls = [call for call in mm.calls if call[0] == "update_index"]
    timeline_calls = [call for call in mm.calls if call[0] == "append_to_timeline"]
    evaluation_calls = [call for call in mm.calls if call[0] == "update_evaluation_table"]

    assert index_calls == [("update_index", "TEST.US", "Test Inc", 72)]
    assert timeline_calls[0][1]["score"] == 72
    assert evaluation_calls[0][1]["current_judgment"].startswith("评分 72/100")


def test_learn_from_history_counts_legacy_and_research_timeline_scores(tmp_path, monkeypatch):
    wiki_dir = tmp_path / "Analysis"
    wiki_dir.mkdir()
    (wiki_dir / "MIXED_US.md").write_text(
        "# MIXED.US\n\n"
        "## 分析时间线\n\n"
        "- **2026-05-20 10:00** | 价格: 10 | 评分: 40/100 | 类型: Claude Code 分析\n"
        "  - 核心观点: old\n"
        "- **2026-05-21 10:00** | 价格: 11 | Research: 72/100 | Timing: Ready | 类型: Cockpit 分析\n"
        "  - 核心观点: new\n\n"
        "## 预测验证\n\n（暂无）\n",
        encoding="utf-8",
    )
    (wiki_dir / "index.md").write_text("# index\n", encoding="utf-8")
    (wiki_dir / "log.md").write_text("# log\n", encoding="utf-8")
    monkeypatch.setattr(memory_manager, "WIKI_DIR", wiki_dir)
    monkeypatch.setattr(memory_manager, "INDEX_PATH", wiki_dir / "index.md")
    monkeypatch.setattr(memory_manager, "LOG_PATH", wiki_dir / "log.md")
    monkeypatch.setattr(
        memory_manager,
        "_stock_wiki_path",
        lambda stock_code: wiki_dir / f"{stock_code.replace('.', '_').replace('/', '_')}.md",
    )

    stats = memory_manager.MemoryManager().learn_from_history()

    assert stats["total_analyses"] == 2
    assert stats["stock_stats"]["MIXED.US"]["count"] == 2
    assert stats["stock_stats"]["MIXED.US"]["avg_score"] == 56.0
    assert stats["stock_stats"]["MIXED.US"]["latest_score"] == 72.0
