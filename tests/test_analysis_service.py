"""分析服务测试 —— web/analysis_service（全组件打桩，不碰网络）"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from config import Config
from memory.manager import MemoryManager
from web import analysis_service, db


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "WEB_DB_PATH", tmp_path / "web.db")
    monkeypatch.setattr(Config, "USERS_DATA_DIR", tmp_path / "users")
    monkeypatch.setattr(Config, "WIKI_SUBDIR", "Analysis")
    monkeypatch.setattr(Config, "MATERIALS_SUBDIR", "Materials")
    db.init_db()
    yield


FAKE_MARKET_DATA = {
    "stock_info": {
        "code": "TEST.US",
        "name": "Test Co",
        "price": 50.0,
        "change_pct": 1.2,
        "currency": "USD",
        "sector": "Tech",
        "industry": "Software",
    },
    "fundamentals": {
        "pe_forward": 20.0,
        "target_mean_price": 60.0,
        "analyst_rating": "Buy",
    },
    "technicals": {"rsi": 55.0, "ma20": 48.0, "ma60": 45.0},
    "wyckoff": {"phase": "Accumulation", "support": 45.0, "resistance": 55.0},
    "earnings": {},
    "liquidity": {},
    "options": {},
    "web_search": {},
    "peers": [],
    "kline_rows": 0,
    "_data_sources": {"technicals": "yfinance"},
}


class FakeScore:
    total_adjusted_score = 70.0
    verdict = "看好"
    confidence = "中"
    dimensions = {}  # ReportGenerator 遍历五维明细

    @staticmethod
    def to_markdown(self):
        return "## 五维打分\nfake"


class FakeTiming:
    state = "Wait"
    entry_triggers = ["突破 55"]

    @staticmethod
    def to_markdown(self):
        return "## 交易时机\nfake"


def _stub_components(monkeypatch):
    monkeypatch.setattr(analysis_service, "generate_analysis",
                        lambda code, wiki_base=None: dict(FAKE_MARKET_DATA))
    monkeypatch.setattr(analysis_service.DataManager, "get_historical_data",
                        lambda self, code, period="1y": None)

    class FakeEvidenceExtractor:
        def extract(self, **kwargs):
            return []

        def to_markdown(self, evidence):
            return "## 证据表\n（暂无）"

    monkeypatch.setattr(analysis_service, "EvidenceExtractor", FakeEvidenceExtractor)

    class FakeResearchEngine:
        def score(self, market_data, evidence):
            return FakeScore()

        def to_markdown(self, obj):
            return "## 五维打分\nfake"

    class FakeTimingEngine:
        def analyze(self, market_data, research_score=None):
            return FakeTiming()

        def to_markdown(self, obj):
            return "## 交易时机\nfake"

    monkeypatch.setattr(analysis_service, "ResearchScoreEngine", FakeResearchEngine)
    monkeypatch.setattr(analysis_service, "TimingEngine", FakeTimingEngine)
    monkeypatch.setattr(analysis_service, "enhance_summary", lambda *a, **k: None)


def test_run_analysis_writes_record_and_vault(tmp_path, monkeypatch):
    _stub_components(monkeypatch)
    user_id = db.create_user("a@b.com", "h", "s")

    result = analysis_service.run_analysis("TEST.US", user_id)

    assert result["record_id"] > 0
    assert result["symbol"] == "TEST.US"
    assert result["score"] == 70.0
    assert result["timing_state"] == "Wait"
    assert result["llm_enhanced"] is False

    # record 落库，报告全文可查
    records = db.get_analysis_records(user_id, symbol="TEST.US")
    assert len(records) == 1
    assert "# Test Co (TEST.US)" in records[0]["report_md"] or "TEST.US" in records[0]["report_md"]

    # 用户 vault 落盘（wiki + 时间线）
    vault = analysis_service.user_vault_dir(user_id)
    wiki_path = vault / "Analysis" / "TEST_US.md"
    assert wiki_path.exists()
    content = wiki_path.read_text(encoding="utf-8")
    assert "Web 分析" in content
    assert "Research: 70.0/100" in content or "Timing: Wait" in content


def test_run_analysis_is_user_isolated(tmp_path, monkeypatch):
    _stub_components(monkeypatch)
    uid_a = db.create_user("a@b.com", "h", "s")
    uid_b = db.create_user("b@b.com", "h", "s")

    analysis_service.run_analysis("TEST.US", uid_a)
    analysis_service.run_analysis("TEST.US", uid_b)

    # 各自 vault 独立
    va = analysis_service.user_vault_dir(uid_a) / "Analysis" / "TEST_US.md"
    vb = analysis_service.user_vault_dir(uid_b) / "Analysis" / "TEST_US.md"
    assert va.exists() and vb.exists()

    # 记录各自归属
    assert len(db.get_analysis_records(uid_a)) == 1
    assert len(db.get_analysis_records(uid_b)) == 1


def test_run_analysis_second_run_appends_timeline(tmp_path, monkeypatch):
    _stub_components(monkeypatch)
    user_id = db.create_user("a@b.com", "h", "s")

    analysis_service.run_analysis("TEST.US", user_id)
    analysis_service.run_analysis("TEST.US", user_id)

    records = db.get_analysis_records(user_id, symbol="TEST.US")
    assert len(records) == 2
    vault = analysis_service.user_vault_dir(user_id)
    content = (vault / "Analysis" / "TEST_US.md").read_text(encoding="utf-8")
    assert content.count("Web 分析") >= 2  # 时间线追加两条
