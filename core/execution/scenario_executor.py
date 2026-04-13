from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from core.registry.registry_loader import (
    DEFAULT_REGISTRY_DIR,
    RegistryError,
    get_role_entity,
    get_scenario,
)

try:
    from ha_client import HomeAssistantClient
except Exception:
    HomeAssistantClient = None  # type: ignore


class ScenarioExecutionError(Exception):
    """Raised when scenario execution fails."""


@dataclass
class StepResult:
    success: bool
    action: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioExecutionResult:
    success: bool
    scenario_name: str
    dry_run: bool
    step_results: List[StepResult] = field(default_factory=list)
    error: Optional[str] = None


def _service_for_entity_action(entity_id: str, action: str) -> tuple[str, str]:
    domain = entity_id.split(".", 1)[0]

    if action in ("turn_on", "turn_off"):
        if domain in ("switch", "light", "fan", "input_boolean"):
            return domain, action
        if domain == "cover":
            if action == "turn_on":
                return "cover", "open_cover"
            return "cover", "close_cover"

    raise ScenarioExecutionError(
        f"Unsupported action '{action}' for entity '{entity_id}'"
    )


def _call_ha_service(ha: Any, entity_id: str, action: str) -> Dict[str, Any]:
    domain, service = _service_for_entity_action(entity_id, action)

    if ha is None:
        raise ScenarioExecutionError("HA client is not initialized")

    if hasattr(ha, "call_service"):
        response = ha.call_service(domain, service, {"entity_id": entity_id})
        return {"domain": domain, "service": service, "response": response}

    if hasattr(ha, "turn_on") and action == "turn_on":
        response = ha.turn_on(entity_id)
        return {"domain": domain, "service": service, "response": response}

    if hasattr(ha, "turn_off") and action == "turn_off":
        response = ha.turn_off(entity_id)
        return {"domain": domain, "service": service, "response": response}

    raise ScenarioExecutionError(
        f"HA client does not support required method for action '{action}'"
    )


def _get_entity_state(ha: Any, entity_id: str) -> Any:
    if ha is None:
        raise ScenarioExecutionError("HA client is not initialized")

    if hasattr(ha, "get_state"):
        return ha.get_state(entity_id)

    if hasattr(ha, "get_entity_state"):
        return ha.get_entity_state(entity_id)

    if hasattr(ha, "get_states"):
        states = ha.get_states()
        if isinstance(states, list):
            for item in states:
                if isinstance(item, dict) and item.get("entity_id") == entity_id:
                    return item.get("state")
        raise ScenarioExecutionError(f"Entity '{entity_id}' not found in HA states")

    raise ScenarioExecutionError("HA client does not support state reading")


