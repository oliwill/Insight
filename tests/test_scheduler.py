import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduler import _task_arguments


def test_update_dashboard_task_arguments_include_scheduled_reason(monkeypatch):
    monkeypatch.setenv("SCHEDULE_NOTIFY", "false")

    args = _task_arguments("update_dashboard.py")

    assert args == ["--json", "--reason", "scheduled"]


def test_scan_and_review_tasks_run_in_json_mode(monkeypatch):
    monkeypatch.setenv("SCHEDULE_NOTIFY", "false")

    assert _task_arguments("scan_inbox.py") == ["--json"]
    assert _task_arguments("run_review.py") == ["--json"]


def test_notify_flag_is_optional(monkeypatch):
    monkeypatch.setenv("SCHEDULE_NOTIFY", "true")

    assert _task_arguments("scan_inbox.py") == ["--json", "--notify"]
