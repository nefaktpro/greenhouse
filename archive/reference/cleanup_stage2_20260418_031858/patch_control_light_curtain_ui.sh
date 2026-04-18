#!/usr/bin/env bash
set -euo pipefail

TPL="/home/mi/greenhouse_v17/interfaces/web_admin/templates"
BACKUP="/home/mi/greenhouse_v17/backups/control_$(date +%Y%m%d_%H%M%S)_light_curtain"

mkdir -p "$BACKUP"
cp "$TPL/control.html" "$BACKUP/control.html.bak"

python3 - <<'PY'
from pathlib import Path

p = Path("/home/mi/greenhouse_v17/interfaces/web_admin/templates/control.html")
t = p.read_text(encoding="utf-8")

# Вставим блоки в конец control-grid (не ломая существующие категории)
insert = """
  <div>
    <h3>💡 Свет</h3>
    <button class="btn action-btn on" onclick="runAction('light_on')">Свет ON</button>
    <button class="btn action-btn" onclick="runAction('light_off')">Свет OFF</button>
  </div>

  <div>
    <h3>🪟 Штора</h3>
    <button class="btn action-btn on" onclick="runAction('curtain_open')">Открыть</button>
    <button class="btn action-btn" onclick="runAction('curtain_close')">Закрыть</button>
  </div>
"""

# Найдём последний control-grid и аккуратно добавим внутрь
anchor = 'class="control-grid"'
idx = t.rfind(anchor)
if idx == -1:
    raise SystemExit("control-grid not found")

# Найдём закрывающий </div> этого блока
start = t.find('>', idx) + 1
depth = 1
i = start
while i < len(t) and depth > 0:
    if t.startswith('<div', i):
        depth += 1
        i += 4
    elif t.startswith('</div>', i):
        depth -= 1
        if depth == 0:
            end = i
            break
        i += 6
    else:
        i += 1

new_t = t[:end] + insert + t[end:]
p.write_text(new_t, encoding="utf-8")
print("OK: control UI updated")
PY

echo "Backup: $BACKUP"
