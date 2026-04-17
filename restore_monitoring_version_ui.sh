#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
cd "$ROOT"

SRC="/home/mi/greenhouse_v17/backups/ui_rollback_before_restore_20260418_015905/interfaces/web_admin"

if [ ! -d "$SRC" ]; then
  echo "ERROR: source backup not found: $SRC"
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
SAFETY_BACKUP="$ROOT/backups/before_restore_monitoring_ui_$TS"
mkdir -p "$SAFETY_BACKUP"

backup_if_exists() {
  local path="$1"
  if [ -e "$path" ]; then
    mkdir -p "$SAFETY_BACKUP/$(dirname "$path")"
    cp -R "$path" "$SAFETY_BACKUP/$path"
    echo "[backup] $path"
  fi
}

echo "=== BACKUP CURRENT BROKEN UI ==="
backup_if_exists "interfaces/web_admin"

echo
echo "=== RESTORE MONITORING VERSION UI ==="
rm -rf interfaces/web_admin
mkdir -p interfaces
cp -R "$SRC" interfaces/web_admin

echo
echo "=== RESTORED FILES ==="
find interfaces/web_admin -maxdepth 3 -type f | sort
echo

echo "=== SHOW api.py ==="
sed -n '1,260p' interfaces/web_admin/api.py
echo

echo "=== SHOW web.py ==="
sed -n '1,260p' interfaces/web_admin/routes/web.py
echo

echo "=== RESTART ==="
sudo systemctl restart greenhouse-web-admin.service
sleep 2
sudo systemctl status greenhouse-web-admin.service --no-pager

echo
echo "=== QUICK ROUTE CHECK ==="
for path in /api/health /web/ /web/monitoring /web/registry /web/safety /web/modes /web/ask /web/control; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8081$path" || true)
  echo "$path -> $code"
done

echo
echo "Safety backup: $SAFETY_BACKUP"
echo "Restored from: $SRC"
