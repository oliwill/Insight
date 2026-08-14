"""Daily Brief 回归测试 —— scripts/daily_brief.py + input/brief_summarizer + notification。

单元测试不联网：选股/模板/降级逻辑用临时文件与 monkeypatch 验证。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
import scripts.daily_brief as db


def _recent(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


def _write_wiki(tmp_path: Path, code: str, name: str, dates: list[str]) -> None:
    wiki_dir = tmp_path / "Analysis"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# {name} ({code})", "", "## 分析时间线", ""]
    for d in dates:
        lines.append(
            f"- **{d} 10:00** | 价格: 100 | Research: 80/100 | Timing: Ready | 类型: 综合分析"
        )
        lines.append("  - 核心观点: 测试观点")
    (wiki_dir / f"{code.replace('.', '_')}.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


@pytest.fixture
def wiki_env(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "WIKI_BASE_DIR", tmp_path)
    monkeypatch.setattr(Config, "WIKI_SUBDIR", "Analysis")
    return tmp_path


def test_pick_top_stocks_ranks_and_excludes_zero(wiki_env):
    _write_wiki(wiki_env, "A.US", "A", [_recent(0), _recent(1), _recent(2)])
    _write_wiki(wiki_env, "B.US", "B", [_recent(0)])
    _write_wiki(wiki_env, "C.US", "C", [])  # 无分析 → 排除

    result = db.pick_top_stocks(days=7, top_n=3)
    assert [(c, n, cnt) for c, n, cnt in result] == [
        ("A.US", "A", 3),
        ("B.US", "B", 1),
    ]


def test_pick_top_stocks_respects_time_window(wiki_env):
    # 8 天前的分析不计入 7 天窗口
    _write_wiki(wiki_env, "D.US", "D", [_recent(8), _recent(9)])
    _write_wiki(wiki_env, "E.US", "E", [_recent(0)])

    result = db.pick_top_stocks(days=7, top_n=3)
    assert [(c, cnt) for c, _, cnt in result] == [("E.US", 1)]


def test_pick_top_stocks_skips_special_files(wiki_env):
    _write_wiki(wiki_env, "A.US", "A", [_recent(0)])
    # 复盘/简报/index/log 应被跳过
    (wiki_env / "Analysis").mkdir(exist_ok=True)
    (wiki_env / "Analysis" / "复盘_20260814.md").write_text(
        "# 复盘\n\n## 分析时间线\n- **2026-08-14** | ...\n", encoding="utf-8"
    )
    (wiki_env / "Analysis" / "index.md").write_text(
        "# 总览\n\n## 分析时间线\n- **2026-08-14** | ...\n", encoding="utf-8"
    )

    result = db.pick_top_stocks(days=7, top_n=3)
    assert [(c, cnt) for c, _, cnt in result] == [("A.US", 1)]


def test_collect_parses_five_dimensions_and_timing(wiki_env, monkeypatch):
    monkeypatch.setattr(Config, "BRIEF_MATERIALS_LIMIT", 5)
    mat_file = wiki_env / "mat.md"
    mat_file.write_text(
        "## 摘要\n\n一句话概要内容\n\n## 原文\n\n" + "机密长正文" * 50,
        encoding="utf-8",
    )

    class FakeMM:
        def get_stock_wiki(self, code):
            return (
                f"# 名 ({code})\n\n"
                "## 五维打分\n"
                "| 维度 | Base | Adjusted | 权重 | 加权分 | 证据 | 置信度 |\n"
                "|---|---:|---:|---:|---:|---|---|\n"
                "| 行业/TAM | 5.0 | 5.6 | 20% | 11.2 | x | high |\n"
                "| 护城河 | 7.4 | 7.4 | 20% | 14.8 | x | medium |\n"
                "| 增长质量 | 3.2 | 4.4 | 20% | 8.8 | x | high |\n"
                "| 估值 | 3.5 | 3.5 | 25% | 8.8 | x | high |\n"
                "| 团队/治理 | 6.0 | 6.0 | 15% | 9.0 | x | medium |\n"
                "| **综合** | **49.0** | **52.5** | **100%** | **52.5** | **观察** | **high** |\n"
                "\n## 交易时机状态\n"
                "状态：**Wait**\n内部时机分：约 **74/100**\n\n"
                "### 触发条件\n- 回调企稳\n\n### 失效条件\n- 跌破支撑\n\n"
                "## 综合评估\n"
                "| 维度 | 当前判断 | 上次判断 | 变化 | 更新时间 |\n"
                "|------|----------|----------|------|----------|\n"
                "| 综合 | 评分 52.5/100 - Research 52.5/100（观察），Timing Wait；分析师目标价 $72.50 vs 当前 $77.48 (潜在 -6.4%) | - | 已更新 | 2026-08-13 |\n"
                "\n## 分析时间线\n"
                f"- **{_recent(0)} 10:00** | 价格: 10 | Research: 80/100 | Timing: Ready | 类型: 综合分析\n"
                "  - 核心观点: 一句观点\n"
            )

        def get_materials(self, code, limit=5):
            return [
                {
                    "title": "文章A",
                    "source_type": "article",
                    "timestamp": _recent(0),
                    "filepath": str(mat_file),
                }
            ]

    c = db.collect(FakeMM(), "X.US", "名", 2)
    assert c["research"] == "80"
    assert c["timing"] == "Ready"
    assert c["verdict"] == "观察"
    assert c["dims"] == {
        "行业": "5.6",
        "护城河": "7.4",
        "增长": "4.4",
        "估值": "3.5",
        "团队": "6.0",
    }
    assert c["target"] == "$72.50 vs 当前 $77.48（潜在 -6.4%）"  # X.US → $
    assert c["entry"] == "回调企稳"
    assert c["invalidation"] == "跌破支撑"
    assert c["materials"][0]["summary"] == "一句话概要内容"
    # 只读 ## 摘要，不读 ## 原文
    assert "机密" not in c["materials"][0]["summary"]


def test_currency_symbol():
    assert db._currency_symbol("SH603087") == "¥"
    assert db._currency_symbol("09988.HK") == "HK$"
    assert db._currency_symbol("MU.US") == "$"


def test_normalize_money_replaces_bare_dollar():
    # A 股：裸 $ → ¥
    assert (
        db._normalize_money("跌破 Wyckoff 支撑 $54.89", "SH603087")
        == "跌破 Wyckoff 支撑 ¥54.89"
    )
    # 港股：裸 $ → HK$，且不破坏已有的 HK$
    assert db._normalize_money("回踩 MA50 $63.03", "09988.HK") == "回踩 MA50 HK$63.03"
    assert db._normalize_money("阻力 HK$58.91", "09988.HK") == "阻力 HK$58.91"
    # 美股：不变
    assert db._normalize_money("跌破 $54.89", "MU.US") == "跌破 $54.89"


def test_deterministic_template_detailed_structure():
    stocks = [
        {
            "code": "A.US",
            "name": "A",
            "count": 3,
            "research": "80",
            "verdict": "观察",
            "timing": "Ready",
            "target": "$80 vs 当前 $70（潜在 +14.3%）",
            "dims": {"行业": "5.6", "护城河": "7.4"},
            "entry": "回踩支撑",
            "invalidation": "跌破支撑",
            "materials": [{"title": "文章1", "summary": "概要1"}],
        },
        {
            "code": "B.US",
            "name": "B",
            "count": 1,
            "research": None,
            "verdict": "",
            "timing": None,
            "target": "",
            "dims": {},
            "entry": "",
            "invalidation": "",
            "materials": [],
        },
    ]
    from input.brief_summarizer import deterministic_template

    text = deterministic_template(stocks, lookback_days=7)
    assert "Top2" in text
    assert "A.US" in text and "B.US" in text
    assert (
        "目标价" in text and "基本面" in text and "操作" in text and "相关文章" in text
    )
    assert "文章1" in text and "概要1" in text
    assert "$80 vs 当前 $70" in text
    assert "N/A" in text  # B 缺 research/timing 显示 N/A
    assert "—" in text  # 缺失字段显示 —


def test_summarize_brief_returns_none_without_api_key(monkeypatch):
    from input.brief_summarizer import summarize_brief

    monkeypatch.setattr(Config, "LLM_API_KEY", None)
    assert summarize_brief([], 7) is None


def test_notify_brief_prefers_feishu(monkeypatch):
    from notification import notify_brief

    monkeypatch.setattr("notification.notify_feishu", lambda t, m: True)
    assert notify_brief("t", "m") == "feishu"


def test_notify_brief_falls_back_to_log(monkeypatch):
    from notification import notify_brief

    monkeypatch.setattr("notification.notify_feishu", lambda t, m: False)
    monkeypatch.setattr("notification.notify_wecom", lambda t, m: False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_USER_ID", raising=False)
    monkeypatch.setattr("notification.notify", lambda t, m: False)
    assert notify_brief("t", "m") == "log"


def test_notify_feishu_returns_false_without_url(monkeypatch):
    from notification import notify_feishu

    monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
    assert notify_feishu("t", "m") is False
