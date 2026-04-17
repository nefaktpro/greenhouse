#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import requests
from telebot import types
from reports import get_ha

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "devices_controls.csv")
ENV_PATH = os.path.join(BASE_DIR, ".env")

ALLOWED_TYPES = {
    "switch", "cover", "climate", "select", "number",
    "light", "pump", "fan", "socket"
}

GROUP_ORDER = [
    "electricity",
    "light",
    "airflow",
    "watering",
    "curtain",
    "climate",
    "other",
]

GROUP_LABELS = {
    "electricity": "⚡ Питание",
    "light": "💡 Свет",
    "airflow": "🌬 Вентиляция",
    "watering": "💧 Полив",
    "curtain": "🪟 Штора",
    "climate": "♨️ Климат",
    "other": "🔧 Служебное",
}


def _load_env_file(path: str):
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def _ha_base_and_token():
    env = _load_env_file(ENV_PATH)
    base_url = env.get("HA_BASE_URL") or env.get("HA_URL") or os.getenv("HA_BASE_URL") or os.getenv("HA_URL")
    token = env.get("HA_TOKEN") or os.getenv("HA_TOKEN")
    return base_url, token


def _call_ha_service(domain: str, service: str, entity_id: str):
    base_url, token = _ha_base_and_token()
    if not base_url or not token:
        return False, "HA URL/token не найдены"

    url = f"{base_url}/api/services/{domain}/{service}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(url, headers=headers, json={"entity_id": entity_id}, timeout=15)
        if 200 <= r.status_code < 300:
            return True, "ok"
        return False, f"{r.status_code} {r.text[:300]}"
    except Exception as e:
        return False, str(e)


def _load_controls():
    if not os.path.exists(CSV_PATH):
        return []

    with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    result = []
    seen = set()

    for r in rows:
        entity_id = (r.get("EntityID") or "").strip()
        typ = (r.get("Type") or "").strip().lower()
        if not entity_id or typ not in ALLOWED_TYPES:
            continue

        # Убираем режим двигателя из пульта
        if entity_id == "select.wifi_curtain_driver_converter_motor_mode":
            continue

        key = (r.get("DeviceID", ""), r.get("SubID", ""), entity_id)
        if key in seen:
            continue
        seen.add(key)

        result.append({
            "device_id": (r.get("DeviceID") or "").strip(),
            "sub_id": (r.get("SubID") or "").strip(),
            "name": (r.get("Name") or "").strip() or entity_id,
            "type": typ,
            "entity_id": entity_id,
            "location": (r.get("Location") or "").strip(),
            "description": (r.get("Description") or "").strip(),
            "group": ((r.get("Group") or "").strip().lower() or "other"),
        })

    return result


def _item_code(item):
    device_id = item.get("device_id", "")
    sub_id = item.get("sub_id", "")
    return f"{device_id}.{sub_id}" if device_id and sub_id and sub_id != "0" else device_id


def _read_state(entity_id: str):
    ha = get_ha()
    if ha is None:
        return "нет данных"
    try:
        data = ha.get_state(entity_id)
        if not data:
            return "нет данных"
        return str(data.get("state", "нет данных"))
    except Exception:
        return "нет данных"


def _state_label(item, state: str):
    typ = item.get("type", "")
    s = (state or "").lower()

    if typ == "cover":
        if s == "open":
            return "🟢 ОТКРЫТА"
        if s == "closed":
            return "⚪ ЗАКРЫТА"
        if s == "opening":
            return "🟢 ОТКРЫВАЕТСЯ"
        if s == "closing":
            return "⚪ ЗАКРЫВАЕТСЯ"
        return f"⚪ {state}"

    if typ == "climate":
        if s == "off":
            return "⚪ OFF"
        return f"🟢 {state}"

    if typ == "number":
        return f"🔢 {state}"

    if typ == "select":
        return f"📋 {state}"

    if s == "on":
        return "🟢 ВКЛ"
    if s == "off":
        return "⚪ ВЫКЛ"

    return f"⚪ {state}"


def _normalize_group(group: str) -> str:
    g = (group or "").strip().lower()
    return g if g in GROUP_LABELS else "other"


def get_groups():
    items = _load_controls()
    groups = []
    seen = set()

    for g in GROUP_ORDER:
        for item in items:
            ig = _normalize_group(item.get("group", "other"))
            if ig == g and g not in seen:
                groups.append(g)
                seen.add(g)

    for item in items:
        ig = _normalize_group(item.get("group", "other"))
        if ig not in seen:
            groups.append(ig)
            seen.add(ig)

    return groups


