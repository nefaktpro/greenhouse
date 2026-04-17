#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
TPL="$ROOT/interfaces/web_admin/templates"
BACKUP_DIR="$ROOT/backups/web_admin_$(date +%Y%m%d_%H%M%S)_patch1"

mkdir -p "$BACKUP_DIR"
mkdir -p "$TPL"

for f in base.html login.html dashboard.html modes.html ask.html control.html; do
  [ -f "$TPL/$f" ] && cp "$TPL/$f" "$BACKUP_DIR/$f.bak" || true
done

cat > "$TPL/base.html" <<'HTML'
{% set page_id = page_id|default('page') %}
{% set require_auth = require_auth|default('1') %}
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Greenhouse v17 — Web Admin</title>
  <style>
    :root{
      --bg:#061228;
      --bg2:#081a36;
      --panel:#0d1b33;
      --panel2:#0a1730;
      --line:#213a63;
      --text:#eaf1ff;
      --muted:#9fb2d4;
      --green:#69d88e;
      --green2:#57c77d;
      --danger:#ff6b6b;
      --warn:#ffd166;
      --chip:#112443;
      --shadow:0 16px 50px rgba(0,0,0,.28);
      --radius:22px;
    }
    *{box-sizing:border-box}
    html,body{margin:0;padding:0;background:
      radial-gradient(circle at top, #08265b 0%, #061228 42%, #041022 100%);
      color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Arial,sans-serif}
    a{color:inherit;text-decoration:none}
    .app{display:grid;grid-template-columns:300px 1fr;min-height:100vh}
    .sidebar{
      border-right:1px solid var(--line);
      padding:22px 18px;
      background:linear-gradient(180deg,rgba(5,18,40,.96),rgba(4,14,31,.94));
    }
    .brand{margin-bottom:24px}
    .brand h1{font-size:28px;line-height:1.05;margin:0 0 4px 0;font-weight:800;letter-spacing:.3px}
    .brand .sub{font-size:18px;color:var(--muted)}
    .nav{display:flex;flex-direction:column;gap:14px;margin-top:28px}
    .nav a{
      display:flex;align-items:center;gap:12px;
      min-height:66px;padding:0 18px;border:1px solid var(--line);
      border-radius:20px;background:rgba(15,28,52,.88);
      font-size:18px;font-weight:700;transition:.18s ease;
      box-shadow:inset 0 0 0 1px rgba(255,255,255,.02);
    }
    .nav a:hover{transform:translateY(-1px);border-color:#3a5d96}
    .nav a.active{border-color:#7ea8ff;background:#102343;box-shadow:0 0 0 1px rgba(126,168,255,.18)}
    .side-note{
      margin-top:34px;padding:18px;border:1px solid var(--line);border-radius:22px;
      background:rgba(17,31,56,.82)
    }
    .side-note h3{margin:0 0 12px 0;font-size:20px}
    .side-note p{margin:0;color:var(--muted);font-size:15px;line-height:1.45}
    .main{padding:24px 26px 34px 26px}
    .topbar{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px}
    .page-title{font-size:34px;line-height:1.1;margin:0;font-weight:800}
    .top-actions{display:flex;gap:12px;align-items:center}
    .btn{
      display:inline-flex;align-items:center;justify-content:center;
      min-height:52px;padding:0 22px;border-radius:18px;border:1px solid var(--line);
      background:#10213f;color:var(--text);font-size:16px;font-weight:800;cursor:pointer
    }
    .btn:hover{filter:brightness(1.08)}
    .btn-primary{background:linear-gradient(180deg,var(--green),var(--green2));color:#082012;border:none}
    .btn-danger{background:rgba(255,107,107,.12);border-color:rgba(255,107,107,.35);color:#ffdede}
    .btn-ghost{background:transparent}
    .layout-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
    .card{
      background:linear-gradient(180deg,rgba(18,31,55,.92),rgba(11,24,47,.90));
      border:1px solid var(--line);border-radius:30px;padding:24px;box-shadow:var(--shadow)
    }
    .card h2{margin:0 0 8px 0;font-size:20px}
    .eyebrow{
      color:var(--green);font-size:14px;font-weight:900;letter-spacing:1px;text-transform:uppercase;
      margin-bottom:10px
    }
    .muted{color:var(--muted)}
    .mono{
      font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;
      white-space:pre-wrap;word-break:break-word
    }
    .result{
      margin-top:16px;min-height:86px;border-radius:20px;padding:18px;border:1px solid var(--line);
      background:#05112a
    }
    .chips{display:flex;flex-wrap:wrap;gap:10px}
    .chip{
      display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;
      background:var(--chip);border:1px solid var(--line);font-weight:800;font-size:14px
    }
    .chip.ok{border-color:rgba(105,216,142,.35);color:#aaf3c1}
    .chip.warn{border-color:rgba(255,209,102,.35);color:#ffe6a6}
    .chip.danger{border-color:rgba(255,107,107,.35);color:#ffc1c1}
    .list{display:flex;flex-direction:column;gap:12px}
    .row{
      display:flex;align-items:center;justify-content:space-between;gap:16px;
      padding:14px 16px;border-radius:18px;border:1px solid var(--line);background:#0a1730
    }
    .row .name{font-weight:800}
    .row .sub{color:var(--muted);font-size:14px;margin-top:4px}
    .cta-grid{display:flex;flex-wrap:wrap;gap:12px}
    .modes-grid,.control-grid{display:flex;flex-wrap:wrap;gap:12px}
    .mode-btn,.action-btn{min-width:120px}
    .action-btn.on{background:linear-gradient(180deg,var(--green),var(--green2));color:#082012;border:none}
    .search{
      width:100%;min-height:52px;border-radius:18px;border:1px solid var(--line);
      background:#10213f;color:var(--text);padding:0 16px;font-size:16px
    }
    .two-col{display:grid;grid-template-columns:1.1fr .9fr;gap:20px}
    .kv{display:grid;grid-template-columns:170px 1fr;gap:8px 16px;margin-top:14px}
    .kv div:nth-child(odd){color:var(--muted)}
    .empty{
      border:1px dashed #35588a;border-radius:22px;padding:26px;text-align:left;color:var(--muted);background:#08142b
    }
    .small{font-size:14px}
    .hidden{display:none!important}
    @media (max-width: 1180px){
      .app{grid-template-columns:1fr}
      .sidebar{border-right:none;border-bottom:1px solid var(--line)}
      .layout-grid,.two-col{grid-template-columns:1fr}
    }
  </style>
</head>
<body data-page="{{ page_id }}" data-require-auth="{{ require_auth }}">
  <div class="app">
    <aside class="sidebar">
      <div class="brand">
        <h1>GREENHOUSE v17</h1>
        <div class="sub">Web Admin</div>
      </div>

      <nav class="nav">
        <a href="/" data-nav="dashboard">🏠 Dashboard</a>
        <a href="/control" data-nav="control">🎛 Control</a>
        <a href="/ask" data-nav="ask">❓ ASK</a>
        <a href="/modes" data-nav="modes">🧠 Modes</a>
        <a href="/registry" data-nav="registry">🗂 Registry</a>
        <a href="/login" data-nav="login">🔐 Login</a>
      </nav>

      <div class="side-note">
        <h3>Интерфейсы</h3>
        <p>Telegram + Web работают поверх одного v17 Core.</p>
      </div>
    </aside>

    <main class="main">
      <div class="topbar">
        <h1 class="page-title">{% block title %}Greenhouse v17{% endblock %}</h1>
        <div class="top-actions">
          <button id="logoutBtn" class="btn btn-ghost" onclick="GH.logout()">Выйти</button>
        </div>
      </div>

      {% block content %}{% endblock %}
    </main>
  </div>

  <script>
    const GH = {
      tokenKey: "gh_web_token",
      get token(){ return localStorage.getItem(this.tokenKey) || ""; },
      setToken(v){ localStorage.setItem(this.tokenKey, v); },
      clearToken(){ localStorage.removeItem(this.tokenKey); },
      headers(json=true){
        const h = {};
        if (json) h["Content-Type"] = "application/json";
        if (this.token) h["Authorization"] = `Bearer ${this.token}`;
        return h;
      },
      async api(url, opts={}){
        const finalOpts = {
          method: opts.method || "GET",
          headers: { ...(opts.headers || {}), ...this.headers(opts.json !== false) }
        };
        if (opts.body !== undefined) {
          finalOpts.body = typeof opts.body === "string" ? opts.body : JSON.stringify(opts.body);
        }
        const res = await fetch(url, finalOpts);
        const text = await res.text();
        let data = null;
        try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
        if (!res.ok) {
          const err = new Error((data && (data.detail || data.error || data.raw)) || `HTTP ${res.status}`);
          err.payload = data;
          err.status = res.status;
          throw err;
        }
        return data;
      },
      async postFirstOk(variants, body=null){
        let lastErr = null;
        for (const v of variants) {
          try {
            return await this.api(v.url, { method: v.method || "POST", body: body ?? v.body ?? undefined });
          } catch (e) {
            lastErr = e;
          }
        }
        throw lastErr || new Error("No endpoint variant succeeded");
      },
      fmtBool(v){
        return v ? "Да" : "Нет";
      },
      modeChip(mode){
        const m = (mode || "").toUpperCase();
        let cls = "chip";
        if (m === "ASK") cls += " warn";
        else if (m === "AUTO" || m === "AUTOPILOT") cls += " ok";
        return `<span class="${cls}">${m || "—"}</span>`;
      },
      renderModeFlags(flags = {}){
        return `
          <div class="chips">
            <span class="chip ${flags.execute ? 'ok' : ''}">execute: ${this.fmtBool(flags.execute)}</span>
            <span class="chip ${flags.log ? 'ok' : ''}">log: ${this.fmtBool(flags.log)}</span>
            <span class="chip ${flags.ask ? 'warn' : ''}">ask: ${this.fmtBool(flags.ask)}</span>
            <span class="chip ${flags.ai_control ? 'ok' : ''}">ai_control: ${this.fmtBool(flags.ai_control)}</span>
          </div>
        `;
      },
      renderAskCard(item){
        if (!item) {
          return `<div class="empty">Сейчас нет pending ASK. Можно запускать действия из Control или test/ask потока.</div>`;
        }
        return `
          <div class="card">
            <div class="eyebrow">Pending ASK</div>
            <h2>${item.title || item.action_key || "Без названия"}</h2>
            <div class="kv">
              <div>action_key</div><div class="mono">${item.action_key || "—"}</div>
              <div>kind</div><div>${item.kind || "—"}</div>
              <div>mode</div><div>${item.mode || "—"}</div>
              <div>created_at</div><div>${item.created_at || "—"}</div>
            </div>
          </div>
        `;
      },
      showResult(el, text, kind="info"){
        if (!el) return;
        const cls = kind === "error" ? "chip danger" : kind === "ok" ? "chip ok" : kind === "warn" ? "chip warn" : "chip";
        el.innerHTML = `<span class="${cls}">${text}</span>`;
      },
      logout(){
        this.clearToken();
        location.href = "/login";
      }
    };

    document.addEventListener("DOMContentLoaded", () => {
      const page = document.body.dataset.page || "";
      const needAuth = document.body.dataset.requireAuth === "1";
      const logoutBtn = document.getElementById("logoutBtn");

      document.querySelectorAll("[data-nav]").forEach(el => {
        if (el.dataset.nav === page) el.classList.add("active");
      });

      if (page === "login") {
        logoutBtn?.classList.add("hidden");
      } else {
        logoutBtn?.classList.remove("hidden");
      }

      if (needAuth && !GH.token) {
        location.href = "/login";
      }
    });
  </script>

  {% block scripts %}{% endblock %}
</body>
</html>
HTML

cat > "$TPL/login.html" <<'HTML'
{% set page_id = 'login' %}
{% set require_auth = '0' %}
{% extends "base.html" %}

{% block title %}Greenhouse v17 — Login{% endblock %}

{% block content %}
<div class="layout-grid" style="grid-template-columns:minmax(320px,780px);">
  <section class="card">
    <div class="eyebrow">Локальный защищённый вход</div>
    <h2 style="font-size:26px;margin-bottom:14px;">Вход в Web Admin</h2>
    <p class="muted" style="margin-top:0;">Панель управления теплицей v17. Логин идёт через текущий API.</p>

    <div class="list" style="margin-top:22px;">
      <div>
        <div class="muted" style="margin-bottom:8px;">Логин</div>
        <input id="username" class="search" autocomplete="username" placeholder="Mi" />
      </div>
      <div>
        <div class="muted" style="margin-bottom:8px;">Пароль</div>
        <input id="password" class="search" type="password" autocomplete="current-password" placeholder="••••••••" />
      </div>
      <div>
        <button id="loginBtn" class="btn btn-primary" style="width:100%;">Войти</button>
      </div>
      <div id="loginResult" class="result"></div>
    </div>
  </section>
</div>
{% endblock %}

{% block scripts %}
<script>
  const loginBtn = document.getElementById("loginBtn");
  const resultEl = document.getElementById("loginResult");

  async function doLogin() {
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    try {
      GH.showResult(resultEl, "Выполняю вход...", "warn");
      const data = await fetch("/api/auth/login", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ username, password })
      }).then(async r => {
        const t = await r.text();
        let j = {};
        try { j = t ? JSON.parse(t) : {}; } catch { j = { raw: t }; }
        if (!r.ok) throw new Error(j.detail || j.error || j.raw || `HTTP ${r.status}`);
        return j;
      });

      if (!data.access_token) throw new Error("API не вернул access_token");
      GH.setToken(data.access_token);
      GH.showResult(resultEl, "Успешный вход. Перехожу на Dashboard...", "ok");
      setTimeout(() => location.href = "/", 400);
    } catch (e) {
      GH.showResult(resultEl, `Ошибка входа: ${e.message}`, "error");
    }
  }

  loginBtn.addEventListener("click", doLogin);
  document.getElementById("password").addEventListener("keydown", (e) => {
    if (e.key === "Enter") doLogin();
  });
</script>
{% endblock %}
HTML

cat > "$TPL/dashboard.html" <<'HTML'
{% set page_id = 'dashboard' %}
{% extends "base.html" %}

{% block title %}Greenhouse v17 — Dashboard{% endblock %}

{% block content %}
<div class="chips" style="margin-bottom:18px;">
  <span id="chipMode" class="chip">Mode: ...</span>
  <span id="chipExec" class="chip">Execution: ...</span>
  <span id="chipAsk" class="chip">Pending ASK: ...</span>
  <span class="chip ok">Core: online</span>
</div>

<div class="layout-grid">
  <section class="card">
    <div class="eyebrow">Система</div>
    <h2>Текущий режим</h2>
    <div id="modeBox" class="result">Загрузка...</div>
  </section>

  <section class="card">
    <div class="eyebrow">Исполнение</div>
    <h2>Текущий ASK</h2>
    <div id="askBox" class="result">Загрузка...</div>
  </section>

  <section class="card">
    <div class="eyebrow">Возможности</div>
    <h2>Что уже есть</h2>
    <div class="list" style="margin-top:14px;">
      <div class="row"><div><div class="name">ASK current / confirm / cancel</div></div></div>
      <div class="row"><div><div class="name">Режимы системы</div></div></div>
      <div class="row"><div><div class="name">Registry / actions / capabilities / scenarios</div></div></div>
      <div class="row"><div><div class="name">Execution + verify через общий v17 pipeline</div></div></div>
      <div class="row"><div><div class="name">Telegram и Web поверх одного контура</div></div></div>
    </div>
  </section>

  <section class="card">
    <div class="eyebrow">Навигация</div>
    <h2>Быстрые действия</h2>
    <div class="cta-grid" style="margin-top:14px;">
      <a class="btn" href="/control">Открыть Control</a>
      <a class="btn" href="/ask">Открыть ASK</a>
      <a class="btn" href="/modes">Modes</a>
      <a class="btn" href="/registry">Registry</a>
    </div>
  </section>
</div>
{% endblock %}

{% block scripts %}
<script>
  async function loadDashboard() {
    const modeBox = document.getElementById("modeBox");
    const askBox = document.getElementById("askBox");
    try {
      const [mode, ask] = await Promise.all([
        GH.api("/api/modes/current"),
        GH.api("/api/ask/current")
      ]);

      document.getElementById("chipMode").outerHTML =
        `<span id="chipMode" class="chip">Mode: ${(mode.mode || "—").toUpperCase()}</span>`;
      document.getElementById("chipExec").outerHTML =
        `<span id="chipExec" class="chip ${mode.flags?.execute ? "ok" : ""}">Execution: ${GH.fmtBool(!!mode.flags?.execute)}</span>`;
      document.getElementById("chipAsk").outerHTML =
        `<span id="chipAsk" class="chip ${ask.has_pending ? "warn" : ""}">Pending ASK: ${ask.has_pending ? "yes" : "no"}</span>`;

      modeBox.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px;">
          <div style="font-size:22px;font-weight:800;">${(mode.mode || "—").toUpperCase()}</div>
          ${GH.modeChip(mode.mode)}
        </div>
        ${GH.renderModeFlags(mode.flags || {})}
      `;

      askBox.innerHTML = ask.has_pending
        ? GH.renderAskCard(ask.item)
        : `<div class="empty">Сейчас нет pending ASK. Это хорошо для спокойного состояния системы.</div>`;
    } catch (e) {
      modeBox.textContent = `Ошибка: ${e.message}`;
      askBox.textContent = `Ошибка: ${e.message}`;
    }
  }
  loadDashboard();
</script>
{% endblock %}
HTML

cat > "$TPL/modes.html" <<'HTML'
{% set page_id = 'modes' %}
{% extends "base.html" %}

{% block title %}Greenhouse v17 — Modes{% endblock %}

{% block content %}
<div class="card">
  <div class="eyebrow">Modes</div>
  <h2 style="font-size:24px;">Управление режимами системы</h2>

  <div class="modes-grid" style="margin:18px 0 16px 0;">
    <button class="btn mode-btn" onclick="loadMode()">Обновить</button>
    <button class="btn mode-btn" onclick="setMode('MANUAL')">MANUAL</button>
    <button class="btn mode-btn" onclick="setMode('TEST')">TEST</button>
    <button class="btn mode-btn" onclick="setMode('ASK')">ASK</button>
    <button class="btn mode-btn" onclick="setMode('AUTO')">AUTO</button>
    <button class="btn mode-btn" onclick="setMode('AUTOPILOT')">AUTOPILOT</button>
  </div>

  <div id="modeHuman" class="result">Загрузка...</div>
  <div id="modeResult" class="result"></div>
</div>
{% endblock %}

{% block scripts %}
<script>
  async function loadMode() {
    const box = document.getElementById("modeHuman");
    try {
      const mode = await GH.api("/api/modes/current");
      box.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px;">
          <div style="font-size:22px;font-weight:800;">${(mode.mode || "—").toUpperCase()}</div>
          ${GH.modeChip(mode.mode)}
        </div>
        ${GH.renderModeFlags(mode.flags || {})}
        <div class="kv">
          <div>name</div><div>${mode.flags?.name || mode.mode || "—"}</div>
          <div>mode</div><div>${mode.mode || "—"}</div>
        </div>
      `;
    } catch (e) {
      box.textContent = `Ошибка загрузки режима: ${e.message}`;
    }
  }

  async function setMode(mode) {
    const result = document.getElementById("modeResult");
    try {
      GH.showResult(result, `Переключаю в ${mode}...`, "warn");
      const data = await GH.postFirstOk([
        { url: `/api/modes/set/${mode}` },
        { url: `/api/modes/${mode}` },
        { url: `/api/modes/set`, body: { mode } }
      ]);
      GH.showResult(result, `Режим переключён: ${data.mode || mode}`, "ok");
      await loadMode();
    } catch (e) {
      GH.showResult(result, `Ошибка переключения режима: ${e.message}`, "error");
    }
  }

  loadMode();
</script>
{% endblock %}
HTML

cat > "$TPL/ask.html" <<'HTML'
{% set page_id = 'ask' %}
{% extends "base.html" %}

{% block title %}Greenhouse v17 — ASK{% endblock %}

{% block content %}
<div class="two-col">
  <section class="card">
    <div class="eyebrow">ASK</div>
    <h2 style="font-size:24px;">Pending действие</h2>
    <div class="cta-grid" style="margin:18px 0 16px 0;">
      <button class="btn" onclick="loadAsk()">Обновить</button>
      <button class="btn btn-primary" onclick="confirmAsk()">Подтвердить</button>
      <button class="btn btn-danger" onclick="cancelAsk()">Отменить</button>
    </div>
    <div id="askHuman" class="result">Загрузка...</div>
  </section>

  <section class="card">
    <div class="eyebrow">Execution</div>
    <h2 style="font-size:24px;">Результат</h2>
    <div class="empty small" style="margin-bottom:16px;">
      В режиме ASK действие сначала попадает в pending, а исполняется только после confirm.
    </div>
    <div id="askResult" class="result">Жду действия...</div>
  </section>
</div>
{% endblock %}

{% block scripts %}
<script>
  async function loadAsk() {
    const box = document.getElementById("askHuman");
    try {
      const ask = await GH.api("/api/ask/current");
      if (!ask.has_pending) {
        box.innerHTML = `<div class="empty">Сейчас нет pending ASK.</div>`;
        return;
      }
      box.innerHTML = GH.renderAskCard(ask.item);
    } catch (e) {
      box.textContent = `Ошибка загрузки ASK: ${e.message}`;
    }
  }

  async function confirmAsk() {
    const result = document.getElementById("askResult");
    try {
      GH.showResult(result, "Подтверждаю ASK...", "warn");
      const data = await GH.api("/api/ask/confirm", { method: "POST", body: {} });
      GH.showResult(result, `ASK подтверждён. ${JSON.stringify(data)}`, "ok");
      await loadAsk();
    } catch (e) {
      GH.showResult(result, `Ошибка confirm: ${e.message}`, "error");
    }
  }

  async function cancelAsk() {
    const result = document.getElementById("askResult");
    try {
      GH.showResult(result, "Отменяю ASK...", "warn");
      const data = await GH.api("/api/ask/cancel", { method: "POST", body: {} });
      GH.showResult(result, `ASK отменён. ${JSON.stringify(data)}`, "ok");
      await loadAsk();
    } catch (e) {
      GH.showResult(result, `Ошибка cancel: ${e.message}`, "error");
    }
  }

  loadAsk();
</script>
{% endblock %}
HTML

cat > "$TPL/control.html" <<'HTML'
{% set page_id = 'control' %}
{% extends "base.html" %}

{% block title %}Greenhouse v17 — Control{% endblock %}

{% block content %}
<div class="two-col">
  <section class="card">
    <div class="eyebrow">Control</div>
    <h2 style="font-size:24px;">Тестовые действия через v17 execution</h2>

    <div class="control-grid" style="margin:18px 0 16px 0;flex-direction:column;align-items:flex-start;">
      <button class="btn action-btn on" onclick="runAction('fan_top_on')">Верх: включить вентиляторы</button>
      <button class="btn action-btn" onclick="runAction('fan_top_off')">Верх: выключить вентиляторы</button>
      <button class="btn action-btn on" onclick="runAction('fan_bottom_on')">Низ: включить вентиляторы</button>
      <button class="btn action-btn" onclick="runAction('fan_bottom_off')">Низ: выключить вентиляторы</button>
    </div>

    <div id="controlResult" class="result">Нажми кнопку действия.</div>
  </section>

  <section class="card">
    <div class="eyebrow">Mode + ASK</div>
    <h2 style="font-size:24px;">Состояние перед тестом</h2>
    <div class="cta-grid" style="margin:18px 0 16px 0;">
      <button class="btn" onclick="loadControlState()">Обновить состояние</button>
    </div>
    <div id="controlState" class="result">Загрузка...</div>
  </section>
</div>
{% endblock %}

{% block scripts %}
<script>
  async function loadControlState() {
    const box = document.getElementById("controlState");
    try {
      const [mode, ask] = await Promise.all([
        GH.api("/api/modes/current"),
        GH.api("/api/ask/current")
      ]);
      box.innerHTML = `
        <div style="margin-bottom:14px;">
          <div class="muted" style="margin-bottom:8px;">Текущий режим</div>
          <div style="font-size:22px;font-weight:800;">${(mode.mode || "—").toUpperCase()}</div>
          ${GH.renderModeFlags(mode.flags || {})}
        </div>
        <div>
          <div class="muted" style="margin-bottom:8px;">ASK статус</div>
          ${ask.has_pending ? GH.renderAskCard(ask.item) : `<div class="empty">Pending ASK нет.</div>`}
        </div>
      `;
    } catch (e) {
      box.textContent = `Ошибка загрузки состояния: ${e.message}`;
    }
  }

  async function runAction(actionKey) {
    const result = document.getElementById("controlResult");
    try {
      GH.showResult(result, `Отправляю ${actionKey}...`, "warn");
      const data = await GH.postFirstOk([
        { url: `/api/actions/${actionKey}` },
        { url: `/api/control/${actionKey}` },
        { url: `/api/actions/run`, body: { action_key: actionKey } }
      ]);
      GH.showResult(result, `Ответ: ${JSON.stringify(data)}`, "ok");
      await loadControlState();
    } catch (e) {
      GH.showResult(result, `Ошибка действия ${actionKey}: ${e.message}`, "error");
    }
  }

  loadControlState();
</script>
{% endblock %}
HTML

echo "Patch 1 applied."
echo "Backup: $BACKUP_DIR"
