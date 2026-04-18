import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Request

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("WEB_ADMIN_JWT_SECRET", "change_me_web_admin_secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("WEB_ADMIN_JWT_EXPIRE_MINUTES", "720"))

WEB_ADMIN_USERNAME = os.getenv("WEB_ADMIN_USERNAME", "admin")
WEB_ADMIN_PASSWORD_HASH = os.getenv("WEB_ADMIN_PASSWORD_HASH", "")

WEB_AUTH_COOKIE = "gh_web_token"

def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)

def authenticate_admin(username: str, password: str) -> bool:
    if username != WEB_ADMIN_USERNAME:
        return False
    if not WEB_ADMIN_PASSWORD_HASH:
        return False
    return verify_password(password, WEB_ADMIN_PASSWORD_HASH)

def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None

def get_token_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get(WEB_AUTH_COOKIE)
    if cookie_token:
        return cookie_token
    return None

def get_current_user_from_request(request: Request) -> Optional[dict]:
    token = get_token_from_request(request)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or payload.get("type") != "access":
        return None
    return payload
