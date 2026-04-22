#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$ROOT/backups/debug_full_device_panel_$STAMP"

mkdir -p "$BACKUP"
mkdir -p "$ROOT/interfaces/web_admin/routes"
mkdir -p "$ROOT/interfaces/web_admin/templates"

for f in \
  "$ROOT/interfaces/web_admin/api.py"
do
  if [ -f "$f" ]; then
    cp "$f" "$BACKUP/$(basename "$f").bak"
  fi
done

cat > "$ROOT/interfaces/web_admin/routes/control_debug.py" <<'PY'
from __future__ import annotations

import csv
import os
from collections import OrderedDict
from pathlib import Path
from urllib.parse import quote

import requests
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
router = APIRouter()

REGISTRY_PATH = Path("/home/mi/greenhouse_v17/data/registry/devices.csv")


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _ha_base_url() -> str:
    return _env("HOME_ASSISTANT_URL", "HA_BASE_URL", default="http://127.0.0.1:8123").rstrip("/")


def _ha_token() -> str:
    return _env("HOME_ASSISTANT_TOKEN", "HA_TOKEN")


def _ha_headers() -> dict[str, str]:
    token = _ha_token()
    if not token:
        return {"Content-Type": "application/json"}
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _safe_get(row: dict, *keys: str) -> str:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for key in keys:
        val = row.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
        val = lowered.get(key.strip().lower())
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _parse_id_sort(value: str):
    raw = str(value or "")
    parts = raw.split(".")
    out = []
    for p in parts:
        try:
            out.append((0, int(p)))
        except Exception:
            out.append((1, p))
    return tuple(out)


def _load_devices() -> list[dict]:
    items: list[dict] = []
    if not REGISTRY_PATH.exists():
        return items

    with REGISTRY_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_id = _safe_get(
                row,
                "Entity_ID",
                "entity_id",
                "entity",
                "ha_entity_id",
                "ha_entity",
            )
            if not entity_id:
                continue

            item = {
                "id": _safe_get(row, "ID", "DeviceID", "device_id", "id"),
                "parent": _safe_get(row, "Parent", "ParentID", "parent", "parent_id"),
                "name": _safe_get(row, "Name", "name", "title"),
                "type": _safe_get(row, "Type", "type", "kind"),
                "unit": _safe_get(row, "Unit", "unit"),
                "location": _safe_get(row, "Location", "location", "zone"),
                "logical_role": _safe_get(row, "logical_role", "Logical_Role", "role"),
                "entity_id": entity_id,
                "description": _safe_get(row, "Description", "description"),
            }
            items.append(item)

    items.sort(key=lambda x: (_parse_id_sort(x.get("id", "")), x.get("name", "")))
    return items


def _infer_ops(entity_id: str, item_type: str, name: str, logical_role: str) -> list[str]:
    domain = (entity_id.split(".", 1)[0] if "." in entity_id else "").strip().lower()
    hint = " ".join([item_type or "", name or "", logical_role or ""]).lower()

    if domain in {"switch", "light", "fan", "input_boolean", "humidifier", "media_player"}:
        return ["on", "off", "toggle"]
    if domain == "cover":
        return ["open", "close", "stop"]
    if domain == "climate":
        return ["on", "off"]
    if domain == "lock":
        return ["lock", "unlock"]
    if domain == "valve":
        return ["open", "close"]
    if any(x in hint for x in ["curtain", "shtor", "штор", "cover"]):
        return ["open", "close", "stop"]
    if any(x in hint for x in ["fan", "vent", "вент", "циркуляц"]):
        return ["on", "off", "toggle"]
    if any(x in hint for x in ["humid", "увлаж"]):
        return ["on", "off", "toggle"]
    if any(x in hint for x in ["pump", "valve", "water", "полив", "насос", "клапан"]):
        return ["on", "off"]
    if any(x in hint for x in ["light", "lamp", "свет", "ламп"]):
        return ["on", "off", "toggle"]
    if any(x in hint for x in ["power", "relay", "switch", "щит", "реле", "питание", "розет"]):
        return ["on", "off", "toggle"]
    return []


