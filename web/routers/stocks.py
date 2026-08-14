"""股票路由：股票页 / 发起分析 / 分析详情 / 图表服务"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from config import Config
from data.manager import DataManager
from web import db, tasks
from web.analysis_service import user_vault_dir
from web.deps import get_current_user
from web.symbols import normalize_symbol_or_none
from web.templates import templates

router = APIRouter(prefix="/stocks")


@router.get("/search")
def search(request: Request, q: str = "", user: dict = Depends(get_current_user)):
    """符号搜索建议（HTMX 即时提示）—— 本地规范化校验，不访问外部数据源"""
    q = q.strip().upper()
    if not q:
        return templates.TemplateResponse(request, "partials/search_results.html", {"results": []})
    suggestions = []
    for prefix in (q, q + ".US"):
        try:
            norm = DataManager.normalize_symbol(prefix)
            if norm and norm not in suggestions:
                suggestions.append(norm)
        except Exception:
            continue
    return templates.TemplateResponse(request, "partials/search_results.html", {"results": suggestions[:5]})


@router.get("/{symbol}", response_class=HTMLResponse)
def stock_page(request: Request, symbol: str, user: dict = Depends(get_current_user)):
    norm = _normalize_or_400(symbol)
    records = db.get_analysis_records(user["id"], symbol=norm, limit=20)
    return templates.TemplateResponse(request, "stock_detail.html", {
        "symbol": norm,
        "in_watchlist": db.is_in_watchlist(user["id"], norm),
        "records": [dict(r) for r in records],
        "quota": db.count_jobs_today(user["id"]),
        "quota_max": Config.ANALYSIS_DAILY_QUOTA,
        "submitted": request.query_params.get("submitted") == "1",
    })


@router.post("/{symbol}/analyze")
def analyze(request: Request, symbol: str, user: dict = Depends(get_current_user)):
    norm = _normalize_or_400(symbol)
    if db.count_jobs_today(user["id"]) >= Config.ANALYSIS_DAILY_QUOTA:
        return templates.TemplateResponse(request, "partials/quota_error.html", {
            "quota_max": Config.ANALYSIS_DAILY_QUOTA,
        }, status_code=429)
    job_id = db.create_job(user["id"], norm)
    tasks.submit_analysis(job_id)
    return RedirectResponse(f"/stocks/{norm}?submitted=1", status_code=303)


@router.get("/records/{record_id}", response_class=HTMLResponse)
def record_page(request: Request, record_id: int, user: dict = Depends(get_current_user)):
    record = db.get_analysis_record(record_id, user["id"])
    if record is None:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return templates.TemplateResponse(request, "analysis_detail.html", {
        "record": dict(record),
        "symbol": record["symbol"],
    })


@router.get("/media/charts/{filename}")
def chart_file(filename: str, user: dict = Depends(get_current_user)):
    """用户图表服务（防目录穿越：解析后必须落在用户 Charts 目录内）"""
    charts_dir = (user_vault_dir(user["id"]) / "Charts").resolve()
    target = (charts_dir / filename).resolve()
    if charts_dir not in target.parents and target != charts_dir:
        raise HTTPException(status_code=403, detail="forbidden")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(target)


def _normalize_or_400(symbol: str) -> str:
    norm = normalize_symbol_or_none(symbol)
    if not norm:
        raise HTTPException(status_code=400, detail=f"无法识别的股票代码: {symbol}")
    return norm
