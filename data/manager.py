"""
数据管理器 - 统一数据接入层
数据源: 长桥API (美股/港股) + Yahoo Finance (备用/基本面)
"""

import os
import sys
import io
import json
import shutil
import subprocess
from pathlib import Path
import pandas as pd
from typing import Any, List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from contextlib import contextmanager

import yfinance as yf
from loguru import logger

# Load .env on import so DataManager picks up credentials without an explicit
# load_dotenv() call in the caller (mirrors the master CLI contract).
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv is optional; callers without it must set env vars themselves.
    pass


def _configure_yfinance_cache(cache_dir: Optional[Path] = None) -> Optional[Path]:
    """Direct yfinance's SQLite caches to a project-writable location.

    In sandboxed/portable Windows environments yfinance's per-user cache directory
    may not be writable.  The cache must be configured before a ticker is fetched;
    keeping it under ``tmp_analysis`` also ensures it remains generated local state.
    """
    raw_dir = cache_dir or os.getenv("YFINANCE_CACHE_DIR")
    target = (
        Path(raw_dir).expanduser()
        if raw_dir
        else Path(__file__).resolve().parents[1] / "tmp_analysis" / "yfinance_cache"
    )
    try:
        target.mkdir(parents=True, exist_ok=True)
        cache_module = getattr(yf, "cache", None)
        setter = getattr(cache_module, "set_cache_location", None)
        if not callable(setter):
            logger.warning(
                "yfinance cache configuration API is unavailable; using its default cache path"
            )
            return None
        setter(str(target))
        return target
    except OSError as exc:
        logger.warning(f"Unable to configure yfinance cache at {target}: {exc}")
        return None


YFINANCE_CACHE_DIR = _configure_yfinance_cache()


@contextmanager
def suppress_stdout():
    """Context manager to suppress stdout (for Longbridge SDK debug output)"""
    old_stdout = sys.stdout
    old_stdout_fd = None
    saved_stdout_fd = None
    devnull_fd = None

    try:
        try:
            old_stdout_fd = old_stdout.fileno()
        except (AttributeError, io.UnsupportedOperation, OSError):
            old_stdout_fd = None

        if old_stdout_fd is not None:
            old_stdout.flush()
            saved_stdout_fd = os.dup(old_stdout_fd)
            devnull_fd = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull_fd, old_stdout_fd)
        # Also redirect Python's sys.stdout
        sys.stdout = io.StringIO()
        yield
    finally:
        if saved_stdout_fd is not None and old_stdout_fd is not None:
            os.dup2(saved_stdout_fd, old_stdout_fd)
            os.close(saved_stdout_fd)
        if devnull_fd is not None:
            os.close(devnull_fd)
        # Restore Python's sys.stdout after the file descriptor is restored.
        sys.stdout = old_stdout


# 长桥SDK - lazy import to avoid debug output during module load
LONGBRIDGE_AVAILABLE = False
Config = None
QuoteContext = None
AdjustType = None
Period = None


def _import_longbridge():
    """Lazy import Longbridge SDK with stdout suppression"""
    global LONGBRIDGE_AVAILABLE, Config, QuoteContext, AdjustType, Period
    if Config is not None:  # Already imported
        return

    try:
        with suppress_stdout():
            from longbridge.openapi import (
                Config as _Config,
                QuoteContext as _QuoteContext,
                AdjustType as _AdjustType,
                Period as _Period,
            )
        Config = _Config
        QuoteContext = _QuoteContext
        AdjustType = _AdjustType
        Period = _Period
        LONGBRIDGE_AVAILABLE = True
    except ImportError as e:
        LONGBRIDGE_AVAILABLE = False
        logger.warning(
            f"longbridge SDK not installed ({e}), falling back to Yahoo Finance"
        )


@dataclass
class StockInfo:
    """股票信息"""

    code: str
    name: str
    market: str  # 'US' | 'HK'
    price: float = 0.0
    change_pct: float = 0.0
    currency: str = "USD"
    sector: str = ""
    industry: str = ""


@dataclass
class DataSourceAttempt:
    """Single data source attempt for an operation."""

    operation: str
    source: str
    status: str
    detail: str = ""
    rows: int = 0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "source": self.source,
            "status": self.status,
            "detail": self.detail,
            "rows": self.rows,
            "timestamp": self.timestamp,
        }


