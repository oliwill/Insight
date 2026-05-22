import importlib.util
import subprocess
import sys
from pathlib import Path

import telegram_bot


def test_telegram_bot_help_does_not_require_telegram_package(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "telegram_bot.py"

    original_find_spec = importlib.util.find_spec

    def fake_find_spec(name, package=None):
        if name == "telegram" or name.startswith("telegram."):
            return None
        return original_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Telegram Bot - Trader-Obsidian" in result.stdout


def test_extract_ticker_supports_advertised_note_formats():
    assert telegram_bot.extract_ticker("AAPL bullish note") == "AAPL"
    assert telegram_bot.normalize_ticker(telegram_bot.extract_ticker("AAPL bullish note")) == "AAPL.US"
    assert telegram_bot.extract_ticker("SH603906") == "SH603906"
    assert telegram_bot.normalize_ticker(telegram_bot.extract_ticker("SH603906")) == "SH603906"
    assert telegram_bot.extract_ticker("00700.HK breakout") == "00700.HK"
