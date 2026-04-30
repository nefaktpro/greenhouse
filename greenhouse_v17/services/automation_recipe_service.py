from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


RECIPES_FILE = Path("data/runtime/automation_recipes.json")
RECIPES_LOG_FILE = Path("data/memory/logs/automation_recipes_log.json")

_WORKER_STARTED = False


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _local_now() -> datetime:
    return datetime.now()


def _ensure_files() -> None:
    RECIPES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RECIPES_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not RECIPES_FILE.exists():
        RECIPES_FILE.write_text("[]", encoding="utf-8")
    if not RECIPES_LOG_FILE.exists():
        RECIPES_LOG_FILE.write_text("[]", encoding="utf-8")


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
    logs = _read_json(RECIPES_LOG_FILE, [])
    if not isinstance(logs, list):
        logs = []
    logs.append({"time": _now(), **event})
    _write_json(RECIPES_LOG_FILE, logs[-500:])


def _infer_off_action(action_key: str) -> Optional[str]:
    if action_key.endswith("_on"):
        return action_key[:-3] + "_off"
    return None


def _execute(action_key: str) -> Dict[str, Any]:
    from greenhouse_v17.services.webadmin_execution_service import execute_action
    try:
        res = execute_action(action_key=action_key, source="automation_recipe")
    except TypeError:
        res = execute_action(action_key)
    return res if isinstance(res, dict) else {"ok": True, "result": res}


def _condition_true(condition: Dict[str, Any]) -> Dict[str, Any]:
    from greenhouse_v17.services.ai_rules_service import _get_ha_state, evaluate_condition

    entity_id = condition.get("entity_id")
    operator = condition.get("operator")
    value = condition.get("value")

    ha_state = _get_ha_state(entity_id)
    actual = ha_state.get("state")
    triggered = evaluate_condition(actual, operator, value)

    return {
        "ok": True,
        "triggered": triggered,
        "actual": actual,
        "condition": condition,
        "ha_state": ha_state,
    }


def list_recipes() -> List[Dict[str, Any]]:
    items = _read_json(RECIPES_FILE, [])
    return items if isinstance(items, list) else []


def read_recipes_log(limit: int = 100) -> List[Dict[str, Any]]:
    logs = _read_json(RECIPES_LOG_FILE, [])
    if not isinstance(logs, list):
        return []
    return logs[-limit:]


def _save_recipes(items: List[Dict[str, Any]]) -> None:
    _write_json(RECIPES_FILE, items)


def create_delay_duration_recipe(
    action_key: str,
    delay_sec: int,
    duration_sec: int,
    title: str = "",
    off_action_key: Optional[str] = None,
    enabled: bool = True,
    source_text: str = "",
) -> Dict[str, Any]:
    items = list_recipes()
    now_ts = time.time()

    recipe = {
        "recipe_id": "auto_" + uuid.uuid4().hex[:10],
        "type": "delay_duration",
        "enabled": bool(enabled),
        "status": "scheduled",
        "title": title or f"Через {delay_sec}s включить {action_key} на {duration_sec}s",
        "action": {
            "action_key": action_key,
            "off_action_key": off_action_key or _infer_off_action(action_key),
            "delay_sec": int(delay_sec),
            "duration_sec": int(duration_sec),
        },
        "due_on_ts": now_ts + int(delay_sec),
        "due_off_ts": None,
        "source_text": source_text,
        "created_at": _now(),
        "updated_at": _now(),
        "last_result": None,
    }

    items.append(recipe)
    _save_recipes(items)
    _log({"type": "recipe_created", "recipe_id": recipe["recipe_id"], "recipe_type": recipe["type"]})
    return recipe


def create_scheduled_condition_duration_recipe(
    title: str,
    days: List[str],
    time_hhmm: str,
    condition: Dict[str, Any],
    action_key: str,
    duration_sec: int,
    off_action_key: Optional[str] = None,
    enabled: bool = True,
    source_text: str = "",
) -> Dict[str, Any]:
    items = list_recipes()

    recipe = {
        "recipe_id": "auto_" + uuid.uuid4().hex[:10],
        "type": "scheduled_condition_duration",
        "enabled": bool(enabled),
        "status": "active",
        "title": title,
        "schedule": {
            "days": [d.lower() for d in days],
            "time": time_hhmm,
        },
        "condition": condition,
        "action": {
            "action_key": action_key,
            "off_action_key": off_action_key or _infer_off_action(action_key),
            "duration_sec": int(duration_sec),
        },
        "runtime": {
            "last_run_key": None,
            "pending_off": None,
        },
        "source_text": source_text,
        "created_at": _now(),
        "updated_at": _now(),
        "last_result": None,
    }

    items.append(recipe)
    _save_recipes(items)
    _log({"type": "recipe_created", "recipe_id": recipe["recipe_id"], "recipe_type": recipe["type"]})
    return recipe


def set_recipe_enabled(recipe_id: str, enabled: bool) -> Optional[Dict[str, Any]]:
    items = list_recipes()
    found = None
    for r in items:
        if r.get("recipe_id") == recipe_id:
            r["enabled"] = bool(enabled)
            r["updated_at"] = _now()
            found = r
            break
    if found:
        _save_recipes(items)
        _log({"type": "recipe_enabled_changed", "recipe_id": recipe_id, "enabled": enabled})
    return found


