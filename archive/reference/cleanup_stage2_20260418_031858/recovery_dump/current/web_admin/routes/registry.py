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
