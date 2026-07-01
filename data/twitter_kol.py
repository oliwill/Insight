"""
Twitter / X KOL 观点抓取模块

通过官方 X MCP（xdevplatform/xmcp）或 xurl CLI 抓取：
- 定向关注 KOL（KOL_WATCHLIST）的近期推文
- 按 $TICKER / 公司名的实时讨论

设计原则：
1. 纯只读 — 不发推、不互动、不关注（符合 CLAUDE.md 安全约束）
2. 永不抛异常 — 失败返回空结果，不影响主分析流程（对齐 search_reddit/search_polymarket）
3. 向后兼容 — 无 X 凭据时，has_credentials() 返回 False，管线自动跳过
4. 超时保护 — 复用 Config.ANALYSIS_TIMEOUT

返回 item 字段：
    author, text, created_at, likes, retweets, views, url, source_tag

source_tag 取 "twitter" 或 "kol"，被 EvidenceExtractor 自动降权为低可信度源
（见 input/evidence.py:76-85 LOW_CREDIBILITY_SOURCES），不会污染五维评分。

用法：
    from data.twitter_kol import KOLFetcher
    kf = KOLFetcher()
    if kf.has_credentials():
        signals = kf.fetch_all("AAPL.US")   # {"kol": [...], "ticker": [...]}
"""
import json
import subprocess
from typing import Dict, List, Optional

from config import Config

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("trader_kol")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())


# ========== 符号归一化 ==========

def _ticker_from_code(stock_code: str) -> str:
    """AAPL.US → AAPL；00700.HK → 00700；SH603906 → 603906（对齐 search._normalize_for_search）"""
    code = stock_code.upper()
    if code.endswith(".US"):
        return code.replace(".US", "")
    if code.endswith(".HK"):
        return code.replace(".HK", "")
    if code.startswith("SH") or code.startswith("SZ"):
        return code[2:]
    return code


# ========== 核心类 ==========