class LongBridgeClient:
    """长桥API客户端

    两条数据通道，均复用同一对外接口（get_quote/get_history/get_static_info）：
      1. SDK 通道：.env 三件套 → Config.from_apikey + QuoteContext（更快，无 subprocess 开销）
      2. CLI 通道：longbridge CLI 的 OAuth token（`longbridge auth login` 登录后存于本地）
         适用于 SDK 三件套缺失/失效，或需要 CLI 独有覆盖（如 A 股基金 LOF/ETF）的场景。

    每个查询方法内部 SDK 优先，SDK 不可用或失败时自动降级到 CLI。is_available() 在
    任一通道可用时即返回 True，保证鸭子类型调用方（DataManager）无需感知底层差异。
    """

    # subprocess 超时（秒）。quote/static 很快；kline 历史可能稍慢，调用处可覆盖。
    _CLI_TIMEOUT = 20

    def __init__(self):
        self.quote_ctx = None
        self._cli_bin: Optional[str] = None  # longbridge 可执行文件路径，None=未找到
        self._cli_checked: bool = False  # 是否已完成 CLI 探活
        self._init_client()
        self._init_cli()

    def _init_client(self):
        # Lazy import to suppress debug output
        _import_longbridge()
        if not LONGBRIDGE_AVAILABLE:
            return
        try:
            app_key = os.getenv("LONGBRIDGE_APP_KEY")
            app_secret = os.getenv("LONGBRIDGE_APP_SECRET")
            access_token = os.getenv("LONGBRIDGE_ACCESS_TOKEN")

            if all([app_key, app_secret, access_token]):
                # Suppress stdout during Longbridge SDK initialization
                # to prevent debug tables from corrupting JSON output
                with suppress_stdout():
                    config = Config.from_apikey(app_key, app_secret, access_token)
                    self.quote_ctx = QuoteContext(config)
                logger.info("Longbridge API initialized")
            else:
                logger.warning("Longbridge credentials incomplete")
        except Exception as e:
            logger.error(f"Longbridge init failed: {e}")
            self.quote_ctx = None

    # ---------- CLI 通道 ----------

    def _init_cli(self) -> None:
        """探活 longbridge CLI：定位可执行文件即可，不在此发起网络请求。

        真正的认证/可用性在首次实际查询时由 CLI 自身处理（token 过期会自动 refresh）。
        这样避免每次实例化都产生 subprocess + 网络开销。
        """
        if self._cli_checked:
            return
        self._cli_checked = True
        self._cli_bin = shutil.which("longbridge")
        if self._cli_bin:
            logger.info("Longbridge CLI available (OAuth token fallback enabled)")
        else:
            logger.debug("Longbridge CLI not found on PATH; SDK-only mode")

    def is_available(self) -> bool:
        return self.quote_ctx is not None or self._cli_bin is not None

    # ---------- CLI 底层辅助 ----------

    @staticmethod
    def _cli_symbol(symbol: str) -> str:
        """内部长桥代码 → CLI 代码格式。

        SDK/内部: SH603906 / SZ161725 / AAPL.US / 00700.HK
        CLI     : 603906.SH / 161725.SZ / AAPL.US / 00700.HK
        （仅 A 股的 SH/SZ 前缀需要反转后缀；US/HK 两种格式一致）
        """
        if symbol.startswith("SH"):
            return f"{symbol[2:]}.SH"
        if symbol.startswith("SZ"):
            return f"{symbol[2:]}.SZ"
        return symbol

    def _cli_call(
        self, args: List[str], timeout: Optional[int] = None
    ) -> Optional[Any]:
        """执行 longbridge CLI 子命令，返回解析后的 JSON。

        - 复用 CLI 已登录的 OAuth token（无需三件套）。
        - 任何失败（未安装/超时/非零退出/解析失败）都返回 None 并记录日志，由调用方降级。
        - 强制 --format json，stderr 丢弃（CLI 可能在 stderr 打印更新提示等噪声）。
        """
        if not self._cli_bin:
            return None
        cmd = [self._cli_bin, *args, "--format", "json"]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self._CLI_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"Longbridge CLI timeout: {' '.join(args)}")
            return None
        except Exception as e:
            logger.warning(f"Longbridge CLI exec failed: {e}")
            return None
        if proc.returncode != 0:
            # 非零退出：可能是认证过期、符号无效、权限不足等。stderr 含原因。
            err = (proc.stderr or "").strip()
            logger.warning(
                f"Longbridge CLI nonzero exit for {' '.join(args)}: {err[:200]}"
            )
            return None
        out = (proc.stdout or "").strip()
        if not out:
            return None
        try:
            return json.loads(out)
        except json.JSONDecodeError as e:
            logger.warning(f"Longbridge CLI JSON parse failed: {e}")
            return None

    @staticmethod
    def _to_float(v: Any) -> Optional[float]:
        """CLI 数值字段是字符串；转 float，空/None/'0' 风格按字面处理（0 是合法值）。"""
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(v: Any) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    # ---------- 行情 ----------

    def get_quote(self, symbol: str) -> Optional[Dict]:
        """获取实时行情（SDK 优先，CLI 兜底）"""
        if not self.is_available():
            return None
        # SDK 通道
        if self.quote_ctx is not None:
            try:
                quotes = self.quote_ctx.quote([symbol])
                if quotes:
                    q = quotes[0]
                    change_pct = 0.0
                    if q.prev_close and q.prev_close > 0:
                        change_pct = (q.last_done - q.prev_close) / q.prev_close * 100
                    return {
                        "symbol": q.symbol,
                        "price": q.last_done,
                        "open": q.open,
                        "high": q.high,
                        "low": q.low,
                        "prev_close": q.prev_close,
                        "volume": q.volume,
                        "turnover": q.turnover,
                        "change_pct": round(change_pct, 2),
                        "timestamp": str(q.timestamp),
                    }
            except Exception as e:
                logger.error(f"Longbridge quote failed for {symbol}: {e}")
        # CLI 兜底
        return self._cli_get_quote(symbol)

    def _cli_get_quote(self, symbol: str) -> Optional[Dict]:
        data = self._cli_call(["quote", self._cli_symbol(symbol)])
        if not data or not isinstance(data, list) or not data:
            return None
        q = data[0]
        price = self._to_float(q.get("last"))
        prev_close = self._to_float(q.get("prev_close"))
        change_pct = self._to_float(q.get("change_percentage"))
        if change_pct is None and price and prev_close and prev_close > 0:
            change_pct = round((price - prev_close) / prev_close * 100, 2)
        return {
            "symbol": q.get("symbol", symbol),
            "price": price,
            "open": self._to_float(q.get("open")),
            "high": self._to_float(q.get("high")),
            "low": self._to_float(q.get("low")),
            "prev_close": prev_close,
            "volume": self._to_int(q.get("volume")),
            "turnover": self._to_float(q.get("turnover")),
            "change_pct": change_pct,
            "timestamp": q.get("time"),
        }

    # ---------- 历史K线 ----------

    def get_history(self, symbol: str, days: int = 365) -> Optional[pd.DataFrame]:
        """获取历史K线（前复权；SDK 优先，CLI 兜底）"""
        if not self.is_available():
            return None
        # SDK 通道
        if self.quote_ctx is not None:
            try:
                end = datetime.now()
                start = end - timedelta(days=days)
                candles = self.quote_ctx.history_candlesticks_by_date(
                    symbol=symbol,
                    period=Period.Day,
                    adjust_type=AdjustType.ForwardAdjust,
                    start=start,
                    end=end,
                )
                if candles:
                    df = pd.DataFrame(
                        [
                            {
                                "date": c.timestamp,
                                "open": c.open,
                                "high": c.high,
                                "low": c.low,
                                "close": c.close,
                                "volume": c.volume,
                            }
                            for c in candles
                        ]
                    )
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception as e:
                logger.error(f"Longbridge history failed for {symbol}: {e}")
        # CLI 兜底
        return self._cli_get_history(symbol, days)

    def _cli_get_history(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        # CLI count 是根数；按 days 估算，留 20% 余量覆盖周末/假日
        count = max(int(days * 1.2), 30)
        data = self._cli_call(
            [
                "kline",
                self._cli_symbol(symbol),
                "--period",
                "day",
                "--count",
                str(count),
                "--adjust",
                "forward",
            ],
            timeout=30,
        )
        if not data or not isinstance(data, list) or not data:
            return None
        rows = []
        for c in data:
            if not c.get("time"):
                continue
            rows.append(
                {
                    "date": c.get("time"),
                    "open": self._to_float(c.get("open")),
                    "high": self._to_float(c.get("high")),
                    "low": self._to_float(c.get("low")),
                    "close": self._to_float(c.get("close")),
                    "volume": self._to_int(c.get("volume")),
                }
            )
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        # CLI 的 time 字段带时区（如 ...T16:00:00Z）；SDK 返回 tz-naive。
        # 统一去掉时区，与 SDK 通道及下游（如 wyckoff_chart）保持一致。
        try:
            if getattr(df["date"].dt, "tz", None) is not None:
                df["date"] = df["date"].dt.tz_localize(None)
        except Exception:
            pass
        df = df.sort_values("date").reset_index(drop=True)
        # 截断到请求的 days 窗口（CLI 按 count 返回，可能略多）
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df["date"] >= pd.Timestamp(cutoff)].reset_index(drop=True)
        return df

    # ---------- 静态信息 ----------

    def get_static_info(self, symbol: str) -> Optional[Dict]:
        """获取股票静态信息（名称、行业等；SDK 优先，CLI 兜底）"""
        if not self.is_available():
            return None
        # SDK 通道
        if self.quote_ctx is not None:
            try:
                infos = self.quote_ctx.static_info([symbol])
                if infos:
                    s = infos[0]
                    return {
                        "symbol": s.symbol,
                        "name_cn": s.name_cn,
                        "name_en": s.name_en,
                        "exchange": str(s.exchange),
                        "currency": s.currency,
                        "lot_size": s.lot_size,
                        "total_shares": s.total_shares,
                        "circulating_shares": s.circulating_shares,
                        "eps": s.eps,
                        "bps": s.bps,
                        "dividend_yield": s.dividend_yield,
                    }
            except Exception as e:
                logger.error(f"Longbridge static_info failed for {symbol}: {e}")
        # CLI 兜底
        return self._cli_get_static_info(symbol)

    def _cli_get_static_info(self, symbol: str) -> Optional[Dict]:
        data = self._cli_call(["static", self._cli_symbol(symbol)])
        if not data or not isinstance(data, list) or not data:
            return None
        s = data[0]
        # CLI static 的 `dividend` 字段是"每股股息(元)"，非股息率百分比。
        # 用 calc-index 的 dps_rate 拿真实股息率；失败则用 quote 现价反推。
        dividend_yield = self._cli_dividend_yield(symbol)
        return {
            "symbol": s.get("symbol", symbol),
            "name_cn": s.get("name"),
            "name_en": s.get("name_en") or s.get("name"),
            "exchange": s.get("exchange"),
            "currency": s.get("currency"),
            "lot_size": self._to_int(s.get("lot_size")),
            "total_shares": self._to_int(s.get("total_shares")),
            # CLI 字段缩写：circ._shares
            "circulating_shares": self._to_int(
                s.get("circ._shares") or s.get("circulating_shares")
            ),
            "eps": self._to_float(s.get("eps_ttm") or s.get("eps")),
            "bps": self._to_float(s.get("bps")),
            "dividend_yield": dividend_yield,
        }

    def _cli_dividend_yield(self, symbol: str) -> Optional[float]:
        """通过 calc-index dps_rate 取真实股息率（百分比）。失败返回 None。

        calc-index 的 dps_rate 与现价反算一致（如茅台 3.82），
        优于 static.dividend（那只是每股股息元值，会被误当成百分比）。
        """
        data = self._cli_call(
            ["calc-index", self._cli_symbol(symbol), "--fields", "dps_rate"]
        )
        if not data or not isinstance(data, list) or not data:
            return None
        return self._to_float(data[0].get("dps_rate"))


