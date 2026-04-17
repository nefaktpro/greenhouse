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
