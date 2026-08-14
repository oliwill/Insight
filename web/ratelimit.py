"""限流与配额 —— 登录尝试 IP 限流 + 分析日配额

- 登录限流：进程内存滑动窗口（1 分钟 5 次 / IP）
- 分析配额：db.count_jobs_today 按用户（Config.ANALYSIS_DAILY_QUOTA）
"""
import time
from threading import Lock

_LOGIN_WINDOW_SECONDS = 60
_LOGIN_MAX_ATTEMPTS = 5

_attempts: dict = {}
_lock = Lock()


def check_login_rate(ip: str) -> bool:
    """IP 在窗口内尝试是否超限；通过则记录本次尝试"""
    now = time.time()
    with _lock:
        stamps = [t for t in _attempts.get(ip, []) if now - t < _LOGIN_WINDOW_SECONDS]
        if len(stamps) >= _LOGIN_MAX_ATTEMPTS:
            _attempts[ip] = stamps
            return False
        stamps.append(now)
        _attempts[ip] = stamps
        return True