def _group_title(entity_id: str, item_type: str, name: str, logical_role: str) -> str:
    domain = (entity_id.split(".", 1)[0] if "." in entity_id else "").strip().lower()
    hint = " ".join([item_type or "", name or "", logical_role or ""]).lower()

    if domain == "cover" or any(x in hint for x in ["curtain", "штор", "cover"]):
        return "Шторы / Cover"
    if domain == "fan" or any(x in hint for x in ["fan", "vent", "вент", "циркуляц"]):
        return "Вентиляция"
    if domain in {"humidifier", "climate"} or any(x in hint for x in ["humid", "увлаж", "climate", "термостат", "обогрев"]):
        return "Климат / Увлажнение / Обогрев"
    if domain == "light" or any(x in hint for x in ["light", "lamp", "свет", "ламп"]):
        return "Свет"
    if domain in {"switch", "input_boolean"} or any(x in hint for x in ["power", "relay", "switch", "щит", "реле", "питание", "розет"]):
        return "Питание / Реле / Розетки"
    if domain == "valve" or any(x in hint for x in ["pump", "valve", "water", "полив", "насос", "клапан"]):
        return "Полив / Насосы / Клапаны"
    if domain in {"lock", "media_player"}:
        return "Прочее управление"
    return "Мониторинг / Без управления"


