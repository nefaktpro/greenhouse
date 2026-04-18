#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
WEB="$ROOT/interfaces/web_admin"

mkdir -p "$WEB/routes" "$WEB/templates" "$WEB/static"

ts="$(date +%F_%H-%M-%S)"
mkdir -p "$ROOT/backups/rebuild_clean_web_admin_$ts"

cp -a "$WEB" "$ROOT/backups/rebuild_clean_web_admin_$ts/" 2>/dev/null || true

echo "== rewrite api.py =="
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
    version="1.0.0",
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

echo "== rewrite routes/web.py =="
cat > "$WEB/routes/web.py" <<'PY'
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/web", tags=["web"])

def render(request: Request, template_name: str, page_title: str):
    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "page_title": page_title,
        },
    )

@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return render(request, "dashboard.html", "Greenhouse v17 — Dashboard")

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html", "Greenhouse v17 — Login")

@router.get("/control", response_class=HTMLResponse)
def control_page(request: Request):
    return render(request, "control.html", "Greenhouse v17 — Control")

@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    return render(request, "ask.html", "Greenhouse v17 — ASK")

@router.get("/modes", response_class=HTMLResponse)
def modes_page(request: Request):
    return render(request, "modes.html", "Greenhouse v17 — Modes")

@router.get("/registry", response_class=HTMLResponse)
def registry_page(request: Request):
    return render(request, "registry.html", "Greenhouse v17 — Registry")

@router.get("/monitoring", response_class=HTMLResponse)
def monitoring_page(request: Request):
    return render(request, "monitoring.html", "Greenhouse v17 — Monitoring")

@router.get("/safety", response_class=HTMLResponse)
def safety_page(request: Request):
    return render(request, "safety.html", "Greenhouse v17 — Safety")
PY

echo "== write static/app.js =="
cat > "$WEB/static/app.js" <<'JS'
function ghToken() {
  return localStorage.getItem("gh_token");
}

