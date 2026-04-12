from __future__ import annotations

from typing import Any

from registry.loader.registry_loader import get_registry_loader


def get_all_devices() -> list[dict[str, Any]]:
    snapshot = get_registry_loader().load()
    return snapshot.devices


def get_enabled_devices() -> list[dict[str, Any]]:
    devices = get_all_devices()
    result: list[dict[str, Any]] = []

    for device in devices:
        enabled = str(device.get("is_enabled", "")).strip().lower()
        if enabled in ("true", "1", "yes", "y"):
            result.append(device)

    return result


def find_devices_by_role(logical_role: str) -> list[dict[str, Any]]:
    devices = get_enabled_devices()
    return [
        d for d in devices
        if str(d.get("logical_role", "")).strip() == logical_role
    ]


def find_device_by_entity_id(entity_id: str) -> dict[str, Any] | None:
    devices = get_all_devices()
    for device in devices:
        if str(device.get("entity_id", "")).strip() == entity_id:
            return device
    return None
