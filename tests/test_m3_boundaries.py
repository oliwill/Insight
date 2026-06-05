import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import inbox_watcher
import telegram_bot


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_telegram_bot_helpers_cover_normalization_and_summary(monkeypatch):
    monkeypatch.setattr(telegram_bot, "LOG_FILE", None)

    assert telegram_bot.extract_ticker("看好 $AAPL 和 00700.HK") == "AAPL"
    assert telegram_bot.normalize_ticker("aapl") == "AAPL.US"
    assert telegram_bot.normalize_ticker("00700") == "00700.HK"
    assert telegram_bot.normalize_ticker("SH603906") == "SH603906"

    summary = telegram_bot.format_analysis_summary(
        "## 综合评估\nA\n## 分析时间线\nB\n## 研究笔记\nC",
        "AAPL.US",
    )

    assert "【综合评估】" in summary
    assert "【最近分析】" in summary
    assert "AAPL.US" in summary


def test_telegram_bot_note_and_scan_commands(monkeypatch):
    monkeypatch.setattr(telegram_bot, "LOG_FILE", None)
    monkeypatch.setattr(telegram_bot, "is_authorized", lambda user_id: True)

    note_calls = {}

    class FakeMemoryManager:
        def save_material(self, **kwargs):
            note_calls.update(kwargs)
            return Path("Materials/AAPL_US.md")

    monkeypatch.setattr(telegram_bot, "MemoryManager", lambda: FakeMemoryManager())

    note_reply = AsyncMock()
    note_update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        message=SimpleNamespace(text="/note $AAPL 看好财报", reply_text=note_reply),
    )
    asyncio.run(telegram_bot.note_command(note_update, SimpleNamespace(args=[])))

    assert note_calls["stock_code"] == "AAPL.US"
    assert note_calls["source_type"] == "telegram"
    assert "AAPL.US" in note_reply.await_args.args[0]

    run_calls = {}

    def fake_run(cmd, cwd, capture_output, text, timeout):
        run_calls["cmd"] = cmd
        run_calls["cwd"] = cwd
        run_calls["capture_output"] = capture_output
        run_calls["text"] = text
        run_calls["timeout"] = timeout
        return SimpleNamespace(returncode=0, stdout="scan ok", stderr="")

    monkeypatch.setattr(telegram_bot.subprocess, "run", fake_run)

    scan_reply = AsyncMock()
    scan_update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        message=SimpleNamespace(text="/scan", reply_text=scan_reply),
    )
    asyncio.run(telegram_bot.scan_command(scan_update, SimpleNamespace(args=[])))

    assert run_calls["cmd"] == [sys.executable, "run_analysis.py", "--scan"]
    assert run_calls["cwd"] == telegram_bot.PROJECT_DIR
    assert run_calls["timeout"] == 300
    assert "✅ 扫描完成" in scan_reply.await_args.args[0]


def test_inbox_watcher_debouncer_and_handler_filters_non_md(monkeypatch):
    captured = []

    class FakeTimer:
        def __init__(self, delay, callback):
            self.delay = delay
            self.callback = callback
            self.started = False
            self.cancelled = False

        def start(self):
            self.started = True

        def cancel(self):
            self.cancelled = True

    monkeypatch.setattr(inbox_watcher, "Timer", FakeTimer)

    debouncer = inbox_watcher.Debouncer(2, lambda files: captured.append(list(files)))
    debouncer.trigger("first.md")
    first_timer = debouncer.timer
    debouncer.trigger("second.md")

    assert first_timer.cancelled is True
    assert debouncer.pending_files == {"first.md", "second.md"}

    debouncer._execute()
    assert len(captured) == 1
    assert set(captured[0]) == {"first.md", "second.md"}
    assert debouncer.pending_files == set()

    trigger_calls = []
    handler = inbox_watcher.InboxHandler(SimpleNamespace(trigger=trigger_calls.append))

    handler.on_created(SimpleNamespace(is_directory=False, src_path="/tmp/ignore.txt"))
    handler.on_created(SimpleNamespace(is_directory=False, src_path="/tmp/note.md"))
    handler.on_created(SimpleNamespace(is_directory=False, src_path="/tmp/~draft.md"))
    handler.on_created(SimpleNamespace(is_directory=False, src_path="/tmp/.obsidian/cache.md"))
    handler.on_moved(SimpleNamespace(is_directory=False, dest_path="/tmp/moved.md"))

    assert trigger_calls == ["/tmp/note.md", "/tmp/moved.md"]


def test_inbox_watcher_trigger_scan_uses_run_analysis_and_notifies(monkeypatch):
    run_calls = {}
    notify_calls = []

    def fake_run(cmd, cwd, capture_output, text, timeout):
        run_calls["cmd"] = cmd
        run_calls["cwd"] = cwd
        run_calls["timeout"] = timeout
        return SimpleNamespace(returncode=0, stdout="scan ok", stderr="")

    monkeypatch.setattr(inbox_watcher.subprocess, "run", fake_run)
    monkeypatch.setattr(inbox_watcher, "notify_telegram", lambda title, msg: notify_calls.append((title, msg)))

    inbox_watcher.trigger_scan(["/tmp/a.md", "/tmp/b.md"])

    assert run_calls["cmd"] == [sys.executable, "run_analysis.py", "--scan"]
    assert run_calls["cwd"] == inbox_watcher.PROJECT_DIR
    assert run_calls["timeout"] == inbox_watcher.SCAN_TIMEOUT
    assert notify_calls and notify_calls[0][0] == "Inbox 监控"
    assert "处理文件: 2" in notify_calls[0][1]


def test_windows_automation_scripts_keep_m3_contracts():
    run_scheduled = _read("scripts/windows/run_scheduled_task.ps1")
    register_tasks = _read("scripts/windows/register_scheduled_tasks.ps1")
    verify_tasks = _read("scripts/windows/verify_scheduled_tasks.ps1")
    smoke = _read("scripts/windows/run_smoke_tests.ps1")

    assert "-WindowStyle Hidden" in run_scheduled
    assert "scripts\\update_dashboard.py" in run_scheduled
    assert "--reason\", \"scheduled\"" in run_scheduled
    assert "Start-Process" in run_scheduled
    assert "RedirectStandardOutput" in run_scheduled
    assert "RedirectStandardError" in run_scheduled

    assert "-WindowStyle" in register_tasks
    assert "Hidden" in register_tasks
    assert '"trader-obsidian"' in register_tasks
    assert '-ShortName "dashboard"' in register_tasks

    assert "LastRunTime" in verify_tasks
    assert "LastTaskResult" in verify_tasks
    assert "-DryRunInbox" in verify_tasks

    assert "telegram_bot.py" in smoke
    assert "inbox_watcher.py" in smoke
    assert "scheduler.py" in smoke
    assert "tests\\test_automation_entrypoints.py" in smoke
    assert "tests\\test_scheduler.py" in smoke
    assert "tests\\test_m3_boundaries.py" in smoke