function ghHeaders(json = true) {
  const headers = {};
  const token = ghToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

async function ghApi(url, options = {}) {
  const opts = { ...options };
  if (!opts.headers) opts.headers = ghHeaders(!opts.formData);
  if (opts.formData) delete opts.headers["Content-Type"];

  const resp = await fetch(url, opts);
  let data = null;
  try {
    data = await resp.json();
  } catch (_) {
    data = { ok: false, error: "invalid_json_response" };
  }

  if (resp.status === 401) {
    localStorage.removeItem("gh_token");
    if (!location.pathname.endsWith("/web/login")) {
      window.location.href = "/web/login";
    }
  }

  return { resp, data };
}

function pretty(elId, data) {
  const el = document.getElementById(elId);
  if (el) el.textContent = JSON.stringify(data, null, 2);
}

function logout() {
  localStorage.removeItem("gh_token");
  window.location.href = "/web/login";
}

function requireAuth() {
  if (!ghToken()) {
    window.location.href = "/web/login";
    return false;
  }
  return true;
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
JS

echo "== write static/app.css =="
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

button, .primary-btn, .ghost-btn-link {
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

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: 14px 0 0 0;
}

.kpi {
  background: rgba(5, 12, 23, 0.95);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 14px;
}

.kpi-title {
  color: var(--muted);
  font-size: 13px;
  margin-bottom: 6px;
}

.kpi-value {
  font-size: 28px;
  font-weight: 800;
}

.table-wrap {
  overflow: auto;
  margin-top: 12px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  text-align: left;
  padding: 12px 10px;
  border-bottom: 1px solid rgba(94,143,255,0.14);
  vertical-align: top;
}

.badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.badge.ok { background: rgba(55,201,120,0.14); color: #7be3a8; }
.badge.warn { background: rgba(255,182,72,0.14); color: #ffd089; }
.badge.danger { background: rgba(255,95,116,0.14); color: #ff9aa9; }

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

echo "== write templates/base.html =="
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
      <div class="sidebar-note">
        Telegram + Web работают поверх одного v17 Core / Registry / Execution контура.
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

echo "== write templates/login.html =="
cat > "$WEB/templates/login.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="hero-card narrow">
  <div class="hero-kicker">Локальный защищённый вход</div>
  <h2>Вход в Web Admin</h2>
  <p class="muted">Логин идёт через текущий API и сохраняет bearer token в localStorage.</p>

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
    body: JSON.stringify({
      username: document.getElementById("username").value,
      password: document.getElementById("password").value
    })
  });

  if (!resp.ok || !data.access_token) {
    result.textContent = JSON.stringify(data, null, 2);
    return;
  }

  localStorage.setItem("gh_token", data.access_token);
  result.textContent = "Успешный вход";
  window.location.href = "/web/";
});
</script>
{% endblock %}
HTML

echo "== write templates/dashboard.html =="
cat > "$WEB/templates/dashboard.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="cards-grid">
  <article class="card">
    <div class="card-label">Система</div>
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
    <h3>Обзор</h3>
    <pre id="overview-box" class="result-box">Загрузка...</pre>
  </article>

  <article class="card">
    <div class="card-label">Safety</div>
    <h3>Сводка безопасности</h3>
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
    </div>
  </article>

  <article class="card">
    <div class="card-label">Состояние</div>
    <h3>Health</h3>
    <pre id="health-box" class="result-box">Загрузка...</pre>
  </article>
</section>
{% endblock %}

{% block scripts %}
<script>
(async function loadDashboard() {
  if (!requireAuth()) return;

  const [health, mode, ask, overview, safety] = await Promise.all([
    ghApi("/api/health", { method: "GET", headers: ghHeaders(false) }),
    ghApi("/api/modes/current", { method: "GET", headers: ghHeaders(false) }),
    ghApi("/api/ask/current", { method: "GET", headers: ghHeaders(false) }),
    ghApi("/api/monitoring/overview", { method: "GET", headers: ghHeaders(false) }),
    ghApi("/api/monitoring/safety", { method: "GET", headers: ghHeaders(false) }),
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

echo "== write templates/control.html =="
cat > "$WEB/templates/control.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="card">
  <div class="card-label">Execution</div>
  <h3>Control</h3>
  <p class="muted">
    Страница читает action map и позволяет запускать действия через общий API.
  </p>
  <div id="actions-grid" class="actions-grid"></div>
  <pre id="control-result" class="result-box">Загрузка action map...</pre>
</section>
{% endblock %}

{% block scripts %}
<script>
async function runAction(actionKey) {
  const result = document.getElementById("control-result");
  result.textContent = "Выполняю: " + actionKey;

  const { data } = await ghApi("/api/actions/execute", {
    method: "POST",
    body: JSON.stringify({ action_key: actionKey })
  });

  pretty("control-result", data);
}

(async function loadControl() {
  if (!requireAuth()) return;

  const result = document.getElementById("control-result");
  const grid = document.getElementById("actions-grid");

  const { data } = await ghApi("/api/actions/debug/action-map", {
    method: "GET",
    headers: ghHeaders(false)
  });

  pretty("control-result", data);

  const items = data.items || data.actions || data.action_map || [];
  const pairs = Array.isArray(items)
    ? items
    : Object.entries(items).map(([key, val]) => ({ action_key: key, ...(val || {}) }));

  if (!pairs.length) {
    grid.innerHTML = '<div class="muted">Action map пустой или другой структуры.</div>';
    return;
  }

  grid.innerHTML = pairs.map((item) => {
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
          <button class="primary-btn" onclick="runAction('${esc(key)}')">Выполнить</button>
        </div>
      </div>
    `;
  }).join("");
})();
</script>
{% endblock %}
HTML

echo "== write templates/ask.html =="
cat > "$WEB/templates/ask.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<section class="cards-grid">
  <article class="card">
    <div class="card-label">ASK</div>
    <h3>Current pending</h3>
    <pre id="ask-box" class="result-box">Загрузка...</pre>
    <div class="button-row" style="margin-top:12px">
      <button class="primary-btn" onclick="confirmAsk()">Confirm</button>
      <button class="ghost-btn" onclick="cancelAsk()">Cancel</button>
      <button class="ghost-btn" onclick="refreshAsk()">Refresh</button>
    </div>
  </article>
</section>
{% endblock %}

{% block scripts %}
<script>
async function refreshAsk() {
  if (!requireAuth()) return;
  const { data } = await ghApi("/api/ask/current", {
    method: "GET",
    headers: ghHeaders(false)
  });
  pretty("ask-box", data);
}

async function confirmAsk() {
  const { data } = await ghApi("/api/ask/confirm", {
    method: "POST",
    body: JSON.stringify({})
  });
  pretty("ask-box", data);
}

async function cancelAsk() {
  const { data } = await ghApi("/api/ask/cancel", {
    method: "POST",
    body: JSON.stringify({})
  });
  pretty("ask-box", data);
}

refreshAsk();
</script>
{% endblock %}
HTML

echo "== write templates/modes.html =="
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
  if (!requireAuth()) return;
  const { data } = await ghApi("/api/modes/current", {
    method: "GET",
    headers: ghHeaders(false)
  });
  pretty("mode-box", data);
}

async function setMode(mode) {
  const { data } = await ghApi("/api/modes/set", {
    method: "POST",
    body: JSON.stringify({ mode })
  });
  pretty("mode-box", data);
}

refreshMode();
</script>
{% endblock %}
HTML

echo "== write templates/registry.html =="
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
(async function loadRegistry() {
  if (!requireAuth()) return;

  const [devices, caps] = await Promise.all([
    ghApi("/api/registry/devices", { method: "GET", headers: ghHeaders(false) }),
    ghApi("/api/registry/capabilities", { method: "GET", headers: ghHeaders(false) })
  ]);

  pretty("devices-box", devices.data);
  pretty("caps-box", caps.data);
})();
</script>
{% endblock %}
HTML

echo "== write templates/monitoring.html =="
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
(async function loadMonitoring() {
  if (!requireAuth()) return;
  const { data } = await ghApi("/api/monitoring/overview", {
    method: "GET",
    headers: ghHeaders(false)
  });
  pretty("overview-box", data);
})();
</script>
{% endblock %}
HTML

echo "== write templates/safety.html =="
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
(async function loadSafety() {
  if (!requireAuth()) return;
  const { data } = await ghApi("/api/monitoring/safety", {
    method: "GET",
    headers: ghHeaders(false)
  });
  pretty("safety-box", data);
})();
</script>
{% endblock %}
HTML

echo "== optional: create empty init if missing =="
touch "$WEB/__init__.py"
touch "$WEB/routes/__init__.py"

echo "== restart service =="
sudo systemctl restart greenhouse-web-admin.service
sleep 2
sudo systemctl status greenhouse-web-admin.service --no-pager
journalctl -u greenhouse-web-admin.service -n 80 --no-pager

echo "== done =="
echo "Open:"
echo "  http://127.0.0.1:8081/web/login"
echo "  http://127.0.0.1:8081/web/"
