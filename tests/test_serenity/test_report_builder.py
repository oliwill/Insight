import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.serenity.report_builder import ReportBuilder

FIXTURE_DIR = Path(__file__).parent / "test_data"

def _load():
    p = FIXTURE_DIR / "ai_semiconductor.json"
    return json.loads(p.read_text(encoding="utf-8"))

def test_all_five_sections_present():
    d = _load(); b = ReportBuilder(); md = b.build(d)
    for s in ["\u4e00\u3001\u4e3b\u9898\u5b9a\u4f4d", "\u4e8c\u3001\u4ea7\u4e1a\u94fe\u62c6\u89e3", "\u4e09\u3001\u74f6\u9888\u5224\u65ad", "\u56db\u3001\u4f18\u5148\u7814\u7a76\u6e05\u5355", "\u4e94\u3001\u4e0b\u4e00\u6b65\u68c0\u67e5\u6e05\u5355"]:
        assert s in md, f"Missing: {s}"

def test_headers_in_order():
    d = _load(); b = ReportBuilder(); md = b.build(d)
    hs = [l for l in md.splitlines() if l.startswith("### ")]
    exp = ["\u4ea7\u4e1a\u94fe\u626b\u63cf", "\u4e00\u3001\u4e3b\u9898\u5b9a\u4f4d", "\u4e8c\u3001\u4ea7\u4e1a\u94fe\u62c6\u89e3", "\u4e09\u3001\u74f6\u9888\u5224\u65ad", "\u56db\u3001\u4f18\u5148\u7814\u7a76\u6e05\u5355", "\u4e94\u3001\u4e0b\u4e00\u6b65\u68c0\u67e5\u6e05\u5355"]
    for i, e in enumerate(exp):
        assert e in hs[i], f"Header {i}: expected {e}, got {hs[i]}"

def test_includes_topic():
    d = _load(); md = ReportBuilder().build(d)
    assert "\u4ea7\u4e1a\u94fe\u626b\u63cf\uff1aAI \u534a\u5bfc\u4f53" in md

def test_empty_no_crash():
    md = ReportBuilder().build({"topic": "t", "summary": {}, "layers": [], "candidates": []})
    assert md

def test_section_order():
    d = _load(); md = ReportBuilder().build(d)
    ks = ["\u4e00\u3001\u4e3b\u9898\u5b9a\u4f4d", "\u4e8c\u3001\u4ea7\u4e1a\u94fe\u62c6\u89e3", "\u4e09\u3001\u74f6\u9888\u5224\u65ad", "\u56db\u3001\u4f18\u5148\u7814\u7a76\u6e05\u5355", "\u4e94\u3001\u4e0b\u4e00\u6b65\u68c0\u67e5\u6e05\u5355"]
    is_ = [md.index(k) for k in ks]
    for i in range(len(is_) - 1):
        assert is_[i] < is_[i + 1], "Section order broken"
