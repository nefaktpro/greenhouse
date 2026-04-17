import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
REGISTRY_DIR = BASE_DIR / "data" / "registry"

def load_action_map():
    p = REGISTRY_DIR / "action_map.json"
    return json.loads(p.read_text(encoding="utf-8"))

def load_devices():
    candidates = [
        REGISTRY_DIR / "devices_registry_full.csv",
        REGISTRY_DIR / "devices.csv",
    ]
    for p in candidates:
        if p.exists():
            with p.open("r", encoding="utf-8-sig", newline="") as f:
                return list(csv.DictReader(f))
    return []

def find_device_by_role(role: str):
    for row in load_devices():
        if str(row.get("logical_role", "")).strip() == role and str(row.get("is_enabled", "true")).lower() == "true":
            return row
    return None

def resolve_action_to_entity(action_key: str):
    action_map = load_action_map()
    entry = action_map.get(action_key)
    if not entry:
        raise KeyError(f"Unknown action_key: {action_key}")

    role = entry["target_role"]
    op = entry["operation"]

    device = find_device_by_role(role)
    if not device:
        raise KeyError(f"No enabled device for role: {role}")

    entity_id = str(device.get("entity_id", "")).strip()
    if not entity_id:
        raise KeyError(f"Device for role {role} has empty entity_id")

    return {
        "target_role": role,
        "operation": op,
        "entity_id": entity_id,
        "device": device,
    }
