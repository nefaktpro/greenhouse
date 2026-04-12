from __future__ import annotations

from typing import Any

from registry.loader.registry_loader import get_registry_loader


class ActionMappingError(Exception):
    pass


def resolve_action(action_key: str) -> dict[str, Any]:
    snapshot = get_registry_loader().load()
    action_map = snapshot.action_map

    if action_key not in action_map:
        raise ActionMappingError(f"Action '{action_key}' not found in action_map.json")

    mapping = action_map[action_key]
    if not isinstance(mapping, dict):
        raise ActionMappingError(f"Action '{action_key}' has invalid mapping format")

    target_role = mapping.get("target_role")
    operation = mapping.get("operation")

    if not target_role or not operation:
        raise ActionMappingError(
            f"Action '{action_key}' must define 'target_role' and 'operation'"
        )

    return mapping
