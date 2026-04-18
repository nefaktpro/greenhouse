#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
cd "$ROOT"

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/backups/restore_missing_templates_$TS"
mkdir -p "$BACKUP_DIR"

backup_if_exists() {
  local path="$1"
  if [ -f "$path" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$path")"
    cp "$path" "$BACKUP_DIR/$path"
    echo "[backup] $path"
  fi
}

mkdir -p interfaces/web_admin/templates
mkdir -p interfaces/web_admin/static

backup_if_exists "interfaces/web_admin/templates/base.html"
backup_if_exists "interfaces/web_admin/templates/monitoring.html"
backup_if_exists "interfaces/web_admin/templates/registry.html"
backup_if_exists "interfaces/web_admin/templates/safety.html"
backup_if_exists "interfaces/web_admin/static/app.css"

cat > interfaces/web_admin/templates/base.html <<'HTML'
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{% block title %}Greenhouse v17 Web Admin{% endblock %}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/app.css">
  <style>
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0b1220;
      color: #eef2ff;
    }
    .wrap {
      max-width: 1240px;
      margin: 0 auto;
      padding: 24px;
    }
    .topbar {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-bottom: 24px;
    }
    .brand {
      font-size: 24px;
      font-weight: 700;
    }
    .nav {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .nav a {
      color: #dbeafe;
      text-decoration: none;
      background: #172036;
      border: 1px solid #26314a;
      padding: 9px 12px;
      border-radius: 12px;
    }
    .nav a:hover {
      background: #1d2944;
    }
    .card {
      background: #141c2f;
      border: 1px solid #24314d;
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 8px 24px rgba(0,0,0,.22);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
    }
    h1, h2, h3, p {
      margin-top: 0;
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #0a0f1d;
      border: 1px solid #24314d;
      border-radius: 12px;
      padding: 12px;
      min-height: 120px;
      overflow: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      text-align: left;
      padding: 8px 10px;
      border-bottom: 1px solid #24314d;
      vertical-align: top;
    }
    .muted {
      color: #9fb0d1;
    }
    .ok { color: #86efac; }
    .warn { color: #fcd34d; }
    .bad { color: #fca5a5; }
    button {
      cursor: pointer;
      padding: 10px 14px;
      border-radius: 10px;
      border: 0;
      font-weight: 600;
      background: #8b5cf6;
      color: white;
    }
    button.secondary {
      background: #334155;
    }
  </style>
  {% block head_extra %}{% endblock %}
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div class="brand">Greenhouse v17 Web Admin</div>
      <nav class="nav">
        <a href="/web/">Главная</a>
        <a href="/web/monitoring">Мониторинг</a>
        <a href="/web/registry">Реестр</a>
        <a href="/web/safety">Safety</a>
        <a href="/web/modes">Режимы</a>
        <a href="/web/ask">ASK</a>
        <a href="/web/control">Control</a>
      </nav>
    </div>

    {% block content %}{% endblock %}
  </div>
  {% block scripts %}{% endblock %}
</body>
</html>
HTML

cat > interfaces/web_admin/templates/monitoring.html <<'HTML'
{% extends "base.html" %}
{% block title %}Мониторинг — Greenhouse v17{% endblock %}

{% block content %}
<h1>Мониторинг</h1>
<p class="muted">Обзор состояния и safety-слоя.</p>

<div class="grid">
  <section class="card">
    <h2>Overview</h2>
    <pre id="overviewBox">Загрузка...</pre>
  </section>

  <section class="card">
    <h2>Safety</h2>
    <pre id="safetyBox">Загрузка...</pre>
  </section>
</div>
{% endblock %}

{% block scripts %}
<script>
async function loadJson(url, targetId) {
  try {
    const r = await fetch(url);
    const data = await r.json();
    document.getElementById(targetId).textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    document.getElementById(targetId).textContent = "Ошибка загрузки: " + e;
  }
}

loadJson('/api/monitoring/overview', 'overviewBox');
loadJson('/api/monitoring/safety', 'safetyBox');
</script>
{% endblock %}
HTML

cat > interfaces/web_admin/templates/registry.html <<'HTML'
{% extends "base.html" %}
{% block title %}Реестр — Greenhouse v17{% endblock %}

{% block content %}
<h1>Реестр</h1>
<p class="muted">Устройства и capability-слой.</p>

<div class="grid">
  <section class="card">
    <h2>Устройства</h2>
    <div style="overflow:auto;">
      <table id="devicesTable">
        <thead>
          <tr>
            <th>ID</th>
            <th>Имя</th>
            <th>Тип</th>
            <th>Зона</th>
            <th>Entity</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <section class="card">
    <h2>Capabilities</h2>
    <pre id="capBox">Загрузка...</pre>
  </section>
</div>
{% endblock %}

{% block scripts %}
<script>
async function loadDevices() {
  const tbody = document.querySelector('#devicesTable tbody');
  try {
    const r = await fetch('/api/registry/devices');
    const data = await r.json();
    const items = data.items || data.devices || [];
    tbody.innerHTML = '';
    for (const item of items.slice(0, 200)) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${item.device_id ?? item.id ?? ''}</td>
        <td>${item.name ?? ''}</td>
        <td>${item.type ?? ''}</td>
        <td>${item.zone ?? item.location ?? ''}</td>
        <td>${item.entity_id ?? ''}</td>
      `;
      tbody.appendChild(tr);
    }
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="muted">Нет данных</td></tr>';
    }
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5">Ошибка: ${e}</td></tr>`;
  }
}

async function loadCaps() {
  try {
    const r = await fetch('/api/registry/capabilities');
    const data = await r.json();
    document.getElementById('capBox').textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    document.getElementById('capBox').textContent = "Ошибка загрузки: " + e;
  }
}

loadDevices();
loadCaps();
</script>
{% endblock %}
HTML

cat > interfaces/web_admin/templates/safety.html <<'HTML'
{% extends "base.html" %}
{% block title %}Safety — Greenhouse v17{% endblock %}

{% block content %}
<h1>Safety</h1>
<p class="muted">Критичные состояния и текущая safety-сводка.</p>

<div class="grid">
  <section class="card">
    <h2>Safety API</h2>
    <pre id="safetyApiBox">Загрузка...</pre>
  </section>

  <section class="card">
    <h2>Подсказка</h2>
    <p>При пожарной логике сначала отключается <strong>щиток веранда</strong>, затем резервный выключатель веранды. Это закреплённое правило проекта. :contentReference[oaicite:0]{index=0}</p>
  </section>
</div>
{% endblock %}

{% block scripts %}
<script>
async function loadSafety() {
  try {
    const r = await fetch('/api/monitoring/safety');
    const data = await r.json();
    document.getElementById('safetyApiBox').textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    document.getElementById('safetyApiBox').textContent = "Ошибка загрузки: " + e;
  }
}

loadSafety();
</script>
{% endblock %}
HTML

if [ ! -f interfaces/web_admin/static/app.css ]; then
  cat > interfaces/web_admin/static/app.css <<'CSS'
/* placeholder file */
CSS
fi

sudo systemctl restart greenhouse-web-admin.service
sleep 2

echo
echo "=== QUICK CHECKS ==="
for path in /web/ /web/monitoring /web/registry /web/safety /web/modes /web/ask /web/control; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8081$path" || true)
  echo "$path -> $code"
done
