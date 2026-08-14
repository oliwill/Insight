"""后台分析任务执行器 —— 进程内线程池 + 信号量

- _workers(2)：执行分析（重 IO/CPU）；_timeout_runner(8)：180s 超时标记
- Semaphore(2)：数据源 API 配额兜底，多用户共享服务器 key 不被打爆
- 状态机：pending → running → succeeded | failed（db）
- run_analysis 不直接写 job 状态：succeeded/failed 由本模块统一更新，
  超时后不会出现"迟到的 succeeded 覆盖 failed"的竞态
"""
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

from web import db
from web.analysis_service import run_analysis

JOB_TIMEOUT_SECONDS = 180

_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis-worker")
_timeout_runner = ThreadPoolExecutor(max_workers=8, thread_name_prefix="analysis-timeout")
_sem = BoundedSemaphore(2)


def submit_analysis(job_id: int) -> None:
    """提交任务到后台执行；仅 pending 状态会被处理（幂等）"""
    job = db.get_job(job_id)
    if job is None or job["status"] != db.JOB_PENDING:
        return
    _timeout_runner.submit(_run, job_id)


def _run(job_id: int) -> None:
    # 原子抢占：重复提交/竞态下只有一个执行者
    if not db.try_claim_job(job_id):
        return
    with _sem:
        job = db.get_job(job_id)
        if job is None:
            return
        future = _workers.submit(run_analysis, job["symbol"], job["user_id"])
        try:
            future.result(timeout=JOB_TIMEOUT_SECONDS)
            db.update_job_status(job_id, db.JOB_SUCCEEDED)
        except TimeoutError:
            db.update_job_status(job_id, db.JOB_FAILED, error="timeout")
        except Exception as exc:  # run_analysis 内部未捕获异常 → failed
            db.update_job_status(job_id, db.JOB_FAILED, error=f"Unexpected: {exc}")
