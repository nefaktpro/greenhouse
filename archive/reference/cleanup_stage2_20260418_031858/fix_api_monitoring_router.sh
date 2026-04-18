#!/usr/bin/env bash
set -euo pipefail

FILE="$HOME/greenhouse_v17/interfaces/web_admin/api.py"
BACKUP="$HOME/greenhouse_v17/backups/api_py_$(date +%Y%m%d_%H%M%S)_monitoring_fix.py"

mkdir -p "$(dirname "$BACKUP")"
cp "$FILE" "$BACKUP"

python3 - <<'PY'
from pathlib import Path
p = Path.home() / "greenhouse_v17" / "interfaces" / "web_admin" / "api.py"
text = p.read_text(encoding="utf-8")

# 1. Убираем битые варианты include/import, если они есть
text = text.replace("app.include_router(monitoring_router)", "app.include_router(router_monitoring)")
text = text.replace("from interfaces.web_admin.routes.monitoring import router as monitoring_router",
                    "from interfaces.web_admin.routes.monitoring import router as router_monitoring")

# 2. Если импорта вообще нет — добавляем
import_line = "from interfaces.web_admin.routes.monitoring import router as router_monitoring"
if import_line not in text:
    marker = "from interfaces.web_admin.routes.web import router as web_router"
    if marker in text:
        text = text.replace(marker, marker + "\n" + import_line)
    else:
        # fallback: просто в начало блока импортов
        text = import_line + "\n" + text

# 3. Если include вообще нет — добавляем
if "app.include_router(router_monitoring)" not in text:
    text = text.rstrip() + "\napp.include_router(router_monitoring)\n"

p.write_text(text, encoding="utf-8")
print("OK: api.py monitoring router fixed")
PY

echo "Backup: $BACKUP"
