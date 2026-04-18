#!/usr/bin/env bash
set -euo pipefail

TPL="/home/mi/greenhouse_v17/interfaces/web_admin/templates"
BACKUP="/home/mi/greenhouse_v17/backups/web_admin_$(date +%Y%m%d_%H%M%S)_ask_refresh"

mkdir -p "$BACKUP"
cp "$TPL/ask.html" "$BACKUP/ask.html.bak"

python3 - <<'PY'
from pathlib import Path

p = Path("/home/mi/greenhouse_v17/interfaces/web_admin/templates/ask.html")
t = p.read_text(encoding="utf-8")

inject = """
  // авто-обновление каждые 5 секунд
  setInterval(loadAsk, 5000);
"""

t = t.replace("loadAsk();", "loadAsk();" + inject)

p.write_text(t, encoding="utf-8")

print("ask auto-refresh added")
PY
