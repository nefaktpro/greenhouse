#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
cd "$ROOT"

SRC="$ROOT/backups/full_webadmin_before_rollback_20260418_020718/interfaces/web_admin"

if [ ! -d "$SRC" ]; then
  echo "ERROR: source backup not found: $SRC"
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
SAFETY="$ROOT/backups/safety_before_full_webadmin_restore_$TS"
mkdir -p "$SAFETY"

echo "=== SAFETY BACKUP CURRENT BROKEN STATE ==="
if [ -e interfaces/web_admin ]; then
  mkdir -p "$SAFETY/interfaces"
  cp -R interfaces/web_admin "$SAFETY/interfaces/"
  echo "[backup] interfaces/web_admin"
fi

echo
echo "=== RESTORE FULL COHERENT WEBADMIN SNAPSHOT ==="
rm -rf interfaces/web_admin
mkdir -p interfaces
cp -R "$SRC" interfaces/web_admin

echo
echo "=== CLEAN PYCACHE ==="
find interfaces/web_admin -type d -name '__pycache__' -prune -exec rm -rf {} + || true

echo
echo "=== RESTORED TREE ==="
find interfaces/web_admin -maxdepth 3 -type f | sort
echo

echo "=== IMPORT TEST ==="
python3 - <<'PY'
import traceback
try:
    import interfaces.web_admin.api as m
    print("IMPORT OK:", bool(m.app))
except Exception:
    traceback.print_exc()
    raise
PY

echo
echo "=== RESTART SERVICE ==="
sudo systemctl restart greenhouse-web-admin.service
sleep 2
sudo systemctl status greenhouse-web-admin.service --no-pager

echo
echo "=== ROUTE CHECK ==="
for path in /api/health /web/ /web/monitoring /web/registry /web/safety /web/modes /web/ask /web/control; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8081$path" || true)
  echo "$path -> $code"
done

echo
echo "=== LAST LOGS ==="
journalctl -u greenhouse-web-admin.service -n 80 --no-pager

echo
echo "Safety backup saved to: $SAFETY"
