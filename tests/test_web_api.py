"""Web API 全流程测试 —— 注册/登录/自选/分析/追踪/配额"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from config import Config
from web import db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "WEB_DB_PATH", tmp_path / "web.db")
    monkeypatch.setattr(Config, "USERS_DATA_DIR", tmp_path / "users")
    monkeypatch.setattr(Config, "WIKI_SUBDIR", "Analysis")
    monkeypatch.setattr(Config, "MATERIALS_SUBDIR", "Materials")

    from web.app import create_app

    return TestClient(create_app())


@pytest.fixture()
def authed_client(client):
    r = client.post("/auth/register", data={
        "email": "user@example.com", "password": "password123", "password2": "password123",
    }, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("/watchlist")
    return client


# ==================== 认证 ====================

def test_register_login_logout_flow(client):
    # 未登录访问 → 重定向登录页
    r = client.get("/watchlist", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("/auth/login")

    # 注册
    r = client.post("/auth/register", data={
        "email": "u@x.com", "password": "password123", "password2": "password123",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "session" in client.cookies

    # 已登录可访问
    assert client.get("/watchlist").status_code == 200

    # 登出
    r = client.post("/auth/logout", follow_redirects=False)
    assert r.status_code == 303
    client.cookies.clear()
    assert client.get("/watchlist", follow_redirects=False).status_code == 303


def test_register_requires_invite_code_when_configured(client, monkeypatch):
    monkeypatch.setattr(Config, "INVITE_CODE", "secret-invite")
    data = {"email": "v@x.com", "password": "password123", "password2": "password123"}

    # 不填/填错 → 400
    r = client.post("/auth/register", data=data)
    assert r.status_code == 400 and "邀请码" in r.text
    r = client.post("/auth/register", data={**data, "invite_code": "wrong"})
    assert r.status_code == 400 and "邀请码" in r.text

    # 填对 → 303 并登录
    r = client.post("/auth/register", data={**data, "invite_code": "secret-invite"}, follow_redirects=False)
    assert r.status_code == 303
    assert "session" in client.cookies


def test_register_no_invite_required_when_unconfigured(client):
    # 未配置 INVITE_CODE → 无需邀请码（现有测试覆盖，这里显式断言页面不出现邀请码输入框）
    assert "invite_code" not in client.get("/auth/register").text


def test_register_rejects_duplicate_email(client):
    data = {"email": "u@x.com", "password": "password123", "password2": "password123"}
    assert client.post("/auth/register", data=data, follow_redirects=False).status_code == 303
    r = client.post("/auth/register", data=data)
    assert r.status_code == 400
    assert "已注册" in r.text


def test_register_rejects_short_password(client):
    r = client.post("/auth/register", data={
        "email": "u@x.com", "password": "short", "password2": "short",
    })
    assert r.status_code == 400


def test_login_rejects_wrong_password(client):
    client.post("/auth/register", data={
        "email": "u@x.com", "password": "password123", "password2": "password123",
    })
    r = client.post("/auth/login", data={"email": "u@x.com", "password": "wrong"})
    assert r.status_code == 400
    assert "邮箱或密码错误" in r.text


def test_login_rate_limited_after_5_failures(client):
    client.post("/auth/register", data={
        "email": "u@x.com", "password": "password123", "password2": "password123",
    })
    for _ in range(5):
        client.post("/auth/login", data={"email": "u@x.com", "password": "wrong"})
    r = client.post("/auth/login", data={"email": "u@x.com", "password": "password123"})
    assert r.status_code == 429


# ==================== 自选 ====================

def test_watchlist_add_and_list(authed_client):
    r = authed_client.post("/watchlist/add", data={"symbol": "aapl"})
    assert r.status_code == 200
    assert "AAPL" in r.text

    page = authed_client.get("/watchlist")
    assert page.status_code == 200
    assert "AAPL" in page.text


def test_watchlist_remove(authed_client):
    authed_client.post("/watchlist/add", data={"symbol": "AAPL"})
    r = authed_client.post("/watchlist/remove", data={"symbol": "AAPL"})
    assert r.status_code == 200
    assert "AAPL.US" not in authed_client.get("/watchlist").text


def test_watchlist_rejects_bad_symbol(authed_client):
    r = authed_client.post("/watchlist/add", data={"symbol": "!!!bad!!!"})
    assert r.status_code == 400


# ==================== 分析任务 ====================

def _install_sync_submit(monkeypatch, user_id):
    """把任务提交替换为同步执行（分析体 fake，避免网络）"""
    import web.tasks as tasks_mod

    def fake_submit(job_id):
        job = db.get_job(job_id)
        db.update_job_status(job_id, db.JOB_RUNNING)
        db.update_job_status(job_id, db.JOB_SUCCEEDED)
        db.save_analysis_record(
            user_id=user_id, symbol=job["symbol"],
            report_md="# Test Co (TEST.US)\n\n## 一、本次分析总结\nfake report",
            research_score=66.0, timing_state="Wait",
            chart_path=None, data_sources="{}", llm_enhanced=False,
        )

    monkeypatch.setattr(tasks_mod, "submit_analysis", fake_submit)


def test_analysis_full_flow(authed_client, monkeypatch):
    uid = db.get_user_by_email("user@example.com")["id"]
    _install_sync_submit(monkeypatch, uid)

    r = authed_client.post("/stocks/TEST.US/analyze", follow_redirects=False)
    assert r.status_code == 303

    # 股票页显示记录
    page = authed_client.get("/stocks/TEST.US")
    assert page.status_code == 200
    assert "66.0" in page.text

    # 详情页含报告
    record = db.get_analysis_records(uid, symbol="TEST.US")[0]
    detail = authed_client.get(f"/stocks/records/{record['id']}")
    assert detail.status_code == 200
    assert "fake report" in detail.text

    # 追踪页含记录
    timeline = authed_client.get("/timeline")
    assert timeline.status_code == 200
    assert "TEST.US" in timeline.text

    # 任务页含任务
    jobs_page = authed_client.get("/jobs")
    assert jobs_page.status_code == 200
    assert "完成" in jobs_page.text


def test_analysis_record_isolated_between_users(client):
    client.post("/auth/register", data={
        "email": "a@x.com", "password": "password123", "password2": "password123",
    }, follow_redirects=False)
    uid_a = db.get_user_by_email("a@x.com")["id"]
    db.save_analysis_record(uid_a, "SECRET.US", "report-A", 70.0, "Ready", None, "{}", False)

    client.post("/auth/logout", follow_redirects=False)
    client.cookies.clear()
    client.post("/auth/register", data={
        "email": "b@x.com", "password": "password123", "password2": "password123",
    }, follow_redirects=False)
    uid_b = db.get_user_by_email("b@x.com")["id"]

    # B 看不到 A 的股票页记录与详情
    assert "report-A" not in client.get("/stocks/SECRET.US").text
    assert client.get("/timeline").text.count("SECRET.US") == 0
    rec_a = db.get_analysis_records(uid_a)[0]
    assert client.get(f"/stocks/records/{rec_a['id']}").status_code == 404


def test_daily_quota_enforced(client, monkeypatch):
    monkeypatch.setattr(Config, "ANALYSIS_DAILY_QUOTA", 1)
    client.post("/auth/register", data={
        "email": "q@x.com", "password": "password123", "password2": "password123",
    }, follow_redirects=False)
    uid = db.get_user_by_email("q@x.com")["id"]
    _install_sync_submit(monkeypatch, uid)

    assert client.post("/stocks/TEST.US/analyze", follow_redirects=False).status_code == 303
    r = client.post("/stocks/TEST.US/analyze")
    assert r.status_code == 429
    assert "配额" in r.text
