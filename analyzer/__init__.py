__all__ = [
    "BaseAnalyzer",
    "AnalysisResult",
    "FundamentalAnalyzer",
    "WyckoffAnalyzer",
    "ComprehensiveAnalyzer",
    "WyckoffStructure",
    "MarketPhase",
    "WyckoffEvent",
    "get_analyzer",
    "list_analyzers",
    "ResearchScoreEngine",
    "ResearchScore",
    "ResearchDimensionScore",
    "TimingEngine",
    "TimingState",
]


def __getattr__(name):
    if name in {"BaseAnalyzer", "AnalysisResult"}:
        from .base import BaseAnalyzer, AnalysisResult
        return {"BaseAnalyzer": BaseAnalyzer, "AnalysisResult": AnalysisResult}[name]
    if name == "FundamentalAnalyzer":
        from .fundamental import FundamentalAnalyzer
        return FundamentalAnalyzer
    if name in {"WyckoffAnalyzer", "WyckoffStructure", "MarketPhase", "WyckoffEvent"}:
        from .wyckoff import WyckoffAnalyzer, WyckoffStructure, MarketPhase, WyckoffEvent
        return {
            "WyckoffAnalyzer": WyckoffAnalyzer,
            "WyckoffStructure": WyckoffStructure,
            "MarketPhase": MarketPhase,
            "WyckoffEvent": WyckoffEvent,
        }[name]
    if name == "ComprehensiveAnalyzer":
        from .comprehensive import ComprehensiveAnalyzer
        return ComprehensiveAnalyzer
    if name in {"get_analyzer", "list_analyzers"}:
        from .models import get_analyzer, list_analyzers
        return {"get_analyzer": get_analyzer, "list_analyzers": list_analyzers}[name]
    if name in {"ResearchScoreEngine", "ResearchScore", "ResearchDimensionScore"}:
        from .research_score import ResearchScoreEngine, ResearchScore, ResearchDimensionScore
        return {
            "ResearchScoreEngine": ResearchScoreEngine,
            "ResearchScore": ResearchScore,
            "ResearchDimensionScore": ResearchDimensionScore,
        }[name]
    if name in {"TimingEngine", "TimingState"}:
        from .timing_engine import TimingEngine, TimingState
        return {"TimingEngine": TimingEngine, "TimingState": TimingState}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
