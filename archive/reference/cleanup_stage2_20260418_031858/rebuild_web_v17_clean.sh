#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
WEB="$ROOT/interfaces/web_admin"
TS="$(date +%F_%H-%M-%S)"

mkdir -p "$ROOT/backups/rebuild_web_v17_clean_$TS"
cp -a "$WEB" "$ROOT/backups/rebuild_web_v17_clean_$TS/" 2>/dev/null || true

mkdir -p "$WEB/routes" "$WEB/templates" "$WEB/static"

echo "== write security.py =="
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

echo "== write auth.py =="
cat > "$WEB/routes/auth.py" <<'PY'
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
PY

echo "== write api.py =="
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
    version="2.0.0",
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

echo "== write web.py =="
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


def require_web_auth(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        return None
    return user


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    if not require_web_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "dashboard.html", "Greenhouse v17 — Dashboard")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if require_web_auth(request):
        return RedirectResponse(url="/web/", status_code=302)
    return render(request, "login.html", "Greenhouse v17 — Login")


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

echo "== write app.js =="
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

  if (resp.status === 401) {
    if (!location.pathname.endsWith("/web/login")) {
      window.location.href = "/web/login";
    }
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

echo "== write app.css =="
cat > "$WEB/static/app.css" <<'CSS'
:root {
  --bg: #07111f;
  --panel: #0f1c31;
  --panel-2: #132541;
  --line: rgba(94, 143, 255, 0.24);
  --text: #eef4ff;
  --muted: #9fb3d1;
  --accent: #4f8cff;
  --accent-2: #79a9ff;
  --danger: #ff5f74;
  --ok: #37c978;
  --warn: #ffb648;
  --shadow: 0 18px 50px rgba(0, 0, 0, 0.32);
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  background:
    radial-gradient(circle at top left, rgba(56, 100, 255, 0.18), transparent 34%),
    radial-gradient(circle at top right, rgba(0, 181, 255, 0.12), transparent 26%),
    linear-gradient(180deg, #05101d 0%, #07111f 100%);
  color: var(--text);
  font: 16px/1.45 Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  min-height: 100%;
}

body.layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  min-height: 100vh;
}

.sidebar {
  border-right: 1px solid var(--line);
  background: rgba(6, 15, 28, 0.8);
  backdrop-filter: blur(12px);
  padding: 22px 18px;
}

.brand {
  margin-bottom: 26px;
}

.brand-title {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.brand-subtitle {
  color: var(--muted);
  margin-top: 4px;
}

.menu {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 22px;
}

.menu a {
  text-decoration: none;
  color: var(--text);
  background: linear-gradient(180deg, rgba(18,29,49,0.96) 0%, rgba(10,20,36,0.96) 100%);
  border: 1px solid var(--line);
  border-radius: 22px;
  padding: 16px 18px;
  font-size: 17px;
  font-weight: 700;
  box-shadow: var(--shadow);
}

.menu a:hover {
  border-color: rgba(121, 169, 255, 0.5);
}

.sidebar-box {
  background: linear-gradient(180deg, rgba(18,29,49,0.96) 0%, rgba(10,20,36,0.96) 100%);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 16px;
  color: var(--muted);
}

.sidebar-title {
  color: var(--text);
  font-weight: 700;
  margin-bottom: 8px;
}

.main {
  padding: 26px;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 34px;
  line-height: 1.1;
  font-weight: 800;
}

.topbar-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 18px;
  margin-bottom: 18px;
}

.card, .hero-card {
  background: linear-gradient(180deg, rgba(18,29,49,0.96) 0%, rgba(10,20,36,0.96) 100%);
  border: 1px solid var(--line);
  border-radius: 24px;
  padding: 22px;
  box-shadow: var(--shadow);
}

.hero-card.narrow {
  max-width: 560px;
}

.card-label, .hero-kicker {
  color: var(--accent-2);
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}

.muted {
  color: var(--muted);
}

.form-grid {
  display: grid;
  gap: 14px;
  margin-top: 18px;
}

.form-grid label {
  display: grid;
  gap: 6px;
}

input, select, textarea, button {
  font: inherit;
}

input, select, textarea {
  width: 100%;
  background: rgba(6, 14, 27, 0.95);
  color: var(--text);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 12px 14px;
}

button, .primary-btn, .ghost-btn-link, .ghost-btn {
  border-radius: 14px;
  padding: 11px 16px;
  border: 1px solid var(--line);
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.primary-btn {
  background: linear-gradient(180deg, #4f8cff 0%, #3c73db 100%);
  color: white;
  border: 1px solid rgba(121,169,255,0.45);
  font-weight: 700;
}

.ghost-btn, .ghost-btn-link {
  background: rgba(7, 16, 31, 0.95);
  color: var(--text);
}

.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.result-box {
  margin: 0;
  margin-top: 12px;
  background: rgba(5, 12, 23, 0.95);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 14px;
  white-space: pre-wrap;
  word-break: break-word;
  overflow: auto;
  min-height: 90px;
}

.clean-list {
  margin: 0;
  padding-left: 18px;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
  margin-top: 12px;
}

.action-card {
  background: rgba(5, 12, 23, 0.95);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 14px;
}

.action-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 6px;
}

.action-meta {
  color: var(--muted);
  font-size: 14px;
  margin-bottom: 10px;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 980px) {
  body.layout {
    grid-template-columns: 1fr;
  }
  .sidebar {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
}
CSS

echo "== write base.html =="
cat > "$WEB/templates/base.html" <<'HTML'
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ page_title or "Greenhouse v17" }}</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body class="layout">
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-title">GREENHOUSE v17</div>
      <div class="brand-subtitle">Web Admin</div>
    </div>

    <nav class="menu">
      <a href="/web/">🏠 Dashboard</a>
      <a href="/web/control">🎛 Control</a>
      <a href="/web/ask">❓ ASK</a>
      <a href="/web/modes">🧠 Modes</a>
      <a href="/web/registry">🗂 Registry</a>
      <a href="/web/monitoring">📈 Monitoring</a>
      <a href="/web/safety">🛡 Safety</a>
      <a href="/web/login">🔐 Login</a>
    </nav>

    <div class="sidebar-box">
      <div class="sidebar-title">Канон</div>
      <div>
        Telegram + Web поверх одного v17 Core / Registry / Execution контура.
      </div>
    </div>
  </aside>

  <main class="main">
    <header class="topbar">
      <div>
        <h1 class="page-title">{{ page_title or "Greenhouse v17" }}</h1>
      </div>
      <div class="topbar-actions">
        <button class="ghost-btn" onclick="logout()">Выйти</button>
      </div>
    </header>

    {% block content %}{% endblock %}
  </main>

  <script src="/static/app.js"></script>
  {% block scripts %}{% endblock %}
</body>
</html>
HTML

echo "== write login.html =="
cat > "$WEB/templates/login.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="hero-card narrow">
  <div class="hero-kicker">Локальный защищённый вход</div>
  <h2>Вход в Web Admin</h2>
  <p class="muted">После входа сервер сам пустит в разделы, без костылей.</p>

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

echo "== write dashboard.html =="
cat > "$WEB/templates/dashboard.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="cards-grid">
  <article class="card">
    <div class="card-label">System</div>
    <h3>Текущий режим</h3>
    <pre id="mode-box" class="result-box">Загрузка...</pre>
  </article>

  <article class="card">
    <div class="card-label">ASK</div>
    <h3>Текущее ожидание</h3>
    <pre id="ask-box" class="result-box">Загрузка...</pre>
  </article>
</section>

<section class="cards-grid">
  <article class="card">
    <div class="card-label">Monitoring</div>
    <h3>Overview</h3>
    <pre id="overview-box" class="result-box">Загрузка...</pre>
  </article>

  <article class="card">
    <div class="card-label">Safety</div>
    <h3>Safety summary</h3>
    <pre id="safety-box" class="result-box">Загрузка...</pre>
  </article>
</section>

<section class="cards-grid">
  <article class="card">
    <div class="card-label">Навигация</div>
    <h3>Быстрые действия</h3>
    <div class="button-row">
      <a class="primary-btn" href="/web/control">Control</a>
      <a class="ghost-btn-link" href="/web/ask">ASK</a>
      <a class="ghost-btn-link" href="/web/modes">Modes</a>
      <a class="ghost-btn-link" href="/web/registry">Registry</a>
      <a class="ghost-btn-link" href="/web/monitoring">Monitoring</a>
      <a class="ghost-btn-link" href="/web/safety">Safety</a>
    </div>
  </article>

  <article class="card">
    <div class="card-label">Health</div>
    <h3>Service health</h3>
    <pre id="health-box" class="result-box">Загрузка...</pre>
  </article>
</section>
{% endblock %}

{% block scripts %}
<script>
(async function () {
  const [health, mode, ask, overview, safety] = await Promise.all([
    ghApi("/api/health"),
    ghApi("/api/modes/current"),
    ghApi("/api/ask/current"),
    ghApi("/api/monitoring/overview"),
    ghApi("/api/monitoring/safety")
  ]);

  pretty("health-box", health.data);
  pretty("mode-box", mode.data);
  pretty("ask-box", ask.data);
  pretty("overview-box", overview.data);
  pretty("safety-box", safety.data);
})();
</script>
{% endblock %}
HTML

echo "== write control.html =="
cat > "$WEB/templates/control.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="card">
  <div class="card-label">Execution</div>
  <h3>Control</h3>
  <p class="muted">Запуск действий через текущий v17 action/execution pipeline.</p>
  <div id="actions-grid" class="actions-grid"></div>
  <pre id="control-result" class="result-box">Загрузка action map...</pre>
</section>
{% endblock %}

{% block scripts %}
<script>
async function runAction(actionKey) {
  const { data } = await ghApi("/api/actions/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action_key: actionKey })
  });
  pretty("control-result", data);
}

