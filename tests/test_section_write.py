import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_analysis
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


def test_research_note_append_demotes_competitor_pressure_heading():
    wiki = "# TEST\n\n## 研究笔记\n\n（暂无）\n"
    report = "# 手工分析\n\n## 三、基本面与估值\n\n### 护城河压力测试\n\n正文"
    demoted = run_analysis._demote_markdown_headings(report)

    updated = _append_to_section(wiki, "研究笔记", demoted)
    content = _get_section_content(updated, "研究笔记")

    assert "### 手工分析" in content
    assert "#### 护城河压力测试" in content
    assert not re.search(r"^##\s+手工分析\s*$", content, re.MULTILINE)
    assert not re.search(r"^##\s+护城河压力测试\s*$", content, re.MULTILINE)
