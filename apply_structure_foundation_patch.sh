#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v2"
PKG="$ROOT/greenhouse_v17"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/backups/structure_foundation_$STAMP"

mkdir -p "$BACKUP_DIR"

echo "==> backup important files if present"
for f in \
  "$ROOT/.gitignore" \
  "$ROOT/README.md" \
  "$ROOT/devices.csv" \
  "$ROOT/system_state.json" \
  "$ROOT/ask_state.json" \
  "$ROOT/decision_log.json" \
  "$ROOT/observations.json"
do
  if [ -f "$f" ]; then
    cp "$f" "$BACKUP_DIR/$(basename "$f").bak"
  fi
done

echo "==> create canonical dirs"
mkdir -p \
  "$ROOT/data/registry" \
  "$ROOT/data/runtime" \
  "$ROOT/data/logs" \
  "$ROOT/data/memory" \
  "$ROOT/data/generated" \
  "$PKG/services" \
  "$PKG/objects"

touch "$PKG/services/__init__.py"
touch "$PKG/objects/__init__.py"

echo "==> normalize .gitignore"
grep -q "data/runtime/" "$ROOT/.gitignore" 2>/dev/null || cat >> "$ROOT/.gitignore" <<'EOF'

# runtime and local state
data/runtime/
data/logs/
*.bak
*.save
*.pynano
.env.save

# legacy root runtime
system_state.json
ask_state.json
decision_log.json
observations.json
devices_cache.json
deepseek_cache.json
EOF

echo "==> create registry manifest"
cat > "$ROOT/data/registry/registry_manifest.json" <<'JSON'
{
  "version": 1,
  "description": "Canonical registry manifest for GREENHOUSE v17",
  "files": {
    "devices": {
      "path": "data/registry/devices.csv",
      "role": "canonical_source_of_truth",
      "editable_via_interfaces": true
    },
    "action_map": {
      "path": "data/registry/action_map.json",
      "role": "canonical_action_mapping",
      "editable_via_interfaces": true
    },
    "device_capabilities": {
      "path": "data/registry/device_capabilities.json",
      "role": "engineering_capabilities_layer",
      "editable_via_interfaces": true
    },
    "scenarios": {
      "path": "data/registry/scenarios.json",
      "role": "scenario_registry",
      "editable_via_interfaces": true
    }
  }
}
JSON

echo "==> create README foundation if too empty"
if [ ! -f "$ROOT/README.md" ] || [ "$(wc -c < "$ROOT/README.md")" -lt 50 ]; then
cat > "$ROOT/README.md" <<'MD'
# GREENHOUSE v17

## Main principle

Interfaces do not contain business logic.
Devices, action mapping, capabilities and scenarios are stored in registry/data layer.

## Canonical files

- `data/registry/devices.csv`
- `data/registry/action_map.json`
- `data/registry/device_capabilities.json`
- `data/registry/scenarios.json`
- `data/registry/registry_manifest.json`

## Runtime (not committed)

- `data/runtime/`
- `data/logs/`
- `data/memory/`

## Goal

Telegram, Web Admin and future mobile app should all work through the same Core/Registry/Validation/Execution pipeline.
MD
fi

echo "==> move legacy root runtime files if present"
python3 - <<'PY'
from pathlib import Path
import shutil

root = Path("/home/mi/greenhouse_v2")
moves = {
    "system_state.json": root / "data/runtime/system_state.json",
    "ask_state.json": root / "data/runtime/ask_state.json",
    "decision_log.json": root / "data/logs/decision_log.json",
    "observations.json": root / "data/memory/observations.json",
    "devices_cache.json": root / "data/runtime/devices_cache.json",
    "deepseek_cache.json": root / "data/runtime/deepseek_cache.json",
}
for src_name, dst in moves.items():
    src = root / src_name
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        print(f"moved: {src_name} -> {dst}")
PY

echo "==> seed devices.csv into canonical registry if needed"
if [ -f "$ROOT/devices.csv" ] && [ ! -f "$ROOT/data/registry/devices.csv" ]; then
  cp "$ROOT/devices.csv" "$ROOT/data/registry/devices.csv"
fi

echo "==> ensure action_map exists"
if [ ! -f "$ROOT/data/registry/action_map.json" ]; then
cat > "$ROOT/data/registry/action_map.json" <<'JSON'
{
  "fan_top_on": { "target_role": "top_air_circulation", "operation": "turn_on" },
  "fan_top_off": { "target_role": "top_air_circulation", "operation": "turn_off" },
  "fan_bottom_on": { "target_role": "bottom_air_circulation", "operation": "turn_on" },
  "fan_bottom_off": { "target_role": "bottom_air_circulation", "operation": "turn_off" },
  "humidifier_on": { "target_role": "main_humidifier", "operation": "turn_on" },
  "humidifier_off": { "target_role": "main_humidifier", "operation": "turn_off" },
  "veranda_power_on": { "target_role": "veranda_main_power_cutoff", "operation": "turn_on" },
  "veranda_power_off": { "target_role": "veranda_main_power_cutoff", "operation": "turn_off" }
}
JSON
fi

echo "==> ensure scenarios file exists"
if [ ! -f "$ROOT/data/registry/scenarios.json" ]; then
cat > "$ROOT/data/registry/scenarios.json" <<'JSON'
{
  "version": 1,
  "items": []
}
JSON
fi

