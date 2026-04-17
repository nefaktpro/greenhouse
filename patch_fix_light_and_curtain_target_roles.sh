#!/usr/bin/env bash
set -euo pipefail

FILE="/home/mi/greenhouse_v17/data/registry/action_map.json"
BACKUP="/home/mi/greenhouse_v17/backups/action_map_$(date +%Y%m%d_%H%M%S)_target_roles_fix.json"

mkdir -p "$(dirname "$BACKUP")"
cp "$FILE" "$BACKUP"

python3 - <<'PY'
import json
from pathlib import Path

p = Path("/home/mi/greenhouse_v17/data/registry/action_map.json")
data = json.loads(p.read_text(encoding="utf-8"))

# убираем неудачные generic light actions
data.pop("light_on", None)
data.pop("light_off", None)

# свет верх
data["light_top_on"] = {
    "target_role": "light_top_main",
    "operation": "turn_on"
}
data["light_top_off"] = {
    "target_role": "light_top_main",
    "operation": "turn_off"
}

# свет низ
data["light_bottom_on"] = {
    "target_role": "light_bottom_main",
    "operation": "turn_on"
}
data["light_bottom_off"] = {
    "target_role": "light_bottom_main",
    "operation": "turn_off"
}

# штора
data["curtain_open"] = {
    "target_role": "main_curtain",
    "operation": "open"
}
data["curtain_close"] = {
    "target_role": "main_curtain",
    "operation": "close"
}

p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("OK: action_map fixed with target_role")
PY

echo "Backup: $BACKUP"
