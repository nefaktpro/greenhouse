from __future__ import annotations

from typing import Any, Dict, Optional

from .mode_validator import validate_mode
from .safety_validator import validate_safety
from .cooldown_validator import validate_cooldown
from .conflict_validator import validate_conflicts


def validate_action(
    *,
    target_role: str,
    operation: str,
    mode_flags: Dict[str, Any],
    capability: Optional[Dict[str, Any]] = None,
    safety_context: Optional[Dict[str, Any]] = None,
    last_executed_at: Optional[str] = None,
    pending_actions: Optional[list[Dict[str, Any]]] = None,
    active_blocks: Optional[list[str]] = None,
) -> Dict[str, Any]:
    capability = capability or {}
    safety_context = safety_context or {}

    steps = []

    mode_result = validate_mode(
        mode_flags=mode_flags,
        capability=capability,
        operation=operation,
    )
    steps.append({"step": "mode", **mode_result})
    if not mode_result["ok"]:
        return {"ok": False, "failed_at": "mode", "steps": steps}

    safety_result = validate_safety(
        safety_context=safety_context,
        safety_flags=capability.get("safety_flags", []),
    )
    steps.append({"step": "safety", **safety_result})
    if not safety_result["ok"]:
        return {"ok": False, "failed_at": "safety", "steps": steps}

    cooldown_result = validate_cooldown(
        last_executed_at=last_executed_at,
        constraints=capability.get("constraints", {}),
    )
    steps.append({"step": "cooldown", **cooldown_result})
    if not cooldown_result["ok"]:
        return {"ok": False, "failed_at": "cooldown", "steps": steps}

    conflict_result = validate_conflicts(
        target_role=target_role,
        operation=operation,
        pending_actions=pending_actions,
        active_blocks=active_blocks,
    )
    steps.append({"step": "conflict", **conflict_result})
    if not conflict_result["ok"]:
        return {"ok": False, "failed_at": "conflict", "steps": steps}

    return {
        "ok": True,
        "failed_at": None,
        "effective_action": mode_result.get("effective_action", "execute"),
        "steps": steps,
    }
