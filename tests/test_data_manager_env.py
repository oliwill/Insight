import importlib
import sys
import types
from pathlib import Path


def test_data_manager_import_loads_dotenv(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    calls = []
    fake_dotenv = types.SimpleNamespace(load_dotenv=lambda: calls.append("load_dotenv"))

    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)
    sys.path.insert(0, str(repo_root))
    sys.modules.pop("data.manager", None)
    try:
        importlib.import_module("data.manager")
    finally:
        if sys.path[0] == str(repo_root):
            sys.path.pop(0)

    assert calls == ["load_dotenv"]


def test_yfinance_cache_is_configured_to_a_writable_project_path(tmp_path, monkeypatch):
    from data import manager

    calls = []
    monkeypatch.setattr(manager.yf.cache, "set_cache_location", lambda value: calls.append(value))

    configured = manager._configure_yfinance_cache(tmp_path / "yf-cache")

    assert configured == tmp_path / "yf-cache"
    assert configured.is_dir()
    assert calls == [str(configured)]
