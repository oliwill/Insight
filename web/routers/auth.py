"""认证路由：注册 / 登录 / 登出

表单 POST + PRG（重定向），错误通过 query 参数回显。
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import Config
from web import db, security
from web.ratelimit import check_login_rate
from web.templates import templates

router = APIRouter(prefix="/auth")

_SESSION_COOKIE = "session"


def _set_session_cookie(response: RedirectResponse, user_id: int) -> None:
    token = security.new_session_token()
    db.create_session(user_id, token, Config.SESSION_TTL_DAYS)
    response.set_cookie(
        _SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=Config.SESSION_TTL_DAYS * 86400,
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {
        "error": request.query_params.get("error", ""),
        "require_invite": bool(Config.INVITE_CODE),
    })


@router.post("/register")
def register(request: Request, email: str = Form(...), password: str = Form(...),
             password2: str = Form(...), invite_code: str = Form("")):
    email = email.strip().lower()
    if "@" not in email or len(email) < 5:
        return templates.TemplateResponse(request, "register.html", {"error": "邮箱格式不正确"}, status_code=400)
    if len(password) < 8:
        return templates.TemplateResponse(request, "register.html", {"error": "密码至少 8 位"}, status_code=400)
    if password != password2:
        return templates.TemplateResponse(request, "register.html", {"error": "两次密码不一致"}, status_code=400)
    if Config.INVITE_CODE and invite_code.strip() != Config.INVITE_CODE:
        return templates.TemplateResponse(request, "register.html", {"error": "邀请码不正确"}, status_code=400)

    salt = security.generate_salt()
    user_id = db.create_user(email, security.hash_password(password, salt), salt)
    if user_id is None:
        return templates.TemplateResponse(request, "register.html", {"error": "该邮箱已注册"}, status_code=400)

    response = RedirectResponse("/watchlist", status_code=303)
    _set_session_cookie(response, user_id)
    return response


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": request.query_params.get("error", "")})


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    ip = _client_ip(request)
    if not check_login_rate(ip):
        return templates.TemplateResponse(request, "login.html", {"error": "尝试过于频繁，请一分钟后再试"}, status_code=429)

    user = db.get_user_by_email(email.strip().lower())
    if user is None or not security.verify_password(password, user["salt"], user["password_hash"]):
        return templates.TemplateResponse(request, "login.html", {"error": "邮箱或密码错误"}, status_code=400)

    response = RedirectResponse("/watchlist", status_code=303)
    _set_session_cookie(response, user["id"])
    return response


@router.post("/logout")
def logout(request: Request):
    token = request.cookies.get(_SESSION_COOKIE)
    if token:
        db.delete_session(token)
    response = RedirectResponse("/auth/login", status_code=303)
    response.delete_cookie(_SESSION_COOKIE)
    return response
