#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$ROOT/backups/patch_control_debug_ajax_and_menu_$STAMP"

mkdir -p "$BACKUP"
cp "$ROOT/interfaces/web_admin/routes/control_debug.py" "$BACKUP/control_debug.py.bak" || true
cp "$ROOT/interfaces/web_admin/templates/control_debug.html" "$BACKUP/control_debug.html.bak" || true

if [ -f "$ROOT/interfaces/web_admin/templates/base.html" ]; then
  cp "$ROOT/interfaces/web_admin/templates/base.html" "$BACKUP/base.html.bak"
fi

cat > "$ROOT/interfaces/web_admin/routes/control_debug.py" <<'PY'
from __future__ import annotations

import csv
import os
from collections import OrderedDict
from pathlib import Path

import requests
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
REGISTRY_PATH = Path("/home/mi/greenhouse_v17/data/registry/devices.csv")


def env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def ha_base_url() -> str:
    return env_first("HOME_ASSISTANT_URL", "HA_BASE_URL", default="http://127.0.0.1:8123").rstrip("/")


def ha_token() -> str:
    return env_first("HOME_ASSISTANT_TOKEN", "HA_TOKEN", default="")


def ha_headers() -> dict[str, str]:
    token = ha_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def pick(row: dict, *keys: str) -> str:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for key in keys:
        if key in row and str(row[key]).strip():
            return str(row[key]).strip()
        lk = key.strip().lower()
        if lk in lowered and str(lowered[lk]).strip():
            return str(lowered[lk]).strip()
    return ""


def sort_id(raw: str):
    out = []
    for part in str(raw or "").split("."):
        try:
            out.append((0, int(part)))
        except Exception:
            out.append((1, part))
    return tuple(out)


def load_registry_rows() -> list[dict]:
    rows: list[dict] = []
    if not REGISTRY_PATH.exists():
        return rows

    with REGISTRY_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_id = pick(row, "Entity_ID", "entity_id", "entity", "ha_entity_id")
            if not entity_id:
                continue
            rows.append(
                {
                    "id": pick(row, "ID", "DeviceID", "device_id", "id"),
                    "parent": pick(row, "Parent", "ParentID", "parent", "parent_id"),
                    "name": pick(row, "Name", "name"),
                    "type": pick(row, "Type", "type"),
                    "unit": pick(row, "Unit", "unit"),
                    "location": pick(row, "Location", "location", "zone"),
                    "logical_role": pick(row, "logical_role", "Logical_Role", "role"),
                    "entity_id": entity_id,
                    "description": pick(row, "Description", "description"),
                }
            )

    rows.sort(key=lambda x: (sort_id(x.get("id", "")), x.get("name", "")))
    return rows


def infer_ops(entity_id: str, item_type: str, name: str, logical_role: str) -> list[str]:
    domain = (entity_id.split(".", 1)[0] if "." in entity_id else "").lower()
    hint = " ".join([item_type or "", name or "", logical_role or ""]).lower()

    if domain in {"switch", "light", "fan", "input_boolean", "humidifier"}:
        return ["on", "off", "toggle"]
    if domain == "cover":
        return ["open", "close", "stop"]
    if domain == "climate":
        return ["on", "off"]
    if domain == "lock":
        return ["lock", "unlock"]
    if domain == "valve":
        return ["open", "close"]

    if any(x in hint for x in ["штор", "curtain", "cover"]):
        return ["open", "close", "stop"]
    if any(x in hint for x in ["вент", "fan", "vent"]):
        return ["on", "off", "toggle"]
    if any(x in hint for x in ["свет", "lamp", "light"]):
        return ["on", "off", "toggle"]
    if any(x in hint for x in ["увлаж", "humid"]):
        return ["on", "off", "toggle"]
    if any(x in hint for x in ["полив", "насос", "pump", "клапан", "valve"]):
        return ["on", "off"]
    if any(x in hint for x in ["щит", "реле", "розет", "power", "relay", "switch"]):
        return ["on", "off", "toggle"]

    return []


def group_name(entity_id: str, item_type: str, name: str, logical_role: str) -> str:
    domain = (entity_id.split(".", 1)[0] if "." in entity_id else "").lower()
    hint = " ".join([item_type or "", name or "", logical_role or ""]).lower()

    if domain == "cover" or any(x in hint for x in ["штор", "curtain", "cover"]):
        return "Шторы / Cover"
    if domain == "fan" or any(x in hint for x in ["вент", "fan", "vent"]):
        return "Вентиляция"
    if domain in {"climate", "humidifier"} or any(x in hint for x in ["увлаж", "обогрев", "термостат", "climate"]):
        return "Климат / Увлажнение / Обогрев"
    if domain == "light" or any(x in hint for x in ["свет", "lamp", "light"]):
        return "Свет"
    if domain in {"switch", "input_boolean"} or any(x in hint for x in ["щит", "реле", "розет", "power", "relay", "switch"]):
        return "Питание / Реле / Розетки"
    if domain == "valve" or any(x in hint for x in ["полив", "насос", "pump", "клапан", "valve"]):
        return "Полив / Насосы / Клапаны"
    return "Мониторинг / Без управления"


