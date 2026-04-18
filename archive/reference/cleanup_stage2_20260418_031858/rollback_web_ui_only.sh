#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
cd "$ROOT"

echo "=== FINDING ORIGINAL UI BACKUP ==="
ORIG_BACKUP="$(find "$ROOT/backups" -maxdepth 1 -type d -name 'patch_bundle_*' | sort | head -n 1)"

if [ -z "${ORIG_BACKUP:-}" ]; then
  echo "ERROR: original patch_bundle backup not found"
  exit 1
fi

echo "Using backup: $ORIG_BACKUP"

TS="$(date +%Y%m%d_%H%M%S)"
SAFETY_BACKUP="$ROOT/backups/ui_rollback_before_restore_$TS"
mkdir -p "$SAFETY_BACKUP"

backup_if_exists() {
  local path="$1"
  if [ -e "$path" ]; then
    mkdir -p "$SAFETY_BACKUP/$(dirname "$path")"
    cp -R "$path" "$SAFETY_BACKUP/$path"
    echo "[backup] $path"
  fi
}

restore_if_exists() {
  local rel="$1"
  if [ -e "$ORIG_BACKUP/$rel" ]; then
    mkdir -p "$(dirname "$rel")"
    rm -rf "$rel"
    cp -R "$ORIG_BACKUP/$rel" "$rel"
    echo "[restored] $rel"
  else
    echo "[skip] not found in original backup: $rel"
  fi
}

echo
echo "=== BACKUP CURRENT UI FILES ==="
backup_if_exists "interfaces/web_admin/routes/web.py"
backup_if_exists "interfaces/web_admin/templates"
backup_if_exists "interfaces/web_admin/static"

echo
echo "=== RESTORE ORIGINAL UI ==="
restore_if_exists "interfaces/web_admin/routes/web.py"
restore_if_exists "interfaces/web_admin/templates"
restore_if_exists "interfaces/web_admin/static"

echo
echo "=== PATCH ROOT SAFELY IF NEEDED ==="
python3 - <<'PY'
from pathlib import Path
p = Path("/home/mi/greenhouse_v17/interfaces/web_admin/routes/web.py")
text = p.read_text(encoding="utf-8")

# Если в оригинальном web.py нет явного /web/control — не страшно.
# Главное: не ломаем старые рабочие страницы.
# При этом если root рендерит отсутствующий index.html — мягко ведем на monitoring.
if 'TemplateResponse("index.html"' in text and 'monitoring.html' in text:
    text = text.replace('TemplateResponse("index.html", {"request": request})',
                        'TemplateResponse("monitoring.html", {"request": request})')
    text = text.replace('TemplateResponse(request=request, name="index.html", context={"request": request})',
                        'TemplateResponse(request=request, name="monitoring.html", context={"request": request})')

p.write_text(text, encoding="utf-8")
print("[patched if needed] routes/web.py")
PY

echo
echo "=== RESTART ==="
sudo systemctl restart greenhouse-web-admin.service
sleep 2
sudo systemctl status greenhouse-web-admin.service --no-pager

echo
echo "=== QUICK CHECKS ==="
for path in /web/ /web/monitoring /web/registry /web/safety; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8081$path" || true)
  echo "$path -> $code"
done

echo
echo "Safety backup: $SAFETY_BACKUP"
echo "Original UI backup used: $ORIG_BACKUP"
