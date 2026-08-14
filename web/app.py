"""FastAPI 应用组装

启动时初始化 SQLite（幂等）。401 → 重定向登录页（页面型应用）。
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from web import db
from web.routers import auth, jobs, stocks, timeline, watchlist

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


def create_app() -> FastAPI:
    db.init_db()
    app = FastAPI(title="Insight 股票分析平台", docs_url=None, redoc_url=None)

    app.include_router(auth.router)
    app.include_router(stocks.router)
    app.include_router(watchlist.router)
    app.include_router(jobs.router)
    app.include_router(timeline.router)

    if (FRONTEND_DIR / "static").exists():
        app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # 未登录的页面请求 → 登录页
        if exc.status_code == 401 and not request.url.path.startswith("/auth"):
            return RedirectResponse("/auth/login", status_code=303)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get("/", include_in_schema=False)
    def index(request: Request):
        return RedirectResponse("/watchlist", status_code=303)

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    return app


app = create_app()
