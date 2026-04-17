#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/greenhouse_v17"
WEB_ROUTES="$ROOT/interfaces/web_admin/routes"
TEMPLATES="$ROOT/interfaces/web_admin/templates"
BACKUP="$ROOT/backups/web_admin_$(date +%Y%m%d_%H%M%S)_monitoring_safety"

mkdir -p "$BACKUP" "$WEB_ROUTES" "$TEMPLATES"

for f in \
  "$WEB_ROUTES/web.py" \
  "$ROOT/interfaces/web_admin/api.py" \
  "$TEMPLATES/base.html"
do
  [ -f "$f" ] && cp "$f" "$BACKUP/$(basename "$f").bak" || true
done

# 1) API routes: monitoring.py
cat > "$WEB_ROUTES/monitoring.py" <<'PY'
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Dict, List

import requests
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

ROOT = Path(os.path.expanduser("~/greenhouse_v17"))
DEVICES_CSV = ROOT / "data" / "registry" / "devices.csv"

SENSOR_TYPES = {
    "sensor", "smoke", "moisture", "binary_sensor", "battery", "tamper"
}

def _env_first(*names: str) -> str:
    for name in names:
        val = os.getenv(name)
        if val:
            return val
    return ""

def _ha_cfg() -> tuple[str, str]:
    url = _env_first(
        "HOME_ASSISTANT_URL",
        "HOME_ASSISTANT_BASE_URL",
        "HA_URL",
        "HASS_URL",
    ).rstrip("/")
    token = _env_first(
        "HOME_ASSISTANT_TOKEN",
        "HA_TOKEN",
        "HASS_TOKEN",
    )
    return url, token

def _read_registry() -> List[Dict[str, Any]]:
    if not DEVICES_CSV.exists():
        return []
    with DEVICES_CSV.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def _ha_states_map() -> Dict[str, Dict[str, Any]]:
    url, token = _ha_cfg()
    if not url or not token:
        return {}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.get(f"{url}/api/states", headers=headers, timeout=12)
        r.raise_for_status()
        data = r.json()
        return {item.get("entity_id"): item for item in data if item.get("entity_id")}
    except Exception:
        return {}

def _coerce_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    try:
        if "." in s:
            return round(float(s), 2)
        return int(s)
    except Exception:
        return s

def _monitoring_category(row: Dict[str, Any]) -> str | None:
    t = (row.get("type") or "").lower()
    zone = (row.get("zone") or "").lower()
    name = (row.get("name") or "").lower()
    role = (row.get("logical_role") or "").lower()
    notes = (row.get("notes") or "").lower()

    hay = " ".join([t, zone, name, role, notes])

    if t not in SENSOR_TYPES:
        return None
    if t in {"smoke", "moisture", "tamper", "battery", "binary_sensor"}:
        return None
    if zone in {"power_system", "water_system"}:
        return None
    if "дым" in hay or "fire" in hay or "протеч" in hay or "leak" in hay:
        return None

    if any(x in hay for x in ["co2", "voc", "pm10", "pm2", "формальдегид", "air_quality", "качество воздуха"]):
        return "air_quality"
    if any(x in hay for x in ["освещ", "illuminance", "lightsensor", "светимость", "lux", "lx"]):
        return "light"
    if "outside" in hay or "улиц" in hay or zone == "outdoor":
        return "outdoor"
    if any(x in hay for x in ["leaf", "листь", "humidity_sensor_2", "temperature_and_humidity_sensor"]):
        return "leaf_climate"
    if any(x in hay for x in ["почв", "грунт", "корн", "surface", "влажность", "temperature"]) and \
       zone in {"low_rack", "top_rack", "top_rack_window", "low_rack_window"}:
        return "soil"
    return "climate"