def _load_states() -> dict[str, dict]:
    token = _ha_token()
    if not token:
        return {}

    try:
        r = requests.get(
            f"{_ha_base_url()}/api/states",
            headers=_ha_headers(),
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        out = {}
        for item in data:
            eid = item.get("entity_id")
            if eid:
                out[eid] = item
        return out
    except Exception:
        return {}


def _call_ha(entity_id: str, operation: str) -> dict:
    token = _ha_token()
    if not token:
        return {"ok": False, "error": "HA token not found in environment"}

    domain = entity_id.split(".", 1)[0].lower()
    operation = operation.lower().strip()

    if operation == "on":
        service = "turn_on"
    elif operation == "off":
        service = "turn_off"
    elif operation == "toggle":
        service = "toggle"
    elif operation == "open":
        service = "open_cover" if domain == "cover" else "open_valve"
    elif operation == "close":
        service = "close_cover" if domain == "cover" else "close_valve"
    elif operation == "stop":
        service = "stop_cover"
    elif operation in {"lock", "unlock"}:
        service = operation
    else:
        return {"ok": False, "error": f"Unsupported operation: {operation}"}

    if domain in {"sensor", "binary_sensor", "camera", "number", "select"}:
        return {"ok": False, "error": f"Domain {domain} is read-only for this debug panel"}

    try:
        r = requests.post(
            f"{_ha_base_url()}/api/services/{domain}/{service}",
            headers=_ha_headers(),
            json={"entity_id": entity_id},
            timeout=20,
        )
        r.raise_for_status()
        try:
            payload = r.json()
        except Exception:
            payload = {"raw": r.text}
        return {"ok": True, "service": f"{domain}.{service}", "payload": payload}
    except Exception as e:
        return {"ok": False, "error": str(e), "service": f"{domain}.{service}"}


def _build_groups() -> list[dict]:
    devices = _load_devices()
    states = _load_states()
    groups: OrderedDict[str, list[dict]] = OrderedDict()

    order = [
        "Питание / Реле / Розетки",
        "Свет",
        "Шторы / Cover",
        "Вентиляция",
        "Климат / Увлажнение / Обогрев",
        "Полив / Насосы / Клапаны",
        "Прочее управление",
        "Мониторинг / Без управления",
    ]
    for title in order:
        groups[title] = []

    for item in devices:
        ops = _infer_ops(
            item["entity_id"],
            item.get("type", ""),
            item.get("name", ""),
            item.get("logical_role", ""),
        )
        title = _group_title(
            item["entity_id"],
            item.get("type", ""),
            item.get("name", ""),
            item.get("logical_role", ""),
        )
        state_obj = states.get(item["entity_id"], {})
        row = {
            **item,
            "ops": ops,
            "state": state_obj.get("state", "unknown"),
            "last_changed": state_obj.get("last_changed", ""),
            "last_updated": state_obj.get("last_updated", ""),
        }
        groups.setdefault(title, []).append(row)

    out = []
    for title, rows in groups.items():
        if rows:
            out.append({"title": title, "rows": rows})
    return out


@router.get("/web/control-debug", response_class=HTMLResponse)
def control_debug_page(request: Request, msg: str = "", level: str = "info"):
    return templates.TemplateResponse(
        request=request,
        name="control_debug.html",
        context={
            "request": request,
            "page_title": "Greenhouse v17 — Full Debug Control",
            "groups": _build_groups(),
            "msg": msg,
            "level": level,
        },
    )


@router.get("/web/control-debug/execute")
def control_debug_execute(entity_id: str, operation: str):
    result = _call_ha(entity_id=entity_id, operation=operation)
    if result.get("ok"):
        msg = f"OK: {entity_id} -> {operation}"
        level = "ok"
    else:
        msg = f"ERROR: {entity_id} -> {operation} :: {result.get('error', 'unknown')}"
        level = "error"
    return RedirectResponse(
        url=f"/web/control-debug?msg={quote(msg)}&level={quote(level)}",
        status_code=303,
    )
PY

cat > "$ROOT/interfaces/web_admin/templates/control_debug.html" <<'HTML'
{% extends "base.html" %}
{% block content %}

<div style="margin-bottom:16px;padding:14px 16px;border:1px solid #444;border-radius:12px;background:#141414;">
  <h2 style="margin:0 0 8px 0;">Временный debug-пульт всех устройств</h2>
  <div style="opacity:.9;">
    Это временная страница для проверки железа. Здесь intentionally видны все entity из registry, включая read-only.
  </div>
</div>

{% if msg %}
<div style="margin-bottom:16px;padding:12px 14px;border-radius:10px;border:1px solid {% if level == 'ok' %}#1d7a42{% elif level == 'error' %}#8a2f2f{% else %}#555{% endif %};background:{% if level == 'ok' %}#0f2416{% elif level == 'error' %}#2a1212{% else %}#1a1a1a{% endif %};">
  {{ msg }}
</div>
{% endif %}

{% for group in groups %}
<section style="margin-bottom:22px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <h3 style="margin:0;">{{ group.title }}</h3>
    <span style="opacity:.7;">{{ group.rows|length }} шт.</span>
  </div>

  <div style="display:grid;gap:10px;">
    {% for item in group.rows %}
    <div style="border:1px solid #333;border-radius:14px;padding:12px;background:#111;">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;">
        <div style="min-width:320px;flex:1;">
          <div style="font-weight:700;">{{ item.id }} — {{ item.name or item.entity_id }}</div>
          <div style="opacity:.85;font-size:14px;margin-top:4px;">{{ item.entity_id }}</div>
          <div style="opacity:.75;font-size:13px;margin-top:6px;">
            type: {{ item.type or '—' }} |
            role: {{ item.logical_role or '—' }} |
            location: {{ item.location or '—' }} |
            state: <b>{{ item.state }}</b>
          </div>
        </div>

        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          {% if item.ops %}
            {% for op in item.ops %}
            <a
              href="/web/control-debug/execute?entity_id={{ item.entity_id | urlencode }}&operation={{ op | urlencode }}"
              style="text-decoration:none;padding:8px 12px;border-radius:10px;border:1px solid #4a4a4a;background:#1b1b1b;color:#fff;"
            >
              {% if op == "on" %}ВКЛ{% elif op == "off" %}ВЫКЛ{% elif op == "toggle" %}TOGGLE{% elif op == "open" %}ОТКРЫТЬ{% elif op == "close" %}ЗАКРЫТЬ{% elif op == "stop" %}СТОП{% elif op == "lock" %}LOCK{% elif op == "unlock" %}UNLOCK{% else %}{{ op|upper }}{% endif %}
            </a>
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

{% endblock %}
HTML

python3 - <<'PY'
from pathlib import Path

api_path = Path("/home/mi/greenhouse_v17/interfaces/web_admin/api.py")
text = api_path.read_text(encoding="utf-8")

import_line = "from interfaces.web_admin.routes.control_debug import router as control_debug_router"
if import_line not in text:
    marker = "from interfaces.web_admin.routes.web import router as web_router"
    text = text.replace(marker, marker + "\n" + import_line)

include_line = 'app.include_router(control_debug_router, tags=["control_debug"])'
if include_line not in text:
    text = text.rstrip() + "\n" + include_line + "\n"

api_path.write_text(text, encoding="utf-8")
print("api.py patched")
PY

python3 -m compileall "$ROOT/interfaces/web_admin/routes/control_debug.py"

sudo systemctl restart greenhouse-web-admin.service
sleep 2

echo
echo "=== STATUS ==="
sudo systemctl status greenhouse-web-admin.service --no-pager || true
echo
echo "=== OPEN THIS URL ==="
echo "http://127.0.0.1:8081/web/control-debug"
