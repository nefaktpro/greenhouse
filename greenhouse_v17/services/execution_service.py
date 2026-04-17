from greenhouse_v17.registry.loader import load_registry
from greenhouse_v17.services.ha_client import call_ha_service

registry = load_registry()


def execute_action(action_key: str):
    action_map = registry.get("actions", {})

    if action_key not in action_map:
        return f"❌ Неизвестное действие: {action_key}"

    action = action_map[action_key]

    role = action["role"]
    operation = action["operation"]

    devices = registry.get("devices", [])

    target = None
    for d in devices:
        if d.get("logical_role") == role and d.get("is_enabled"):
            target = d
            break

    if not target:
        return f"❌ Не найдено устройство для роли: {role}"

    entity_id = target["entity_id"]

    result = call_ha_service(entity_id, operation)

    return f"✅ {action_key} → {entity_id} → {result}"
