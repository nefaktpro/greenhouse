from __future__ import annotations

from typing import Any, Dict, Iterable, List


def validate_conflicts(
    *,
    target_role: str,
    operation: str,
    pending_actions: Iterable[Dict[str, Any]] | None = None,
    active_blocks: Iterable[str] | None = None,
) -> Dict[str, Any]:
    pending_actions = list(pending_actions or [])
    active_blocks = set(active_blocks or [])

    if target_role in active_blocks:
        return {
            "ok": False,
            "reason": f"target '{target_role}' is blocked by active conflict rule",
            "code": "TARGET_BLOCKED",
        }

    opposite = {
        "turn_on": "turn_off",
        "turn_off": "turn_on",
        "open": "close",
        "close": "open",
        "start": "stop",
        "stop": "start",
    }.get(operation)

    for item in pending_actions:
        if item.get("target_role") == target_role and item.get("operation") == opposite:
            return {
                "ok": False,
                "reason": f"conflicting pending action for '{target_role}'",
                "code": "PENDING_CONFLICT",
            }

    return {
        "ok": True,
        "reason": "no conflicts found",
        "code": "CONFLICTS_OK",
    }
