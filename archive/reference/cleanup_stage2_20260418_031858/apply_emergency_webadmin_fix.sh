#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
cd "$ROOT"

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/backups/emergency_webadmin_fix_$TS"
mkdir -p "$BACKUP_DIR"

backup_if_exists() {
  local path="$1"
  if [ -f "$path" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$path")"
    cp "$path" "$BACKUP_DIR/$path"
    echo "[backup] $path"
  fi
}

backup_if_exists "interfaces/web_admin/routes/actions.py"
backup_if_exists "greenhouse_v17/services/webadmin_execution_service.py"

python3 - <<'PY'
from pathlib import Path

# 1) Чиним импорт и debug endpoint в actions.py
actions_path = Path("/home/mi/greenhouse_v17/interfaces/web_admin/routes/actions.py")
text = actions_path.read_text(encoding="utf-8")

text = text.replace(
    "from greenhouse_v17.services.webadmin_execution_service import execute_action, create_pending_ask, debug_action_map_summary",
    "from greenhouse_v17.services.webadmin_execution_service import execute_action, create_pending_ask, debug_action_map_full",
)

text = text.replace(
    'return {"ok": True, "debug": debug_action_map_summary()}',
    'return {"ok": True, "debug": debug_action_map_full()}',
)

actions_path.write_text(text, encoding="utf-8")
print("[patched] interfaces/web_admin/routes/actions.py")
PY

python3 - <<'PY'
from pathlib import Path

svc_path = Path("/home/mi/greenhouse_v17/greenhouse_v17/services/webadmin_execution_service.py")
text = svc_path.read_text(encoding="utf-8")

old = """    if not entity_id:
        # вариант через logical_role / capability — для тестовых вентиляторов делаем fallback
        logical_role = str(node.get("logical_role") or node.get("role") or "").strip().lower()
        if logical_role in {"top_air_circulation", "fan_top", "top_fan"}:
            entity_id = "switch.setevoi_filtr_novyi_socket_1"
        elif logical_role in {"bottom_air_circulation", "fan_bottom", "fan_low", "bottom_fan"}:
            entity_id = "switch.setevoi_filtr_novyi_socket_2"
"""

new = """    if not entity_id:
        # вариант через logical_role / target_role / capability — для тестовых вентиляторов делаем fallback
        logical_role = str(
            node.get("logical_role")
            or node.get("target_role")
            or node.get("capability")
            or node.get("role")
            or ""
        ).strip().lower()

        if logical_role in {"top_air_circulation", "fan_top", "top_fan"}:
            entity_id = "switch.setevoi_filtr_novyi_socket_1"
        elif logical_role in {"bottom_air_circulation", "fan_bottom", "fan_low", "bottom_fan"}:
            entity_id = "switch.setevoi_filtr_novyi_socket_2"
"""

if old not in text:
    raise SystemExit("Expected resolver block not found; stop to avoid corrupt patch.")

text = text.replace(old, new)

# 2) Добавим alias-совместимость, чтобы старый импорт не валил сервис
if "def debug_action_map_summary() -> Dict[str, Any]:" not in text:
    marker = 'def debug_action_map_full(action_key: Optional[str] = None) -> Dict[str, Any]:\n'
    idx = text.find(marker)
    if idx == -1:
        raise SystemExit("debug_action_map_full marker not found")
    # вставим alias после функции debug_action_map_full
    insert_after = text.find("return payload", idx)
    if insert_after == -1:
        raise SystemExit("return payload not found in debug_action_map_full")
    line_end = text.find("\n", insert_after)
    alias = """

def debug_action_map_summary() -> Dict[str, Any]:
    return debug_action_map_full()
"""
    text = text[:line_end+1] + alias + text[line_end+1:]

svc_path.write_text(text, encoding="utf-8")
print("[patched] greenhouse_v17/services/webadmin_execution_service.py")
PY

echo
echo "=== EMERGENCY FIX APPLIED ==="
echo "Backups: $BACKUP_DIR"
