"""
技术指标常量配置

集中管理所有技术指标的参数，避免 magic numbers 散落在代码中
"""

from typing import Optional


def normalize_growth_rate(value) -> float | None:
    """将营收/盈利增速统一为百分比（%）返回。

    当前基本面数据流中，营收/盈利增速唯一来源是 Yahoo Finance（小数制：
    0.85 = +85%，13.685 = +1368.5%），故一律 ×100。若未来接入百分比制数据源
    （如 akshare），须在其数据源边界归一，勿在此猜测单位。
    |v| > 500（>50000%，疑似源错误）或无法解析 → None。
    """
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if abs(v) > 500:
        return None
    return v * 100


def normalize_margin_ratio(value) -> float | None:
    """将比率（毛利率/ROE/净利率等）统一为百分比（%）返回。

    与 normalize_growth_rate（恒 ×100，Yahoo 小数制契约）不同，本函数用于
    口径来源可能混杂的展示层：|v| ≤ 1.5 视为小数制 ×100，否则按已是百分比原样。
    """
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v * 100 if abs(v) <= 1.5 else v


# ========== 增速异常护栏 ==========
GROWTH_ANOMALY_PCT: float = (
    150.0  # |增速%| 超此值视为可疑数据，评分降权（大型股 YoY 现实上界）
)


# ========== 移动平均线周期 ==========
MA_PERIODS: list[int] = [5, 10, 20, 50, 120, 200]

# ========== RSI 参数 ==========
RSI_PERIOD: int = 14

# ========== MACD 参数 ==========
MACD_FAST: int = 12
MACD_SLOW: int = 26
MACD_SIGNAL: int = 9

# ========== 布林带参数 ==========
BB_PERIOD: int = 20
BB_STD_DEV: float = 2.0

# ========== KDJ 参数 ==========
KDJ_PERIOD: int = 9
KDJ_K_SMOOTH: int = 2  # ewm com 参数
KDJ_D_SMOOTH: int = 2  # ewm com 参数

# ========== 成交量参数 ==========
VOLUME_SHORT_PERIOD: int = 5  # 短期成交量周期
VOLUME_MID_PERIOD: int = 20  # 中期成交量周期

# ========== 支撑/阻力参数 ==========
SUPPORT_RESISTANCE_PERIOD: int = 20  # 用于计算 20 日支撑/阻力

# ========== 近期交易日数 ==========
RECENT_TRADING_DAYS: int = 5

# ========== Wyckoff 分析最小数据量 ==========
WYCKOFF_MIN_ROWS: int = 100

# ========== 成交量语言 (VolumeProfileAnalyzer) ==========
VOLUME_SPIKE_MULTIPLIER: float = 3.0  # 爆冲巨量判定：单日量 ≥ N × 20日均量
FLAT_VOLUME_RATIO_MIN: float = 0.6  # 平量推升：量比下限
FLAT_VOLUME_RATIO_MAX: float = 1.2  # 平量推升：量比上限
FLAT_VOLUME_GAIN_THRESHOLD: float = 3.0  # 平量推升：20日涨幅下限 (%)
PRICE_VOL_CORR_LOOKBACK: int = 20  # 量价相关系数回看窗口

# ========== 道氏通道 (DowChannelAnalyzer) ==========
CHANNEL_LOOKBACK_DAYS: int = 120  # 通道拟合回看天数
CHANNEL_SLOPE_RECENT_DAYS: int = 30  # 近期斜率窗口
CHANNEL_SLOPE_BASELINE_DAYS: int = 90  # 基线斜率窗口
CHANNEL_SLOPE_SLOWDOWN_THRESHOLD: float = (
    0.4  # 斜率趋缓阈值 (降幅 > 此值 → 扶老太太下楼)
)
CHANNEL_RUBBING_LOOKBACK: int = 10  # 摩擦检测回看天数
CHANNEL_RUBBING_MIN_TOUCHES: int = 3  # 摩擦最少触碰次数
CHANNEL_RANGE_RATIO_THRESHOLD: float = 0.25  # 横盘判定：区间/均价 < 此值

