"""
长桥持仓自动拉取 —— 从真实账户读取持仓，替代硬编码清单。

核心问题：longbridge CLI 启动时会自动加载当前目录的 .env，若其中
LONGBRIDGE_APP_KEY/SECRET/TOKEN 已过期，会盖住本地 OAuth token，
导致 `positions` 报 401003 token expired。

解决：在子进程里改 cwd 到临时目录，绕过 .env 自动加载，
让 CLI 用本地 OAuth 凭据（longbridge auth login 存的那份）。
"""
import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

# 直接运行本文件时，把项目根加入 sys.path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """单个持仓（已归一化）。"""
    symbol: str            # 归一化后的长桥代码，如 MU.US / 0700.HK
    raw_symbol: str        # CLI 原始输出，与 symbol 通常一致
    name: str
    quantity: float
    available: float
    cost_price: float
    currency: str          # USD / HKD
    market: str            # US / HK

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize(symbol: str) -> str:
    """复用 DataManager 的归一化规则，避免循环导入。"""
    from data.manager import DataManager
    return DataManager.normalize_symbol(symbol)


def fetch_positions() -> List[Position]:
    """
    调 longbridge CLI 拉取当前持仓。

    在临时目录里执行，绕过项目 .env 中过期的 SDK token，
    强制 CLI 使用本地 OAuth 凭据（Trade 权限）。

    失败时返回空列表（调用方应 fallback 到硬编码清单）。
    """
    # 关键：在子进程环境里剥掉 SDK 三件套，并改 cwd 绕过 .env 自动加载
    env = {k: v for k, v in os.environ.items()
           if k not in ("LONGBRIDGE_APP_KEY", "LONGBRIDGE_APP_SECRET", "LONGBRIDGE_ACCESS_TOKEN")}

    try:
        with tempfile.TemporaryDirectory() as tmp_cwd:
            result = subprocess.run(
                ["longbridge", "positions", "--format", "json"],
                capture_output=True, text=True, timeout=30,
                env=env, cwd=tmp_cwd,
            )
    except FileNotFoundError:
        logger.warning("longbridge CLI 未安装（command not found）")
        return []
    except subprocess.TimeoutExpired:
        logger.warning("longbridge positions 超时")
        return []

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "not logged in" in stderr or "401003" in stderr or "unauthorized" in stderr.lower():
            logger.warning("longbridge 未登录或 token 过期，请运行 `longbridge auth login`")
        else:
            logger.warning("longbridge positions 失败: %s", stderr[:200])
        return []

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.warning("longbridge positions JSON 解析失败: %s", e)
        return []

    positions: List[Position] = []
    for item in raw:
        try:
            sym_raw = item.get("symbol", "")
            positions.append(Position(
                symbol=_normalize(sym_raw),
                raw_symbol=sym_raw,
                name=item.get("name", ""),
                quantity=float(item.get("quantity", 0) or 0),
                available=float(item.get("available", item.get("available_quantity", 0)) or 0),
                cost_price=float(item.get("cost_price", 0) or 0),
                currency=item.get("currency", ""),
                market=item.get("market", ""),
            ))
        except (ValueError, TypeError) as e:
            logger.warning("解析持仓条目失败 %s: %s", item, e)
            continue

    logger.info("从长桥拉取到 %d 个持仓", len(positions))
    return positions


def get_portfolio_symbols(fallback: Optional[List[str]] = None) -> tuple:
    """
    返回 (symbols, source)。

    优先用长桥实时持仓；拉不到时用 fallback 硬编码清单。
    source ∈ {"longbridge", "fallback"}。
    """
    positions = fetch_positions()
    if positions:
        return [p.symbol for p in positions], "longbridge"
    if fallback:
        logger.warning("长桥持仓拉取失败，退回硬编码清单（%d 只）", len(fallback))
        return list(fallback), "fallback"
    return [], "empty"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    pos = fetch_positions()
    if not pos:
        print("（未拉到持仓，可能未登录或 token 过期）")
    else:
        print(f"共 {len(pos)} 个持仓：")
        for p in pos:
            print(f"  {p.symbol:<10} {p.name:<24} qty={p.quantity:<8} cost={p.cost_price:<10} {p.currency}")