echo "==> ensure capabilities exists"
if [ ! -f "$ROOT/data/registry/device_capabilities.json" ]; then
cat > "$ROOT/data/registry/device_capabilities.json" <<'JSON'
{
  "top_air_circulation": {
    "allowed_actions": ["turn_on", "turn_off"],
    "allowed_modes": ["MANUAL", "TEST", "ASK", "AUTO", "AUTOPILOT"],
    "dependencies": [],
    "constraints": { "max_run_minutes": 120, "cooldown_minutes": 1 },
    "pre_checks": ["device_available", "no_fire_emergency"],
    "post_checks": ["entity_state_changed"],
    "safety_flags": ["disable_on_fire"],
    "fallback_behavior": "log_and_notify"
  },
  "bottom_air_circulation": {
    "allowed_actions": ["turn_on", "turn_off"],
    "allowed_modes": ["MANUAL", "TEST", "ASK", "AUTO", "AUTOPILOT"],
    "dependencies": [],
    "constraints": { "max_run_minutes": 120, "cooldown_minutes": 1 },
    "pre_checks": ["device_available", "no_fire_emergency"],
    "post_checks": ["entity_state_changed"],
    "safety_flags": ["disable_on_fire"],
    "fallback_behavior": "log_and_notify"
  }
}
JSON
fi

echo "==> create registry service"
cat > "$PKG/services/registry_service.py" <<'PY'
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
PY

echo "==> create scenario service"
cat > "$PKG/services/scenario_service.py" <<'PY'
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = BASE_DIR / "data" / "registry" / "scenarios.json"

def load_scenarios() -> Dict[str, Any]:
    if not SCENARIOS_PATH.exists():
        return {"version": 1, "items": []}
    return json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))

def save_scenarios(payload: Dict[str, Any]) -> None:
    SCENARIOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCENARIOS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def list_scenarios() -> List[Dict[str, Any]]:
    data = load_scenarios()
    return data.get("items", [])

def upsert_scenario(item: Dict[str, Any]) -> Dict[str, Any]:
    data = load_scenarios()
    items = data.get("items", [])
    key = item["key"]
    replaced = False
    for i, old in enumerate(items):
        if old.get("key") == key:
            items[i] = item
            replaced = True
            break
    if not replaced:
        items.append(item)
    data["items"] = items
    save_scenarios(data)
    return item
PY

echo "==> create capability service"
cat > "$PKG/services/capability_service.py" <<'PY'
from __future__ import annotations

from typing import Dict, Any
from greenhouse_v17.services.registry_service import load_capabilities, save_capabilities

def get_capability(logical_role: str) -> Dict[str, Any]:
    return load_capabilities().get(logical_role, {})

def upsert_capability(logical_role: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = load_capabilities()
    data[logical_role] = payload
    save_capabilities(data)
    return payload
PY

echo "==> create object service stub for future multi-greenhouse"
cat > "$PKG/services/object_service.py" <<'PY'
from __future__ import annotations

from typing import Dict, Any

def get_default_object() -> Dict[str, Any]:
    return {
        "object_id": "greenhouse_main",
        "title": "Main Greenhouse",
        "status": "active",
        "ha_connection": "primary",
        "ui_editable": True
    }
PY

echo "==> create admin crud stub for future web/telegram"
cat > "$PKG/services/admin_registry_api.py" <<'PY'
from __future__ import annotations

from typing import Dict, Any

from greenhouse_v17.services.registry_service import (
    list_devices,
    disable_device,
    enable_device,
    load_action_map,
    save_action_map,
    load_capabilities,
    save_capabilities,
)
from greenhouse_v17.services.scenario_service import list_scenarios, upsert_scenario

def get_registry_snapshot() -> Dict[str, Any]:
    return {
        "devices": list_devices(),
        "action_map": load_action_map(),
        "capabilities": load_capabilities(),
        "scenarios": list_scenarios(),
    }

def set_device_enabled(device_id: str, enabled: bool) -> bool:
    return enable_device(device_id) if enabled else disable_device(device_id)

def replace_action_map(payload: Dict[str, Any]) -> None:
    save_action_map(payload)

def replace_capabilities(payload: Dict[str, Any]) -> None:
    save_capabilities(payload)

def save_scenario(payload: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_scenario(payload)
PY

echo "==> create migration note"
cat > "$ROOT/MIGRATION_V17_NOTES.md" <<'MD'
# GREENHOUSE v17 Migration Notes

## Canonical registry
- data/registry/devices.csv
- data/registry/action_map.json
- data/registry/device_capabilities.json
- data/registry/scenarios.json
- data/registry/registry_manifest.json

## Runtime moved out of root
- data/runtime/
- data/logs/
- data/memory/

## Important principle
Interfaces must edit registry/data via services, not Python business logic.

## Next layer
Web Admin / Telegram Admin should call:
- registry_service
- scenario_service
- capability_service
- admin_registry_api
MD

echo "==> quick sanity check"
python3 - <<'PY'
from greenhouse_v17.services.registry_service import list_devices, load_action_map
from greenhouse_v17.services.scenario_service import load_scenarios
from greenhouse_v17.services.capability_service import get_capability

print("devices:", len(list_devices()))
print("actions:", len(load_action_map()))
print("scenarios:", load_scenarios().get("version"))
print("cap fan top:", bool(get_capability("top_air_circulation")))
PY

echo
echo "STRUCTURE FOUNDATION PATCH APPLIED"
echo "backup dir: $BACKUP_DIR"
