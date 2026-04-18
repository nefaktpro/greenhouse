#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
cd "$ROOT"

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/backups/rebuild_webadmin_backend_shell_$TS"
mkdir -p "$BACKUP_DIR"

backup_if_exists() {
  local path="$1"
  if [ -e "$path" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$path")"
    cp -R "$path" "$BACKUP_DIR/$path"
    echo "[backup] $path"
  fi
}

mkdir -p interfaces/web_admin/routes

backup_if_exists "interfaces/web_admin/api.py"
backup_if_exists "interfaces/web_admin/routes/actions.py"
backup_if_exists "interfaces/web_admin/routes/ask.py"
backup_if_exists "interfaces/web_admin/routes/modes.py"
backup_if_exists "interfaces/web_admin/routes/registry.py"
backup_if_exists "interfaces/web_admin/routes/monitoring.py"
backup_if_exists "interfaces/web_admin/routes/auth.py"

touch interfaces/__init__.py
touch interfaces/web_admin/__init__.py
touch interfaces/web_admin/routes/__init__.py

cat > interfaces/web_admin/api.py <<'PY'
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from interfaces.web_admin.routes.actions import router as actions_router
from interfaces.web_admin.routes.ask import router as ask_router
from interfaces.web_admin.routes.modes import router as modes_router
from interfaces.web_admin.routes.registry import router as registry_router
from interfaces.web_admin.routes.web import router as web_router
from interfaces.web_admin.routes.monitoring import router as monitoring_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Greenhouse v17 Web Admin",
    version="0.5.0",
)

if (BASE_DIR / "static").exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(BASE_DIR / "static")),
        name="static",
    )


@app.get("/api/health")
def health():
    return {"ok": True, "service": "web_admin", "project": "greenhouse_v17"}


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


app.include_router(actions_router, prefix="/api/actions", tags=["actions"])
app.include_router(ask_router, prefix="/api/ask", tags=["ask"])
app.include_router(modes_router, prefix="/api/modes", tags=["modes"])
app.include_router(registry_router, prefix="/api/registry", tags=["registry"])
app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(web_router, prefix="/web", tags=["web"])
PY

cat > interfaces/web_admin/routes/actions.py <<'PY'
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from greenhouse_v17.services.webadmin_execution_service import (
    create_pending_ask,
    debug_action_map_full,
    execute_action,
)

router = APIRouter()


class ExecuteActionIn(BaseModel):
    action_key: str
    ask: bool = False
    title: str | None = None


@router.get("/debug/action-map")
def debug_action_map():
    return {"ok": True, "debug": debug_action_map_full()}


@router.post("/execute")
def execute_action_route(payload: ExecuteActionIn):
    if payload.ask:
        state = create_pending_ask(action_key=payload.action_key, title=payload.title)
        return {"ok": True, "mode": "ASK", "pending": state}

    result = execute_action(action_key=payload.action_key)
    return {"ok": bool(result.get("ok")), "result": result}
PY

cat > interfaces/web_admin/routes/ask.py <<'PY'
from __future__ import annotations

from fastapi import APIRouter

from greenhouse_v17.services.webadmin_execution_service import (
    cancel_pending_ask,
    confirm_pending_ask,
    load_ask_state,
)

router = APIRouter()


@router.get("/current")
def ask_current():
    state = load_ask_state()
    if not state or not state.get("has_pending"):
        return {"ok": True, "has_pending": False, "item": None}
    return {"ok": True, "has_pending": True, "item": state}


@router.post("/confirm")
def ask_confirm():
    return confirm_pending_ask()


@router.post("/cancel")
def ask_cancel():
    return cancel_pending_ask()
PY

cat > interfaces/web_admin/routes/modes.py <<'PY'
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

STATE_PATH = Path("/home/mi/greenhouse_v17/system_state.json")

router = APIRouter()

DEFAULT_STATE = {
    "mode": "MANUAL",
    "execute": False,
    "log": True,
    "ask": False,
    "ai_control": False,
}

