#!/usr/bin/env bash
set -euo pipefail

TPL="/home/mi/greenhouse_v17/interfaces/web_admin/templates/control.html"
BACKUP="/home/mi/greenhouse_v17/backups/control_$(date +%Y%m%d_%H%M%S)_light_buttons_fix.html"

cp "$TPL" "$BACKUP"

python3 - <<'PY'
from pathlib import Path

p = Path("/home/mi/greenhouse_v17/interfaces/web_admin/templates/control.html")
t = p.read_text(encoding="utf-8")

t = t.replace("runAction('light_on')", "runAction('light_top_on')")
t = t.replace("runAction('light_off')", "runAction('light_top_off')")

old_block = """    <h3>💡 Свет</h3>
    <button class="btn action-btn on" onclick="runAction('light_top_on')">Свет ON</button>
    <button class="btn action-btn" onclick="runAction('light_top_off')">Свет OFF</button>"""

new_block = """    <h3>💡 Свет</h3>
    <button class="btn action-btn on" onclick="runAction('light_top_on')">Верх ON</button>
    <button class="btn action-btn" onclick="runAction('light_top_off')">Верх OFF</button>
    <button class="btn action-btn on" onclick="runAction('light_bottom_on')">Низ ON</button>
    <button class="btn action-btn" onclick="runAction('light_bottom_off')">Низ OFF</button>"""

t = t.replace(old_block, new_block)

p.write_text(t, encoding="utf-8")
print("OK: control light buttons fixed")
PY
