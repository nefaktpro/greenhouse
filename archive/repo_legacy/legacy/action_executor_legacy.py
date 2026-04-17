from __future__ import annotations

from typing import Any, Dict, List

from execution.engine.execution_engine import execute_action_key


def execute_action(action_key: str):
    """
    Новый тонкий wrapper для прямого вызова одного action_key.
    """
    return execute_action_key(action_key)


def execute_decisions(decisions: List[Dict[str, Any]], dry_run: bool = False) -> List[Dict[str, Any]]:
    """
    Legacy-compatible wrapper для старого test_mode.py / bot_handlers.py.

    Ожидает список решений вида:
    [
        {"action": "fan_top_on", "reason": "..."},
        ...
    ]

    Возвращает список словарей в старом удобном формате.
    """
    results: List[Dict[str, Any]] = []

    for item in decisions or []:
        action = item.get("action")
        reason = item.get("reason", "")

        if not action or action == "none":
            results.append({
                "action": action or "none",
                "reason": reason,
                "executed": False,
                "blocked": False,
                "dry_run": dry_run,
                "error": None,
                "executor_message": "No action",
            })
            continue

        if dry_run:
            results.append({
                "action": action,
                "reason": reason,
                "executed": False,
                "blocked": False,
                "dry_run": True,
                "error": None,
                "executor_message": "Dry-run only, nothing executed",
            })
            continue

        try:
            exec_results = execute_action_key(action)

            success = any(getattr(r, "success", False) for r in exec_results)
            message_parts = []
            for r in exec_results:
                entity = getattr(r, "entity_id", None) or "-"
                msg = getattr(r, "message", "")
                mark = "OK" if getattr(r, "success", False) else "ERR"
                message_parts.append(f"{mark} {entity}: {msg}")

            results.append({
                "action": action,
                "reason": reason,
                "executed": success,
                "blocked": False,
                "dry_run": False,
                "error": None if success else "Execution failed",
                "executor_message": " | ".join(message_parts),
                "raw_results": [str(r) for r in exec_results],
            })

        except Exception as e:
            results.append({
                "action": action,
                "reason": reason,
                "executed": False,
                "blocked": False,
                "dry_run": False,
                "error": str(e),
                "executor_message": "",
            })

    return results
