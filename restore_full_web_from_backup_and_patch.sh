#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
WEB="$ROOT/interfaces/web_admin"
SVC="$ROOT/greenhouse_v17/services"
SRC="$ROOT/backups/final_restore_everything_20260418_023408"
TS="$(date +%F_%H-%M-%S)"

echo "== 0. precheck =="
test -d "$SRC/interfaces/web_admin"
echo "backup source ok: $SRC"

echo "== 1. backup current state =="
mkdir -p "$ROOT/backups/restore_full_web_from_backup_and_patch_$TS"
cp -a "$WEB" "$ROOT/backups/restore_full_web_from_backup_and_patch_$TS/" 2>/dev/null || true
cp -a "$SVC/webadmin_execution_service.py" "$ROOT/backups/restore_full_web_from_backup_and_patch_$TS/" 2>/dev/null || true

echo "== 2. restore full web_admin from good backup =="
rm -rf "$WEB"
mkdir -p "$(dirname "$WEB")"
cp -a "$SRC/interfaces/web_admin" "$WEB"

echo "== 3. restore webadmin execution service if present =="
if [ -f "$SRC/greenhouse_v17/services/webadmin_execution_service.py" ]; then
  mkdir -p "$SVC"
  cp -f "$SRC/greenhouse_v17/services/webadmin_execution_service.py" "$SVC/webadmin_execution_service.py"
fi

echo "== 4. patch security.py =="
cat > "$WEB/security.py" <<'PY'
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


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def authenticate_admin(username: str, password: str) -> bool:
    if username != WEB_ADMIN_USERNAME:
        return False
    if not WEB_ADMIN_PASSWORD_HASH:
        return False
    return verify_password(password, WEB_ADMIN_PASSWORD_HASH)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "exp": expire,
        "type": "access",
    }
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
    if not payload:
        return None
    if payload.get("type") != "access":
        return None
    return payload
PY

echo "== 5. patch auth.py =="
cat > "$WEB/routes/auth.py" <<'PY'
from fastapi import APIRouter, HTTPException, Response, Request
from pydantic import BaseModel

from interfaces.web_admin.security import (
    authenticate_admin,
    create_access_token,
    WEB_AUTH_COOKIE,
    get_current_user_from_request,
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
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "ok": True,
        "user": {
            "username": user.get("sub"),
        },
    }
PY

echo "== 6. patch api.py (убираем дубль роутеров, оставляем current backend) =="
cat > "$WEB/api.py" <<'PY'
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from interfaces.web_admin.routes.actions import router as actions_router
from interfaces.web_admin.routes.ask import router as ask_router
from interfaces.web_admin.routes.auth import router as auth_router
from interfaces.web_admin.routes.modes import router as modes_router
from interfaces.web_admin.routes.monitoring import router as monitoring_router
from interfaces.web_admin.routes.registry import router as registry_router
from interfaces.web_admin.routes.web import router as web_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Greenhouse v17 Web Admin",
    version="2.1.0",
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "web_admin",
        "project": "greenhouse_v17",
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": "internal_error",
            "details": str(exc),
        },
    )


app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(registry_router, prefix="/api/registry", tags=["registry"])
app.include_router(modes_router, prefix="/api/modes", tags=["modes"])
app.include_router(ask_router, prefix="/api/ask", tags=["ask"])
app.include_router(actions_router, prefix="/api/actions", tags=["actions"])
app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(web_router)
PY

echo "== 7. patch routes/web.py (server-side login gate + login route + safe TemplateResponse) =="
cat > "$WEB/routes/web.py" <<'PY'
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from interfaces.web_admin.security import get_current_user_from_request

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/web", tags=["web"])


def render(request: Request, template_name: str, page_title: str):
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "request": request,
            "page_title": page_title,
        },
    )


def require_web_auth(request: Request) -> bool:
    user = get_current_user_from_request(request)
    return bool(user)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if require_web_auth(request):
        return RedirectResponse(url="/web/", status_code=302)
    return render(request, "login.html", "Greenhouse v17 — Login")


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    if not require_web_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "dashboard.html", "Greenhouse v17 — Dashboard")


