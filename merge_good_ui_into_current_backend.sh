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
SAFETY_BACKUP="$ROOT/backups/before_merge_good_ui_$TS"
mkdir -p "$SAFETY_BACKUP"

backup_if_exists() {
  local path="$1"
  if [ -e "$path" ]; then
    mkdir -p "$SAFETY_BACKUP/$(dirname "$path")"
    cp -R "$path" "$SAFETY_BACKUP/$path"
    echo "[backup] $path"
  fi
}

echo "=== BACKUP CURRENT WEB ADMIN ==="
backup_if_exists "interfaces/web_admin"

mkdir -p interfaces/web_admin/routes
mkdir -p interfaces/web_admin/templates
mkdir -p interfaces/web_admin/static

echo
echo "=== RESTORE ONLY UI LAYER ==="

if [ -f "$SRC/routes/web.py" ]; then
  cp "$SRC/routes/web.py" interfaces/web_admin/routes/web.py
  echo "[restored] routes/web.py"
else
  echo "[skip] no routes/web.py in source"
fi

if [ -d "$SRC/templates" ]; then
  rm -rf interfaces/web_admin/templates
  cp -R "$SRC/templates" interfaces/web_admin/templates
  echo "[restored] templates/"
else
  echo "[skip] no templates in source"
fi

if [ -d "$SRC/static" ]; then
  rm -rf interfaces/web_admin/static
  cp -R "$SRC/static" interfaces/web_admin/static
  echo "[restored] static/"
else
  echo "[skip] no static in source"
fi

echo
echo "=== KEEP CURRENT BACKEND FILES ==="
ls -1 interfaces/web_admin/routes || true
echo

echo "=== CHECK api.py EXISTS ==="
if [ ! -f interfaces/web_admin/api.py ]; then
  echo "ERROR: interfaces/web_admin/api.py missing"
  exit 1
fi

echo
echo "=== SHOW api.py ==="
sed -n '1,260p' interfaces/web_admin/api.py
echo

echo "=== QUICK PATCH FOR web.py PREFIX IF NEEDED ==="
python3 - <<'PY'
from pathlib import Path
p = Path("/home/mi/greenhouse_v17/interfaces/web_admin/routes/web.py")
text = p.read_text(encoding="utf-8")

# если в старом web.py router без prefix — оставляем как есть, потому что api.py обычно include_router(..., prefix="/web")
# если там уже prefix="/web", тоже ок
print("[info] web.py loaded:", p)
PY

echo
echo "=== RESTART ==="
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
echo "Safety backup: $SAFETY_BACKUP"