(async function () {
  const grid = document.getElementById("actions-grid");
  const out = document.getElementById("control-result");

  const { data } = await ghApi("/api/actions/debug/action-map");
  pretty("control-result", data);

  const src = data.items || data.actions || data.action_map || data || [];
  const items = Array.isArray(src)
    ? src
    : Object.entries(src).map(([key, val]) => ({ action_key: key, ...(val || {}) }));

  if (!items.length) {
    out.textContent = JSON.stringify(data, null, 2);
    grid.innerHTML = "";
    return;
  }

  grid.innerHTML = items.map((item) => {
    const key = item.action_key || item.key || item.name || "unknown_action";
    const title = item.title || item.label || key;
    const role = item.logical_role || item.role || "-";
    const op = item.operation || "-";

    return `
      <div class="action-card">
        <div class="action-title">${esc(title)}</div>
        <div class="action-meta">
          <div><b>action_key:</b> ${esc(key)}</div>
          <div><b>role:</b> ${esc(role)}</div>
          <div><b>operation:</b> ${esc(op)}</div>
        </div>
        <div class="action-row">
          <button class="primary-btn" onclick="runAction('${String(key).replaceAll("'", "\\'")}')">Выполнить</button>
        </div>
      </div>
    `;
  }).join("");
})();
</script>
{% endblock %}
HTML