# ========== 多时间框架 (MultiTimeframeAnalyzer) ==========
MTF_WEEKLY_MA: int = 10  # 周线 MA 周期
MTF_MONTHLY_MA: int = 6  # 月线 MA 周期（月线数据点少，用 6 而非 20）
MTF_MIN_MONTHLY_ROWS: int = 6  # 月线最少数据点

# ========== 多空博弈 (ForceBalanceAnalyzer) ==========
FORCE_LONG_SHADOW_RATIO: float = 1.5  # 长下影线：影线 > N × 实体
FORCE_UPPER_SHADOW_RATIO: float = 1.5  # 长上影线：影线 > N × 实体
FORCE_LIMIT_UP_THRESHOLD: float = 9.5  # 涨停近似阈值 (%)
FORCE_SMALL_CAP_THRESHOLD: float = 5e9  # 小市值阈值（低于此值更易抢帽子）

# ========== TimingEngine 阈值（数值与历史一致，集中管理） ==========
# RSI
TIMING_RSI_HEALTHY_MIN: float = 40.0
TIMING_RSI_HEALTHY_MAX: float = 65.0
TIMING_RSI_OVERHEAT: float = 75.0
TIMING_RSI_OVERSOLD: float = 30.0
# 量比
TIMING_VOL_RATIO_MIN: float = 0.7
TIMING_VOL_RATIO_MAX: float = 1.5
TIMING_VOL_RATIO_CROWDED: float = 2.0
# Wyckoff 置信度（0-100）
TIMING_WYCKOFF_CONF_HIGH: float = 70.0
TIMING_WYCKOFF_CONF_LOW: float = 45.0
# 道氏通道位置（0-1）
TIMING_CHANNEL_POS_LOW: float = 0.25
TIMING_CHANNEL_POS_HIGH: float = 0.85
# 多空博弈证据强度（0-100）
TIMING_FORCE_ACCUMULATION_MIN: float = 65.0
TIMING_FORCE_CHIP_LOCK_MIN: float = 65.0
TIMING_FORCE_DISTRIBUTION_MIN: float = 70.0
TIMING_FORCE_TRAP_HIGH: float = 70.0
TIMING_FORCE_TRAP_MED: float = 60.0
# 价格质量
TIMING_TARGET_UPSIDE_MIN_PCT: float = 25.0  # 分析师目标价隐含空间加分阈值 (%)
TIMING_MA50_NEAR_MIN_PCT: float = -3.0
TIMING_MA50_NEAR_MAX_PCT: float = 8.0
TIMING_MA50_FAR_PCT: float = 20.0
TIMING_PCT_FROM_HIGH_NEAR: float = -8.0  # 接近区间高位阈值
TIMING_PCT_FROM_HIGH_DIP_MIN: float = -30.0  # 回调甜点区下限
TIMING_PCT_FROM_HIGH_DIP_MAX: float = -10.0  # 回调甜点区上限
# 财报窗口（天）
TIMING_EARNINGS_NEAR_DAYS: int = 10
TIMING_EARNINGS_WINDOW_DAYS: int = 30
# 流动性
TIMING_DOLLAR_VOL_ADEQUATE: float = 50_000_000
TIMING_DOLLAR_VOL_LOW: float = 10_000_000
TIMING_SHORT_PCT_HIGH: float = 20.0  # %
TIMING_SHORT_PCT_ELEVATED: float = 10.0  # %
TIMING_DAYS_TO_COVER_HIGH: float = 5.0
# 情绪
TIMING_REDDIT_CROWDED: int = 5
TIMING_PUT_CALL_BEARISH: float = 2.0
TIMING_PUT_CALL_BULL_MIN: float = 0.5
TIMING_PUT_CALL_BULL_MAX: float = 1.2
# Research 联动与状态分档
TIMING_RESEARCH_HIGH: float = 75.0
TIMING_RESEARCH_LOW: float = 45.0
TIMING_STATE_READY_MIN: int = 75
TIMING_STATE_WAIT_MIN: int = 55
TIMING_STATE_WATCH_MIN: int = 40
TIMING_STATE_RESEARCH_GATE: int = 70  # Research<45 时，时机分≥此值才能 Watch 否则 Avoid
TIMING_STATE_LIQUIDITY_WAIT_BELOW: int = 75  # 有流动性「偏低」风险标记且低于此分 → Wait