MODE_PRESETS = {
    "MANUAL": {"execute": False, "log": True, "ask": False, "ai_control": False},
    "TEST": {"execute": False, "log": True, "ask": False, "ai_control": False},
    "ASK": {"execute": False, "log": True, "ask": True, "ai_control": False},
    "AUTO": {"execute": True, "log": True, "ask": False, "ai_control": False},
    "AUTOPILOT": {"execute": True, "log": True, "ask": False, "ai_control": True},
}


def read_state():
    if not STATE_PATH.exists():
        return DEFAULT_STATE.copy()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {**DEFAULT_STATE, **data}
    except Exception:
        pass
    return DEFAULT_STATE.copy()


def write_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


class ModeIn(BaseModel):
    mode: str


@router.get("/current")
def current_mode():
    return {"ok": True, "state": read_state()}


@router.post("/set")
def set_mode(payload: ModeIn):
    mode = payload.mode.strip().upper()
    if mode not in MODE_PRESETS:
        return {"ok": False, "error": "unsupported_mode", "mode": mode}
    state = {"mode": mode, **MODE_PRESETS[mode]}
    write_state(state)
    return {"ok": True, "state": state}
PY

cat > interfaces/web_admin/routes/registry.py <<'PY'
from __future__ import annotations

import csv
import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

ROOT = Path("/home/mi/greenhouse_v17")
REGISTRY_DIR = ROOT / "data" / "registry"
DEVICES_PATH = REGISTRY_DIR / "devices.csv"
CAPS_PATH = REGISTRY_DIR / "device_capabilities.json"


def load_devices():
    items = []
    if not DEVICES_PATH.exists():
        return items
    with DEVICES_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {str(k).strip(): ("" if v is None else str(v).strip()) for k, v in row.items() if k is not None}
            items.append({
                "device_id": row.get("ID") or row.get("DeviceID") or row.get("device_id") or row.get("id"),
                "name": row.get("Name") or row.get("name"),
                "type": row.get("Type") or row.get("type"),
                "zone": row.get("Zone") or row.get("zone") or row.get("Location") or row.get("location"),
                "location": row.get("Location") or row.get("location"),
                "entity_id": row.get("Entity_ID") or row.get("EntityID") or row.get("entity_id"),
            })
    return items


def load_caps():
    if not CAPS_PATH.exists():
        return {}
    try:
        return json.loads(CAPS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


@router.get("/devices")
def registry_devices():
    items = load_devices()
    return {"ok": True, "count": len(items), "items": items}


@router.get("/capabilities")
def registry_capabilities():
    data = load_caps()
    return {"ok": True, "items": data}
PY

cat > interfaces/web_admin/routes/monitoring.py <<'PY'
from __future__ import annotations

from fastapi import APIRouter

from interfaces.web_admin.routes.registry import load_devices

router = APIRouter()


@router.get("/overview")
def monitoring_overview():
    items = load_devices()
    categories = {}
    for item in items:
        t = item.get("type") or "unknown"
        categories[t] = categories.get(t, 0) + 1
    return {
        "ok": True,
        "kind": "overview",
        "count": len(items),
        "categories": categories,
        "items": items[:100],
    }


@router.get("/safety")
def monitoring_safety():
    return {
        "ok": True,
        "kind": "safety",
        "status": "available",
        "summary": "Safety API route is alive",
        "critical_rules": [
            "fire_priority",
            "leak_priority",
            "power_priority",
        ],
    }
PY

echo
echo "=== IMPORT TEST ==="
python3 - <<'PY'
import interfaces.web_admin.api as m
print("IMPORT OK:", bool(m.app))
PY

echo
echo "=== RESTART ==="
sudo systemctl restart greenhouse-web-admin.service
sleep 2
sudo systemctl status greenhouse-web-admin.service --no-pager

echo
echo "=== ROUTE CHECK ==="
for path in /api/health /api/actions/debug/action-map /api/ask/current /api/modes/current /api/registry/devices /api/monitoring/overview /web/ /web/monitoring /web/registry /web/safety /web/modes /web/ask /web/control; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8081$path" || true)
  echo "$path -> $code"
done

echo
echo "Backup dir: $BACKUP_DIR"