echo "== write ask.html =="
cat > "$WEB/templates/ask.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="card">
  <div class="card-label">ASK</div>
  <h3>Pending action</h3>
  <pre id="ask-box" class="result-box">Загрузка...</pre>
  <div class="button-row" style="margin-top:12px">
    <button class="primary-btn" onclick="confirmAsk()">Confirm</button>
    <button class="ghost-btn" onclick="cancelAsk()">Cancel</button>
    <button class="ghost-btn" onclick="refreshAsk()">Refresh</button>
  </div>
</section>
{% endblock %}

{% block scripts %}
<script>
async function refreshAsk() {
  const { data } = await ghApi("/api/ask/current");
  pretty("ask-box", data);
}

async function confirmAsk() {
  const { data } = await ghApi("/api/ask/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
  pretty("ask-box", data);
}

async function cancelAsk() {
  const { data } = await ghApi("/api/ask/cancel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
  pretty("ask-box", data);
}

refreshAsk();
</script>
{% endblock %}
HTML

echo "== write modes.html =="
cat > "$WEB/templates/modes.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="card">
  <div class="card-label">Modes</div>
  <h3>Управление режимами</h3>
  <pre id="mode-box" class="result-box">Загрузка...</pre>
  <div class="button-row" style="margin-top:12px">
    <button class="ghost-btn" onclick="setMode('MANUAL')">MANUAL</button>
    <button class="ghost-btn" onclick="setMode('TEST')">TEST</button>
    <button class="ghost-btn" onclick="setMode('ASK')">ASK</button>
    <button class="ghost-btn" onclick="setMode('AUTO')">AUTO</button>
    <button class="ghost-btn" onclick="setMode('AUTOPILOT')">AUTOPILOT</button>
  </div>
</section>
{% endblock %}

{% block scripts %}
<script>
async function refreshMode() {
  const { data } = await ghApi("/api/modes/current");
  pretty("mode-box", data);
}

async function setMode(mode) {
  const { data } = await ghApi("/api/modes/set", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode })
  });
  pretty("mode-box", data);
}

