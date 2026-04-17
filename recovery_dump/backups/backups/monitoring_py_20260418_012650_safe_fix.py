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