def delete_recipe(recipe_id: str) -> bool:
    items = list_recipes()
    new_items = [r for r in items if r.get("recipe_id") != recipe_id]
    if len(new_items) == len(items):
        return False
    _save_recipes(new_items)
    _log({"type": "recipe_deleted", "recipe_id": recipe_id})
    return True


def _weekday_key(dt: datetime) -> str:
    return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][dt.weekday()]


def _start_duration(recipe: Dict[str, Any]) -> Dict[str, Any]:
    action = recipe.get("action") or {}
    action_key = action.get("action_key")
    duration_sec = int(action.get("duration_sec") or 0)

    on_result = _execute(action_key)
    due_off_ts = time.time() + duration_sec

    pending_off = {
        "action_key": action_key,
        "off_action_key": action.get("off_action_key"),
        "due_off_ts": due_off_ts,
        "duration_sec": duration_sec,
        "on_result": on_result,
        "started_at": _now(),
    }

    return {
        "ok": True,
        "status": "started_duration",
        "pending_off": pending_off,
        "on_result": on_result,
    }


def _finish_duration(recipe: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pending = None

    if recipe.get("type") == "delay_duration":
        pending = recipe.get("pending_off")
    else:
        pending = (recipe.get("runtime") or {}).get("pending_off")

    if not pending:
        return None

    if float(pending.get("due_off_ts") or 0) > time.time():
        return None

    off_action_key = pending.get("off_action_key")
    if not off_action_key:
        return {
            "ok": False,
            "status": "missing_off_action",
            "pending_off": pending,
        }

    off_result = _execute(off_action_key)

    return {
        "ok": True,
        "status": "finished_duration",
        "off_action_key": off_action_key,
        "off_result": off_result,
    }


def run_due_recipes_once() -> Dict[str, Any]:
    items = list_recipes()
    dt = _local_now()
    hhmm = dt.strftime("%H:%M")
    day = _weekday_key(dt)

    results = []

    for recipe in items:
        if not recipe.get("enabled"):
            continue

        rid = recipe.get("recipe_id")
        rtype = recipe.get("type")

        # 1. Сначала выключаем pending duration, если пора
        finish = _finish_duration(recipe)
        if finish:
            if rtype == "delay_duration":
                recipe["pending_off"] = None
                recipe["status"] = "completed" if finish.get("ok") else "failed"
            else:
                recipe.setdefault("runtime", {})["pending_off"] = None

            recipe["last_result"] = finish
            recipe["updated_at"] = _now()
            _log({"type": "recipe_duration_finished", "recipe_id": rid, "result": finish})
            results.append({"recipe_id": rid, **finish})
            continue

        # 2. One-shot: delay + duration
        if rtype == "delay_duration":
            if recipe.get("status") != "scheduled":
                continue
            if float(recipe.get("due_on_ts") or 0) > time.time():
                continue

            start = _start_duration(recipe)
            recipe["pending_off"] = start.get("pending_off")
            recipe["status"] = "running"
            recipe["last_result"] = start
            recipe["updated_at"] = _now()

            _log({"type": "recipe_duration_started", "recipe_id": rid, "result": start})
            results.append({"recipe_id": rid, **start})
            continue

        # 3. Regular: schedule + condition + duration
        if rtype == "scheduled_condition_duration":
            schedule = recipe.get("schedule") or {}
            runtime = recipe.setdefault("runtime", {})
            if runtime.get("pending_off"):
                continue

            if day not in (schedule.get("days") or []):
                continue
            if schedule.get("time") != hhmm:
                continue

            run_key = f"{dt.strftime('%Y-%m-%d')}:{hhmm}"
            if runtime.get("last_run_key") == run_key:
                continue

            check = _condition_true(recipe.get("condition") or {})
            runtime["last_run_key"] = run_key

            if check.get("triggered"):
                start = _start_duration(recipe)
                runtime["pending_off"] = start.get("pending_off")
                result = {
                    "ok": True,
                    "status": "condition_true_started_duration",
                    "condition": check,
                    "start": start,
                }
            else:
                result = {
                    "ok": True,
                    "status": "condition_false_skipped",
                    "condition": check,
                }

            recipe["last_result"] = result
            recipe["updated_at"] = _now()
            _log({"type": "recipe_checked", "recipe_id": rid, "result": result})
            results.append({"recipe_id": rid, **result})

    _save_recipes(items)
    return {"ok": True, "checked": len(results), "items": results}


def start_recipe_worker(interval_sec: int = 10) -> None:
    global _WORKER_STARTED
    if _WORKER_STARTED:
        return
    _WORKER_STARTED = True

    def _loop() -> None:
        while True:
            try:
                run_due_recipes_once()
            except Exception as exc:
                _log({"type": "recipe_worker_error", "error": str(exc)})
            time.sleep(interval_sec)

    threading.Thread(target=_loop, name="automation_recipe_worker", daemon=True).start()
    _log({"type": "recipe_worker_started", "interval_sec": interval_sec})
