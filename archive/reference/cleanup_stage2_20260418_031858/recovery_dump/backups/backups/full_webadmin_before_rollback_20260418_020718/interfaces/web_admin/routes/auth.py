from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from interfaces.web_admin.security import authenticate_admin, create_access_token

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(payload: LoginRequest):
    if not authenticate_admin(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(payload.username)
    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
    }
