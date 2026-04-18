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

MONITORING_SENSOR_TYPES = {
    "sensor",
}

SAFETY_TYPES = {
    "smoke",
    "moisture",
    "binary_sensor",
    "battery",
    "tamper",
    "sensor",
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

def _read_registry() -> List[Dict[str, str]]:
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
        out: Dict[str, Dict[str, Any]] = {}
        for item in data:
            if isinstance(item, dict):
                eid = item.get("entity_id")
                if isinstance(eid, str) and eid:
                    out[eid] = item
        return out
    except Exception:
        return {}

def _safe_scalar(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (int, float, bool)):
        return v
    if isinstance(v, dict):
        return str(v)
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    s = str(v).strip()
    try:
        if "." in s:
            return round(float(s), 2)
        return int(s)
    except Exception:
        return s

def _hay(row: Dict[str, str]) -> str:
    parts = [
        row.get("device_id", ""),
        row.get("name", ""),
        row.get("type", ""),
        row.get("entity_id", ""),
        row.get("zone", ""),
        row.get("location", ""),
        row.get("logical_role", ""),
        row.get("notes", ""),
    ]
    return " | ".join(parts).lower()

def _monitoring_category(row: Dict[str, str]) -> str | None:
    t = (row.get("type") or "").lower()
    h = _hay(row)

    if t not in MONITORING_SENSOR_TYPES:
        return None

    if any(x in h for x in ["дым", "fire", "smoke", "протеч", "leak"]):
        return None
    if any(x in h for x in ["power", "voltage", "current", "energy", "питание", "напряжение", "мощность", "ток"]):
        return None
    if any(x in h for x in ["battery", "батар"]):
        return None
    if any(x in h for x in ["zigbee", "gateway", "problem"]):
        return None

    if any(x in h for x in ["co2", "carbon_dioxide", "voc", "pm10", "pm2", "formaldehyde", "формальдегид", "air quality", "качество воздуха"]):
        return "air_quality"
    if any(x in h for x in ["illuminance", "освещ", "lightsensor", "светимость", "luminance", "lx", "lux"]):
        return "light"
    if any(x in h for x in ["улиц", "outdoor", "temperature_and_humidity_alarm"]):
        return "outdoor"
    if any(x in h for x in ["лист", "leaf", "temperature_and_humidity_sensor"]):
        return "leaf_climate"
    if any(x in h for x in ["почв", "грунт", "surface", "корн", "root", "humidity", "temperature"]) and \
       any(z in h for z in ["low_rack", "top_rack", "top_rack_window", "low_rack_window"]):
        return "soil"
    return "climate"

def _safety_category(row: Dict[str, str]) -> str | None:
    t = (row.get("type") or "").lower()
    h = _hay(row)

    if t not in SAFETY_TYPES:
        return None

    if any(x in h for x in ["дым", "fire", "smoke"]):
        return "fire"
    if any(x in h for x in ["протеч", "leak", "moisture"]):
        return "leak"
    if any(x in h for x in ["power", "voltage", "current", "energy", "electric", "питание", "напряжение", "мощность", "ток"]):
        return "power"
    if any(x in h for x in ["zigbee", "gateway", "problem"]):
        return "connectivity"
    if "battery" in h or "батар" in h:
        if any(x in h for x in ["дым", "fire", "leak", "протеч", "power", "electric", "питание"]):
            return "safety_battery"
    return None

def _row_to_item(row: Dict[str, str], states: Dict[str, Dict[str, Any]], category: str) -> Dict[str, Any]:
    entity_id = row.get("entity_id") or ""
    state_obj = states.get(entity_id, {}) if entity_id else {}
    if not isinstance(state_obj, dict):
        state_obj = {}

    attrs = state_obj.get("attributes", {})
    if not isinstance(attrs, dict):
        attrs = {}

    raw_state = state_obj.get("state")
    available = raw_state not in (None, "", "unknown", "unavailable")

    return {
        "device_id": str(row.get("device_id") or ""),
        "name": str(row.get("name") or attrs.get("friendly_name") or entity_id or ""),
        "type": str(row.get("type") or ""),
        "entity_id": str(entity_id),
        "zone": str(row.get("zone") or ""),
        "location": str(row.get("location") or ""),
        "logical_role": str(row.get("logical_role") or ""),
        "unit": str(row.get("unit") or attrs.get("unit_of_measurement") or ""),
        "category": str(category),
        "value": _safe_scalar(raw_state),
        "raw_state": _safe_scalar(raw_state),
        "available": bool(available),
        "last_updated": str(state_obj.get("last_updated") or ""),
        "notes": str(row.get("notes") or ""),
    }

def _build(kind: str) -> Dict[str, Any]:
    rows = _read_registry()
    states = _ha_states_map()

    items: List[Dict[str, Any]] = []
    for row in rows:
        entity_id = row.get("entity_id") or ""
        if not entity_id:
            continue

        category = _monitoring_category(row) if kind == "overview" else _safety_category(row)
        if not category:
            continue

        items.append(_row_to_item(row, states, category))

    items.sort(key=lambda x: (str(x.get("category") or ""), str(x.get("device_id") or "")))

    categories: Dict[str, int] = {}
    for item in items:
        cat = str(item.get("category") or "other")
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "ok": True,
        "kind": kind,
        "count": len(items),
        "categories": categories,
        "items": items,
        "ha_connected": bool(states),
    }

@router.get("/overview")
def overview():
    return JSONResponse(content=_build("overview"))

@router.get("/safety")
def safety():
    return JSONResponse(content=_build("safety"))
