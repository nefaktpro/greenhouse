#!/usr/bin/env bash
set -euo pipefail

FILE="$HOME/greenhouse_v17/interfaces/web_admin/routes/web.py"
BACKUP="$HOME/greenhouse_v17/backups/web_py_$(date +%Y%m%d_%H%M%S)_templateresponse_fix.py"

mkdir -p "$(dirname "$BACKUP")"
cp "$FILE" "$BACKUP"

python3 - <<'PY'
from pathlib import Path

p = Path.home() / "greenhouse_v17" / "interfaces" / "web_admin" / "routes" / "web.py"
text = p.read_text(encoding="utf-8")

text = text.replace(
    'return templates.TemplateResponse("monitoring.html", {"request": request})',
    'return templates.TemplateResponse(request, "monitoring.html", {})'
)

text = text.replace(
    'return templates.TemplateResponse("safety.html", {"request": request})',
    'return templates.TemplateResponse(request, "safety.html", {})'
)

p.write_text(text, encoding="utf-8")
print("OK: TemplateResponse order fixed for monitoring/safety")
PY

echo "Backup: $BACKUP"