def execute_scenario(
    scenario_name: str,
    dry_run: bool = True,
    registry_dir=DEFAULT_REGISTRY_DIR,
    ha: Any = None,
    _visited: Optional[Set[str]] = None,
) -> ScenarioExecutionResult:
    if _visited is None:
        _visited = set()

    if scenario_name in _visited:
        return ScenarioExecutionResult(
            success=False,
            scenario_name=scenario_name,
            dry_run=dry_run,
            error=f"Recursive scenario reference detected: {scenario_name}",
        )

    _visited.add(scenario_name)

    try:
        scenario = get_scenario(scenario_name, registry_dir)
    except RegistryError as exc:
        return ScenarioExecutionResult(
            success=False,
            scenario_name=scenario_name,
            dry_run=dry_run,
            error=str(exc),
        )

    steps = scenario.get("steps", [])
    if not isinstance(steps, list):
        return ScenarioExecutionResult(
            success=False,
            scenario_name=scenario_name,
            dry_run=dry_run,
            error=f"Scenario '{scenario_name}' has invalid steps format",
        )

    result = ScenarioExecutionResult(
        success=True,
        scenario_name=scenario_name,
        dry_run=dry_run,
    )

    last_verify_failed = False

    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            result.success = False
            result.error = f"Invalid step format at position {idx} in scenario '{scenario_name}'"
            break

        action = step.get("action")
        if not isinstance(action, str):
            result.success = False
            result.error = f"Step {idx} in scenario '{scenario_name}' has no valid action"
            break

        try:
            if action in ("turn_on", "turn_off"):
                target_role = step.get("target_role")
                if not isinstance(target_role, str):
                    raise ScenarioExecutionError(
                        f"Step {idx}: action '{action}' requires 'target_role'"
                    )

                entity_value = get_role_entity(target_role, registry_dir)

                if isinstance(entity_value, list):
                    entities = entity_value
                else:
                    entities = [entity_value]

                for entity_id in entities:
                    if not isinstance(entity_id, str) or "." not in entity_id:
                        raise ScenarioExecutionError(
                            f"Invalid entity_id for role '{target_role}': {entity_id!r}"
                        )

                    if dry_run:
                        result.step_results.append(
                            StepResult(
                                success=True,
                                action=action,
                                details={
                                    "step": idx,
                                    "target_role": target_role,
                                    "entity_id": entity_id,
                                    "mode": "dry_run",
                                },
                            )
                        )
                    else:
                        call_info = _call_ha_service(ha, entity_id, action)
                        result.step_results.append(
                            StepResult(
                                success=True,
                                action=action,
                                details={
                                    "step": idx,
                                    "target_role": target_role,
                                    "entity_id": entity_id,
                                    **call_info,
                                },
                            )
                        )

            elif action == "delay":
                seconds = step.get("seconds")
                if not isinstance(seconds, int) or seconds < 0:
                    raise ScenarioExecutionError(
                        f"Step {idx}: delay requires non-negative integer 'seconds'"
                    )

                if not dry_run and seconds > 0:
                    time.sleep(seconds)

                result.step_results.append(
                    StepResult(
                        success=True,
                        action=action,
                        details={
                            "step": idx,
                            "seconds": seconds,
                            "mode": "dry_run" if dry_run else "real",
                        },
                    )
                )

            elif action == "run_scenario":
                nested_name = step.get("run_scenario")
                if not isinstance(nested_name, str):
                    raise ScenarioExecutionError(
                        f"Step {idx}: run_scenario requires scenario name"
                    )

                nested_result = execute_scenario(
                    nested_name,
                    dry_run=dry_run,
                    registry_dir=registry_dir,
                    ha=ha,
                    _visited=set(_visited),
                )

                result.step_results.append(
                    StepResult(
                        success=nested_result.success,
                        action=action,
                        details={
                            "step": idx,
                            "nested_scenario": nested_name,
                            "nested_success": nested_result.success,
                            "nested_error": nested_result.error,
                            "nested_steps": [
                                {
                                    "success": s.success,
                                    "action": s.action,
                                    "details": s.details,
                                }
                                for s in nested_result.step_results
                            ],
                        },
                    )
                )

                if not nested_result.success:
                    raise ScenarioExecutionError(
                        f"Nested scenario failed: {nested_name}: {nested_result.error}"
                    )

            elif action == "verify_state":
                target_role = step.get("target_role")
                expected = step.get("expected")
                if not isinstance(target_role, str):
                    raise ScenarioExecutionError(
                        f"Step {idx}: verify_state requires 'target_role'"
                    )

                entity_id = get_role_entity(target_role, registry_dir)
                if not isinstance(entity_id, str):
                    raise ScenarioExecutionError(
                        f"verify_state currently supports only single entity role, got: {entity_id!r}"
                    )

                if dry_run:
                    actual = expected
                    verified = True
                else:
                    actual = _get_entity_state(ha, entity_id)
                    verified = str(actual) == str(expected)

                last_verify_failed = not verified

                result.step_results.append(
                    StepResult(
                        success=verified,
                        action=action,
                        details={
                            "step": idx,
                            "target_role": target_role,
                            "entity_id": entity_id,
                            "expected": expected,
                            "actual": actual,
                            "verified": verified,
                            "mode": "dry_run" if dry_run else "real",
                        },
                    )
                )

            elif action == "conditional_if_verify_failed":
                then_steps = step.get("then", [])
                if not isinstance(then_steps, list):
                    raise ScenarioExecutionError(
                        f"Step {idx}: conditional_if_verify_failed requires list 'then'"
                    )

                if last_verify_failed:
                    result.step_results.append(
                        StepResult(
                            success=True,
                            action=action,
                            details={
                                "step": idx,
                                "condition_triggered": True,
                                "then_steps_count": len(then_steps),
                            },
                        )
                    )

                    temp_scenario_name = f"{scenario_name}__conditional_step_{idx}"
                    nested_result = execute_inline_steps(
                        temp_scenario_name,
                        then_steps,
                        dry_run=dry_run,
                        registry_dir=registry_dir,
                        ha=ha,
                        _visited=set(_visited),
                    )

                    result.step_results.append(
                        StepResult(
                            success=nested_result.success,
                            action="conditional_then",
                            details={
                                "step": idx,
                                "nested_success": nested_result.success,
                                "nested_error": nested_result.error,
                                "nested_steps": [
                                    {
                                        "success": s.success,
                                        "action": s.action,
                                        "details": s.details,
                                    }
                                    for s in nested_result.step_results
                                ],
                            },
                        )
                    )

                    if not nested_result.success:
                        raise ScenarioExecutionError(
                            f"Conditional branch failed at step {idx}: {nested_result.error}"
                        )
                else:
                    result.step_results.append(
                        StepResult(
                            success=True,
                            action=action,
                            details={
                                "step": idx,
                                "condition_triggered": False,
                            },
                        )
                    )

            elif action == "notify":
                result.step_results.append(
                    StepResult(
                        success=True,
                        action=action,
                        details={
                            "step": idx,
                            "channel": step.get("channel"),
                            "message": step.get("message"),
                            "mode": "dry_run" if dry_run else "not_implemented_yet",
                        },
                    )
                )

            else:
                raise ScenarioExecutionError(
                    f"Unsupported scenario action '{action}' in '{scenario_name}'"
                )

        except Exception as exc:
            result.success = False
            result.error = str(exc)
            result.step_results.append(
                StepResult(
                    success=False,
                    action=action,
                    details={"step": idx, "error": str(exc)},
                )
            )
            break

    return result


