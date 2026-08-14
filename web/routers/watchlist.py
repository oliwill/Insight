"""自选路由：列表 / 增删（HTMX 局部片段）"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from web import db
from web.deps import get_current_user
from web.symbols import normalize_symbol_or_none
from web.templates import templates

router = APIRouter(prefix="/watchlist")


@router.get("", response_class=HTMLResponse)
def watchlist_page(request: Request, user: dict = Depends(get_current_user)):
    symbols = db.get_watchlist_symbols(user["id"])
    records_by_symbol = {}
    for symbol in symbols:
        latest = db.get_latest_record(user["id"], symbol)
        records_by_symbol[symbol] = dict(latest) if latest else None
    return templates.TemplateResponse(request, "watchlist.html", {
        "symbols": symbols,
        "records_by_symbol": records_by_symbol,
    })


@router.post("/add")
def add(request: Request, symbol: str = Form(...), user: dict = Depends(get_current_user)):
    norm = _normalize_or_400(symbol)
    db.add_watchlist_symbol(user["id"], norm)
    return _symbol_row(request, user, norm)


@router.post("/remove")
def remove(request: Request, symbol: str = Form(...), user: dict = Depends(get_current_user)):
    norm = _normalize_or_400(symbol)
    db.remove_watchlist_symbol(user["id"], norm)
    # HTMX oob：返回空片段，前端移除行
    return HTMLResponse("")


@router.post("/analyze-all")
def analyze_all(request: Request, user: dict = Depends(get_current_user)):
    from config import Config
    from web import tasks

    symbols = db.get_watchlist_symbols(user["id"])
    quota_left = Config.ANALYSIS_DAILY_QUOTA - db.count_jobs_today(user["id"])
    queued = 0
    for symbol in symbols[: max(quota_left, 0)]:
        job_id = db.create_job(user["id"], symbol)
        tasks.submit_analysis(job_id)
        queued += 1
    return RedirectResponse("/watchlist?queued=" + str(queued), status_code=303)


def _symbol_row(request: Request, user: dict, symbol: str) -> HTMLResponse:
    latest = db.get_latest_record(user["id"], symbol)
    return templates.TemplateResponse(request, "partials/watchlist_row.html", {
        "symbol": symbol,
        "latest": dict(latest) if latest else None,
    })


def _normalize_or_400(symbol: str) -> str:
    norm = normalize_symbol_or_none(symbol)
    if not norm:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"无法识别的股票代码: {symbol}")
    return norm
