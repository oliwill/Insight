"""媒体服务测试 —— 图表访问与目录穿越防护"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from config import Config
from web.analysis_service import user_vault_dir


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
    client.post("/auth/register", data={
        "email": "m@x.com", "password": "password123", "password2": "password123",
    }, follow_redirects=False)
    return client


def _make_chart(user_id: int, name: str) -> Path:
    charts = user_vault_dir(user_id) / "Charts"
    charts.mkdir(parents=True)
    f = charts / name
    f.write_bytes(b"PNG-DATA")
    return f


def test_chart_served_for_owner(authed_client):
    from web import db
    uid = db.get_user_by_email("m@x.com")["id"]
    _make_chart(uid, "TEST_US_wyckoff.png")

    r = authed_client.get("/stocks/media/charts/TEST_US_wyckoff.png")
    assert r.status_code == 200
    assert r.content == b"PNG-DATA"


def test_chart_traversal_rejected(authed_client):
    r = authed_client.get("/stocks/media/charts/../web.db")
    assert r.status_code in (403, 404)


def test_chart_absolute_path_rejected(authed_client):
    r = authed_client.get("/stocks/media/charts/%2e%2e%2f%2e%2e%2f%2e%2e%2fweb.db")
    assert r.status_code in (403, 404)


def test_chart_missing_404(authed_client):
    assert authed_client.get("/stocks/media/charts/nope.png").status_code == 404