def _safety_category(row: Dict[str, Any]) -> str | None:
    t = (row.get("type") or "").lower()
    zone = (row.get("zone") or "").lower()
    name = (row.get("name") or "").lower()
    role = (row.get("logical_role") or "").lower()
    notes = (row.get("notes") or "").lower()
    hay = " ".join([t, zone, name, role, notes])

    if any(x in hay for x in ["smoke", "дым", "fire"]):
        return "fire"
    if any(x in hay for x in ["moisture", "протеч", "leak"]):
        return "leak"
    if any(x in hay for x in ["power", "voltage", "current", "energy", "electric", "питание", "напряжение", "ток", "мощность"]):
        return "power"
    if any(x in hay for x in ["zigbee", "gateway", "problem"]):
        return "connectivity"
    if t == "battery" and zone in {"power_system", "water_system", "veranda"}:
        return "safety_battery"
    return None

def _row_to_item(row: Dict[str, Any], states: Dict[str, Dict[str, Any]], category: str) -> Dict[str, Any]:
    entity_id = row.get("entity_id") or ""
    state_obj = states.get(entity_id, {}) if entity_id else {}
    state = state_obj.get("state")
    attrs = state_obj.get("attributes", {}) if isinstance(state_obj, dict) else {}
    friendly = attrs.get("friendly_name")
    available = state not in (None, "", "unavailable", "unknown")

    return {
        "device_id": row.get("device_id"),
        "name": row.get("name") or friendly or entity_id,
        "type": row.get("type"),
        "entity_id": entity_id,
        "zone": row.get("zone"),
        "location": row.get("location"),
        "logical_role": row.get("logical_role"),
        "unit": row.get("unit") or attrs.get("unit_of_measurement") or "",
        "category": category,
        "value": _coerce_value(state),
        "raw_state": state,
        "available": bool(available),
        "last_updated": state_obj.get("last_updated"),
        "notes": row.get("notes") or "",
    }

def _build(kind: str) -> Dict[str, Any]:
    rows = _read_registry()
    states = _ha_states_map()
    items: List[Dict[str, Any]] = []

    for row in rows:
        if not row.get("entity_id"):
            continue
        if kind == "overview":
            category = _monitoring_category(row)
        else:
            category = _safety_category(row)
        if not category:
            continue
        items.append(_row_to_item(row, states, category))

    items.sort(key=lambda x: ((x.get("category") or ""), (x.get("device_id") or "")))

    by_cat: Dict[str, int] = {}
    for item in items:
        by_cat[item["category"]] = by_cat.get(item["category"], 0) + 1

    return {
        "ok": True,
        "kind": kind,
        "count": len(items),
        "categories": by_cat,
        "items": items,
        "ha_connected": bool(states),
    }

@router.get("/overview")
def overview():
    return JSONResponse(_build("overview"))

@router.get("/safety")
def safety():
    return JSONResponse(_build("safety"))
PY

# 2) Web pages: append routes to web.py if missing
python3 - <<'PY'
from pathlib import Path
p = Path.home() / "greenhouse_v17" / "interfaces" / "web_admin" / "routes" / "web.py"
text = p.read_text(encoding="utf-8")

append = """

@web_router.get("/monitoring", response_class=HTMLResponse)
def monitoring_page(request: Request):
    return templates.TemplateResponse("monitoring.html", {"request": request})

@web_router.get("/safety", response_class=HTMLResponse)
def safety_page(request: Request):
    return templates.TemplateResponse("safety.html", {"request": request})
"""

if '"/monitoring"' not in text:
    text = text.rstrip() + append + "\n"

p.write_text(text, encoding="utf-8")
print("web.py updated")
PY

# 3) api.py: include monitoring router if missing
python3 - <<'PY'
from pathlib import Path
p = Path.home() / "greenhouse_v17" / "interfaces" / "web_admin" / "api.py"
text = p.read_text(encoding="utf-8")

if "from interfaces.web_admin.routes.monitoring import router as monitoring_router" not in text:
    marker = "from interfaces.web_admin.routes.web import web_router"
    text = text.replace(marker, marker + "\nfrom interfaces.web_admin.routes.monitoring import router as monitoring_router")

if "app.include_router(monitoring_router)" not in text:
    text = text.rstrip() + "\napp.include_router(monitoring_router)\n"

p.write_text(text, encoding="utf-8")
print("api.py updated")
PY