class DataManager:
    """数据管理器 - 长桥API优先，Yahoo Finance备用"""

    def __init__(
        self, longbridge_client: Optional[LongBridgeClient] = None, yahoo_factory=None
    ):
        self.longbridge = (
            longbridge_client if longbridge_client is not None else LongBridgeClient()
        )
        self.yahoo_factory = yahoo_factory or yf.Ticker
        self._source_attempts: Dict[str, List[DataSourceAttempt]] = {}
        logger.info("DataManager initialized")

    def _record_source_attempt(
        self,
        operation: str,
        source: str,
        status: str,
        detail: str = "",
        rows: int = 0,
    ) -> None:
        attempt = DataSourceAttempt(
            operation=operation,
            source=source,
            status=status,
            detail=detail,
            rows=rows,
            timestamp=datetime.now().isoformat(timespec="seconds"),
        )
        self._source_attempts.setdefault(operation, []).append(attempt)

    def get_source_status(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return structured data-source attempts for diagnostics and report gaps."""
        return {
            operation: [attempt.to_dict() for attempt in attempts]
            for operation, attempts in self._source_attempts.items()
        }

    def _get_yf_ticker(self, symbol: str):
        return self.yahoo_factory(self._yf_symbol(symbol))

    # ---------- 符号处理 ----------

    @staticmethod
    def normalize_symbol(code: str) -> str:
        """
        标准化股票代码
        长桥格式: 美股 AAPL.US  港股 00700.HK / 02600.HK  A股 SH603906 / SZ000001
        输入兼容: 603906 / SH603906 / sh603906 / 600000.SH / 000001.SZ / SZ000001
        """
        code = code.strip().upper()
        # 已经是长桥格式
        if code.endswith(".US") or code.endswith(".HK"):
            return code
        if code.endswith(".SH"):
            return f"SH{code[:-3]}"
        if code.endswith(".SZ"):
            return f"SZ{code[:-3]}"
        # A股: SH/SZ 前缀（长桥格式）
        if code.startswith("SH") or code.startswith("SZ"):
            return code
        # 纯数字 → 判断市场
        if code.isdigit():
            num = int(code)
            # 港股5位: 00001-99999
            if 1 <= num <= 99999 and len(code) == 5:
                return f"{code}.HK"
            # A股: 沪市6开头, 深市0/3开头
            if len(code) == 6:
                if code.startswith("6"):
                    return f"SH{code}"
                else:
                    return f"SZ{code}"
            # 其他数字当港股处理
            return f"{code}.HK"
        # 纯字母 → 美股
        if code.isalpha():
            return f"{code}.US"
        return code

    @staticmethod
    def detect_market(symbol: str) -> str:
        if symbol.endswith(".HK"):
            return "HK"
        if symbol.startswith("SH") or symbol.startswith("SZ"):
            return "CN"
        return "US"

    # ---------- 对外接口 ----------

    def search_stocks(self, query: str, limit: int = 10) -> list:
        """搜索股票"""
        results = []

        # 尝试把输入当作代码直接查
        symbol = self.normalize_symbol(query)

        # 长桥: 获取静态信息
        if self.longbridge.is_available():
            static = self.longbridge.get_static_info(symbol)
            if static:
                quote = self.longbridge.get_quote(symbol)
                results.append(
                    {
                        "code": symbol,
                        "name": static.get("name_cn")
                        or static.get("name_en")
                        or symbol,
                        "market": "港股"
                        if self.detect_market(symbol) == "HK"
                        else "美股",
                        "price": quote["price"] if quote else 0,
                    }
                )

        # Yahoo Finance 备用（美股用不带 .US 的代码）
        if not results:
            try:
                ticker = self._get_yf_ticker(symbol)
                info = ticker.info
                name = info.get("shortName") or info.get("longName") or symbol
                if name and name != symbol:
                    results.append(
                        {
                            "code": symbol,
                            "name": name,
                            "market": "港股"
                            if self.detect_market(symbol) == "HK"
                            else "美股",
                            "price": info.get("regularMarketPrice", 0),
                        }
                    )
            except Exception:
                pass

        return results[:limit]

    def get_stock_info(self, code: str) -> StockInfo:
        """获取股票详情"""
        symbol = self.normalize_symbol(code)
        market = self.detect_market(symbol)

        # 长桥
        if self.longbridge.is_available():
            quote = self.longbridge.get_quote(symbol)
            static = self.longbridge.get_static_info(symbol)
            if quote:
                self._record_source_attempt("stock_info", "longbridge", "ok", rows=1)
                return StockInfo(
                    code=symbol,
                    name=static.get("name_cn", "") if static else symbol,
                    market=market,
                    price=quote["price"],
                    change_pct=quote["change_pct"],
                    currency={"HK": "HKD", "CN": "CNY"}.get(market, "USD"),
                )
            self._record_source_attempt(
                "stock_info", "longbridge", "failed", "empty_or_failed"
            )
        else:
            self._record_source_attempt("stock_info", "longbridge", "unavailable")

        # 备用 Yahoo Finance
        info = self._get_yf_stock_info(symbol)
        status = "ok" if info and info.name != "Unknown" else "failed"
        detail = "" if status == "ok" else "empty_or_failed"
        self._record_source_attempt(
            "stock_info", "yahoo", status, detail, rows=1 if status == "ok" else 0
        )
        return info

    @staticmethod
    def _cn_volume_to_shares(
        df: Optional[pd.DataFrame], symbol: str
    ) -> Optional[pd.DataFrame]:
        """A 股行情数据源的成交量按「手」(1手=100股) 返回，统一为股。

        交易所原始数据（Yahoo 与 Longbridge 均透传）对 SH/SZ 标的的 volume 字段是
        手数，与美股/港股的「股」不一致；下游（成交额、换手率、流动性）按股计算，
        故在此数据边界归一。US/HK 不受影响。
        """
        if df is None or df.empty or "volume" not in df.columns:
            return df
        if symbol.startswith("SH") or symbol.startswith("SZ"):
            df = df.copy()
            df["volume"] = df["volume"] * 100
        return df

    def get_historical_data(
        self, code: str, period: str = "1y"
    ) -> Optional[pd.DataFrame]:
        """获取历史行情（A 股成交量统一为股）"""
        symbol = self.normalize_symbol(code)
        days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "3y": 1095}
        days = days_map.get(period, 365)

        # 长桥
        if self.longbridge.is_available():
            df = self.longbridge.get_history(symbol, days)
            if df is not None and not df.empty:
                self._record_source_attempt(
                    "historical_data", "longbridge", "ok", rows=len(df)
                )
                return self._cn_volume_to_shares(df, symbol)
            self._record_source_attempt(
                "historical_data", "longbridge", "failed", "empty_or_failed"
            )
        else:
            self._record_source_attempt("historical_data", "longbridge", "unavailable")

        # 备用 Yahoo Finance
        df = self._get_yf_history(symbol, period)
        if df is not None and not df.empty:
            self._record_source_attempt("historical_data", "yahoo", "ok", rows=len(df))
            return self._cn_volume_to_shares(df, symbol)
        self._record_source_attempt(
            "historical_data", "yahoo", "failed", "empty_or_failed"
        )
        return self._cn_volume_to_shares(df, symbol)

    def get_fundamentals(self, code: str) -> Dict:
        """获取基本面数据：长桥 static_info 优先算 PE/PB，YF 补充其余字段"""
        symbol = self.normalize_symbol(code)
        result = {}

        # ===== 1. 长桥 static_info：拿 EPS/BPS/股本，自己算 PE/PB =====
        lb_data = {}
        if self.longbridge.is_available():
            static = self.longbridge.get_static_info(symbol)
            quote = self.longbridge.get_quote(symbol)
            if static:
                self._record_source_attempt("fundamentals", "longbridge", "ok", rows=1)
                lb_data["eps"] = static.get("eps")
                lb_data["bps"] = static.get("bps")
                lb_data["total_shares"] = static.get("total_shares")
                lb_data["circulating_shares"] = static.get("circulating_shares")
                lb_data["dividend_yield"] = static.get("dividend_yield")
                lb_data["lot_size"] = static.get("lot_size")
                lb_data["name_cn"] = static.get("name_cn")
                lb_data["name_en"] = static.get("name_en")

                # 用长桥数据算 PE/PB（比 YF 更可靠，覆盖港股新股）
                price = None
                if quote and quote.get("price"):
                    price = float(quote["price"])
                eps = lb_data.get("eps")
                bps = lb_data.get("bps")
                if price and eps and float(eps) != 0:
                    result["pe_ttm"] = round(price / float(eps), 2)
                if price and bps and float(bps) != 0:
                    result["pb"] = round(price / float(bps), 2)
                if lb_data.get("total_shares") and price:
                    result["market_cap"] = round(
                        float(lb_data["total_shares"]) * price, 2
                    )
                if lb_data.get("dividend_yield") is not None:
                    result["dividend_yield"] = lb_data["dividend_yield"]
                if lb_data.get("total_shares"):
                    result["total_shares"] = lb_data["total_shares"]
                if lb_data.get("circulating_shares"):
                    result["circulating_shares"] = lb_data["circulating_shares"]
            else:
                self._record_source_attempt(
                    "fundamentals", "longbridge", "failed", "empty_or_failed"
                )
        else:
            self._record_source_attempt("fundamentals", "longbridge", "unavailable")

        # ===== 2. Yahoo Finance：补充毛利率/营收增长/行业/业务描述等 =====
        try:
            ticker = self._get_yf_ticker(symbol)
            info = ticker.info

            # YF 有值且长桥没算出来的字段，用 YF 补
            yf_fields = {
                "pe_ttm": "trailingPE",
                "pe_forward": "forwardPE",
                "pb": "priceToBook",
                "ps": "priceToSalesTrailing12Months",
                "ev_ebitda": "enterpriseToEbitda",
                "roe": "returnOnEquity",
                "roa": "returnOnAssets",
                "gross_margin": "grossMargins",
                "operating_margin": "operatingMargins",
                "profit_margin": "profitMargins",
                "revenue_growth": "revenueGrowth",
                "earnings_growth": "earningsGrowth",
                "current_ratio": "currentRatio",
                "debt_equity": "debtToEquity",
                "total_cash": "totalCash",
                "total_debt": "totalDebt",
                "free_cashflow": "freeCashflow",
                "market_cap": "marketCap",
                "sector": "sector",
                "industry": "industry",
                "employees": "fullTimeEmployees",
                "business_summary": "longBusinessSummary",
                # 分析师目标价 (yfinance-data skill)
                "target_mean_price": "targetMeanPrice",
                "target_high_price": "targetHighPrice",
                "target_low_price": "targetLowPrice",
                "analyst_count": "numberOfAnalystOpinions",
                "recommendation_key": "recommendationKey",
                "recommendation_mean": "recommendationMean",
            }
            for key, yf_key in yf_fields.items():
                val = info.get(yf_key)
                # 长桥已算出的 PE/PB 不覆盖，其余字段 YF 有值就补
                if key in result:
                    continue
                if val is not None:
                    result[key] = val
            if info:
                self._record_source_attempt("fundamentals", "yahoo", "ok", rows=1)
            else:
                self._record_source_attempt(
                    "fundamentals", "yahoo", "failed", "empty_or_failed"
                )
        except Exception as e:
            logger.warning(f"YF fundamentals fallback failed for {symbol}: {e}")
            self._record_source_attempt("fundamentals", "yahoo", "failed", str(e))

        return result

    # ---------- Yahoo Finance 备用 ----------

    @staticmethod
    def _yf_symbol(symbol: str) -> str:
        """长桥代码转 YF 代码"""
        # 美股: AAPL.US → AAPL
        if symbol.endswith(".US"):
            return symbol.replace(".US", "")
        # 港股: 长桥保留 5 位代码；Yahoo Finance 去掉前导 0
        if symbol.endswith(".HK"):
            return f"{symbol[:-3][-4:]}.HK"
        # A股: SH603906 → 603906.SS, SZ000001 → 000001.SZ
        if symbol.startswith("SH"):
            return symbol[2:] + ".SS"
        if symbol.startswith("SZ"):
            return symbol[2:] + ".SZ"
        return symbol

    def _get_yf_stock_info(self, symbol: str) -> StockInfo:
        try:
            ticker = self._get_yf_ticker(symbol)
            info = ticker.info
            market = self.detect_market(symbol)
            return StockInfo(
                code=symbol,
                name=info.get("shortName", symbol),
                market=market,
                price=info.get("regularMarketPrice", 0),
                change_pct=info.get("regularMarketChangePercent", 0),
                currency={"HK": "HKD", "CN": "CNY"}.get(market, "USD"),
                sector=info.get("sector", ""),
                industry=info.get("industry", ""),
            )
        except Exception as e:
            logger.error(f"YF stock info failed: {e}")
            return StockInfo(code=symbol, name="Unknown", market="US")

    def _get_yf_history(self, symbol: str, period: str) -> Optional[pd.DataFrame]:
        try:
            ticker = self._get_yf_ticker(symbol)
            df = ticker.history(period=period)
            df = df.reset_index()
            df.columns = [
                c.lower().replace(" ", "_").replace(".", "_") for c in df.columns
            ]
            return df
        except Exception as e:
            logger.error(f"YF history failed: {e}")
            return None