refreshMode();
</script>
{% endblock %}
HTML

echo "== write registry.html =="
cat > "$WEB/templates/registry.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="cards-grid">
  <article class="card">
    <div class="card-label">Registry</div>
    <h3>Devices</h3>
    <pre id="devices-box" class="result-box">Загрузка...</pre>
  </article>

  <article class="card">
    <div class="card-label">Registry</div>
    <h3>Capabilities</h3>
    <pre id="caps-box" class="result-box">Загрузка...</pre>
  </article>
</section>
{% endblock %}

{% block scripts %}
<script>
(async function () {
  const [devices, caps] = await Promise.all([
    ghApi("/api/registry/devices"),
    ghApi("/api/registry/capabilities")
  ]);

  pretty("devices-box", devices.data);
  pretty("caps-box", caps.data);
})();
</script>
{% endblock %}
HTML

echo "== write monitoring.html =="
cat > "$WEB/templates/monitoring.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="card">
  <div class="card-label">Monitoring</div>
  <h3>Overview</h3>
  <pre id="overview-box" class="result-box">Загрузка...</pre>
</section>
{% endblock %}

{% block scripts %}
<script>
(async function () {
  const { data } = await ghApi("/api/monitoring/overview");
  pretty("overview-box", data);
})();
</script>
{% endblock %}
HTML

echo "== write safety.html =="
cat > "$WEB/templates/safety.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="card">
  <div class="card-label">Safety</div>
  <h3>Safety state</h3>
  <pre id="safety-box" class="result-box">Загрузка...</pre>
</section>
{% endblock %}

{% block scripts %}
<script>
(async function () {
  const { data } = await ghApi("/api/monitoring/safety");
  pretty("safety-box", data);
})();
</script>
{% endblock %}
HTML

touch "$WEB/__init__.py"
touch "$WEB/routes/__init__.py"

echo "== restart =="
sudo systemctl restart greenhouse-web-admin.service
sleep 2

echo "== smoke checks =="
curl -s http://127.0.0.1:8081/api/health
echo
echo "--- /web/login headers ---"
curl -I -s http://127.0.0.1:8081/web/login | head
echo "--- /web/ headers ---"
curl -I -s http://127.0.0.1:8081/web/ | head
echo "--- logs ---"
journalctl -u greenhouse-web-admin.service -n 60 --no-pager