class KOLFetcher:
    """抓取 KOL watchlist + 按 ticker 的 X 推文，返回标准化 dict 列表"""

    def __init__(self, timeout: Optional[int] = None):
        self.timeout = timeout or Config.ANALYSIS_TIMEOUT
        self.watchlist = list(Config.KOL_WATCHLIST)
        self.mode = (Config.X_MCP_MODE or "local").lower()

    # ----- 凭据检查 -----

    def has_credentials(self) -> bool:
        """是否配置了 X 凭据（任一即可启用）"""
        return bool(Config.X_API_BEARER_TOKEN or Config.X_CLIENT_ID)

    # ----- 对外主接口 -----

    def fetch_all(self, stock_code: str) -> Dict[str, List[Dict]]:
        """
        合并 watchlist + ticker 抓取，去重后返回 {"kol": [...], "ticker": [...]}
        永不抛异常；失败返回空 dict。
        """
        if not self.has_credentials():
            return {}

        result: Dict[str, List[Dict]] = {"kol": [], "ticker": []}
        try:
            result["kol"] = self.fetch_watchlist()
        except Exception as e:
            logger.warning(f"KOL watchlist fetch failed: {e}")
        try:
            result["ticker"] = self.fetch_by_ticker(stock_code)
        except Exception as e:
            logger.warning(f"KOL ticker fetch failed for {stock_code}: {e}")

        # 去重（按 url）
        for key in result:
            seen = set()
            deduped = []
            for item in result[key]:
                url = item.get("url", "")
                if url and url in seen:
                    continue
                if url:
                    seen.add(url)
                deduped.append(item)
            result[key] = deduped
        return result

    def fetch_watchlist(self, limit_per_kol: int = 15) -> List[Dict]:
        """拉取全局 KOL watchlist 近期推文"""
        if not self.watchlist:
            return []
        all_items: List[Dict] = []
        for handle in self.watchlist:
            items = self._fetch_user_tweets(handle, limit=limit_per_kol)
            all_items.extend(items)
        return all_items

    def fetch_by_ticker(self, stock_code: str, limit: int = 20) -> List[Dict]:
        """按 $TICKER / 公司名搜索 X 讨论"""
        ticker = _ticker_from_code(stock_code)
        query = f"${ticker}"  # X cashtag 语法
        raw = self._search(query, limit=limit)
        return [self._normalize(item, source_tag="twitter") for item in raw]

    # ----- 传输层（local / remote）-----

    def _fetch_user_tweets(self, username: str, limit: int = 15) -> List[Dict]:
        """单个 KOL 的近期推文"""
        if self.mode == "remote":
            raw = self._remote_call("user_tweets", {"username": username, "max_results": limit})
        else:
            raw = self._local_call(["tweets", username, "--limit", str(limit), "-f", "json"])
        return [self._normalize(item, source_tag="kol") for item in raw]

    def _search(self, query: str, limit: int = 20) -> List[Dict]:
        """search 端点"""
        if self.mode == "remote":
            raw = self._remote_call("search", {"query": query, "max_results": limit})
        else:
            raw = self._local_call(["search", query, "--limit", str(limit), "-f", "json"])
        return raw

    # ----- local：subprocess 调 xurl/xmcp CLI -----

    def _local_call(self, args: List[str]) -> List[Dict]:
        """调用 xurl CLI（opencli-style），受 ANALYSIS_TIMEOUT 保护"""
        # 优先 xurl（官方 CLI），回退 opencli（twitter-reader skill 既有路径）
        cmd_base = self._resolve_cli()
        if not cmd_base:
            logger.warning("No X CLI available (xurl/opencli not found); skipping local KOL fetch")
            return []
        try:
            env_tokens = self._cli_env()
            proc = subprocess.run(
                cmd_base + ["twitter"] + args if "opencli" in cmd_base else cmd_base + args,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env_tokens,
            )
            if proc.returncode != 0:
                logger.warning(f"X CLI error: {proc.stderr[:200]}")
                return []
            return self._parse_jsonl_or_json(proc.stdout)
        except subprocess.TimeoutExpired:
            logger.warning(f"X CLI timeout after {self.timeout}s")
            return []
        except FileNotFoundError:
            logger.warning("X CLI not installed")
            return []

    def _resolve_cli(self) -> List[str]:
        """探测可用 CLI：xurl 优先，opencli 备用"""
        import shutil
        if shutil.which("xurl"):
            return ["xurl"]
        if shutil.which("opencli"):
            return ["opencli"]
        # npx 兜底（Windows 用 cmd /c）
        if shutil.which("npx"):
            return ["cmd", "/c", "npx", "-y", "xurl"]
        return []

    def _cli_env(self):
        """注入 X 凭据到子进程环境"""
        import os
        env = os.environ.copy()
        if Config.X_API_BEARER_TOKEN:
            env["X_API_BEARER_TOKEN"] = Config.X_API_BEARER_TOKEN
        if Config.X_CLIENT_ID:
            env["X_CLIENT_ID"] = Config.X_CLIENT_ID
        if Config.X_CLIENT_SECRET:
            env["X_CLIENT_SECRET"] = Config.X_CLIENT_SECRET
        return env

    # ----- remote：调 docs.x.com 托管 MCP 端点 -----

    def _remote_call(self, tool: str, params: Dict) -> List[Dict]:
        """调 X 托管 MCP 端点（需要 Bearer Token）"""
        token = Config.X_API_BEARER_TOKEN
        if not token:
            logger.warning("Remote X MCP requires X_API_BEARER_TOKEN")
            return []
        try:
            import requests
            resp = requests.post(
                "https://mcp.x.com/v1/tools/call",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"tool": tool, "parameters": params},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            # MCP tools/call 返回 {"content": [{"type":"text","text":"<json>"}]}
            content = data.get("content") or []
            for block in content:
                if block.get("type") == "text":
                    return self._parse_jsonl_or_json(block.get("text", ""))
            return []
        except Exception as e:
            logger.warning(f"Remote X MCP call failed ({tool}): {e}")
            return []

    # ----- 工具：解析 + 归一化 -----

    @staticmethod
    def _parse_jsonl_or_json(text: str) -> List[Dict]:
        """容错解析 CLI 输出（可能是 JSON 数组、JSONL 或单对象）"""
        text = text.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass
        # 尝试 JSONL
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return items

    @staticmethod
    def _normalize(raw: Dict, source_tag: str = "twitter") -> Dict:
        """把 X CLI/API 的原始 item 归一化为报告友好字段"""
        return {
            "author": raw.get("author") or raw.get("username") or raw.get("screen_name") or "",
            "text": raw.get("text") or raw.get("content") or raw.get("full_text") or "",
            "created_at": raw.get("created_at") or raw.get("created_at_iso") or "",
            "likes": raw.get("likes") or raw.get("favorite_count") or 0,
            "retweets": raw.get("retweets") or raw.get("retweet_count") or 0,
            "views": raw.get("views") or raw.get("impression_count") or 0,
            "url": raw.get("url") or raw.get("tweet_url") or "",
            "source_tag": source_tag,
        }


# ========== 便捷入口 ==========

def fetch_kol_signals(stock_code: str) -> Dict[str, List[Dict]]:
    """管线友好的一站式入口；无凭据或失败均返回 {}"""
    kf = KOLFetcher()
    if not kf.has_credentials():
        return {}
    return kf.fetch_all(stock_code)
