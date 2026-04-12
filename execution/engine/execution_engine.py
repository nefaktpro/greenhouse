from __future__ import annotations

from execution.ha.ha_executor import execute_ha_service
from execution.results.execution_result import ExecutionResult
from execution.translators.ha_translator import translate_operation_to_ha
from registry.mapping.action_mapper import resolve_action, ActionMappingError
from registry.queries.registry_queries import find_devices_by_role


def execute_action_key(action_key: str) -> list[ExecutionResult]:
    try:
        mapping = resolve_action(action_key)
    except ActionMappingError as e:
        return [
            ExecutionResult(
                success=False,
                action_key=action_key,
                message=str(e),
            )
        ]

    target_role = mapping["target_role"]
    operation = mapping["operation"]

    devices = find_devices_by_role(target_role)
    if not devices:
        return [
            ExecutionResult(
                success=False,
                action_key=action_key,
                operation=operation,
                message=f"No enabled devices found for role '{target_role}'",
            )
        ]

    results: list[ExecutionResult] = []

    for device in devices:
        entity_id = str(device.get("entity_id", "")).strip()
        if not entity_id:
            results.append(
                ExecutionResult(
                    success=False,
                    action_key=action_key,
                    operation=operation,
                    message=f"Device '{device.get('name', device.get('device_id', '?'))}' has no entity_id",
                    details={"device": device},
                )
            )
            continue

        try:
            domain, service, service_data = translate_operation_to_ha(operation, entity_id)
            raw = execute_ha_service(domain, service, service_data)

            results.append(
                ExecutionResult(
                    success=bool(raw.get("ok", False)),
                    action_key=action_key,
                    operation=operation,
                    entity_id=entity_id,
                    message="Executed",
                    details={"raw": raw, "device": device},
                )
            )
        except Exception as e:
            results.append(
                ExecutionResult(
                    success=False,
                    action_key=action_key,
                    operation=operation,
                    entity_id=entity_id,
                    message=str(e),
                    details={"device": device},
                )
            )

    return results
