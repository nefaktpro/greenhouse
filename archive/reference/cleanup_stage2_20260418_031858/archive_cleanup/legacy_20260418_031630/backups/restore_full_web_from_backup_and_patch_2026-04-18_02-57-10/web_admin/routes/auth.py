from fastapi import APIRouter, HTTPException, Response, Request
from pydantic import BaseModel

from interfaces.web_admin.security import (
    authenticate_admin,
    create_access_token,
    WEB_AUTH_COOKIE,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    if not authenticate_admin(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(payload.username)

    response.set_cookie(
        key=WEB_AUTH_COOKIE,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 12,
        path="/",
    )

    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=WEB_AUTH_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    from interfaces.web_admin.security import get_current_user_from_request

    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "ok": True,
        "user": {
            "username": user.get("sub"),
        },
    }
