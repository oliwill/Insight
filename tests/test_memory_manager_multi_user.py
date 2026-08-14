"""多用户存储隔离测试 —— MemoryManager base_dir 参数化

验证：
1. 两个用户各建 vault，wiki/materials/index/log 完全隔离
2. base_dir=None 时回退到 Config 全局路径（CLI/旧行为兼容）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from memory.manager import MemoryManager


def test_two_users_isolated_vaults(tmp_path):
    base_a = tmp_path / "user_a"
    base_b = tmp_path / "user_b"
    ma = MemoryManager(base_dir=base_a)
    mb = MemoryManager(base_dir=base_b)

    ma.init_stock_wiki("TEM.US", "Tempus AI")
    mb.init_stock_wiki("AAPL.US", "Apple")

    ma.append_to_timeline("TEM.US", price=100, score=70, core_view="用户A的观点")
    mb.append_to_timeline("AAPL.US", price=200, score=80, core_view="用户B的观点")

    wiki_a = ma.get_stock_wiki("TEM.US")
    wiki_b = mb.get_stock_wiki("AAPL.US")

    assert "用户A的观点" in wiki_a
    assert "用户B的观点" not in wiki_a
    assert "用户B的观点" in wiki_b
    assert "用户A的观点" not in wiki_b

    # 文件落位互不串扰
    sub = Config.WIKI_SUBDIR
    assert (base_a / sub / "TEM_US.md").exists()
    assert (base_b / sub / "AAPL_US.md").exists()
    assert not (base_a / sub / "AAPL_US.md").exists()
    assert not (base_b / sub / "TEM_US.md").exists()

    # index.md / log.md 各自独立
    assert (base_a / sub / "index.md").exists()
    assert (base_b / sub / "index.md").exists()


def test_analysis_history_is_user_scoped(tmp_path):
    base_a = tmp_path / "user_a"
    base_b = tmp_path / "user_b"
    ma = MemoryManager(base_dir=base_a)
    mb = MemoryManager(base_dir=base_b)

    ma.init_stock_wiki("TEM.US", "Tempus AI")
    mb.init_stock_wiki("AAPL.US", "Apple")
    ma.append_to_timeline("TEM.US", price=100, score=70, core_view="A 的分析")
    mb.append_to_timeline("AAPL.US", price=200, score=80, core_view="B 的分析")

    hist_a = ma.get_analysis_history(stock_code="TEM.US")
    hist_b = mb.get_analysis_history(stock_code="AAPL.US")
    assert len(hist_a) == 1 and "A 的分析" in hist_a[0]["result"]
    assert len(hist_b) == 1 and "B 的分析" in hist_b[0]["result"]


def test_default_base_dir_uses_config(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "WIKI_BASE_DIR", tmp_path)
    manager = MemoryManager()
    manager.init_stock_wiki("TEST.US", "Test Co")
    assert (tmp_path / Config.WIKI_SUBDIR / "TEST_US.md").exists()


def test_save_material_is_user_scoped(tmp_path):
    base_a = tmp_path / "user_a"
    base_b = tmp_path / "user_b"
    ma = MemoryManager(base_dir=base_a)
    mb = MemoryManager(base_dir=base_b)

    ma.init_stock_wiki("TEM.US", "Tempus AI")
    mb.init_stock_wiki("TEM.US", "Tempus AI")
    sub = Config.MATERIALS_SUBDIR
    (base_a / sub / "TEM_US").mkdir(parents=True)
    (base_b / sub / "TEM_US").mkdir(parents=True)

    pa = ma.save_material("TEM.US", "web_search", "材料内容A", title="A材料")
    pb = mb.save_material("TEM.US", "web_search", "材料内容B", title="B材料")

    assert str(pa).startswith(str(base_a))
    assert str(pb).startswith(str(base_b))
    text_a = "".join(f.read_text(encoding="utf-8") for f in (base_a / sub / "TEM_US").glob("*.md"))
    text_b = "".join(f.read_text(encoding="utf-8") for f in (base_b / sub / "TEM_US").glob("*.md"))
    assert "材料内容A" in text_a
    assert "材料内容B" in text_b
    assert "材料内容B" not in text_a
    assert "材料内容A" not in text_b
