from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

BASE_DIR = Path(__file__).resolve().parents[2]
REGISTRY_DIR = BASE_DIR / "data" / "registry"
DEVICES_PATH = REGISTRY_DIR / "devices.csv"
ACTION_MAP_PATH = REGISTRY_DIR / "action_map.json"
CAPABILITIES_PATH = REGISTRY_DIR / "device_capabilities.json"

def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def list_devices() -> List[Dict[str, str]]:
    if not DEVICES_PATH.exists():
        return []
    with DEVICES_PATH.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def get_device_by_role(logical_role: str) -> Optional[Dict[str, str]]:
    for row in list_devices():
        if row.get("logical_role") == logical_role and str(row.get("is_enabled", "")).lower() in ("true", "1", "yes"):
            return row
    return None

def disable_device(device_id: str) -> bool:
    rows = list_devices()
    changed = False
    for row in rows:
        if row.get("device_id") == device_id:
            row["is_enabled"] = "false"
            changed = True
    if changed:
        save_devices(rows)
    return changed

def enable_device(device_id: str) -> bool:
    rows = list_devices()
    changed = False
    for row in rows:
        if row.get("device_id") == device_id:
            row["is_enabled"] = "true"
            changed = True
    if changed:
        save_devices(rows)
    return changed

def save_devices(rows: List[Dict[str, str]]) -> None:
    if not rows:
        return
    DEVICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with DEVICES_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def load_action_map() -> Dict[str, Any]:
    return _read_json(ACTION_MAP_PATH, {})

def save_action_map(payload: Dict[str, Any]) -> None:
    _write_json(ACTION_MAP_PATH, payload)

def load_capabilities() -> Dict[str, Any]:
    return _read_json(CAPABILITIES_PATH, {})

def save_capabilities(payload: Dict[str, Any]) -> None:
    _write_json(CAPABILITIES_PATH, payload)
