#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
cd "$ROOT"

BASE_SHELL="$ROOT/recovery_dump/backups/backups/full_webadmin_before_rollback_20260418_020718/interfaces/web_admin"
UI_RICH="$ROOT/recovery_dump/backups/backups/ui_rollback_before_restore_20260418_015905/interfaces/web_admin"
EXEC_SRC="$ROOT/recovery_dump/current/services/webadmin_execution_service.py"

echo "=== CHECK SOURCES ==="
for p in "$BASE_SHELL" "$UI_RICH" "$EXEC_SRC"; do
  if [ ! -e "$p" ]; then
    echo "ERROR: missing source: $p"
    exit 1
  fi
  echo "OK: $p"
done
echo

TS="$(date +%Y%m%d_%H%M%S)"
SAFETY="$ROOT/backups/final_restore_everything_$TS"
mkdir -p "$SAFETY"

backup_if_exists() {
  local path="$1"
  if [ -e "$path" ]; then
    mkdir -p "$SAFETY/$(dirname "$path")"
    cp -R "$path" "$SAFETY/$path"
    echo "[backup] $path"
  fi
}

echo "=== SAFETY BACKUP CURRENT STATE ==="
backup_if_exists "interfaces/web_admin"
backup_if_exists "greenhouse_v17/services/webadmin_execution_service.py"
backup_if_exists "data/registry/action_map.json"
echo

echo "=== RESTORE BASE SHELL ==="
rm -rf interfaces/web_admin
mkdir -p interfaces
cp -R "$BASE_SHELL" interfaces/web_admin
echo "[restored] interfaces/web_admin from full shell"
echo

echo "=== OVERLAY RICH UI ==="
if [ -d "$UI_RICH/templates" ]; then
  rm -rf interfaces/web_admin/templates
  cp -R "$UI_RICH/templates" interfaces/web_admin/templates
  echo "[overlay] templates"
fi

if [ -d "$UI_RICH/static" ]; then
  rm -rf interfaces/web_admin/static
  cp -R "$UI_RICH/static" interfaces/web_admin/static
  echo "[overlay] static"
fi

if [ -f "$UI_RICH/routes/web.py" ]; then
  cp "$UI_RICH/routes/web.py" interfaces/web_admin/routes/web.py
  echo "[overlay] routes/web.py"
fi
echo

echo "=== RESTORE WORKING EXECUTION SERVICE ==="
mkdir -p greenhouse_v17/services
cp "$EXEC_SRC" greenhouse_v17/services/webadmin_execution_service.py
echo "[restored] greenhouse_v17/services/webadmin_execution_service.py"
echo

echo "=== ENSURE PACKAGE FILES ==="
mkdir -p interfaces/web_admin/routes
touch interfaces/__init__.py
touch interfaces/web_admin/__init__.py
touch interfaces/web_admin/routes/__init__.py
touch greenhouse_v17/__init__.py
touch greenhouse_v17/services/__init__.py
echo

echo "=== CLEAN PYCACHE ==="
find interfaces/web_admin -type d -name '__pycache__' -prune -exec rm -rf {} + || true
find greenhouse_v17 -type d -name '__pycache__' -prune -exec rm -rf {} + || true
echo

echo "=== SHOW RESTORED TREE ==="
find interfaces/web_admin -maxdepth 3 -type f | sort
echo

echo "=== IMPORT TEST: execution service ==="
python3 - <<'PY'
from greenhouse_v17.services.webadmin_execution_service import resolve_action, debug_action_map_full
print("execution import ok")
print(debug_action_map_full("fan_top_on"))
print(resolve_action("fan_top_on"))
PY
echo

echo "=== IMPORT TEST: web_admin api ==="
python3 - <<'PY'
import traceback
try:
    import interfaces.web_admin.api as m
    print("api import ok:", bool(m.app))
except Exception:
    traceback.print_exc()
    raise
PY
echo

echo "=== RESTART SERVICE ==="
sudo systemctl restart greenhouse-web-admin.service
sleep 3
sudo systemctl status greenhouse-web-admin.service --no-pager
echo

echo "=== ROUTE CHECK ==="
for path in /api/health /api/actions/debug/action-map /api/ask/current /api/modes/current /api/registry/devices /api/monitoring/overview /api/monitoring/safety /web/ /web/monitoring /web/registry /web/safety /web/modes /web/ask /web/control; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8081$path" || true)
  echo "$path -> $code"
done
echo

echo "=== LAST LOGS ==="
journalctl -u greenhouse-web-admin.service -n 120 --no-pager
echo

echo "=== GIT SAVE ==="
git status --short
git add interfaces/web_admin greenhouse_v17/services/webadmin_execution_service.py
git commit -m "Restore coherent web_admin from recovery dump" || true
git push origin recovery/webadmin-backups
echo

echo "=== DONE ==="
echo "Safety backup: $SAFETY"
