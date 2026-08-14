"""认证工具 —— pbkdf2 密码哈希 + 随机 session token

选型：stdlib hashlib.pbkdf2_hmac（无 bcrypt 编译依赖，Windows 友好）；
session 用 DB 存储（可撤销），不用无状态 JWT。
"""
import hashlib
import hmac
import secrets

_ITERATIONS = 100_000


def generate_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS
    ).hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    actual = hash_password(password, salt)
    return hmac.compare_digest(actual, expected_hash)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)
