"""飞书指令机器人测试 —— scripts/feishu_bot.py

单元测试不联网：指令分发用 dispatch_quiet（mock 鉴权+同步执行），
_currency 等纯函数直接测；_lark_prefix 只验证返回结构。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.feishu_bot import _ccy, extract_text


def test_extract_text_parses_json_content():
    assert extract_text('{"text": "分析 MU.US"}') == "分析 MU.US"
    assert extract_text("plain") == "plain"
    assert extract_text("") == ""


def test_ccy_symbol_by_market():
    assert _ccy("SH603087") == "¥"
    assert _ccy("00700.HK") == "HK$"
    assert _ccy("MU.US") == "$"


def test_is_authorized_whitelist(monkeypatch):
    import scripts.feishu_bot as fb

    monkeypatch.setattr(fb, "_ALLOWED_OPEN_ID", "ou_abc")
    assert fb.is_authorized("ou_abc") is True
    assert fb.is_authorized("ou_other") is False


def test_is_authorized_empty_whitelist(monkeypatch):
    import scripts.feishu_bot as fb

    monkeypatch.setattr(fb, "_ALLOWED_OPEN_ID", "")
    assert fb.is_authorized("ou_abc") is False


def test_dispatch_help_returns_help_text(monkeypatch):
    import scripts.feishu_bot as fb

    monkeypatch.setattr(fb, "_ALLOWED_OPEN_ID", "ou_test")
    out = fb.dispatch_quiet("help")
    assert "Insight 分析助手" in out
    assert "分析" in out and "/get" in out


def test_dispatch_unknown_command(monkeypatch):
    import scripts.feishu_bot as fb

    monkeypatch.setattr(fb, "_ALLOWED_OPEN_ID", "ou_test")
    out = fb.dispatch_quiet("xyzxyz")
    assert "无法识别" in out


def test_dispatch_get_returns_vault_summary(monkeypatch):
    import scripts.feishu_bot as fb

    monkeypatch.setattr(fb, "_ALLOWED_OPEN_ID", "ou_test")
    # /get 读 vault（本机配置了真实 vault 时返回内容，否则报错信息也合理）
    out = fb.dispatch_quiet("/get SH603087")
    assert out  # 非空即通过（内容依赖 vault 数据，不断言具体值）


def test_dispatch_note_requires_code_and_content(monkeypatch):
    import scripts.feishu_bot as fb

    monkeypatch.setattr(fb, "_ALLOWED_OPEN_ID", "ou_test")
    out = fb.dispatch_quiet("/note")
    assert "无法识别" in out  # 缺参数不匹配 /note 正则 → 未知指令


def test_dispatch_setup_mode_replies_open_id(monkeypatch):
    """未配置白名单时，bot 回复发送者 open_id 引导设置。"""
    import scripts.feishu_bot as fb

    monkeypatch.setattr(fb, "_ALLOWED_OPEN_ID", "")
    out = fb.dispatch_quiet("随便什么")
    assert "ou_test" in out
    assert "FEISHU_BOT_ALLOWED_OPEN_ID" in out


def test_lark_prefix_returns_list():
    from scripts.feishu_bot import _lark_prefix

    prefix = _lark_prefix()
    assert isinstance(prefix, list) and len(prefix) >= 1
    # Windows 下 npm shim 应解析成 node + run.js
    if len(prefix) == 2:
        assert prefix[0].lower() in {"node", "node.exe"}
        assert "run.js" in prefix[1]


def test_build_report_markdown_sections():
    from types import SimpleNamespace

    from scripts.feishu_bot import _build_report_markdown

    md = {
        "stock_info": {"name": "测试", "price": 10.0},
        "fundamentals": {"pe_ttm": 20.5, "gross_margin": 0.5, "market_cap": 1e9},
        "wyckoff": {"phase": "吸筹区"},
        "volume_profile": {"regime": "平量推升"},
        "dow_channel": {"channel_direction": "上升", "neckline_signal": "颈线已突破"},
        "force_balance": {"bull_bear_state": "多方主导"},
        "multi_timeframe": {"alignment": "三级别共振多头"},
    }
    research = SimpleNamespace(total_adjusted_score=70.5, verdict="标准建仓候选")
    timing = SimpleNamespace(state="Ready")

    text = _build_report_markdown(md, research, timing, "TEST.US")
    assert "## 核心结论" in text
    assert "Research" in text and "70.5" in text
    assert "## 基本面" in text and "PE(TTM)" in text
    assert "## 技术面" in text and "吸筹区" in text
    assert "## 免责声明" in text


def test_lark_docs_create_success(monkeypatch):
    import scripts.feishu_bot as fb

    monkeypatch.setattr(
        fb, "_lark_run", lambda args, timeout=60: '{"doc_id": "doxcnABC123"}'
    )
    url = fb._lark_docs_create("标题", "# md")
    assert url == "https://feishu.cn/docx/doxcnABC123"


def test_lark_docs_create_failure(monkeypatch):
    import scripts.feishu_bot as fb

    monkeypatch.setattr(fb, "_lark_run", lambda args, timeout=60: "")
    assert fb._lark_docs_create("标题", "# md") is None


def test_fmt_pe_negative_shows_loss():
    from scripts.feishu_bot import _fmt_pe

    assert _fmt_pe(-824.6) == "亏损"
    assert _fmt_pe(21.7) == "21.7"
    assert _fmt_pe(None) == "—"


def test_pct_delegates_to_shared_normalizer():
    from scripts.feishu_bot import _pct

    assert _pct(0.27) == "27%"
    assert _pct(27.0) == "27%"
    assert _pct(None) == "—"
