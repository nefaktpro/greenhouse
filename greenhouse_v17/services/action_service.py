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
