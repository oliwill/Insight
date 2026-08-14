"""分析任务执行器测试 —— web/tasks 状态机 + 并发信号量"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from config import Config
from web import db, tasks


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "WEB_DB_PATH", tmp_path / "web.db")
    db.init_db()
    yield


def _wait_status(job_id, status, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = db.get_job(job_id)
        if job is not None and job["status"] == status:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not reach {status} in time")


def test_job_succeeds(monkeypatch):
    monkeypatch.setattr(tasks, "run_analysis", lambda symbol, user_id: {"ok": True})
    user_id = db.create_user("a@b.com", "h", "s")
    job_id = db.create_job(user_id, "TEST.US")

    tasks.submit_analysis(job_id)
    job = _wait_status(job_id, db.JOB_SUCCEEDED)
    assert job["error"] is None
    assert job["symbol"] == "TEST.US"


def test_job_failed_captures_error(monkeypatch):
    def boom(symbol, user_id):
        raise RuntimeError("data source down")

    monkeypatch.setattr(tasks, "run_analysis", boom)
    user_id = db.create_user("a@b.com", "h", "s")
    job_id = db.create_job(user_id, "TEST.US")

    tasks.submit_analysis(job_id)
    job = _wait_status(job_id, db.JOB_FAILED)
    assert "data source down" in (job["error"] or "")


def test_submit_is_idempotent(monkeypatch):
    calls = {"n": 0}

    def fake_run(symbol, user_id):
        calls["n"] += 1
        return {"ok": True}

    monkeypatch.setattr(tasks, "run_analysis", fake_run)
    user_id = db.create_user("a@b.com", "h", "s")
    job_id = db.create_job(user_id, "TEST.US")

    tasks.submit_analysis(job_id)
    tasks.submit_analysis(job_id)  # 重复提交：job 已 running，不再入队
    _wait_status(job_id, db.JOB_SUCCEEDED)
    time.sleep(0.05)
    assert calls["n"] == 1


def test_concurrency_capped_at_two(monkeypatch):
    counter = {"active": 0, "max": 0}

    def slow_run(symbol, user_id):
        counter["active"] += 1
        counter["max"] = max(counter["max"], counter["active"])
        time.sleep(0.05)
        counter["active"] -= 1
        return {"ok": True}

    monkeypatch.setattr(tasks, "run_analysis", slow_run)
    user_id = db.create_user("a@b.com", "h", "s")
    job_ids = [db.create_job(user_id, f"T{i}.US") for i in range(4)]
    for jid in job_ids:
        tasks.submit_analysis(jid)
    for jid in job_ids:
        _wait_status(jid, db.JOB_SUCCEEDED)

    assert counter["max"] <= 2
    assert all(db.get_job(jid)["status"] == db.JOB_SUCCEEDED for jid in job_ids)
