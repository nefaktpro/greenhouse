from __future__ import annotations

import json
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


RECIPES_FILE = Path("data/runtime/automation_recipes_v2.json")
LOG_FILE = Path("data/memory/logs/automation_recipes_v2_log.json")
_WORKER_STARTED = False


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _ensure_files() -> None:
    RECIPES_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not RECIPES_FILE.exists():
        RECIPES_FILE.write_text("[]", encoding="utf-8")
    if not LOG_FILE.exists():
        LOG_FILE.write_text("[]", encoding="utf-8")


def _read_json(path: Path, default: Any) -> Any:
    _ensure_files()
    try:
        return json.loads(path.read_text(encoding="utf-8") or "null")
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _log(event: Dict[str, Any]) -> None:
    logs = _read_json(LOG_FILE, [])
    if not isinstance(logs, list):
        logs = []
    logs.append({"time": _now(), **event})
    _write_json(LOG_FILE, logs[-500:])


def list_recipes_v2() -> List[Dict[str, Any]]:
    items = _read_json(RECIPES_FILE, [])
    return items if isinstance(items, list) else []


def read_recipes_v2_log(limit: int = 100) -> List[Dict[str, Any]]:
    logs = _read_json(LOG_FILE, [])
    if not isinstance(logs, list):
        return []
    return logs[-limit:]


def _save(items: List[Dict[str, Any]]) -> None:
    _write_json(RECIPES_FILE, items)


def _infer_off_action(action_key: str) -> Optional[str]:
    if action_key and action_key.endswith("_on"):
        return action_key[:-3] + "_off"
    return None


def _execute(action_key: str) -> Dict[str, Any]:
    from greenhouse_v17.services.webadmin_execution_service import execute_action
    try:
        res = execute_action(action_key=action_key, source="automation_recipe_v2")
    except TypeError:
        res = execute_action(action_key)
    return res if isinstance(res, dict) else {"ok": True, "result": res}


def _get_state(entity_id: str) -> Any:
    from greenhouse_v17.services.ai_rules_service import _get_ha_state
    return _get_ha_state(entity_id).get("state")


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    from greenhouse_v17.services.ai_rules_service import evaluate_condition
    return evaluate_condition(actual, operator, expected)


def eval_condition_node(node: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not node:
        return {"ok": True, "result": True, "reason": "no_condition"}

    logic = str(node.get("logic") or "").upper()
    if logic in ("AND", "OR"):
        children = node.get("items") or []
        results = [eval_condition_node(x) for x in children]
        values = [bool(x.get("result")) for x in results]
        final = all(values) if logic == "AND" else any(values)
        return {"ok": True, "result": final, "logic": logic, "items": results}

    ctype = node.get("type") or "sensor"
    if ctype in ("sensor", "state"):
        entity_id = node.get("entity_id")
        actual = _get_state(entity_id)
        final = _compare(actual, node.get("operator"), node.get("value"))
        return {"ok": True, "result": final, "actual": actual, "condition": node}

    if ctype == "time_window":
        now = datetime.now().strftime("%H:%M")
        start = node.get("from")
        end = node.get("to")
        if not start or not end:
            return {"ok": False, "result": False, "error": "bad_time_window", "condition": node}
        if start <= end:
            final = start <= now <= end
        else:
            final = now >= start or now <= end
        return {"ok": True, "result": final, "actual": now, "condition": node}

    return {"ok": False, "result": False, "error": "unsupported_condition", "condition": node}


def create_recipe_v2(
    title: str,
    trigger: Dict[str, Any],
    action_plan: Dict[str, Any],
    conditions: Optional[Dict[str, Any]] = None,
    enabled: bool = True,
    source_text: str = "",
) -> Dict[str, Any]:
    items = list_recipes_v2()
    now_ts = time.time()

    recipe = {
        "recipe_id": "auto2_" + uuid.uuid4().hex[:10],
        "version": 2,
        "enabled": bool(enabled),
        "status": "active",
        "title": title,
        "trigger": trigger,
        "conditions": conditions,
        "action_plan": action_plan,
        "runtime": {
            "created_ts": now_ts,
            "last_run_key": None,
            "next_due_ts": _calc_next_due_ts(trigger, now_ts),
            "pending_steps": [],
        },
        "source_text": source_text,
        "created_at": _now(),
        "updated_at": _now(),
        "last_result": None,
    }

    items.append(recipe)
    _save(items)
    _log({"type": "recipe_v2_created", "recipe_id": recipe["recipe_id"], "title": title})
    return recipe


def set_recipe_v2_enabled(recipe_id: str, enabled: bool) -> Optional[Dict[str, Any]]:
    items = list_recipes_v2()
    found = None
    for r in items:
        if r.get("recipe_id") == recipe_id:
            r["enabled"] = bool(enabled)
            r["updated_at"] = _now()
            found = r
            break
    if found:
        _save(items)
        _log({"type": "recipe_v2_enabled_changed", "recipe_id": recipe_id, "enabled": enabled})
    return found


def delete_recipe_v2(recipe_id: str) -> bool:
    items = list_recipes_v2()
    new_items = [x for x in items if x.get("recipe_id") != recipe_id]
    if len(new_items) == len(items):
        return False
    _save(new_items)
    _log({"type": "recipe_v2_deleted", "recipe_id": recipe_id})
    return True


def _calc_next_due_ts(trigger: Dict[str, Any], base_ts: float) -> Optional[float]:
    t = trigger.get("type")
    if t == "now":
        return base_ts
    if t == "delay":
        return base_ts + int(trigger.get("delay_sec") or 0)
    if t == "interval":
        return base_ts + int(trigger.get("every_sec") or 60)
    return None


def _weekday_key(dt: datetime) -> str:
    return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][dt.weekday()]


