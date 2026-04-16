from __future__ import annotations

from typing import Any, Dict, Optional


def validate_mode(
    *,
    mode_flags: Dict[str, Any],
    capability: Optional[Dict[str, Any]],
    operation: str,
) -> Dict[str, Any]:
    """
    Проверяет, разрешена ли операция в текущем режиме.

    mode_flags ожидаются в стиле:
    {
        "name": "TEST",
        "execute": False,
        "log": True,
        "ask": False,
        "ai_control": False,
    }
    """

    mode_name = str(mode_flags.get("name", "UNKNOWN")).upper()
    execute_enabled = bool(mode_flags.get("execute", False))
    ask_enabled = bool(mode_flags.get("ask", False))

    allowed_modes = set(
        str(x).upper() for x in (capability or {}).get("allowed_modes", [])
    )

    if allowed_modes and mode_name not in allowed_modes:
        return {
            "ok": False,
            "reason": f"operation '{operation}' is not allowed in mode '{mode_name}'",
            "code": "MODE_NOT_ALLOWED",
            "effective_action": "deny",
        }

    if mode_name == "TEST":
        return {
            "ok": True,
            "reason": "TEST mode: dry-run only",
            "code": "TEST_DRY_RUN",
            "effective_action": "dry_run",
        }

    if ask_enabled or mode_name == "ASK":
        return {
            "ok": True,
            "reason": "ASK mode: confirmation required",
            "code": "ASK_REQUIRED",
            "effective_action": "ask",
        }

    if not execute_enabled:
        return {
            "ok": False,
            "reason": f"execution is disabled in mode '{mode_name}'",
            "code": "EXECUTION_DISABLED",
            "effective_action": "deny",
        }

    return {
        "ok": True,
        "reason": f"operation '{operation}' allowed in mode '{mode_name}'",
        "code": "MODE_OK",
        "effective_action": "execute",
    }