def get_state(entity_id: str) -> dict:
    token = ha_token()
    if not token:
        return {"entity_id": entity_id, "state": "unknown", "error": "HA token not found"}

    try:
        r = requests.get(f"{ha_base_url()}/api/states/{entity_id}", headers=ha_headers(), timeout=20)
        r.raise_for_status()
        data = r.json()
        return {
            "entity_id": entity_id,
            "state": data.get("state", "unknown"),
            "last_changed": data.get("last_changed", ""),
            "last_updated": data.get("last_updated", ""),
            "attributes": data.get("attributes", {}),
        }
    except Exception as e:
        return {"entity_id": entity_id, "state": "unknown", "error": str(e)}


def load_states() -> dict[str, dict]:
    token = ha_token()
    if not token:
        return {}

    try:
        r = requests.get(f"{ha_base_url()}/api/states", headers=ha_headers(), timeout=20)
        r.raise_for_status()
        result = {}
        for item in r.json():
            eid = item.get("entity_id")
            if eid:
                result[eid] = item
        return result
    except Exception:
        return {}


def build_groups() -> list[dict]:
    rows = load_registry_rows()
    states = load_states()
    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for title in [
        "Питание / Реле / Розетки",
        "Свет",
        "Шторы / Cover",
        "Вентиляция",
        "Климат / Увлажнение / Обогрев",
        "Полив / Насосы / Клапаны",
        "Мониторинг / Без управления",
    ]:
        groups[title] = []

    for item in rows:
        ops = infer_ops(item["entity_id"], item["type"], item["name"], item["logical_role"])
        title = group_name(item["entity_id"], item["type"], item["name"], item["logical_role"])
        state_obj = states.get(item["entity_id"], {})
        groups[title].append(
            {
                **item,
                "ops": ops,
                "state": state_obj.get("state", "unknown"),
            }
        )

    return [{"title": k, "rows": v} for k, v in groups.items() if v]


def call_ha(entity_id: str, operation: str) -> dict:
    if not ha_token():
        return {"ok": False, "error": "HA token not found in environment"}

    domain = entity_id.split(".", 1)[0].lower()
    op = operation.lower().strip()

    if domain in {"sensor", "binary_sensor", "camera", "number", "select"}:
        return {"ok": False, "error": f"{domain} is read-only"}

    if op == "on":
        service = "turn_on"
    elif op == "off":
        service = "turn_off"
    elif op == "toggle":
        service = "toggle"
    elif op == "open":
        service = "open_cover" if domain == "cover" else "open_valve"
    elif op == "close":
        service = "close_cover" if domain == "cover" else "close_valve"
    elif op == "stop":
        service = "stop_cover"
    elif op in {"lock", "unlock"}:
        service = op
    else:
        return {"ok": False, "error": f"unsupported operation: {operation}"}

    try:
        r = requests.post(
            f"{ha_base_url()}/api/services/{domain}/{service}",
            headers=ha_headers(),
            json={"entity_id": entity_id},
            timeout=20,
        )
        r.raise_for_status()
        return {"ok": True, "service": f"{domain}.{service}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/web/control-debug", response_class=HTMLResponse)
def control_debug_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="control_debug.html",
        context={
            "request": request,
            "groups": build_groups(),
        },
    )


@router.post("/web/control-debug/execute")
def control_debug_execute(payload: dict):
    entity_id = str(payload.get("entity_id", "")).strip()
    operation = str(payload.get("operation", "")).strip()

    if not entity_id or not operation:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "entity_id and operation are required"},
        )

    result = call_ha(entity_id, operation)
    state = get_state(entity_id)

    if result.get("ok"):
        return {
            "ok": True,
            "message": f"OK: {entity_id} -> {operation}",
            "entity_id": entity_id,
            "operation": operation,
            "state": state.get("state", "unknown"),
            "state_payload": state,
        }

    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "message": f"ERROR: {entity_id} -> {operation}",
            "error": result.get("error", "unknown"),
            "entity_id": entity_id,
            "operation": operation,
            "state": state.get("state", "unknown"),
            "state_payload": state,
        },
    )
PY

cat > "$ROOT/interfaces/web_admin/templates/control_debug.html" <<'HTML'
{% extends "base.html" %}
{% block content %}
<div style="margin-bottom:16px;padding:14px 16px;border:1px solid #444;border-radius:12px;background:#141414;">
  <h2 style="margin:0 0 8px 0;">Debug-пульт всех устройств</h2>
  <div style="opacity:.9;">Временная страница для проверки всех entity из registry по категориям.</div>
</div>

