"""FastAPI 依赖注入 —— 当前用户解析

所有用户数据路由必须通过 get_current_user，禁止绕过。
"""
from fastapi import Request, HTTPException

from web import db


def get_current_user(request: Request):
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    user = db.get_session_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="会话无效或已过期")
    return user
