import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.serenity.bottleneck_scorer import BottleneckScorer

FIXTURE_DIR = Path(__file__).parent / "test_data"

def _load():
    p = FIXTURE_DIR / "ai_semiconductor.json"
    return json.loads(p.read_text(encoding="utf-8"))

def test_score_never_exceeds_ten():
    d = _load(); s = BottleneckScorer()
    s.score_layers(d["layers"])
    for l in d["layers"]: assert 0 <= l["bottleneck_score"] <= 10

def test_top_bottleneck_strong():
    d = _load(); s = BottleneckScorer()
    s.score_layers(d["layers"])
    sc = sorted(d["layers"], key=lambda l: l["bottleneck_score"], reverse=True)
    assert sc[0]["bottleneck_score"] >= 5

def test_score_classify():
    s = BottleneckScorer()
    assert s._classify(8) == "强瓶颈"
    assert s._classify(5) == "中等瓶颈"
    assert s._classify(3) == "弱瓶颈"

def test_candidates_sorted():
    d = _load(); s = BottleneckScorer()
    cs = s.rank_candidates(d["candidates"])
    for i, c in enumerate(cs): assert c["priority"] == i + 1

def test_empty():
    s = BottleneckScorer()
    assert s.score_layers([]) == []
    assert s.rank_candidates([]) == []