# 4) base.html: add menu items if missing
python3 - <<'PY'
from pathlib import Path
p = Path.home() / "greenhouse_v17" / "interfaces" / "web_admin" / "templates" / "base.html"
text = p.read_text(encoding="utf-8")

if 'data-nav="monitoring"' not in text:
    text = text.replace(
        '        <a href="/web/registry" data-nav="registry">🗂 Registry</a>\n',
        '        <a href="/web/registry" data-nav="registry">🗂 Registry</a>\n'
        '        <a href="/web/monitoring" data-nav="monitoring">🌡 Monitoring</a>\n'
        '        <a href="/web/safety" data-nav="safety">🛡 Safety</a>\n'
    )

p.write_text(text, encoding="utf-8")
print("base.html updated")
PY

# 5) monitoring.html
cat > "$TEMPLATES/monitoring.html" <<'HTML'
{% set page_id = 'monitoring' %}
{% extends "base.html" %}

{% block title %}Greenhouse v17 — Monitoring{% endblock %}

{% block content %}
<div class="card">
  <div class="eyebrow">Monitoring</div>
  <h2 style="font-size:24px;">Климат, почва, воздух, CO₂, улица, свет</h2>
  <input id="monitorSearch" class="search" placeholder="Поиск по name / entity_id / zone / category" style="margin:16px 0;" />
  <div id="monitorMeta" class="chips" style="margin-bottom:14px;"></div>
  <div id="monitorChips" class="chips" style="margin-bottom:16px;"></div>
  <div id="monitorList" class="list">Загрузка...</div>
</div>
{% endblock %}

{% block scripts %}
<script>
  let MON_ITEMS = [];
  let MON_FILTER = "";

  function monText(x) {
    return [
      x.device_id, x.name, x.entity_id, x.zone, x.category, x.logical_role, x.location
    ].join(" ").toLowerCase();
  }

  function fmtVal(x) {
    const v = x.value ?? "—";
    return `${v}${x.unit ? " " + x.unit : ""}`;
  }

  function renderMonitoring() {
    const q = document.getElementById("monitorSearch").value.trim().toLowerCase();
    let items = MON_ITEMS.filter(x => !q || monText(x).includes(q));
    if (MON_FILTER) items = items.filter(x => x.category === MON_FILTER);

    document.getElementById("monitorMeta").innerHTML = `
      <span class="chip ok">count: ${MON_ITEMS.length}</span>
      <span class="chip">filtered: ${items.length}</span>
    `;

    const cats = [...new Set(MON_ITEMS.map(x => x.category))];
    document.getElementById("monitorChips").innerHTML =
      `<button class="btn ${!MON_FILTER ? 'btn-primary' : ''}" onclick="setMonFilter('')">Все</button>` +
      cats.map(c => `<button class="btn ${MON_FILTER===c ? 'btn-primary' : ''}" onclick="setMonFilter('${c}')">${c}</button>`).join("");

    const root = document.getElementById("monitorList");
    if (!items.length) {
      root.innerHTML = `<div class="empty">Нет датчиков по текущему фильтру.</div>`;
      return;
    }

    root.innerHTML = items.map(x => `
      <div class="row" style="align-items:flex-start;">
        <div style="width:100%;">
          <div class="name">${x.name || "—"}</div>
          <div class="sub">${x.category} · ${x.zone || "—"} · ${x.type || "—"}</div>
          <div class="kv" style="margin-top:10px;">
            <div>value</div><div>${fmtVal(x)}</div>
            <div>entity_id</div><div class="mono">${x.entity_id || "—"}</div>
            <div>location</div><div>${x.location || "—"}</div>
            <div>logical_role</div><div>${x.logical_role || "—"}</div>
            <div>available</div><div>${x.available ? "yes" : "no"}</div>
            <div>updated</div><div>${x.last_updated || "—"}</div>
          </div>
        </div>
      </div>
    `).join("");
  }

  function setMonFilter(v) {
    MON_FILTER = v;
    renderMonitoring();
  }

  async function loadMonitoring() {
    const root = document.getElementById("monitorList");
    try {
      const data = await GH.api("/api/monitoring/overview");
      MON_ITEMS = Array.isArray(data.items) ? data.items : [];
      renderMonitoring();
    } catch (e) {
      root.innerHTML = `<div class="empty">Ошибка загрузки monitoring: ${e.message}</div>`;
    }
  }

  document.getElementById("monitorSearch").addEventListener("input", renderMonitoring);
  loadMonitoring();
