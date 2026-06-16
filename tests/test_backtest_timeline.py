import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.core import BacktestResult
from backtest.runner import BacktestRunner


class FakeMemoryManager:
    def __init__(self, wiki):
        self.wiki = wiki
        self.backtest_entries = []

    def get_stock_wiki(self, ticker):
        return self.wiki

    def append_to_section(self, ticker, section_name, entry):
        self.backtest_entries.append((ticker, section_name, entry))


class FakeEngine:
    def __init__(self):
        self.calls = []

    def backtest_analysis(self, ticker, result, analysis_date, days_after):
        self.calls.append((ticker, result, analysis_date, days_after))
        return BacktestResult(ticker=ticker, analysis_date=analysis_date)


def test_legacy_timeline_without_action_word_defaults_to_hold(monkeypatch):
    wiki = (
        "# TEST.US\n\n"
        "## 分析时间线\n\n"
        "- **2026-01-01 10:00** | 价格: 10 | 评分: 55/100 | 类型: Claude Code 分析\n"
        "  - 核心观点: 估值偏贵，继续观察\n"
    )
    runner = BacktestRunner(data_manager=object(), memory_manager=FakeMemoryManager(wiki))
    fake_engine = FakeEngine()
    runner.engine = fake_engine

    results = runner.backtest_wiki_timeline("TEST.US", days_after=1, lookback_days=3650)

    assert len(results) == 1
    assert fake_engine.calls[0][1].signals == ["HOLD"]
