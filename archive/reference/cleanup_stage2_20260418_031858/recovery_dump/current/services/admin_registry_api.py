from __future__ import annotations

from typing import Dict, Any

from greenhouse_v17.services.registry_service import (
    list_devices,
    disable_device,
    enable_device,
    load_action_map,
    save_action_map,
    load_capabilities,
    save_capabilities,
)
from greenhouse_v17.services.scenario_service import list_scenarios, upsert_scenario

def get_registry_snapshot() -> Dict[str, Any]:
    return {
        "devices": list_devices(),
        "action_map": load_action_map(),
        "capabilities": load_capabilities(),
        "scenarios": list_scenarios(),
    }

def set_device_enabled(device_id: str, enabled: bool) -> bool:
    return enable_device(device_id) if enabled else disable_device(device_id)

def replace_action_map(payload: Dict[str, Any]) -> None:
    save_action_map(payload)

def replace_capabilities(payload: Dict[str, Any]) -> None:
    save_capabilities(payload)

def save_scenario(payload: Dict[str, Any]) -> Dict[str, Any]:
    return upsert_scenario(payload)
