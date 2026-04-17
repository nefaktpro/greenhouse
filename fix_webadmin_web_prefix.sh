#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
TPL="$ROOT/interfaces/web_admin/templates"
BACKUP_DIR="$ROOT/backups/web_admin_$(date +%Y%m%d_%H%M%S)_webprefix_fix"

mkdir -p "$BACKUP_DIR"

for f in base.html login.html dashboard.html; do
  [ -f "$TPL/$f" ] && cp "$TPL/$f" "$BACKUP_DIR/$f.bak" || true
done

python3 - <<'PY'
from pathlib import Path

tpl = Path("/home/mi/greenhouse_v17/interfaces/web_admin/templates")

base = tpl / "base.html"
text = base.read_text(encoding="utf-8")

repls = {
    'href="/" data-nav="dashboard"': 'href="/web/" data-nav="dashboard"',
    'href="/control" data-nav="control"': 'href="/web/control" data-nav="control"',
    'href="/ask" data-nav="ask"': 'href="/web/ask" data-nav="ask"',
    'href="/modes" data-nav="modes"': 'href="/web/modes" data-nav="modes"',
    'href="/registry" data-nav="registry"': 'href="/web/registry" data-nav="registry"',
    'href="/login" data-nav="login"': 'href="/web/login" data-nav="login"',
    'location.href = "/login";': 'location.href = "/web/login";',
    'location.href = "/login"': 'location.href = "/web/login"',
}
for old, new in repls.items():
    text = text.replace(old, new)

# logout()
text = text.replace('location.href = "/web/login";', 'location.href = "/web/login";')

base.write_text(text, encoding="utf-8")

login = tpl / "login.html"
text = login.read_text(encoding="utf-8")
text = text.replace('setTimeout(() => location.href = "/", 400);', 'setTimeout(() => location.href = "/web/", 400);')
login.write_text(text, encoding="utf-8")

dashboard = tpl / "dashboard.html"
text = dashboard.read_text(encoding="utf-8")
text = text.replace('href="/control"', 'href="/web/control"')
text = text.replace('href="/ask"', 'href="/web/ask"')
text = text.replace('href="/modes"', 'href="/web/modes"')
text = text.replace('href="/registry"', 'href="/web/registry"')
dashboard.write_text(text, encoding="utf-8")

print("web prefix fixed")
PY

echo "Backup saved to: $BACKUP_DIR"