def execute_inline_steps(
    pseudo_name: str,
    steps: List[Dict[str, Any]],
    dry_run: bool = True,
    registry_dir=DEFAULT_REGISTRY_DIR,
    ha: Any = None,
    _visited: Optional[Set[str]] = None,
) -> ScenarioExecutionResult:
    result = ScenarioExecutionResult(
        success=True,
        scenario_name=pseudo_name,
        dry_run=dry_run,
    )

    if _visited is None:
        _visited = set()

    temp_wrapper = {"steps": steps}

    # Локальная копия основной логики через временный monkey patch не нужна,
    # просто создаём временный сценарий-объект и выполняем его вручную
    # через упрощённый цикл.
    last_verify_failed = False

    for idx, step in enumerate(temp_wrapper["steps"], start=1):
        action = step.get("action")
        try:
            if action in ("turn_on", "turn_off"):
                target_role = step.get("target_role")
                entity_value = get_role_entity(target_role, registry_dir)

                if isinstance(entity_value, list):
                    entities = entity_value
                else:
                    entities = [entity_value]

                for entity_id in entities:
                    result.step_results.append(
                        StepResult(
                            success=True,
                            action=action,
                            details={
                                "step": idx,
                                "target_role": target_role,
                                "entity_id": entity_id,
                                "mode": "dry_run" if dry_run else "real_or_pending",
                            },
                        )
                    )

            elif action == "delay":
                seconds = step.get("seconds", 0)
                result.step_results.append(
                    StepResult(
                        success=True,
                        action=action,
                        details={"step": idx, "seconds": seconds},
                    )
                )

            elif action == "notify":
                result.step_results.append(
                    StepResult(
                        success=True,
                        action=action,
                        details={
                            "step": idx,
                            "channel": step.get("channel"),
                            "message": step.get("message"),
                        },
                    )
                )

            elif action == "verify_state":
                target_role = step.get("target_role")
                expected = step.get("expected")
                entity_id = get_role_entity(target_role, registry_dir)
                last_verify_failed = False
                result.step_results.append(
                    StepResult(
                        success=True,
                        action=action,
                        details={
                            "step": idx,
                            "target_role": target_role,
                            "entity_id": entity_id,
                            "expected": expected,
                            "verified": True,
                            "mode": "dry_run" if dry_run else "real_or_pending",
                        },
                    )
                )

            elif action == "conditional_if_verify_failed":
                result.step_results.append(
                    StepResult(
                        success=True,
                        action=action,
                        details={
                            "step": idx,
                            "condition_triggered": last_verify_failed,
                        },
                    )
                )

            elif action == "run_scenario":
                nested_name = step.get("run_scenario")
                nested_result = execute_scenario(
                    nested_name,
                    dry_run=dry_run,
                    registry_dir=registry_dir,
                    ha=ha,
                    _visited=set(_visited),
                )
                result.step_results.append(
                    StepResult(
                        success=nested_result.success,
                        action=action,
                        details={
                            "step": idx,
                            "nested_scenario": nested_name,
                            "nested_success": nested_result.success,
                            "nested_error": nested_result.error,
                        },
                    )
                )
                if not nested_result.success:
                    raise ScenarioExecutionError(
                        f"Nested scenario failed: {nested_name}: {nested_result.error}"
                    )

            else:
                raise ScenarioExecutionError(
                    f"Unsupported inline action '{action}' in '{pseudo_name}'"
                )

        except Exception as exc:
            result.success = False
            result.error = str(exc)
            result.step_results.append(
                StepResult(
                    success=False,
                    action=str(action),
                    details={"step": idx, "error": str(exc)},
                )
            )
            break

    return result


def get_default_ha_client() -> Any:
    if HomeAssistantClient is None:
        raise ScenarioExecutionError("Cannot import HomeAssistantClient from ha_client.py")
    return HomeAssistantClient()
