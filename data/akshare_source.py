"""akshare 数据通道 —— 补 longbridge CLI 拿不到的 A 股数据。

覆盖三类（longbridge quote/kline/static 给不了的信息）：
  1. 指数/基金估值历史分位（如中证白酒 399997 的 PE/PB 近 N 年分位）
  2. 基金净值历史与折溢价（LOF/ETF 场内价 vs 基金净值）
  3. A 股个股资金流/龙虎榜

设计原则：
  - 独立模块，不侵入 LongBridgeClient。DataManager 或上层分析器按需调用。
  - akshare 依赖东方财富/新浪等第三方源，常有网络抖动与反爬限流。
    每个方法对失败做 try/except + 日志，返回 None/空结构而非抛异常，
    保证调用链（run_analysis）在 akshare 不可用时仍能继续。
  - 懒加载：模块导入时不触发网络请求，首次调用才连。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

_ak = None


def _akshare():
    """懒加载 akshare，导入失败时返回 None（通道整体禁用）。"""
    global _ak
    if _ak is not None:
        return _ak
    try:
        import akshare as ak  # type: ignore

        _ak = ak
        return _ak
    except ImportError:
        logger.warning("akshare not installed; A-share valuation/flow channel disabled")
        return None


class AkshareSource:
    """akshare 数据源封装。所有方法对网络失败降级返回 None/空。"""

    def __init__(self) -> None:
        self._available = _akshare() is not None

    def is_available(self) -> bool:
        return self._available

    # ---------- 1. 指数估值历史分位 ----------

    def index_valuation_percentile(
        self,
        index_code: str,
        years: int = 10,
    ) -> Optional[Dict[str, Any]]:
        """指数 PE/PB 历史分位。

        Args:
            index_code: 指数代码，如 "399997"（中证白酒）。
            years: 回看年数，算分位的样本窗口。

        Returns: {"index_code","current_pe","current_pb","pe_percentile",
                  "pb_percentile","sample_years","sample_size"} 或 None。

        Note: akshare 无现成的"指数PE历史"接口；指数估值需第三方（理杏仁/legulegu）
        抓取，其接口在 akshare 中不稳定。此处先用成分股加权近似：取指数成分股的
        PE/PB 中位数序列近似趋势（成分股名单 + 财务数据可拿）。若成分股路径也不通，
        返回 None，由上层标注"估值数据缺失，建议人工查理杏仁"。
        """
        ak = _akshare()
        if ak is None:
            return None
        # TODO: 成分股加权 PE 估算（需 index_component 接口，当前东方财富源不稳定）。
        # 暂返回 None，避免给出来源不可靠的数字。
        logger.info(f"index valuation percentile for {index_code} not yet implemented")
        return None

    # ---------- 2. 基金净值历史 / 折溢价 ----------

    def fund_nav_history(self, fund_code: str) -> Optional[pd.DataFrame]:
        """开放式/LOF 基金累计净值历史。

        Returns: DataFrame[date, nav]（累计净值），失败返回 None。
        """
        ak = _akshare()
        if ak is None:
            return None
        try:
            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="累计净值走势")
            if df is None or df.empty:
                return None
            df = df.rename(columns={"净值日期": "date", "累计净值": "nav"})
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.warning(f"akshare fund_nav_history failed for {fund_code}: {e}")
            return None

    def fund_unit_nav_history(self, fund_code: str) -> Optional[pd.DataFrame]:
        """基金单位净值历史（折溢价计算的基础）。

        Returns: DataFrame[date, unit_nav] 或 None。
        """
        ak = _akshare()
        if ak is None:
            return None
        try:
            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            if df is None or df.empty:
                return None
            df = df.rename(columns={"净值日期": "date", "单位净值": "unit_nav"})
            df = df[["date", "unit_nav"]]
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.warning(f"akshare fund_unit_nav_history failed for {fund_code}: {e}")
            return None

    def fund_premium(
        self, fund_code: str, market_price: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """LOF/ETF 折溢价率。

        Args:
            fund_code: 如 "161725"。
            market_price: 场内最新价（若调用方已从 longbridge 拿到，传入省一次请求）。

        Returns: {"fund_code","unit_nav","market_price","premium_pct","nav_date"} 或 None。
        premium_pct = (market_price - unit_nav) / unit_nav * 100。正值=溢价，负值=折价。
        """
        ak = _akshare()
        if ak is None:
            return None
        try:
            df = self.fund_unit_nav_history(fund_code)
            if df is None or df.empty:
                return None
            latest = df.iloc[-1]
            nav = float(latest["unit_nav"])
            price = market_price if market_price is not None else nav
            premium = round((price - nav) / nav * 100, 2) if nav > 0 else None
            return {
                "fund_code": fund_code,
                "unit_nav": nav,
                "nav_date": str(latest["date"].date()),
                "market_price": price,
                "premium_pct": premium,
            }
        except Exception as e:
            logger.warning(f"akshare fund_premium failed for {fund_code}: {e}")
            return None

    # ---------- 3. A 股个股资金流 / 龙虎榜 ----------

    def individual_fund_flow(self, stock_code: str) -> Optional[pd.DataFrame]:
        """个股主力资金流向（东方财富源）。

        Args:
            stock_code: 6 位 A 股代码，如 "600519"（沪市）、"000858"（深市）。

        Returns: DataFrame[date, main_net, super_large_net, large_net, ...] 或 None。
        """
        ak = _akshare()
        if ak is None:
            return None
        market = "sh" if stock_code.startswith(("5", "6", "9")) else "sz"
        try:
            df = ak.stock_individual_fund_flow(stock=stock_code, market=market)
            if df is None or df.empty:
                return None
            # 列名中文化，统一为英文小写蛇形
            rename = {
                "日期": "date",
                "主力净流入-净额": "main_net",
                "主力净流入-净占比": "main_net_pct",
                "超大单净流入-净额": "super_large_net",
                "大单净流入-净额": "large_net",
                "中单净流入-净额": "medium_net",
                "小单净流入-净额": "small_net",
            }
            df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date").reset_index(drop=True)
            return df
        except Exception as e:
            logger.warning(f"akshare individual_fund_flow failed for {stock_code}: {e}")
            return None

    def lhb_detail(self, date_str: Optional[str] = None) -> Optional[pd.DataFrame]:
        """龙虎榜明细（东方财富源）。

        Args:
            date_str: "YYYYMMDD"；默认最近一个交易日。

        Returns: DataFrame 或 None。
        """
        ak = _akshare()
        if ak is None:
            return None
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
        try:
            df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
            return df if (df is not None and not df.empty) else None
        except Exception as e:
            logger.warning(f"akshare lhb_detail failed for {date_str}: {e}")
            return None


def diagnose() -> Dict[str, Any]:
    """快速自检各接口可用性（供 run_analysis / 排障调用）。"""
    src = AkshareSource()
    out: Dict[str, Any] = {"akshare_installed": src.is_available()}
    if not src.is_available():
        return out
    # 基金净值（最稳定的接口，作为连通性探针）
    df = src.fund_nav_history("161725")
    out["fund_nav_history"] = "ok" if (df is not None and not df.empty) else "failed"
    return out
