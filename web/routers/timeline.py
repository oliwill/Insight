"""追踪路由：分析历史时间线"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from web import db
from web.deps import get_current_user
from web.templates import templates

router = APIRouter(prefix="/timeline")


@router.get("", response_class=HTMLResponse)
def timeline_page(request: Request, symbol: str = "", user: dict = Depends(get_current_user)):
    symbol = symbol.strip().upper()
    records = db.get_analysis_records(user["id"], symbol=symbol or None, limit=100)
    return templates.TemplateResponse(request, "timeline.html", {
        "records": [dict(r) for r in records],
        "filter_symbol": symbol,
    })
