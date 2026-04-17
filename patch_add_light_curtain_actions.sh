#!/usr/bin/env bash
set -euo pipefail

FILE="/home/mi/greenhouse_v17/data/registry/action_map.json"
BACKUP="/home/mi/greenhouse_v17/backups/action_map_$(date +%Y%m%d_%H%M%S)_light_curtain.json"

mkdir -p "$(dirname "$BACKUP")"
cp "$FILE" "$BACKUP"

python3 - <<'PY'
import json
from pathlib import Path

p = Path("/home/mi/greenhouse_v17/data/registry/action_map.json")
data = json.loads(p.read_text(encoding="utf-8"))

def ensure(k, v):
    if k not in data:
        data[k] = v

# Свет (если у тебя свет уже есть в HA как switch/light)
ensure("light_on",  {"operation": "turn_on"})
ensure("light_off", {"operation": "turn_off"})

# Штора (cover)
ensure("curtain_open",  {"operation": "open"})
ensure("curtain_close", {"operation": "close"})

p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("OK: action_map updated")
PY

echo "Backup: $BACKUP"
