#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
TPL="$ROOT/interfaces/web_admin/templates"
BACKUP_DIR="$ROOT/backups/web_admin_$(date +%Y%m%d_%H%M%S)_login_control_fix"

mkdir -p "$BACKUP_DIR"

for f in login.html control.html; do
  [ -f "$TPL/$f" ] && cp "$TPL/$f" "$BACKUP_DIR/$f.bak" || true
done

python3 - <<'PY'
from pathlib import Path

tpl = Path("/home/mi/greenhouse_v17/interfaces/web_admin/templates")

# 1) login: placeholder -> value
login = tpl / "login.html"
text = login.read_text(encoding="utf-8")
text = text.replace(
    '<input id="username" class="search" autocomplete="username" placeholder="Mi" />',
    '<input id="username" class="search" autocomplete="username" placeholder="Логин" value="Mi" />'
)
login.write_text(text, encoding="utf-8")

# 2) control: use real endpoint /api/actions/execute
control = tpl / "control.html"
text = control.read_text(encoding="utf-8")

old = """      const data = await GH.postFirstOk([
        { url: `/api/actions/${actionKey}` },
        { url: `/api/control/${actionKey}` },
        { url: `/api/actions/run`, body: { action_key: actionKey } }
      ]);"""

new = """      const data = await GH.api("/api/actions/execute", {
        method: "POST",
        body: { action_key: actionKey }
      });"""

text = text.replace(old, new)
control.write_text(text, encoding="utf-8")

print("login + control fixed")
PY

echo "Backup saved to: $BACKUP_DIR"
