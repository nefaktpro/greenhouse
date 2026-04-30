from __future__ import annotations

import re
from typing import Any, Dict, Optional


def _parse_duration_sec(t: str, default: int = 10) -> int:
    m = re.search(r"на\s+(\d+)\s*(сек|секунд|секунды|s)", t)
    if m:
        return int(m.group(1))

    m = re.search(r"на\s+(\d+)\s*(мин|минут|минуты|m)", t)
    if m:
        return int(m.group(1)) * 60

    return default


def _parse_conditions(t: str) -> Optional[Dict[str, Any]]:
    if "влаж" in t and ("ниже" in t or "меньше" in t or "<" in t):
        value = "55"
        m = re.search(r"(?:ниже|меньше|<)\s*(\d+)", t)
        if m:
            value = m.group(1)
        return {
            "entity_id": "sensor.nobito_humidity",
            "operator": "<",
            "value": value,
        }

    if "температур" in t and ("выше" in t or "больше" in t or ">" in t):
        value = "28"
        m = re.search(r"(?:выше|больше|>)\s*(\d+)", t)
        if m:
            value = m.group(1)
        return {
            "entity_id": "sensor.kachestvo_vozdukha_temperature",
            "operator": ">",
            "value": value,
        }

    return None


def _parse_trigger(t: str) -> Optional[Dict[str, Any]]:
    if "каждый час" in t or "каждые час" in t:
        return {"type": "interval", "every_sec": 3600}

    m = re.search(r"каждые?\s+(\d+)\s*(мин|минут|минуты)", t)
    if m:
        return {"type": "interval", "every_sec": int(m.group(1)) * 60}

    m = re.search(r"каждые?\s+(\d+)\s*(сек|секунд|секунды)", t)
    if m:
        return {"type": "interval", "every_sec": int(m.group(1))}

    m = re.search(r"через\s+(\d+)\s*(сек|секунд|секунды)", t)
    if m:
        return {"type": "delay", "delay_sec": int(m.group(1))}

    m = re.search(r"через\s+(\d+)\s*(мин|минут|минуты)", t)
    if m:
        return {"type": "delay", "delay_sec": int(m.group(1)) * 60}

    # weekly: пн/вт/ср ... в 08:00
    days_map = {
        "пн": "mon", "понедельник": "mon",
        "вт": "tue", "вторник": "tue",
        "ср": "wed", "среда": "wed",
        "чт": "thu", "четверг": "thu",
        "пт": "fri", "пятница": "fri",
        "сб": "sat", "суббота": "sat",
        "вс": "sun", "воскресенье": "sun",
    }
    days = []
    for ru, en in days_map.items():
        if re.search(rf"\b{ru}\b", t):
            days.append(en)

    tm = re.search(r"\bв\s*(\d{1,2})(?::(\d{2}))?\b", t)
    if days and tm:
        hh = int(tm.group(1))
        mm = int(tm.group(2) or 0)
        return {"type": "weekly", "days": sorted(set(days)), "time": f"{hh:02d}:{mm:02d}"}

    return None


def _resolve_action_plan(t: str, duration_sec: int) -> Optional[Dict[str, Any]]:
    # MVP: пока только верхний вент через action_map-known keys.
    # Следующим шагом заменим на nl_action_resolver/action_map lookup.
    if "вент" in t:
        return {
            "type": "duration",
            "action_key": "fan_top_on",
            "off_action_key": "fan_top_off",
            "duration_sec": duration_sec,
        }

    return None


def _describe_trigger(trigger: Dict[str, Any]) -> str:
    if trigger["type"] == "interval":
        sec = int(trigger.get("every_sec") or 0)
        if sec == 3600:
            return "каждый час"
        if sec % 60 == 0:
            return f"каждые {sec // 60} мин"
        return f"каждые {sec} сек"

    if trigger["type"] == "delay":
        sec = int(trigger.get("delay_sec") or 0)
        if sec % 60 == 0 and sec >= 60:
            return f"через {sec // 60} мин"
        return f"через {sec} сек"

    if trigger["type"] == "weekly":
        return f"{','.join(trigger.get('days') or [])} в {trigger.get('time')}"

    return trigger.get("type", "trigger")


def _describe_condition(condition: Optional[Dict[str, Any]]) -> str:
    if not condition:
        return ""
    ent = condition.get("entity_id", "")
    if "humidity" in ent:
        return f" если влажность {condition.get('operator')} {condition.get('value')}"
    if "temperature" in ent:
        return f" если температура {condition.get('operator')} {condition.get('value')}"
    return " если условие выполнено"


def detect_recipe_v2(text: str) -> Optional[Dict[str, Any]]:
    t = text.strip().lower()
    if not t:
        return None

    trigger = _parse_trigger(t)
    if not trigger:
        return None

    duration_sec = _parse_duration_sec(t, default=10)
    action_plan = _resolve_action_plan(t, duration_sec)
    if not action_plan:
        return None

    conditions = _parse_conditions(t)

    title = f"{_describe_trigger(trigger)}: вент на {duration_sec} сек"
    title += _describe_condition(conditions)

    return {
        "kind": "recipe_v2_candidate",
        "title": title,
        "payload": {
            "title": title,
            "trigger": trigger,
            "conditions": conditions,
            "action_plan": action_plan,
            "source_text": text,
        },
    }
