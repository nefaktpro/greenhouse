#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v2"
PKG="$ROOT/greenhouse_v17"

echo "==> patch intent_router.py"
cat > "$PKG/core/intent/intent_router.py" <<'PY'
from __future__ import annotations

from typing import Dict, Optional

BUTTON_TO_ACTION = {
    "верх вкл": "fan_top_on",
    "верх выкл": "fan_top_off",
    "низ вкл": "fan_bottom_on",
    "низ выкл": "fan_bottom_off",
    "увлажнитель вкл": "humidifier_on",
    "увлажнитель выкл": "humidifier_off",
    "питание веранды выкл": "veranda_power_off",
    "питание веранды вкл": "veranda_power_on",
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
        .replace("/", "")
        .strip()
    )

def route_text(text: str) -> Dict[str, Optional[str]]:
    raw = (text or "").strip()
    normalized = normalize_text(raw)

    if normalized == "режим":
        return {"intent_type": "mode_status", "action_key": None, "confidence": "high"}

    if normalized == "статус":
        return {"intent_type": "status", "action_key": None, "confidence": "high"}

    if normalized in BUTTON_TO_ACTION:
        return {
            "intent_type": "device_action",
            "action_key": BUTTON_TO_ACTION[normalized],
            "confidence": "high",
        }

    for tokens, action_key in TEXT_PATTERNS:
        if all(tok in normalized for tok in tokens):
            return {
                "intent_type": "device_action",
                "action_key": action_key,
                "confidence": "medium",
            }

    slash_map = {
        "fan_top_on": "fan_top_on",
        "fan_top_off": "fan_top_off",
        "fan_low_on": "fan_bottom_on",
        "fan_low_off": "fan_bottom_off",
        "humidifier_on": "humidifier_on",
        "humidifier_off": "humidifier_off",
        "mode": None,
        "status": None,
    }
    if raw.startswith("/"):
        slash = normalized
        if slash in slash_map:
            if slash == "mode":
                return {"intent_type": "mode_status", "action_key": None, "confidence": "high"}
            if slash == "status":
                return {"intent_type": "status", "action_key": None, "confidence": "high"}
            return {
                "intent_type": "device_action",
                "action_key": slash_map[slash],
                "confidence": "high",
            }

    return {"intent_type": "unknown", "action_key": None, "confidence": "low"}
PY

echo "==> patch feedback_engine.py with retry verify"
cat > "$PKG/core/feedback/feedback_engine.py" <<'PY'
from __future__ import annotations

import time
import requests
from typing import Optional, Dict, Any

def _load_ha_config():
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

def verify_entity_state(
    entity_id: str,
    expected_state: Optional[str],
    retries: int = 4,
    delay_seconds: float = 1.5,
) -> Dict[str, Any]:
    last_payload = None
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            payload = get_entity_state(entity_id)
            last_payload = payload
            actual = str(payload.get("state"))
            ok = expected_state is None or actual == expected_state
            if ok:
                return {
                    "ok": True,
                    "entity_id": entity_id,
                    "expected_state": expected_state,
                    "actual_state": actual,
                    "last_updated": payload.get("last_updated"),
                    "attempt": attempt,
                }
        except Exception as e:
            last_error = str(e)

        if attempt < retries:
            time.sleep(delay_seconds)

    if last_payload is not None:
        return {
            "ok": False,
            "entity_id": entity_id,
            "expected_state": expected_state,
            "actual_state": str(last_payload.get("state")),
            "last_updated": last_payload.get("last_updated"),
            "attempt": retries,
        }

    return {
        "ok": False,
        "entity_id": entity_id,
        "expected_state": expected_state,
        "actual_state": None,
        "error": last_error,
        "attempt": retries,
    }
PY

echo "==> quick import test"
python3 - <<'PY'
from greenhouse_v17.core.intent.intent_router import route_text
print(route_text("🌬 Верх ВКЛ"))
print(route_text("Включи верхний вентилятор"))
from greenhouse_v17.core.feedback.feedback_engine import verify_entity_state
print("imports ok")
PY

echo "==> restart service"
sudo systemctl restart greenhouse-v17.service
sleep 2
sudo systemctl status greenhouse-v17.service --no-pager
