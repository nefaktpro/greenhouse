#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v2"
PKG="$ROOT/greenhouse_v17"

if [ ! -d "$PKG" ]; then
  echo "ERROR: expected package dir $PKG"
  exit 1
fi

echo "==> backup touched files"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/backups/big_patch_$STAMP"
mkdir -p "$BACKUP_DIR"

for f in \
  "$PKG/interfaces/telegram_v3/handlers.py" \
  "$PKG/services/ha_client.py" \
  "$PKG/services/mode_service.py" \
  "$PKG/registry/loader.py" \
  "$ROOT/.gitignore"
do
  if [ -f "$f" ]; then
    cp "$f" "$BACKUP_DIR/$(basename "$f").bak"
  fi
done

echo "==> create dirs"
mkdir -p \
  "$PKG/core" \
  "$PKG/core/feedback" \
  "$PKG/core/intent" \
  "$PKG/services" \
  "$ROOT/data/registry" \
  "$ROOT/data/runtime" \
  "$ROOT/data/logs" \
  "$ROOT/data/memory"

touch \
  "$PKG/core/__init__.py" \
  "$PKG/core/feedback/__init__.py" \
  "$PKG/core/intent/__init__.py"

echo "==> extend .gitignore"
grep -q "data/runtime/" "$ROOT/.gitignore" 2>/dev/null || cat >> "$ROOT/.gitignore" <<'EOF'

# runtime / logs / memory
data/runtime/
data/logs/
*.bak
*.save
*.pynano
.env.save
decision_log.json
system_state.json
ask_state.json
observations.json
EOF

echo "==> create runtime path helpers"
cat > "$PKG/services/runtime_paths.py" <<'PY'
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
REGISTRY_DIR = DATA_DIR / "registry"
RUNTIME_DIR = DATA_DIR / "runtime"
LOGS_DIR = DATA_DIR / "logs"
MEMORY_DIR = DATA_DIR / "memory"

ASK_STATE_PATH = RUNTIME_DIR / "ask_state.json"
SYSTEM_STATE_PATH = RUNTIME_DIR / "system_state.json"
DECISION_LOG_PATH = LOGS_DIR / "decision_log.json"
OBSERVATIONS_PATH = MEMORY_DIR / "observations.json"

def ensure_runtime_dirs() -> None:
    for p in [DATA_DIR, REGISTRY_DIR, RUNTIME_DIR, LOGS_DIR, MEMORY_DIR]:
        p.mkdir(parents=True, exist_ok=True)
PY

echo "==> create ask service"
cat > "$PKG/services/ask_service.py" <<'PY'
import json
from datetime import datetime
from typing import Any, Dict, Optional

from greenhouse_v17.services.runtime_paths import ASK_STATE_PATH, ensure_runtime_dirs

def save_ask_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_runtime_dirs()
    data = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        **payload,
    }
    ASK_STATE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data

