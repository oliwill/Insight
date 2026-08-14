"""任务路由：状态轮询片段 + 任务列表"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from web import db
from web.deps import get_current_user
from web.templates import templates

router = APIRouter(prefix="/jobs")


@router.get("/{job_id}", response_class=HTMLResponse)
def job_fragment(request: Request, job_id: int, user: dict = Depends(get_current_user)):
    """HTMX 轮询片段：任务状态行"""
    job = db.get_job(job_id)
    if job is None or job["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="任务不存在")
    return templates.TemplateResponse(request, "partials/job_row.html", {"job": dict(job)})


@router.get("", response_class=HTMLResponse)
def job_list(request: Request, user: dict = Depends(get_current_user)):
    jobs = [dict(j) for j in db.get_jobs(user["id"], limit=20)]
    return templates.TemplateResponse(request, "jobs.html", {"jobs": jobs})
