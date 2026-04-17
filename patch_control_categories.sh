#!/usr/bin/env bash
set -euo pipefail

TPL="/home/mi/greenhouse_v17/interfaces/web_admin/templates"
BACKUP="/home/mi/greenhouse_v17/backups/web_admin_$(date +%Y%m%d_%H%M%S)_control_categories"

mkdir -p "$BACKUP"
cp "$TPL/control.html" "$BACKUP/control.html.bak"

python3 - <<'PY'
from pathlib import Path

p = Path("/home/mi/greenhouse_v17/interfaces/web_admin/templates/control.html")
t = p.read_text(encoding="utf-8")

start = t.find('<div class="control-grid"')
end = t.find('</div>', start) + 6

new_block = """
<div class="control-grid" style="flex-direction:column; gap:24px;">

  <div>
    <h3>🌪 Вентиляция</h3>
    <button class="btn action-btn on" onclick="runAction('fan_top_on')">Верх ON</button>
    <button class="btn action-btn" onclick="runAction('fan_top_off')">Верх OFF</button>
    <button class="btn action-btn on" onclick="runAction('fan_bottom_on')">Низ ON</button>
    <button class="btn action-btn" onclick="runAction('fan_bottom_off')">Низ OFF</button>
    <button class="btn action-btn on" onclick="runAction('fan_low_on')">Нижний ON</button>
    <button class="btn action-btn" onclick="runAction('fan_low_off')">Нижний OFF</button>
  </div>

  <div>
    <h3>💧 Полив</h3>
    <button class="btn action-btn on" onclick="runAction('watering_top_on')">Верх ON</button>
    <button class="btn action-btn" onclick="runAction('watering_top_off')">Верх OFF</button>
    <button class="btn action-btn on" onclick="runAction('watering_bottom_on')">Низ ON</button>
    <button class="btn action-btn" onclick="runAction('watering_bottom_off')">Низ OFF</button>
  </div>

  <div>
    <h3>🌫 Увлажнение</h3>
    <button class="btn action-btn on" onclick="runAction('humidifier_power_on')">Питание ON</button>
    <button class="btn action-btn" onclick="runAction('humidifier_power_off')">Питание OFF</button>
    <button class="btn action-btn on" onclick="runAction('humidifier_on')">Работа ON</button>
    <button class="btn action-btn" onclick="runAction('humidifier_off')">Работа OFF</button>
  </div>

</div>
"""

t = t[:start] + new_block + t[end:]
p.write_text(t, encoding="utf-8")

print("control categories applied")
PY