</script>
{% endblock %}
HTML

# 6) safety.html
cat > "$TEMPLATES/safety.html" <<'HTML'
{% set page_id = 'safety' %}
{% extends "base.html" %}

{% block title %}Greenhouse v17 — Safety{% endblock %}

{% block content %}
<div class="card">
  <div class="eyebrow">Safety</div>
  <h2 style="font-size:24px;">Питание, пожар, протечка, safety-батарейки, связность</h2>
  <input id="safetySearch" class="search" placeholder="Поиск по name / entity_id / zone / category" style="margin:16px 0;" />
  <div id="safetyMeta" class="chips" style="margin-bottom:14px;"></div>
  <div id="safetyChips" class="chips" style="margin-bottom:16px;"></div>
  <div id="safetyList" class="list">Загрузка...</div>
</div>
{% endblock %}

{% block scripts %}
<script>
  let SAFE_ITEMS = [];
  let SAFE_FILTER = "";

  function safeText(x) {
    return [
      x.device_id, x.name, x.entity_id, x.zone, x.category, x.logical_role, x.location
    ].join(" ").toLowerCase();
  }

  function fmtVal(x) {
    const v = x.value ?? "—";
    return `${v}${x.unit ? " " + x.unit : ""}`;
  }

  function renderSafety() {
    const q = document.getElementById("safetySearch").value.trim().toLowerCase();
    let items = SAFE_ITEMS.filter(x => !q || safeText(x).includes(q));
    if (SAFE_FILTER) items = items.filter(x => x.category === SAFE_FILTER);

    document.getElementById("safetyMeta").innerHTML = `
      <span class="chip ok">count: ${SAFE_ITEMS.length}</span>
      <span class="chip">filtered: ${items.length}</span>
    `;

    const cats = [...new Set(SAFE_ITEMS.map(x => x.category))];
    document.getElementById("safetyChips").innerHTML =
      `<button class="btn ${!SAFE_FILTER ? 'btn-primary' : ''}" onclick="setSafeFilter('')">Все</button>` +
      cats.map(c => `<button class="btn ${SAFE_FILTER===c ? 'btn-primary' : ''}" onclick="setSafeFilter('${c}')">${c}</button>`).join("");

    const root = document.getElementById("safetyList");
    if (!items.length) {
      root.innerHTML = `<div class="empty">Нет safety-данных по текущему фильтру.</div>`;
      return;
    }

    root.innerHTML = items.map(x => `
      <div class="row" style="align-items:flex-start;">
        <div style="width:100%;">
          <div class="name">${x.name || "—"}</div>
          <div class="sub">${x.category} · ${x.zone || "—"} · ${x.type || "—"}</div>
          <div class="kv" style="margin-top:10px;">
            <div>value</div><div>${fmtVal(x)}</div>
            <div>entity_id</div><div class="mono">${x.entity_id || "—"}</div>
            <div>location</div><div>${x.location || "—"}</div>
            <div>logical_role</div><div>${x.logical_role || "—"}</div>
            <div>available</div><div>${x.available ? "yes" : "no"}</div>
            <div>updated</div><div>${x.last_updated || "—"}</div>
          </div>
        </div>
      </div>
    `).join("");
  }

  function setSafeFilter(v) {
    SAFE_FILTER = v;
    renderSafety();
  }

  async function loadSafety() {
    const root = document.getElementById("safetyList");
    try {
      const data = await GH.api("/api/monitoring/safety");
      SAFE_ITEMS = Array.isArray(data.items) ? data.items : [];
      renderSafety();
    } catch (e) {
      root.innerHTML = `<div class="empty">Ошибка загрузки safety: ${e.message}</div>`;
    }
  }

  document.getElementById("safetySearch").addEventListener("input", renderSafety);
  loadSafety();
</script>
{% endblock %}
HTML

echo "Patch applied. Backups: $BACKUP"
