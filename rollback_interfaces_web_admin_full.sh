#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
cd "$ROOT"

echo "=== SEARCH BACKUPS FOR OLD WEB ADMIN ==="

find "$ROOT/backups" -maxdepth 2 -type f | grep 'interfaces/web_admin' || true
echo

TS="$(date +%Y%m%d_%H%M%S)"
SAFETY_BACKUP="$ROOT/backups/full_webadmin_before_rollback_$TS"
mkdir -p "$SAFETY_BACKUP"

backup_if_exists() {
  local path="$1"
  if [ -e "$path" ]; then
    mkdir -p "$SAFETY_BACKUP/$(dirname "$path")"
    cp -R "$path" "$SAFETY_BACKUP/$path"
    echo "[backup] $path"
  fi
}

echo "=== BACKUP CURRENT interfaces/web_admin ==="
backup_if_exists "interfaces/web_admin"

echo
echo "=== CHOOSING SOURCE BACKUP ==="

# 1) сначала пробуем самый ранний patch_bundle
SRC=""
if [ -d "$ROOT/backups/patch_bundle_20260418_014001/interfaces/web_admin" ]; then
  SRC="$ROOT/backups/patch_bundle_20260418_014001/interfaces/web_admin"
fi

# 2) если нет — ищем любой самый ранний backup, где есть web_admin
if [ -z "$SRC" ]; then
  SRC="$(find "$ROOT/backups" -type d -path '*/interfaces/web_admin' | sort | head -n 1 || true)"
fi

if [ -z "$SRC" ]; then
  echo "ERROR: no backup source with interfaces/web_admin found"
  exit 1
fi

echo "Using source: $SRC"

echo
echo "=== RESTORE interfaces/web_admin ==="
rm -rf "$ROOT/interfaces/web_admin"
mkdir -p "$ROOT/interfaces"
cp -R "$SRC" "$ROOT/interfaces/web_admin"

echo
echo "=== SHOW RESTORED FILES ==="
find "$ROOT/interfaces/web_admin" -maxdepth 3 -type f | sort
echo

echo "=== OPTIONAL CLEAN: __pycache__ ==="
find "$ROOT/interfaces/web_admin" -type d -name '__pycache__' -prune -exec rm -rf {} + || true

echo
echo "=== RESTART SERVICE ==="
sudo systemctl restart greenhouse-web-admin.service
sleep 2
sudo systemctl status greenhouse-web-admin.service --no-pager

echo
echo "=== QUICK HTTP CHECKS ==="
for path in / /web/ /web/monitoring /web/registry /web/safety /web/modes /web/ask /web/control /api/health; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8081$path" || true)
  echo "$path -> $code"
done

echo
echo "Safety backup saved to: $SAFETY_BACKUP"
echo "Restored from: $SRC"
