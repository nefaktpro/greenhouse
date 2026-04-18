#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
WEB="$ROOT/interfaces/web_admin"
TS="$(date +%F_%H-%M-%S)"

mkdir -p "$ROOT/backups/fill_good_design_pages_only_$TS"
cp -a "$WEB" "$ROOT/backups/fill_good_design_pages_only_$TS/" 2>/dev/null || true

echo "== 1. patch auth/security/api/web gate only =="
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
PY

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
    return {"ok": True, "access_token": token, "token_type": "bearer"}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=WEB_AUTH_COOKIE, path="/")
    return {"ok": True}

@router.get("/me")
def me(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"ok": True, "user": {"username": user.get("sub")}}
PY

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

app = FastAPI(title="Greenhouse v17 Web Admin", version="2.3.0")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.get("/api/health")
def health():
    return {"ok": True, "service": "web_admin", "project": "greenhouse_v17"}

@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": "internal_error", "details": str(exc)},
    )

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(registry_router, prefix="/api/registry", tags=["registry"])
app.include_router(modes_router, prefix="/api/modes", tags=["modes"])
app.include_router(ask_router, prefix="/api/ask", tags=["ask"])
app.include_router(actions_router, prefix="/api/actions", tags=["actions"])
app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(web_router)
PY

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
        context={"request": request, "page_title": page_title},
    )

def is_auth(request: Request) -> bool:
    return bool(get_current_user_from_request(request))

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_auth(request):
        return RedirectResponse(url="/web/", status_code=302)
    return render(request, "login.html", "Greenhouse v17 — Login")

@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "dashboard.html", "Greenhouse v17 — Dashboard")

@router.get("/control", response_class=HTMLResponse)
def control_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "control.html", "Greenhouse v17 — Control")

@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "ask.html", "Greenhouse v17 — ASK")

@router.get("/modes", response_class=HTMLResponse)
def modes_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "modes.html", "Greenhouse v17 — Modes")

@router.get("/registry", response_class=HTMLResponse)
def registry_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "registry.html", "Greenhouse v17 — Registry")

@router.get("/monitoring", response_class=HTMLResponse)
def monitoring_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "monitoring.html", "Greenhouse v17 — Monitoring")

@router.get("/safety", response_class=HTMLResponse)
def safety_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "safety.html", "Greenhouse v17 — Safety")
PY

echo "== 2. patch app.js only =="
cat > "$WEB/static/app.js" <<'JS'
async function ghApi(url, options = {}) {
  const opts = { credentials: "same-origin", ...options };
  opts.headers = { ...(opts.headers || {}) };

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

echo "== 3. fill login page =="
cat > "$WEB/templates/login.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="hero-card narrow">
  <div class="hero-kicker">Web Admin Login</div>
  <h2>Вход в панель</h2>
  <p class="muted">Нормальный вход в тот же backend, без пустых разделов.</p>

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

echo "== 4. fill dashboard =="
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
    <h3>Pending</h3>
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
    <div class="card-label">Actions</div>
    <h3>Быстрые переходы</h3>
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

echo "== 5. fill ask =="
cat > "$WEB/templates/ask.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="card">
  <div class="card-label">ASK</div>
  <h3>Текущее ожидающее действие</h3>
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

echo "== 6. fill modes =="
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
  let payload = null;

  const try1 = await ghApi("/api/modes/set", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode })
  });
  if (try1.resp.ok) {
    pretty("mode-box", try1.data);
    return;
  }

  const try2 = await ghApi("/api/modes/switch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode })
  });
  payload = try2.data;
  pretty("mode-box", payload);
}

refreshMode();
</script>
{% endblock %}
HTML

echo "== 7. fill registry =="
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

echo "== 8. fill monitoring =="
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

echo "== 9. fill safety =="
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

echo "== 10. fill control with actual buttons =="
cat > "$WEB/templates/control.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="card">
  <div class="card-label">Execution</div>
  <h3>Control</h3>
  <p class="muted">Запуск действий через общий v17 pipeline.</p>
  <div id="actions-grid" class="actions-grid"></div>
  <pre id="control-result" class="result-box">Загрузка action map...</pre>
</section>
{% endblock %}

{% block scripts %}
<script>
async function executeAction(actionKey) {
  const out = document.getElementById("control-result");
  out.textContent = "Выполняю: " + actionKey;

  let res = await ghApi("/api/actions/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action_key: actionKey })
  });

  if (!res.resp.ok) {
    res = await ghApi("/api/actions/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_key: actionKey })
    });
  }

  pretty("control-result", res.data);
}

(async function () {
  const grid = document.getElementById("actions-grid");
  const out = document.getElementById("control-result");

  let mapRes = await ghApi("/api/actions/debug/action-map");
  if (!mapRes.resp.ok) {
    mapRes = await ghApi("/api/actions/action-map");
  }

  const data = mapRes.data;
  pretty("control-result", data);

  const src = data.items || data.actions || data.action_map || data || [];
  const items = Array.isArray(src)
    ? src
    : Object.entries(src).map(([key, val]) => ({ action_key: key, ...(val || {}) }));

  if (!items.length) {
    grid.innerHTML = '<div class="muted">Action map пустой или другой структуры.</div>';
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
          <button class="primary-btn" onclick="executeAction('${String(key).replaceAll("'", "\\'")}')">Выполнить</button>
        </div>
      </div>
    `;
  }).join("");
})();
</script>
{% endblock %}
HTML

echo "== 11. restart =="
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
echo "=== DASHBOARD HEADERS ==="
curl -I -s http://127.0.0.1:8081/web/ | head
echo
echo "=== LOGS ==="
journalctl -u greenhouse-web-admin.service -n 100 --no-pager
