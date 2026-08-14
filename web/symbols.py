"""股票代码规范化与格式校验（web 层）

normalize_symbol 对无法识别的输入原样返回（不抛异常），
web 入口必须用 _VALID 正则兜底，避免把垃圾代码写进自选/任务。
"""
import re

from data.manager import DataManager

# 合法长桥格式：美股 AAPL.US / 港股 00700.HK / A股 SH603906 / SZ000001
_VALID = re.compile(r"^(?:[A-Z]{1,10}\.US|(?:\d{1,5})\.HK|SH\d{6}|SZ\d{6})$")


def normalize_symbol_or_none(symbol: str):
    """规范化股票代码；非法输入返回 None"""
    try:
        norm = DataManager.normalize_symbol(symbol)
    except Exception:
        return None
    if norm and _VALID.match(norm):
        return norm
    return None