def _trigger_due(recipe: Dict[str, Any], now_ts: float) -> Dict[str, Any]:
    trigger = recipe.get("trigger") or {}
    runtime = recipe.setdefault("runtime", {})
    t = trigger.get("type")

    if t in ("now", "delay", "interval"):
        due = runtime.get("next_due_ts")
        return {"due": due is not None and float(due) <= now_ts, "trigger": trigger}

    if t == "weekly":
        dt = datetime.now()
        day = _weekday_key(dt)
        hhmm = dt.strftime("%H:%M")
        days = trigger.get("days") or []
        wanted_time = trigger.get("time")
        run_key = f"{dt.strftime('%Y-%m-%d')}:{hhmm}"
        due = day in days and hhmm == wanted_time and runtime.get("last_run_key") != run_key
        return {"due": due, "trigger": trigger, "run_key": run_key}

    return {"due": False, "trigger": trigger, "error": "unsupported_trigger"}


def _schedule_next(recipe: Dict[str, Any], trigger_info: Dict[str, Any]) -> None:
    trigger = recipe.get("trigger") or {}
    runtime = recipe.setdefault("runtime", {})
    now_ts = time.time()
    t = trigger.get("type")

    if t == "now":
        runtime["next_due_ts"] = None
        recipe["status"] = "completed"
        recipe["enabled"] = False

    elif t == "delay":
        runtime["next_due_ts"] = None
        recipe["status"] = "completed"
        recipe["enabled"] = False

    elif t == "interval":
        runtime["next_due_ts"] = now_ts + int(trigger.get("every_sec") or 60)

    elif t == "weekly":
        if trigger_info.get("run_key"):
            runtime["last_run_key"] = trigger_info["run_key"]


def _run_duration(action: Dict[str, Any]) -> Dict[str, Any]:
    action_key = action.get("action_key")
    off_action_key = action.get("off_action_key") or _infer_off_action(action_key)
    duration_sec = int(action.get("duration_sec") or 0)

    on_result = _execute(action_key)
    if duration_sec > 0 and off_action_key:
        time.sleep(duration_sec)
        off_result = _execute(off_action_key)
    else:
        off_result = None

    return {
        "ok": True,
        "type": "duration",
        "action_key": action_key,
        "off_action_key": off_action_key,
        "duration_sec": duration_sec,
        "on_result": on_result,
        "off_result": off_result,
    }


def _run_action_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    ptype = plan.get("type")

    if ptype == "action":
        return {"ok": True, "type": "action", "result": _execute(plan.get("action_key"))}

    if ptype == "duration":
        return _run_duration(plan)

    if ptype == "sequence":
        results = []
        for item in plan.get("items") or []:
            if item.get("type") == "wait":
                time.sleep(int(item.get("duration_sec") or 0))
                results.append({"ok": True, "type": "wait", "duration_sec": item.get("duration_sec")})
            else:
                results.append(_run_action_plan(item))
        return {"ok": True, "type": "sequence", "results": results}

    if ptype == "decision":
        cases = sorted(plan.get("cases") or [], key=lambda x: int(x.get("priority") or 999))
        checked = []
        for case in cases:
            cond = eval_condition_node(case.get("condition"))
            checked.append({"priority": case.get("priority"), "title": case.get("title"), "condition": cond})
            if cond.get("result"):
                result = _run_action_plan(case.get("action_plan") or case.get("action") or {})
                return {"ok": True, "type": "decision", "matched": case, "checked": checked, "result": result}
        default_plan = plan.get("default")
        if default_plan:
            return {"ok": True, "type": "decision", "matched": "default", "checked": checked, "result": _run_action_plan(default_plan)}
        return {"ok": True, "type": "decision", "matched": None, "checked": checked, "result": None}

    return {"ok": False, "error": "unsupported_action_plan", "plan": plan}


def run_due_recipes_v2_once() -> Dict[str, Any]:
    items = list_recipes_v2()
    now_ts = time.time()
    results = []

    for recipe in items:
        if not recipe.get("enabled"):
            continue

        trigger_info = _trigger_due(recipe, now_ts)
        if not trigger_info.get("due"):
            continue

        condition = eval_condition_node(recipe.get("conditions"))
        if not condition.get("result"):
            result = {"ok": True, "status": "conditions_false_skipped", "condition": condition}
        else:
            action_result = _run_action_plan(recipe.get("action_plan") or {})
            result = {"ok": True, "status": "executed", "condition": condition, "action_result": action_result}

        recipe["last_result"] = result
        recipe["updated_at"] = _now()
        _schedule_next(recipe, trigger_info)

        _log({"type": "recipe_v2_checked", "recipe_id": recipe.get("recipe_id"), "result": result})
        results.append({"recipe_id": recipe.get("recipe_id"), **result})

    _save(items)
    return {"ok": True, "checked": len(results), "items": results}


def start_recipe_v2_worker(interval_sec: int = 10) -> None:
    global _WORKER_STARTED
    if _WORKER_STARTED:
        return
    _WORKER_STARTED = True

    def _loop() -> None:
        while True:
            try:
                run_due_recipes_v2_once()
            except Exception as exc:
                _log({"type": "recipe_v2_worker_error", "error": str(exc)})
            time.sleep(interval_sec)

    threading.Thread(target=_loop, name="automation_recipe_v2_worker", daemon=True).start()
    _log({"type": "recipe_v2_worker_started", "interval_sec": interval_sec})