<div id="debug-flash"
     style="display:none;margin-bottom:16px;padding:12px 14px;border-radius:10px;border:1px solid #555;background:#1a1a1a;">
</div>

{% for group in groups %}
<section style="margin-bottom:22px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <h3 style="margin:0;">{{ group.title }}</h3>
    <span style="opacity:.7;">{{ group.rows|length }} шт.</span>
  </div>

  <div style="display:grid;gap:10px;">
    {% for item in group.rows %}
    <div id="card-{{ item.entity_id | replace('.', '_') }}"
         style="border:1px solid #333;border-radius:14px;padding:12px;background:#111;">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;">
        <div style="min-width:320px;flex:1;">
          <div style="font-weight:700;">{{ item.id }} — {{ item.name or item.entity_id }}</div>
          <div style="opacity:.85;font-size:14px;margin-top:4px;">{{ item.entity_id }}</div>
          <div style="opacity:.75;font-size:13px;margin-top:6px;">
            type: {{ item.type or '—' }} |
            role: {{ item.logical_role or '—' }} |
            location: {{ item.location or '—' }} |
            state: <b id="state-{{ item.entity_id | replace('.', '_') }}">{{ item.state }}</b>
          </div>
        </div>

        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          {% if item.ops %}
            {% for op in item.ops %}
            <button
              type="button"
              data-entity-id="{{ item.entity_id }}"
              data-operation="{{ op }}"
              class="debug-action-btn"
              style="cursor:pointer;padding:8px 12px;border-radius:10px;border:1px solid #4a4a4a;background:#1b1b1b;color:#fff;"
            >
              {% if op == "on" %}ВКЛ{% elif op == "off" %}ВЫКЛ{% elif op == "toggle" %}TOGGLE{% elif op == "open" %}ОТКРЫТЬ{% elif op == "close" %}ЗАКРЫТЬ{% elif op == "stop" %}СТОП{% elif op == "lock" %}LOCK{% elif op == "unlock" %}UNLOCK{% else %}{{ op|upper }}{% endif %}
            </button>
            {% endfor %}
          {% else %}
            <span style="padding:8px 12px;border-radius:10px;border:1px dashed #444;opacity:.7;">read-only</span>
          {% endif %}
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
</section>
{% endfor %}

<script>
(function () {
  const flash = document.getElementById("debug-flash");

  function showFlash(message, kind) {
    flash.style.display = "block";
    flash.textContent = message;

    if (kind === "ok") {
      flash.style.border = "1px solid #1d7a42";
      flash.style.background = "#0f2416";
    } else {
      flash.style.border = "1px solid #8a2f2f";
      flash.style.background = "#2a1212";
    }
  }

  async function handleClick(btn) {
    const entityId = btn.dataset.entityId;
    const operation = btn.dataset.operation;
    const stateId = "state-" + entityId.replaceAll(".", "_");

    const oldText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "…";

    try {
      const res = await fetch("/web/control-debug/execute", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          entity_id: entityId,
          operation: operation
        })
      });

      const data = await res.json();

      if (data.state !== undefined) {
        const stateNode = document.getElementById(stateId);
        if (stateNode) stateNode.textContent = data.state;
      }

      if (data.ok) {
        showFlash(data.message + " | state: " + (data.state || "unknown"), "ok");
      } else {
        showFlash((data.message || "ERROR") + " | " + (data.error || "unknown"), "error");
      }
    } catch (e) {
      showFlash("ERROR: request failed: " + e, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = oldText;
    }
  }

  document.querySelectorAll(".debug-action-btn").forEach((btn) => {
    btn.addEventListener("click", () => handleClick(btn));
  });
})();
</script>
{% endblock %}
HTML

python3 - <<'PY'
from pathlib import Path

base = Path("/home/mi/greenhouse_v17/interfaces/web_admin/templates/base.html")
if base.exists():
    text = base.read_text(encoding="utf-8")
    link = '<a href="/web/control-debug">🧪 Debug Control</a>'
    if link not in text:
        if '<a href="/web/ask">❓ ASK</a>' in text:
            text = text.replace('<a href="/web/ask">❓ ASK</a>', '<a href="/web/ask">❓ ASK</a>\n      ' + link)
        elif '<nav class="menu">' in text:
            text = text.replace('<nav class="menu">', '<nav class="menu">\n      ' + link)
        base.write_text(text, encoding="utf-8")
        print("base.html updated")
    else:
        print("base.html already contains debug link")
else:
    print("base.html not found, skipped menu patch")
PY

python3 -m compileall \
  "$ROOT/interfaces/web_admin/routes/control_debug.py"

sudo systemctl restart greenhouse-web-admin.service
sleep 2

echo
echo "=== STATUS ==="
sudo systemctl status greenhouse-web-admin.service --no-pager || true
echo
echo "=== OPEN ==="
echo "http://127.0.0.1:8081/web/control-debug"
