"""
技术指标常量配置

集中管理所有技术指标的参数，避免 magic numbers 散落在代码中
"""
from typing import List


# ========== 移动平均线周期 ==========
MA_PERIODS: List[int] = [5, 10, 20, 50, 120, 200]

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
VOLUME_SHORT_PERIOD: int = 5   # 短期成交量周期
VOLUME_MID_PERIOD: int = 20    # 中期成交量周期

# ========== 支撑/阻力参数 ==========
SUPPORT_RESISTANCE_PERIOD: int = 20  # 用于计算 20 日支撑/阻力

# ========== 近期交易日数 ==========
RECENT_TRADING_DAYS: int = 5

# ========== Wyckoff 分析最小数据量 ==========
WYCKOFF_MIN_ROWS: int = 100

# ========== 成交量语言 (VolumeProfileAnalyzer) ==========
VOLUME_SPIKE_MULTIPLIER: float = 3.0       # 爆冲巨量判定：单日量 ≥ N × 20日均量
FLAT_VOLUME_RATIO_MIN: float = 0.6         # 平量推升：量比下限
FLAT_VOLUME_RATIO_MAX: float = 1.2         # 平量推升：量比上限
FLAT_VOLUME_GAIN_THRESHOLD: float = 3.0    # 平量推升：20日涨幅下限 (%)
PRICE_VOL_CORR_LOOKBACK: int = 20          # 量价相关系数回看窗口

# ========== 道氏通道 (DowChannelAnalyzer) ==========
CHANNEL_LOOKBACK_DAYS: int = 120           # 通道拟合回看天数
CHANNEL_SLOPE_RECENT_DAYS: int = 30        # 近期斜率窗口
CHANNEL_SLOPE_BASELINE_DAYS: int = 90      # 基线斜率窗口
CHANNEL_SLOPE_SLOWDOWN_THRESHOLD: float = 0.4  # 斜率趋缓阈值 (降幅 > 此值 → 扶老太太下楼)
CHANNEL_RUBBING_LOOKBACK: int = 10         # 摩擦检测回看天数
CHANNEL_RUBBING_MIN_TOUCHES: int = 3       # 摩擦最少触碰次数
CHANNEL_RANGE_RATIO_THRESHOLD: float = 0.25  # 横盘判定：区间/均价 < 此值

# ========== 多时间框架 (MultiTimeframeAnalyzer) ==========
MTF_WEEKLY_MA: int = 10                    # 周线 MA 周期
MTF_MONTHLY_MA: int = 6                    # 月线 MA 周期（月线数据点少，用 6 而非 20）
MTF_MIN_MONTHLY_ROWS: int = 6             # 月线最少数据点

# ========== 多空博弈 (ForceBalanceAnalyzer) ==========
FORCE_LONG_SHADOW_RATIO: float = 1.5       # 长下影线：影线 > N × 实体
FORCE_UPPER_SHADOW_RATIO: float = 1.5      # 长上影线：影线 > N × 实体
FORCE_LIMIT_UP_THRESHOLD: float = 9.5      # 涨停近似阈值 (%)
FORCE_SMALL_CAP_THRESHOLD: float = 5e9     # 小市值阈值（低于此值更易抢帽子）
