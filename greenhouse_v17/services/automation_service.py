from __future__ import annotations

from typing import Any, Dict


def automation_summary() -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": True, "layers": {}}

    try:
        from greenhouse_v17.services.ai_rules_service import list_ai_rules
        rules = list_ai_rules()
        out["layers"]["rules"] = {
            "ok": True,
            "total": len(rules),
            "enabled": len([x for x in rules if x.get("enabled")]),
            "items": rules,
        }
    except Exception as exc:
        out["layers"]["rules"] = {"ok": False, "error": str(exc)}

    try:
        from greenhouse_v17.services.ai_schedule_service import list_ai_schedules
        schedules = list_ai_schedules()
        out["layers"]["schedules"] = {
            "ok": True,
            "total": len(schedules),
            "enabled": len([x for x in schedules if x.get("enabled")]),
            "items": schedules,
        }
    except Exception as exc:
        out["layers"]["schedules"] = {"ok": False, "error": str(exc)}

    try:
        from greenhouse_v17.services.webadmin_execution_service import list_ai_timers
        timers = list_ai_timers()
        out["layers"]["timers"] = {
            "ok": True,
            "total": len(timers),
            "active": len([x for x in timers if x.get("status") not in ("completed", "cancelled", "failed")]),
            "items": timers,
        }
    except Exception as exc:
        out["layers"]["timers"] = {"ok": False, "error": str(exc)}

    try:
        from greenhouse_v17.services.followup_service import list_followups
        followups = list_followups()
        out["layers"]["followups"] = {
            "ok": True,
            "total": len(followups),
            "pending": len([x for x in followups if x.get("status") == "pending"]),
            "items": followups,
        }
    except Exception as exc:
        out["layers"]["followups"] = {"ok": False, "error": str(exc)}

    try:
        from greenhouse_v17.services.automation_recipe_service import list_recipes
        recipes = list_recipes()
        out["layers"]["recipes"] = {
            "ok": True,
            "total": len(recipes),
            "enabled": len([x for x in recipes if x.get("enabled")]),
            "items": recipes,
        }
    except Exception as exc:
        out["layers"]["recipes"] = {"ok": False, "error": str(exc)}

    return out


def run_due_all(dry_run_rules: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {"ok": True, "results": {}}

    try:
        from greenhouse_v17.services.ai_rules_service import run_due_rules_once
        result["results"]["rules"] = run_due_rules_once(dry_run=dry_run_rules)
    except Exception as exc:
        result["results"]["rules"] = {"ok": False, "error": str(exc)}

    try:
        from greenhouse_v17.services.ai_schedule_service import run_due_schedules_once
        result["results"]["schedules"] = run_due_schedules_once()
    except Exception as exc:
        result["results"]["schedules"] = {"ok": False, "error": str(exc)}

    try:
        from greenhouse_v17.services.followup_service import run_due_followups_once
        result["results"]["followups"] = run_due_followups_once()
    except Exception as exc:
        result["results"]["followups"] = {"ok": False, "error": str(exc)}

    try:
        from greenhouse_v17.services.automation_recipe_service import run_due_recipes_once
        result["results"]["recipes"] = run_due_recipes_once()
    except Exception as exc:
        result["results"]["recipes"] = {"ok": False, "error": str(exc)}

    return result
