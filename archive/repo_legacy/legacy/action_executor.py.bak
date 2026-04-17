#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests

HA_URL = os.getenv("HA_URL") or os.getenv("HA_BASE_URL", "http://127.0.0.1:8123")
HA_TOKEN = os.getenv("HA_TOKEN", "").strip()

ACTION_ENTITY_MAP = {
    "fan_top_on":  "switch.setevoi_filtr_novyi_socket_1",
    "fan_top_off": "switch.setevoi_filtr_novyi_socket_1",
    "fan_low_on":  "switch.setevoi_filtr_novyi_usb_1",
    "fan_low_off": "switch.setevoi_filtr_novyi_usb_1",
}

ACTION_SERVICE_MAP = {
    "fan_top_on":  "switch.turn_on",
    "fan_top_off": "switch.turn_off",
    "fan_low_on":  "switch.turn_on",
    "fan_low_off": "switch.turn_off",
}


def _load_allowed_actions():
    raw = os.getenv("AUTO_ALLOWED_ACTIONS", "fan_low_on,fan_low_off,fan_top_on,fan_top_off")
    return {x.strip() for x in raw.split(",") if x.strip()}


def _actions_enabled():
    return os.getenv("AUTO_ACTIONS_ENABLED", "0").strip() == "1"


def _ha_headers():
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }


def _call_ha_service(service_name: str, entity_id: str):
    if "." not in service_name:
        raise ValueError(f"Invalid service name: {service_name}")

    domain, service = service_name.split(".", 1)
    url = f"{HA_URL.rstrip('/')}/api/services/{domain}/{service}"

    resp = requests.post(
        url,
        headers=_ha_headers(),
        json={"entity_id": entity_id},
        timeout=10,
    )
    resp.raise_for_status()
    return True, f"{service_name} -> {entity_id}"


def execute_decisions(decisions, dry_run=True):
    """
    dry_run=True:
        Ничего реально не выполняем, только помечаем как подтверждённое dry-run действие.

    dry_run=False:
        Реально можно выполнять ТОЛЬКО действия из whitelist.
        И только если AUTO_ACTIONS_ENABLED=1.
    """
    result = []
    allowed_actions = _load_allowed_actions()
    real_enabled = _actions_enabled()

    for d in decisions or []:
        item = dict(d)
        action = item.get("action")

        item.setdefault("executed", False)
        item.setdefault("dry_run", False)
        item.setdefault("blocked", False)
        item.setdefault("block_reason", "")
        item.setdefault("error", "")

        if dry_run:
            item["executed"] = True
            item["dry_run"] = True
            item["blocked"] = False
            item["block_reason"] = ""
            result.append(item)
            continue

        if not real_enabled:
            item["executed"] = False
            item["dry_run"] = False
            item["blocked"] = True
            item["block_reason"] = "AUTO_ACTIONS_ENABLED=0"
            result.append(item)
            continue

        if action not in allowed_actions:
            item["executed"] = False
            item["dry_run"] = False
            item["blocked"] = True
            item["block_reason"] = f"action_not_allowed:{action}"
            result.append(item)
            continue

        entity_id = ACTION_ENTITY_MAP.get(action)
        service_name = ACTION_SERVICE_MAP.get(action)

        if not entity_id or not service_name:
            item["executed"] = False
            item["dry_run"] = False
            item["blocked"] = True
            item["block_reason"] = f"mapping_missing:{action}"
            result.append(item)
            continue

        if not HA_TOKEN:
            item["executed"] = False
            item["dry_run"] = False
            item["blocked"] = True
            item["block_reason"] = "HA_TOKEN_missing"
            result.append(item)
            continue

        try:
            ok, msg = _call_ha_service(service_name, entity_id)
            item["executed"] = bool(ok)
            item["dry_run"] = False
            item["blocked"] = False
            item["block_reason"] = ""
            item["executor_message"] = msg
        except Exception as e:
            item["executed"] = False
            item["dry_run"] = False
            item["blocked"] = False
            item["error"] = str(e)

        result.append(item)

    return result
