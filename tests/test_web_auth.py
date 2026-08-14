"""认证与数据访问层测试 —— web.db / web.security / web.deps"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config import Config
from web import db, security


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "WEB_DB_PATH", tmp_path / "web.db")
    db.init_db()
    yield


# ==================== security ====================

def test_password_hash_roundtrip():
    salt = security.generate_salt()
    h = security.hash_password("secret123", salt)
    assert security.verify_password("secret123", salt, h)
    assert not security.verify_password("wrong", salt, h)


def test_password_salt_makes_hash_unique():
    h1 = security.hash_password("secret", security.generate_salt())
    h2 = security.hash_password("secret", security.generate_salt())
    assert h1 != h2


def test_session_token_is_urlsafe_random():
    a = security.new_session_token()
    b = security.new_session_token()
    assert a != b
    assert len(a) >= 32


# ==================== users / sessions ====================

def test_create_and_fetch_user():
    salt = security.generate_salt()
    uid = db.create_user("User@Example.com", security.hash_password("pw", salt), salt)
    assert uid is not None
    row = db.get_user_by_email("user@example.com")  # 大小写归一
    assert row is not None and row["id"] == uid


def test_duplicate_email_rejected():
    salt = security.generate_salt()
    db.create_user("a@b.com", security.hash_password("pw", salt), salt)
    assert db.create_user("a@b.com", security.hash_password("pw2", salt), salt) is None


def test_session_lifecycle():
    salt = security.generate_salt()
    uid = db.create_user("u@x.com", security.hash_password("pw", salt), salt)
    token = security.new_session_token()
    db.create_session(uid, token, ttl_days=7)
    user = db.get_session_user(token)
    assert user is not None and user["id"] == uid
    db.delete_session(token)
    assert db.get_session_user(token) is None


def test_expired_session_rejected():
    salt = security.generate_salt()
    uid = db.create_user("u@x.com", security.hash_password("pw", salt), salt)
    token = security.new_session_token()
    db.create_session(uid, token, ttl_days=-1)  # 立即过期
    assert db.get_session_user(token) is None


def test_unknown_token_rejected():
    assert db.get_session_user("no-such-token") is None


# ==================== deps 集成 ====================

def test_get_current_user_requires_login():
    app = FastAPI()
    app.include_router(_auth_probe_router())
    client = TestClient(app)

    r = client.get("/probe")
    assert r.status_code == 401

    salt = security.generate_salt()
    uid = db.create_user("probe@x.com", security.hash_password("pw", salt), salt)
    token = security.new_session_token()
    db.create_session(uid, token, ttl_days=7)
    client.cookies.set("session", token)
    r = client.get("/probe")
    assert r.status_code == 200
    assert r.json()["email"] == "probe@x.com"


def _auth_probe_router():
    from fastapi import APIRouter, Depends
    from web.deps import get_current_user

    router = APIRouter()

    @router.get("/probe")
    def probe(user: dict = Depends(get_current_user)):
        return {"email": user["email"]}

    return router