def load_ask_state() -> Optional[Dict[str, Any]]:
    ensure_runtime_dirs()
    if not ASK_STATE_PATH.exists():
        return None
    try:
        return json.loads(ASK_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None

def clear_ask_state() -> None:
    ensure_runtime_dirs()
    if ASK_STATE_PATH.exists():
        ASK_STATE_PATH.unlink()
PY

echo "==> create feedback engine"
cat > "$PKG/core/feedback/feedback_engine.py" <<'PY'
from __future__ import annotations

import requests
from typing import Optional, Dict, Any

def _load_ha_config():
    # try several naming variants to survive transitional config
    try:
        from greenhouse_v17.config import HOME_ASSISTANT_URL as url
    except Exception:
        try:
            from greenhouse_v17.config import HA_BASE_URL as url
        except Exception:
            from greenhouse_v17.config import HOME_ASSISTANT_BASE_URL as url  # type: ignore
    try:
        from greenhouse_v17.config import HOME_ASSISTANT_TOKEN as token
    except Exception:
        try:
            from greenhouse_v17.config import HA_TOKEN as token
        except Exception:
            from greenhouse_v17.config import HOME_ASSISTANT_ACCESS_TOKEN as token  # type: ignore
    try:
        from greenhouse_v17.config import REQUEST_TIMEOUT as timeout
    except Exception:
        timeout = 10
    return url.rstrip("/"), token, timeout

def get_entity_state(entity_id: str) -> Dict[str, Any]:
    base_url, token, timeout = _load_ha_config()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    r = requests.get(
        f"{base_url}/api/states/{entity_id}",
        headers=headers,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()

def verify_entity_state(entity_id: str, expected_state: Optional[str]) -> Dict[str, Any]:
    try:
        payload = get_entity_state(entity_id)
        actual = str(payload.get("state"))
        ok = expected_state is None or actual == expected_state
        return {
            "ok": ok,
            "entity_id": entity_id,
            "expected_state": expected_state,
            "actual_state": actual,
            "last_updated": payload.get("last_updated"),
        }
    except Exception as e:
        return {
            "ok": False,
            "entity_id": entity_id,
            "expected_state": expected_state,
            "actual_state": None,
            "error": str(e),
        }
PY

echo "==> create intent router"
cat > "$PKG/core/intent/intent_router.py" <<'PY'
from __future__ import annotations

from typing import Dict, Optional

BUTTON_TO_ACTION = {
    "🌬 верх вкл": "fan_top_on",
    "🌬 верх выкл": "fan_top_off",
    "🌬 низ вкл": "fan_bottom_on",
    "🌬 низ выкл": "fan_bottom_off",
    "💧 увлажнитель вкл": "humidifier_on",
    "💧 увлажнитель выкл": "humidifier_off",
    "⚡ питание веранды выкл": "veranda_power_off",
    "⚡ питание веранды вкл": "veranda_power_on",
}

TEXT_PATTERNS = [
    (("вент", "верх", "выключ"), "fan_top_off"),
    (("вент", "верх", "отключ"), "fan_top_off"),
    (("вент", "верх"), "fan_top_on"),
    (("вент", "низ", "выключ"), "fan_bottom_off"),
    (("вент", "низ", "отключ"), "fan_bottom_off"),
    (("вент", "ниж", "выключ"), "fan_bottom_off"),
    (("вент", "ниж", "отключ"), "fan_bottom_off"),
    (("вент", "низ"), "fan_bottom_on"),
    (("вент", "ниж"), "fan_bottom_on"),
    (("увлаж", "выключ"), "humidifier_off"),
    (("увлаж", "отключ"), "humidifier_off"),
    (("увлаж",), "humidifier_on"),
    (("питание", "веранд", "выключ"), "veranda_power_off"),
    (("питание", "веранд", "отключ"), "veranda_power_off"),
    (("питание", "веранд", "включ"), "veranda_power_on"),
]

def normalize_text(text: str) -> str:
    return (
        (text or "")
        .lower()
        .replace("ё", "е")
        .replace("?", "")
        .replace("!", "")
        .replace("📊", "")
        .replace("🤖", "")
        .replace("🌬", "")
        .replace("💧", "")
        .replace("⚡", "")
        .strip()
    )

def route_text(text: str) -> Dict[str, Optional[str]]:
    normalized = normalize_text(text)

    if normalized == "режим":
        return {"intent_type": "mode_status", "action_key": None, "confidence": "high"}

    if normalized == "статус":
        return {"intent_type": "status", "action_key": None, "confidence": "high"}

    if normalized in BUTTON_TO_ACTION:
        return {"intent_type": "device_action", "action_key": BUTTON_TO_ACTION[normalized], "confidence": "high"}

    for tokens, action_key in TEXT_PATTERNS:
        if all(tok in normalized for tok in tokens):
            return {"intent_type": "device_action", "action_key": action_key, "confidence": "medium"}

    if normalized.startswith("/"):
        slash = normalized[1:]
        slash_map = {
            "fan_top_on": "fan_top_on",
            "fan_top_off": "fan_top_off",
            "fan_low_on": "fan_bottom_on",
            "fan_low_off": "fan_bottom_off",
            "humidifier_on": "humidifier_on",
            "humidifier_off": "humidifier_off",
        }
        if slash in slash_map:
            return {"intent_type": "device_action", "action_key": slash_map[slash], "confidence": "high"}
        if slash == "mode":
            return {"intent_type": "mode_status", "action_key": None, "confidence": "high"}
        if slash == "status":
            return {"intent_type": "status", "action_key": None, "confidence": "high"}

    return {"intent_type": "unknown", "action_key": None, "confidence": "low"}
PY

echo "==> create action service"
cat > "$PKG/services/action_service.py" <<'PY'
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from greenhouse_v17.registry.loader import resolve_action_to_entity
from greenhouse_v17.services.mode_service import get_mode
from greenhouse_v17.services.ha_client import call_switch
from greenhouse_v17.services.ask_service import save_ask_state
from greenhouse_v17.services.runtime_paths import REGISTRY_DIR, ensure_runtime_dirs
from greenhouse_v17.core.feedback.feedback_engine import verify_entity_state

ACTION_TARGET_ROLE = {
    "fan_top_on": "top_air_circulation",
    "fan_top_off": "top_air_circulation",
    "fan_bottom_on": "bottom_air_circulation",
    "fan_bottom_off": "bottom_air_circulation",
    "humidifier_on": "main_humidifier",
    "humidifier_off": "main_humidifier",
    "veranda_power_off": "veranda_main_power_cutoff",
    "veranda_power_on": "veranda_main_power_cutoff",
}

def _load_capabilities() -> Dict[str, Any]:
    ensure_runtime_dirs()
    p = REGISTRY_DIR / "device_capabilities.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _check_caps(action_key: str, mode: str) -> Optional[str]:
    role = ACTION_TARGET_ROLE.get(action_key)
    if not role:
        return None
    caps = _load_capabilities().get(role, {})
    if not caps:
        return None
    allowed_modes = caps.get("allowed_modes") or []
    allowed_actions = caps.get("allowed_actions") or []
    if allowed_modes and mode not in allowed_modes:
        return f"Роль {role} запрещена в режиме {mode}"
    resolved = resolve_action_to_entity(action_key)
    operation = resolved["operation"]
    if allowed_actions and operation not in allowed_actions:
        return f"Операция {operation} запрещена для роли {role}"
    return None

def _human_title(action_key: str) -> str:
    titles = {
        "fan_top_on": "Верх: включить вентиляторы",
        "fan_top_off": "Верх: выключить вентиляторы",
        "fan_bottom_on": "Низ: включить вентиляторы",
        "fan_bottom_off": "Низ: выключить вентиляторы",
        "humidifier_on": "Увлажнитель: включить",
        "humidifier_off": "Увлажнитель: выключить",
        "veranda_power_off": "Питание веранды: выключить",
        "veranda_power_on": "Питание веранды: включить",
    }
    return titles.get(action_key, action_key)

def execute_action(action_key: str, force_execute: bool = False) -> Dict[str, Any]:
    mode = get_mode()
    cap_error = _check_caps(action_key, mode)
    if cap_error:
        return {
            "status": "blocked",
            "mode": mode,
            "action_key": action_key,
            "message": cap_error,
        }

    if mode == "ASK" and not force_execute:
        payload = save_ask_state(
            {
                "kind": "single_action",
                "action_key": action_key,
                "title": _human_title(action_key),
                "mode": mode,
            }
        )
        return {
            "status": "ask",
            "mode": mode,
            "action_key": action_key,
            "title": payload["title"],
            "message": "Требуется подтверждение",
        }

    resolved = resolve_action_to_entity(action_key)
    entity_id = resolved["entity_id"]
    operation = resolved["operation"]

    if mode == "TEST" and not force_execute:
        return {
            "status": "dry_run",
            "mode": mode,
            "action_key": action_key,
            "entity_id": entity_id,
            "operation": operation,
            "message": "TEST: команда распознана, но не исполнена",
        }

    if operation not in ("turn_on", "turn_off"):
        return {
            "status": "unsupported",
            "mode": mode,
            "action_key": action_key,
            "entity_id": entity_id,
            "operation": operation,
            "message": f"Пока поддерживается только switch on/off. Получено: {operation}",
        }

    result = call_switch(entity_id, turn_on=(operation == "turn_on"))
    expected_state = "on" if operation == "turn_on" else "off"
    verify = verify_entity_state(entity_id, expected_state=expected_state)

    return {
        "status": "executed" if verify.get("ok") else "degraded",
        "mode": mode,
        "action_key": action_key,
        "entity_id": entity_id,
        "operation": operation,
        "ha_result": result,
        "verify": verify,
        "message": _human_title(action_key),
    }
PY

echo "==> create initial capabilities file if empty or missing"
python3 - <<'PY'
from pathlib import Path
import json

p = Path("/home/mi/greenhouse_v2/data/registry/device_capabilities.json")
data = {}
if p.exists():
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}

base = {
  "top_air_circulation": {
    "allowed_actions": ["turn_on", "turn_off"],
    "allowed_modes": ["MANUAL", "TEST", "ASK", "AUTO", "AUTOPILOT"],
    "dependencies": [],
    "constraints": {"max_run_minutes": 120, "cooldown_minutes": 1},
    "pre_checks": ["device_available", "no_fire_emergency"],
    "post_checks": ["entity_state_changed"],
    "safety_flags": ["disable_on_fire"],
    "fallback_behavior": "log_and_notify"
  },
  "bottom_air_circulation": {
    "allowed_actions": ["turn_on", "turn_off"],
    "allowed_modes": ["MANUAL", "TEST", "ASK", "AUTO", "AUTOPILOT"],
    "dependencies": [],
    "constraints": {"max_run_minutes": 120, "cooldown_minutes": 1},
    "pre_checks": ["device_available", "no_fire_emergency"],
    "post_checks": ["entity_state_changed"],
    "safety_flags": ["disable_on_fire"],
    "fallback_behavior": "log_and_notify"
  },
  "main_humidifier": {
    "allowed_actions": ["turn_on", "turn_off"],
    "allowed_modes": ["MANUAL", "TEST", "ASK", "AUTO", "AUTOPILOT"],
    "dependencies": ["main_humidifier_power"],
    "constraints": {"max_run_minutes": 60, "cooldown_minutes": 15},
    "pre_checks": ["device_available", "no_fire_emergency"],
    "post_checks": ["entity_state_changed", "leaf_humidity_followup"],
    "safety_flags": ["disable_on_fire"],
    "fallback_behavior": "log_and_notify"
  },
  "veranda_main_power_cutoff": {
    "allowed_actions": ["turn_on", "turn_off"],
    "allowed_modes": ["MANUAL", "TEST", "ASK"],
    "dependencies": [],
    "constraints": {"critical_action": True},
    "pre_checks": ["device_available"],
    "post_checks": ["power_state_followup"],
    "safety_flags": ["critical_power_cutoff"],
    "fallback_behavior": "notify_only"
  }
}

changed = False
for k, v in base.items():
    if k not in data:
        data[k] = v
        changed = True

if changed or not p.exists():
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("device_capabilities.json updated")
else:
    print("device_capabilities.json kept as-is")
PY

echo "==> replace telegram handlers with unified v17 version"
cat > "$PKG/interfaces/telegram_v3/handlers.py" <<'PY'
from __future__ import annotations

from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from greenhouse_v17.core.intent.intent_router import route_text
from greenhouse_v17.services.mode_service import get_mode, set_mode
from greenhouse_v17.services.action_service import execute_action
from greenhouse_v17.services.ask_service import load_ask_state, clear_ask_state

def build_main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 Статус"), KeyboardButton("🤖 Режим"))
    kb.row(KeyboardButton("🌬 Верх ВКЛ"), KeyboardButton("🌬 Верх ВЫКЛ"))
    kb.row(KeyboardButton("🌬 Низ ВКЛ"), KeyboardButton("🌬 Низ ВЫКЛ"))
    kb.row(KeyboardButton("💧 Увлажнитель ВКЛ"), KeyboardButton("💧 Увлажнитель ВЫКЛ"))
    return kb

def build_ask_keyboard(action_key: str):
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"ask:confirm:{action_key}"),
        InlineKeyboardButton("❌ Отмена", callback_data="ask:cancel"),
    )
    return kb