def build_devices_groups_text() -> str:
    groups = get_groups()
    if not groups:
        return "🔌 Устройства\n\nНет данных для управления."
    lines = ["🔌 Устройства", "", "Выбери группу:"]
    for g in groups:
        lines.append(f"• {GROUP_LABELS.get(g, g)}")
    return "\n".join(lines)


def build_devices_groups_keyboard():
    kb = types.InlineKeyboardMarkup()
    for g in get_groups():
        kb.add(types.InlineKeyboardButton(GROUP_LABELS.get(g, g), callback_data=f"devgrp|{g}"))
    return kb


def _group_items(group: str):
    g = _normalize_group(group)
    return [x for x in _load_controls() if _normalize_group(x.get("group", "other")) == g]


def build_group_report(group: str) -> str:
    items = _group_items(group)
    title = GROUP_LABELS.get(_normalize_group(group), group)

    if not items:
        return f"{title}\n\nНет устройств."

    lines = [title, ""]
    for item in items:
        code = _item_code(item)
        state = _read_state(item["entity_id"])
        label = _state_label(item, state)
        lines.append(f"• {code} — {item['name']}: {label}")

    return "\n".join(lines)


def build_group_keyboard(group: str):
    items = _group_items(group)
    kb = types.InlineKeyboardMarkup()

    for item in items:
        code = _item_code(item)
        state = (_read_state(item["entity_id"]) or "").lower()
        typ = item.get("type", "")

        kb.add(types.InlineKeyboardButton(f"{code} — {item['name']}", callback_data="noop_devices"))

        if typ == "cover":
            open_label = "🟢 ОТКРЫТЬ" if state in ("open", "opening") else "⚪ ОТКРЫТЬ"
            close_label = "🟢 ЗАКРЫТЬ" if state in ("closed", "closing") else "⚪ ЗАКРЫТЬ"
            kb.row(
                types.InlineKeyboardButton(open_label, callback_data=f"devctl|on|{code}|{_normalize_group(group)}"),
                types.InlineKeyboardButton(close_label, callback_data=f"devctl|off|{code}|{_normalize_group(group)}"),
            )
        elif typ in ("climate", "switch", "light", "pump", "fan", "socket"):
            on_label = "🟢 ВКЛ" if state == "on" else "⚪ ВКЛ"
            off_label = "🟢 ВЫКЛ" if state == "off" else "⚪ ВЫКЛ"
            kb.row(
                types.InlineKeyboardButton(on_label, callback_data=f"devctl|on|{code}|{_normalize_group(group)}"),
                types.InlineKeyboardButton(off_label, callback_data=f"devctl|off|{code}|{_normalize_group(group)}"),
            )
        else:
            kb.row(types.InlineKeyboardButton("🔄 Обновить", callback_data=f"devrefresh|{_normalize_group(group)}"))

    kb.row(
        types.InlineKeyboardButton("⬅️ Назад", callback_data="devmenu"),
        types.InlineKeyboardButton("🔄 Обновить", callback_data=f"devrefresh|{_normalize_group(group)}"),
    )
    return kb


def execute_device_action(code: str, action: str):
    items = _load_controls()
    target = None

    for item in items:
        if _item_code(item) == code:
            target = item
            break

    if target is None:
        return False, f"Устройство {code} не найдено"

    entity_id = target["entity_id"]
    typ = target["type"]
    ha = get_ha()
    if ha is None:
        return False, "HA недоступен"

    try:
        if typ == "cover":
            if action == "on":
                ok, msg = _call_ha_service("cover", "close_cover", entity_id)
            elif action == "off":
                ok, msg = _call_ha_service("cover", "open_cover", entity_id)
            else:
                return False, f"Неизвестное действие: {action}"
        else:
            if action == "on":
                ok = ha.turn_on(entity_id)
                msg = "ok" if ok else "turn_on failed"
            elif action == "off":
                ok = ha.turn_off(entity_id)
                msg = "ok" if ok else "turn_off failed"
            else:
                return False, f"Неизвестное действие: {action}"

        if ok:
            return True, f"{target['name']}: команда {action} отправлена"
        return False, f"{target['name']}: команда {action} не выполнена ({msg})"

    except Exception as e:
        return False, f"{target['name']}: ошибка {e}"
