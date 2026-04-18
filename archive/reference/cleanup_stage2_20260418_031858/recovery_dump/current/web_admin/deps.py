from fastapi import Request
def require_admin(request: Request):
    return True