def _format_execution_result(res):
    status = res.get("status")
    mode = res.get("mode")
    msg = res.get("message", "")
    entity_id = res.get("entity_id")

    if status == "ask":
        return f"{msg}\nРежим: {mode}\nТребуется подтверждение."
    if status == "dry_run":
        return f"{msg}\nРежим: {mode}\n🧪 TEST: команда распознана, но не исполнена."
    if status == "blocked":
        return f"⛔ {msg}\nРежим: {mode}"
    if status == "unsupported":
        return f"⚠️ {msg}\nРежим: {mode}"
    if status in ("executed", "degraded"):
        verify = res.get("verify", {})
        verify_line = "✅ verify ok" if verify.get("ok") else f"⚠️ verify failed (actual={verify.get('actual_state')})"
        return (
            f"{msg}\n"
            f"Режим: {mode}\n"
            f"Устройство: {entity_id}\n"
            f"{verify_line}"
        )
    return str(res)

def register_v3_handlers(bot):
    @bot.message_handler(commands=["start"])
    def cmd_start(message):
        bot.send_message(
            message.chat.id,
            "GREENHOUSE v17 / TG v3\n\nЕдиный router + ASK + execution + verify.",
            reply_markup=build_main_menu(),
        )

    @bot.message_handler(commands=["mode"])
    def cmd_mode(message):
        bot.send_message(
            message.chat.id,
            f"Текущий режим: {get_mode()}\n\n"
            "/mode_manual\n/mode_test\n/mode_ask\n/mode_auto\n/mode_autopilot",
            reply_markup=build_main_menu(),
        )

    @bot.message_handler(commands=["mode_manual"])
    def cmd_mode_manual(message):
        set_mode("MANUAL")
        bot.send_message(message.chat.id, "Режим переключен: MANUAL", reply_markup=build_main_menu())

    @bot.message_handler(commands=["mode_test"])
    def cmd_mode_test(message):
        set_mode("TEST")
        bot.send_message(message.chat.id, "Режим переключен: TEST", reply_markup=build_main_menu())

    @bot.message_handler(commands=["mode_ask"])
    def cmd_mode_ask(message):
        set_mode("ASK")
        bot.send_message(message.chat.id, "Режим переключен: ASK", reply_markup=build_main_menu())

    @bot.message_handler(commands=["mode_auto"])
    def cmd_mode_auto(message):
        set_mode("AUTO")
        bot.send_message(message.chat.id, "Режим переключен: AUTO", reply_markup=build_main_menu())

    @bot.message_handler(commands=["mode_autopilot"])
    def cmd_mode_autopilot(message):
        set_mode("AUTOPILOT")
        bot.send_message(message.chat.id, "Режим переключен: AUTOPILOT", reply_markup=build_main_menu())

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ask:"))
    def on_ask_callback(call):
        if call.data == "ask:cancel":
            clear_ask_state()
            bot.answer_callback_query(call.id, "Отменено")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, "ASK отменён.", reply_markup=build_main_menu())
            return

        parts = call.data.split(":")
        if len(parts) != 3 or parts[1] != "confirm":
            bot.answer_callback_query(call.id, "Неверный callback")
            return

        action_key = parts[2]
        stored = load_ask_state()
        if not stored or stored.get("action_key") != action_key:
            bot.answer_callback_query(call.id, "ASK state не найден")
            bot.send_message(call.message.chat.id, "Не найдено ожидающее ASK-состояние.", reply_markup=build_main_menu())
            return

        res = execute_action(action_key, force_execute=True)
        clear_ask_state()
        bot.answer_callback_query(call.id, "Подтверждено")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, _format_execution_result(res), reply_markup=build_main_menu())

    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def handle_any_text(message):
        routed = route_text(message.text or "")
        intent_type = routed.get("intent_type")
        action_key = routed.get("action_key")

        if intent_type == "mode_status":
            return cmd_mode(message)

        if intent_type == "status":
            bot.send_message(
                message.chat.id,
                "Status layer ещё упрощён. Следующий шаг — нормальный status/snapshot поверх нового Core.",
                reply_markup=build_main_menu(),
            )
            return

        if intent_type == "device_action" and action_key:
            res = execute_action(action_key)
            if res.get("status") == "ask":
                bot.send_message(
                    message.chat.id,
                    _format_execution_result(res),
                    reply_markup=build_main_menu(),
                )
                bot.send_message(
                    message.chat.id,
                    f"Подтвердить действие: {action_key}",
                    reply_markup=build_main_menu(),
                )
                bot.send_message(
                    message.chat.id,
                    "Нажми подтверждение ниже:",
                    reply_markup=build_main_menu(),
                )
                bot.send_message(
                    message.chat.id,
                    "ASK pending",
                    reply_markup=build_main_menu(),
                )
                bot.send_message(
                    message.chat.id,
                    f"Действие: {action_key}",
                    reply_markup=build_main_menu(),
                )
                bot.send_message(
                    message.chat.id,
                    "Подтверждение:",
                    reply_markup=build_ask_keyboard(action_key),
                )
                return

            bot.send_message(
                message.chat.id,
                _format_execution_result(res),
                reply_markup=build_main_menu(),
            )
            return

        bot.send_message(
            message.chat.id,
            "Команда пока не подключена в новом пакете.",
            reply_markup=build_main_menu(),
        )
PY

echo "==> relocate runtime files if they exist in root"
python3 - <<'PY'
from pathlib import Path
import shutil

root = Path("/home/mi/greenhouse_v2")
targets = {
    "ask_state.json": root / "data/runtime/ask_state.json",
    "system_state.json": root / "data/runtime/system_state.json",
    "decision_log.json": root / "data/logs/decision_log.json",
    "observations.json": root / "data/memory/observations.json",
}
for src_name, dst in targets.items():
    src = root / src_name
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        print(f"moved {src} -> {dst}")
PY

echo "==> sanity import check"
python3 - <<'PY'
from greenhouse_v17.core.intent.intent_router import route_text
print(route_text("Включи верхний вентилятор"))
from greenhouse_v17.services.action_service import execute_action
print("imports ok")
PY

echo
echo "BIG PATCH APPLIED"
echo "Backups: $BACKUP_DIR"
echo
echo "Next:"
echo "  sudo systemctl restart greenhouse-v17.service"
echo "  sleep 2"
echo "  sudo systemctl status greenhouse-v17.service --no-pager"
echo "  journalctl -u greenhouse-v17.service -n 80 --no-pager"
