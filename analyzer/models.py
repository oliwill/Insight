"""
分析器注册表 - 工厂函数
"""
from .base import BaseAnalyzer
from .fundamental import FundamentalAnalyzer
from .wyckoff import WyckoffAnalyzer
from .comprehensive import ComprehensiveAnalyzer
from .dow_channel import DowChannelAnalyzer
from .force_balance import ForceBalanceAnalyzer
from .multi_timeframe import MultiTimeframeAnalyzer
from .volume_profile import VolumeProfileAnalyzer


# 分析器注册表
ANALYZER_REGISTRY = {
    "fundamental": FundamentalAnalyzer,
    "wyckoff": WyckoffAnalyzer,
    "dow_channel": DowChannelAnalyzer,
    "volume_profile": VolumeProfileAnalyzer,
    "multi_timeframe": MultiTimeframeAnalyzer,
    "force_balance": ForceBalanceAnalyzer,
    "comprehensive": ComprehensiveAnalyzer,
}


def get_analyzer(name: str) -> BaseAnalyzer:
    """获取分析器实例"""
    if name in ANALYZER_REGISTRY:
        return ANALYZER_REGISTRY[name]()
    return ComprehensiveAnalyzer()


def list_analyzers() -> list:
    """列出可用分析器"""
    return [
        {"key": k, "name": v().name, "description": v().description}
        for k, v in ANALYZER_REGISTRY.items()
    ]
