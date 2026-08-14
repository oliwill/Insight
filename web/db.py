"""Web 平台数据访问层 —— stdlib sqlite3（WAL 模式，无 ORM 依赖）

表：
- users            用户（邮箱 + pbkdf2 密码哈希）
- sessions         登录会话（DB 存储，可撤销）
- watchlists       自选组（v1 每用户一个默认组，结构支持多组）
- watchlist_items  自选条目（symbol 去重）
- analysis_jobs    分析任务（状态机 pending/running/succeeded/failed）
- analysis_records 分析结果快照（追踪分析历史）

线程模型：每个操作独立连接；SQLite WAL 允许多读单写并发，
写竞争由内置锁 + 30s busy timeout 兜底。
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import Config

JOB_PENDING = "pending"
JOB_RUNNING = "running"
JOB_SUCCEEDED = "succeeded"
JOB_FAILED = "failed"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _db_path() -> Path:
    path = Path(Config.WEB_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT '默认自选',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(watchlist_id, symbol)
);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON analysis_jobs(user_id, created_at);

CREATE TABLE IF NOT EXISTS analysis_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    report_md TEXT,
    research_score REAL,
    timing_state TEXT,
    chart_path TEXT,
    data_sources TEXT,
    llm_enhanced INTEGER NOT NULL DEFAULT 0,
    llm_summary TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_records_user ON analysis_records(user_id, symbol, created_at);
"""


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ==================== users ====================

def create_user(email: str, password_hash: str, salt: str) -> Optional[int]:
    email = email.strip().lower()
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (email, password_hash, salt, _now_utc()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    email = email.strip().lower()
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


# ==================== sessions ====================

def create_session(user_id: int, token: str, ttl_days: int) -> None:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=ttl_days)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now.strftime("%Y-%m-%dT%H:%M:%SZ"), expires.strftime("%Y-%m-%dT%H:%M:%SZ")),
        )


def get_session_user(token: str) -> Optional[sqlite3.Row]:
    now = _now_utc()
    with get_conn() as conn:
        return conn.execute(
            """SELECT u.*, s.expires_at FROM sessions s
               JOIN users u ON u.id = s.user_id
               WHERE s.token = ? AND s.expires_at > ?""",
            (token, now),
        ).fetchone()


def delete_session(token: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def delete_expired_sessions() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (_now_utc(),))


# ==================== watchlists ====================

def ensure_default_watchlist(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM watchlists WHERE user_id = ? ORDER BY id LIMIT 1", (user_id,)
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO watchlists (user_id, name, created_at) VALUES (?, '默认自选', ?)",
            (user_id, _now_utc()),
        )
        return cur.lastrowid


def add_watchlist_symbol(user_id: int, symbol: str) -> bool:
    """加入自选，成功返回 True；已存在返回 False"""
    watchlist_id = ensure_default_watchlist(user_id)
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO watchlist_items (watchlist_id, symbol, created_at) VALUES (?, ?, ?)",
                (watchlist_id, symbol.upper(), _now_utc()),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def remove_watchlist_symbol(user_id: int, symbol: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            """DELETE FROM watchlist_items
               WHERE symbol = ? AND watchlist_id IN
                   (SELECT id FROM watchlists WHERE user_id = ?)""",
            (symbol.upper(), user_id),
        )
        return cur.rowcount > 0


def get_watchlist_symbols(user_id: int) -> List[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT i.symbol FROM watchlist_items i
               JOIN watchlists w ON w.id = i.watchlist_id
               WHERE w.user_id = ? ORDER BY i.created_at DESC""",
            (user_id,),
        ).fetchall()
        return [r["symbol"] for r in rows]


def is_in_watchlist(user_id: int, symbol: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT 1 FROM watchlist_items i
               JOIN watchlists w ON w.id = i.watchlist_id
               WHERE w.user_id = ? AND i.symbol = ?""",
            (user_id, symbol.upper()),
        ).fetchone()
        return row is not None


# ==================== analysis jobs ====================

def create_job(user_id: int, symbol: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO analysis_jobs (user_id, symbol, status, created_at) VALUES (?, ?, ?, ?)",
            (user_id, symbol.upper(), JOB_PENDING, _now_utc()),
        )
        return cur.lastrowid


def try_claim_job(job_id: int) -> bool:
    """原子抢占 pending 任务（pending → running）；已被处理返回 False"""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE analysis_jobs SET status = ?, started_at = ? WHERE id = ? AND status = ?",
            (JOB_RUNNING, _now_utc(), job_id, JOB_PENDING),
        )
        return cur.rowcount > 0


def update_job_status(job_id: int, status: str, error: Optional[str] = None) -> None:
    with get_conn() as conn:
        if status == JOB_RUNNING:
            conn.execute(
                "UPDATE analysis_jobs SET status = ?, started_at = ? WHERE id = ?",
                (status, _now_utc(), job_id),
            )
        elif status in (JOB_SUCCEEDED, JOB_FAILED):
            conn.execute(
                "UPDATE analysis_jobs SET status = ?, error = ?, finished_at = ? WHERE id = ?",
                (status, error, _now_utc(), job_id),
            )
        else:
            conn.execute("UPDATE analysis_jobs SET status = ? WHERE id = ?", (status, job_id))


def get_job(job_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM analysis_jobs WHERE id = ?", (job_id,)).fetchone()


def get_jobs(user_id: int, limit: int = 20) -> List[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM analysis_jobs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def count_jobs_today(user_id: int) -> int:
    """今日已创建的分析任务数（日配额依据）"""
    today_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM analysis_jobs WHERE user_id = ? AND created_at >= ?",
            (user_id, today_start),
        ).fetchone()
        return row["c"]


# ==================== analysis records ====================

def save_analysis_record(
    user_id: int,
    symbol: str,
    report_md: str,
    research_score: Optional[float],
    timing_state: Optional[str],
    chart_path: Optional[str],
    data_sources: Optional[str],
    llm_enhanced: bool,
    llm_summary: Optional[str] = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO analysis_records
               (user_id, symbol, report_md, research_score, timing_state, chart_path, data_sources, llm_enhanced, llm_summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, symbol.upper(), report_md, research_score, timing_state, chart_path,
             data_sources, 1 if llm_enhanced else 0, llm_summary, _now_utc()),
        )
        return cur.lastrowid


def get_analysis_records(user_id: int, symbol: Optional[str] = None, limit: int = 50) -> List[sqlite3.Row]:
    with get_conn() as conn:
        if symbol:
            return conn.execute(
                "SELECT * FROM analysis_records WHERE user_id = ? AND symbol = ? ORDER BY id DESC LIMIT ?",
                (user_id, symbol.upper(), limit),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM analysis_records WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def get_analysis_record(record_id: int, user_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM analysis_records WHERE id = ? AND user_id = ?",
            (record_id, user_id),
        ).fetchone()


def get_latest_record(user_id: int, symbol: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM analysis_records WHERE user_id = ? AND symbol = ? ORDER BY id DESC LIMIT 1",
            (user_id, symbol.upper()),
        ).fetchone()
