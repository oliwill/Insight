import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_review as run_review
import scripts.scan_inbox as scan_inbox
import scripts.update_dashboard as update_dashboard


def test_scan_inbox_dry_run_does_not_call_processing(monkeypatch):
    pending = [
        SimpleNamespace(filename="no_codes.md", title="No codes", stock_codes=[]),
        SimpleNamespace(filename="with_codes.md", title="With codes", stock_codes=["AAPL.US"]),
    ]
    calls = {"generate": 0, "mark": 0}

    monkeypatch.setattr(scan_inbox, "get_pending_analysis", lambda: pending)
    monkeypatch.setattr(scan_inbox, "generate_analysis", lambda code: calls.__setitem__("generate", calls["generate"] + 1))
    monkeypatch.setattr(scan_inbox, "load_wiki_context", lambda code: {})
    monkeypatch.setattr(scan_inbox, "load_inbox_materials", lambda code: [])
    monkeypatch.setattr(scan_inbox, "mark_processed", lambda item: calls.__setitem__("mark", calls["mark"] + 1))

    results = scan_inbox.process_pending_items(dry_run=True)

    assert results["processed"] == 0
    assert results["skipped"] == 1
    assert results["errors"] == 0
    assert [detail["status"] for detail in results["details"]] == ["skipped_no_codes", "dry_run"]
    assert calls == {"generate": 0, "mark": 0}


def test_scan_inbox_processes_items_and_marks_processed(monkeypatch):
    pending = [SimpleNamespace(filename="with_codes.md", title="With codes", stock_codes=["AAPL.US"])]
    calls = {"generate": 0, "mark": 0}

    def fake_generate(code):
        calls["generate"] += 1
        return {"stock_code": code}

    def fake_mark(item):
        calls["mark"] += 1

    monkeypatch.setattr(scan_inbox, "get_pending_analysis", lambda: pending)
    monkeypatch.setattr(scan_inbox, "generate_analysis", fake_generate)
    monkeypatch.setattr(scan_inbox, "load_wiki_context", lambda code: {"wiki_status": "HAS_HISTORY"})
    monkeypatch.setattr(scan_inbox, "load_inbox_materials", lambda code: [])
    monkeypatch.setattr(scan_inbox, "mark_processed", fake_mark)

    results = scan_inbox.process_pending_items(dry_run=False)

    assert results["processed"] == 1
    assert results["skipped"] == 0
    assert results["errors"] == 0
    assert results["details"][0]["status"] == "data_fetched"
    assert results["details"][0]["market_data_ok"] is True
    assert calls == {"generate": 1, "mark": 1}


def test_run_review_list_tickers_uses_discovery_without_running_review(monkeypatch, capsys):
    class StubScheduler:
        def __init__(self):
            self.runner = SimpleNamespace(_discover_tickers=lambda: ["AAPL.US", "NVDA.US"])

    monkeypatch.setattr(run_review, "ReviewScheduler", StubScheduler)
    monkeypatch.setattr(sys, "argv", ["run_review.py", "--list-tickers", "--json"])

    exit_code = run_review.main()
    out = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert out == {"tickers": ["AAPL.US", "NVDA.US"], "count": 2}


def test_update_dashboard_cli_passes_scheduled_reason(monkeypatch, capsys):
    captured = {}

    def fake_update_dashboard(update_reason="manual", verbose=True):
        captured["update_reason"] = update_reason
        captured["verbose"] = verbose
        return {
            "dashboard_path": "Dashboard.md",
            "backup_path": "Dashboard.md.bak",
            "tracked_stocks": 2,
            "pending_tasks": 1,
            "recent_logs": 5,
            "update_reason": update_reason,
            "timestamp": "2026-06-04T10:00:00",
        }

    monkeypatch.setattr(update_dashboard, "update_dashboard", fake_update_dashboard)
    monkeypatch.setattr(sys, "argv", ["update_dashboard.py", "--json", "--reason", "scheduled"])

    exit_code = update_dashboard.main()
    out = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured == {"update_reason": "scheduled", "verbose": False}
    assert out["success"] is True
    assert out["action"] == "update"
    assert out["update_reason"] == "scheduled"


def test_update_dashboard_cli_restore_backup_uses_config_path(monkeypatch, capsys):
    monkeypatch.setattr(update_dashboard, "restore_dashboard_backup", lambda verbose=True: Path("Dashboard.md.bak"))
    monkeypatch.setattr(update_dashboard.Config, "OBSIDIAN_DASHBOARD_PATH", Path("Dashboard.md"))
    monkeypatch.setattr(sys, "argv", ["update_dashboard.py", "--json", "--restore-backup"])

    exit_code = update_dashboard.main()
    out = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert out["success"] is True
    assert out["action"] == "restore"
    assert out["dashboard_path"] == "Dashboard.md"
    assert out["backup_path"].endswith("Dashboard.md.bak")
