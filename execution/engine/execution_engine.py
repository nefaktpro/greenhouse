from __future__ import annotations

from execution.ha.ha_executor import execute_ha_service
from execution.results.execution_result import ExecutionResult
from execution.translators.ha_translator import translate_operation_to_ha
from registry.mapping.action_mapper import resolve_action, ActionMappingError
from registry.queries.registry_queries import find_devices_by_role
from registry.capabilities import get_capability_for_role
from core.validation import validate_action
import mode_manager
from ask_manager import save_ask_state, build_action_ask_payload


def execute_action_key(action_key: str, force_execute: bool = False) -> list[ExecutionResult]:
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

    capability = get_capability_for_role(target_role)
    mode_flags = _build_mode_flags()

    validation = validate_action(
        target_role=target_role,
        operation=operation,
        mode_flags=mode_flags,
        capability=capability,
        safety_context=_build_safety_context(),
        last_executed_at=None,
        pending_actions=[],
        active_blocks=[],
    )

    if force_execute and validation.get("ok", False):
        validation["effective_action"] = "execute"
        validation["confirmed_via_ask"] = True

    if not validation.get("ok", False):
        return [
            ExecutionResult(
                success=False,
                action_key=action_key,
                operation=operation,
                message=f"Validation failed at '{validation.get('failed_at')}'",
                details={"validation": validation, "target_role": target_role},
            )
        ]

    effective_action = validation.get("effective_action", "execute")

    if effective_action == "dry_run":
        return [
            ExecutionResult(
                success=True,
                action_key=action_key,
                operation=operation,
                message="Validation passed: TEST mode dry-run, nothing executed",
                details={
                    "validation": validation,
                    "target_role": target_role,
                    "mode_flags": mode_flags,
                },
            )
        ]

    if effective_action == "ask":
        ask_payload = build_action_ask_payload(
            action_key=action_key,
            target_role=target_role,
            operation=operation,
            mode_flags=mode_flags,
            validation=validation,
        )
        save_ask_state(ask_payload)

        return [
            ExecutionResult(
                success=True,
                action_key=action_key,
                operation=operation,
                message="Validation passed: ASK mode confirmation required and state saved",
                details={
                    "validation": validation,
                    "target_role": target_role,
                    "mode_flags": mode_flags,
                    "ask_required": True,
                    "ask_payload": ask_payload,
                },
            )
        ]

    devices = find_devices_by_role(target_role)
    if not devices:
        return [
            ExecutionResult(
                success=False,
                action_key=action_key,
                operation=operation,
                message=f"No enabled devices found for role '{target_role}'",
                details={"validation": validation},
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
                    details={"device": device, "validation": validation},
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
                    details={
                        "raw": raw,
                        "device": device,
                        "validation": validation,
                        "target_role": target_role,
                    },
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
                    details={
                        "device": device,
                        "validation": validation,
                        "target_role": target_role,
                    },
                )
            )

    return results


def _build_mode_flags() -> dict:
    raw = {}

    try:
        if hasattr(mode_manager, "get_mode_flags"):
            raw = mode_manager.get_mode_flags() or {}
        elif hasattr(mode_manager, "get_current_mode"):
            raw = mode_manager.get_current_mode() or {}
        elif hasattr(mode_manager, "load_mode"):
            raw = mode_manager.load_mode() or {}
        elif hasattr(mode_manager, "get_mode"):
            raw = mode_manager.get_mode()
    except Exception:
        raw = {}

    if isinstance(raw, str):
        mode_name = raw.upper()

        defaults = {
            "MANUAL": {"execute": True, "log": True, "ask": False, "ai_control": False},
            "TEST": {"execute": False, "log": True, "ask": False, "ai_control": False},
            "ASK": {"execute": False, "log": True, "ask": True, "ai_control": False},
            "AUTO": {"execute": True, "log": True, "ask": False, "ai_control": False},
            "AUTOPILOT": {"execute": True, "log": True, "ask": False, "ai_control": True},
        }

        config = defaults.get(mode_name, {}).copy()
        try:
            if hasattr(mode_manager, "get_mode_config"):
                loaded = mode_manager.get_mode_config(mode_name) or {}
                config.update(loaded)
        except Exception:
            pass

        return {
            "name": mode_name,
            "execute": bool(config.get("execute", False)),
            "log": bool(config.get("log", False)),
            "ask": bool(config.get("ask", False)),
            "ai_control": bool(config.get("ai_control", False)),
        }

    if not isinstance(raw, dict):
        raw = {}

    mode_name = (
        raw.get("key")
        or raw.get("name")
        or raw.get("mode")
        or raw.get("current_mode")
        or "UNKNOWN"
    )

    return {
        "name": str(mode_name).upper(),
        "execute": bool(raw.get("execute", False)),
        "log": bool(raw.get("log", False)),
        "ask": bool(raw.get("ask", False)),
        "ai_control": bool(raw.get("ai_control", False)),
    }


def _build_safety_context() -> dict:
    return {
        "fire_active": False,
        "leak_active": False,
        "power_unknown": False,
        "critical_sensor_missing": False,
    }
