from fastapi import Header, HTTPException

from interfaces.web_admin.security import decode_access_token

def require_admin(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    return {
        "username": subject,
        "token_payload": payload,
    }
