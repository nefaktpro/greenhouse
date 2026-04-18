#!/usr/bin/env bash
set -euo pipefail

TPL="/home/mi/greenhouse_v17/interfaces/web_admin/templates"
BACKUP="/home/mi/greenhouse_v17/backups/web_admin_$(date +%Y%m%d_%H%M%S)_result_ui"

mkdir -p "$BACKUP"
cp "$TPL/control.html" "$BACKUP/control.html.bak"

python3 - <<'PY'
from pathlib import Path

p = Path("/home/mi/greenhouse_v17/interfaces/web_admin/templates/control.html")
t = p.read_text(encoding="utf-8")

old = """      GH.showResult(result, `Ответ: ${JSON.stringify(data)}`, "ok");"""

new = """      if (data?.ask_payload || data?.status === "ask_pending") {
        GH.showResult(result, "Действие отправлено в ASK (нужно подтверждение)", "warn");
      } else if (data?.success === true || data?.status === "executed") {
        GH.showResult(result, "Действие выполнено", "ok");
      } else {
        GH.showResult(result, `Ответ: ${JSON.stringify(data)}`, "ok");
      }"""

t = t.replace(old, new)
p.write_text(t, encoding="utf-8")

print("control result improved")
PY