@router.get("/control", response_class=HTMLResponse)
def control_page(request: Request):
    if not require_web_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "control.html", "Greenhouse v17 — Control")


@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    if not require_web_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "ask.html", "Greenhouse v17 — ASK")


@router.get("/modes", response_class=HTMLResponse)
def modes_page(request: Request):
    if not require_web_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "modes.html", "Greenhouse v17 — Modes")


@router.get("/registry", response_class=HTMLResponse)
def registry_page(request: Request):
    if not require_web_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "registry.html", "Greenhouse v17 — Registry")


@router.get("/monitoring", response_class=HTMLResponse)
def monitoring_page(request: Request):
    if not require_web_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "monitoring.html", "Greenhouse v17 — Monitoring")


@router.get("/safety", response_class=HTMLResponse)
def safety_page(request: Request):
    if not require_web_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "safety.html", "Greenhouse v17 — Safety")
PY

echo "== 8. patch static/app.js (cookie auth + working pages) =="
cat > "$WEB/static/app.js" <<'JS'
async function ghApi(url, options = {}) {
  const opts = {
    credentials: "same-origin",
    ...options,
  };

  opts.headers = {
    ...(opts.headers || {}),
  };

  const resp = await fetch(url, opts);

  let data = null;
  try {
    data = await resp.json();
  } catch (_) {
    data = { ok: false, error: "invalid_json_response" };
  }

  if (resp.status === 401 && !location.pathname.endsWith("/web/login")) {
    window.location.href = "/web/login";
  }

  return { resp, data };
}

function pretty(id, data) {
  const el = document.getElementById(id);
  if (el) el.textContent = JSON.stringify(data, null, 2);
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function logout() {
  await ghApi("/api/auth/logout", {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  window.location.href = "/web/login";
}
JS

echo "== 9. patch login template only if missing/bad =="
cat > "$WEB/templates/login.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="hero-card narrow">
  <div class="hero-kicker">Локальный защищённый вход</div>
  <h2>Вход в Web Admin</h2>
  <p class="muted">После входа сервер сам откроет доступ ко всем разделам.</p>

  <form id="login-form" class="form-grid">
    <label>
      <span>Логин</span>
      <input id="username" type="text" value="Mi" autocomplete="username">
    </label>

    <label>
      <span>Пароль</span>
      <input id="password" type="password" autocomplete="current-password">
    </label>

    <button type="submit" class="primary-btn">Войти</button>
  </form>

  <pre id="login-result" class="result-box"></pre>
</section>
{% endblock %}

{% block scripts %}
<script>
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const result = document.getElementById("login-result");
  result.textContent = "Выполняю вход...";

  const { resp, data } = await ghApi("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: document.getElementById("username").value,
      password: document.getElementById("password").value
    })
  });

  if (!resp.ok || !data.access_token) {
    result.textContent = JSON.stringify(data, null, 2);
    return;
  }

  result.textContent = "Успешный вход";
  window.location.href = "/web/";
});
</script>
{% endblock %}
HTML

echo "== 10. ensure __init__ =="
touch "$WEB/__init__.py"
touch "$WEB/routes/__init__.py"

echo "== 11. restart service =="
sudo systemctl restart greenhouse-web-admin.service
sleep 2

echo
echo "=== HEALTH ==="
curl -s http://127.0.0.1:8081/api/health
echo
echo
echo "=== LOGIN HEADERS ==="
curl -I -s http://127.0.0.1:8081/web/login | head
echo
echo "=== DASHBOARD HEADERS (without login should redirect) ==="
curl -I -s http://127.0.0.1:8081/web/ | head
echo
echo "=== SERVICE STATUS ==="
sudo systemctl status greenhouse-web-admin.service --no-pager
echo
echo "=== LOGS ==="
journalctl -u greenhouse-web-admin.service -n 80 --no-pager
