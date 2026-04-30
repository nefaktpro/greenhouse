from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


RULES_FILE = Path("data/runtime/ai_rules.json")
RULES_LOG_FILE = Path("data/memory/logs/rules_log.json")


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _ensure_files() -> None:
    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RULES_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not RULES_FILE.exists():
        RULES_FILE.write_text("[]", encoding="utf-8")
    if not RULES_LOG_FILE.exists():
        RULES_LOG_FILE.write_text("[]", encoding="utf-8")


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
    logs = _read_json(RULES_LOG_FILE, [])
    logs.append({
        "time": _now(),
        **event,
    })
    _write_json(RULES_LOG_FILE, logs[-500:])


def list_ai_rules() -> List[Dict[str, Any]]:
    rules = _read_json(RULES_FILE, [])
    return rules if isinstance(rules, list) else []


def read_rules_log(limit: int = 100) -> List[Dict[str, Any]]:
    logs = _read_json(RULES_LOG_FILE, [])
    if not isinstance(logs, list):
        return []
    return logs[-limit:]


def create_ai_rule(
    title: str,
    entity_id: str,
    operator: str,
    value: Any,
    action_key: Optional[str] = None,
    action_keys: Optional[List[str]] = None,
    enabled: bool = True,
    cooldown_sec: int = 1800,
    source_text: str = "",
) -> Dict[str, Any]:
    rules = list_ai_rules()

    keys = action_keys or ([action_key] if action_key else [])
    keys = [k for k in keys if k]

    rule = {
        "rule_id": "rule_" + uuid.uuid4().hex[:10],
        "enabled": bool(enabled),
        "title": title or "Новое условие",
        "condition": {
            "entity_id": entity_id,
            "operator": operator,
            "value": value,
        },
        "action_key": keys[0] if keys else None,
        "action_keys": keys,
        "cooldown_sec": int(cooldown_sec or 0),
        "source_text": source_text,
        "created_at": _now(),
        "updated_at": _now(),
        "last_run_at": None,
        "last_result": None,
    }

    rules.append(rule)
    _write_json(RULES_FILE, rules)
    _log({"type": "rule_created", "rule_id": rule["rule_id"], "title": rule["title"]})
    return rule


def set_ai_rule_enabled(rule_id: str, enabled: bool) -> Optional[Dict[str, Any]]:
    rules = list_ai_rules()
    found = None
    for rule in rules:
        if rule.get("rule_id") == rule_id:
            rule["enabled"] = bool(enabled)
            rule["updated_at"] = _now()
            found = rule
            break
    if found:
        _write_json(RULES_FILE, rules)
        _log({"type": "rule_enabled_changed", "rule_id": rule_id, "enabled": enabled})
    return found


def delete_ai_rule(rule_id: str) -> bool:
    rules = list_ai_rules()
    new_rules = [r for r in rules if r.get("rule_id") != rule_id]
    if len(new_rules) == len(rules):
        return False
    _write_json(RULES_FILE, new_rules)
    _log({"type": "rule_deleted", "rule_id": rule_id})
    return True


def _to_number(value: Any) -> Optional[float]:
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def evaluate_condition(actual: Any, operator: str, expected: Any) -> bool:
    op = (operator or "").strip()
    a_num = _to_number(actual)
    e_num = _to_number(expected)

    if op in ("<", "<=", ">", ">="):
        if a_num is None or e_num is None:
            return False
        if op == "<":
            return a_num < e_num
        if op == "<=":
            return a_num <= e_num
        if op == ">":
            return a_num > e_num
        if op == ">=":
            return a_num >= e_num

    if op in ("=", "=="):
        return str(actual).strip().lower() == str(expected).strip().lower()

    if op in ("!=", "not"):
        return str(actual).strip().lower() != str(expected).strip().lower()

    return False


def _get_ha_state(entity_id: str) -> Dict[str, Any]:
    """
    Адаптер MVP. Пытается использовать существующий HA client проекта.
    Если путь клиента отличается — вернёт понятную ошибку, не ломая rules UI.
    """
    candidates = [
        ("greenhouse_v17.services.ha_client", "get_state"),
        ("greenhouse_v17.services.ha_client", "get_ha_state"),
        ("services.ha_client", "get_state"),
        ("core.ha_client", "get_state"),
        ("app.ha_client", "get_state"),
    ]

    last_error = None
    for module_name, func_name in candidates:
        try:
            mod = __import__(module_name, fromlist=[func_name])
            func = getattr(mod, func_name)
            state = func(entity_id)
            if isinstance(state, dict):
                return state
            return {"entity_id": entity_id, "state": state}
        except Exception as exc:
            last_error = str(exc)

    return {
        "entity_id": entity_id,
        "state": None,
        "error": "ha_state_adapter_not_found",
        "details": last_error,
    }



def _current_mode_for_rules() -> str:
    try:
        from greenhouse_v17.services.mode_service import get_mode_flags
        flags = get_mode_flags()
        if isinstance(flags, dict):
            return str(flags.get("mode") or flags.get("name") or "MANUAL").upper()
    except Exception:
        pass
    return "MANUAL"




def _has_pending_ask_for_rule(rule_id: str, action_key: str) -> bool:
    try:
        from greenhouse_v17.services.webadmin_execution_service import load_ask_state
        state = load_ask_state()
        if not state or not state.get("has_pending"):
            return False
        item = state
        if item.get("action_key") != action_key:
            return False
        meta = item.get("meta") or {}
        return meta.get("rule_id") == rule_id
    except Exception:
        return False


def _create_execution_ask_from_rule(rule: Dict[str, Any], action_key: str) -> Dict[str, Any]:
    try:
        from greenhouse_v17.services.webadmin_execution_service import save_ask_state

        if _has_pending_ask_for_rule(rule.get("rule_id"), action_key):
            return {
                "ok": True,
                "status": "ask_skipped_duplicate",
                "action_key": action_key
            }

        payload = {
            "has_pending": True,
            "kind": "single_action",
            "action_key": action_key,
            "title": f"Условие сработало: {rule.get('title')}",
            "source": "rules_worker",
            "created_at": _now(),
            "meta": {
                "source": "rules_worker",
                "rule_id": rule.get("rule_id"),
                "rule_title": rule.get("title"),
                "condition": rule.get("condition"),
            },
        }
        save_ask_state(payload)
        return {"ok": True, "status": "ask_created", "action_key": action_key, "ask": payload}
    except Exception as exc:
        return {"ok": False, "status": "ask_create_failed", "action_key": action_key, "error": str(exc)}


def _execute_action_key(action_key: str, requested_mode: Optional[str] = None) -> Dict[str, Any]:
    candidates = [
        ("greenhouse_v17.services.webadmin_execution_service", "execute_action"),
        ("execution.engine.execution_engine", "execute_action"),
        ("greenhouse_v17.execution.engine.execution_engine", "execute_action"),
    ]

    last_error = None
    for module_name, func_name in candidates:
        try:
            mod = __import__(module_name, fromlist=[func_name])
            func = getattr(mod, func_name)
            try:
                result = func(action_key=action_key, source="rules_worker", requested_mode=requested_mode)
            except TypeError:
                try:
                    result = func(action_key=action_key, source="rules_worker")
                except TypeError:
                    result = func(action_key)
            return result if isinstance(result, dict) else {"ok": True, "result": result}
        except Exception as exc:
            last_error = str(exc)

    return {
        "ok": False,
        "status": "execution_adapter_not_found",
        "error": last_error,
        "action_key": action_key,
    }


def test_rule(rule_id: str) -> Dict[str, Any]:
    rule = next((r for r in list_ai_rules() if r.get("rule_id") == rule_id), None)
    if not rule:
        return {"ok": False, "error": "rule_not_found", "rule_id": rule_id}

    condition = rule.get("condition") or {}
    entity_id = condition.get("entity_id")
    ha_state = _get_ha_state(entity_id)
    actual = ha_state.get("state")
    triggered = evaluate_condition(actual, condition.get("operator"), condition.get("value"))

    return {
        "ok": True,
        "rule_id": rule_id,
        "title": rule.get("title"),
        "triggered": triggered,
        "actual": actual,
        "condition": condition,
        "ha_state": ha_state,
        "dry_run": True,
    }


def run_due_rules_once(dry_run: bool = False) -> Dict[str, Any]:
    rules = list_ai_rules()
    now_ts = time.time()
    results = []

    for rule in rules:
        if not rule.get("enabled"):
            continue

        rule_id = rule.get("rule_id")
        condition = rule.get("condition") or {}
        entity_id = condition.get("entity_id")

        ha_state = _get_ha_state(entity_id)
        actual = ha_state.get("state")
        triggered = evaluate_condition(actual, condition.get("operator"), condition.get("value"))

        result = {
            "rule_id": rule_id,
            "title": rule.get("title"),
            "triggered": triggered,
            "actual": actual,
            "condition": condition,
            "dry_run": dry_run,
            "actions": [],
        }

        if triggered:
            last_run_at = rule.get("last_run_at")
            cooldown_sec = int(rule.get("cooldown_sec") or 0)

            cooldown_blocked = False
            if last_run_at and cooldown_sec:
                try:
                    last_ts = datetime.fromisoformat(last_run_at.replace("Z", "")).timestamp()
                    cooldown_blocked = (now_ts - last_ts) < cooldown_sec
                except Exception:
                    cooldown_blocked = False

            if cooldown_blocked:
                result["status"] = "cooldown_blocked"
            else:
                action_keys = rule.get("action_keys") or ([rule.get("action_key")] if rule.get("action_key") else [])
                mode = _current_mode_for_rules()
                result["mode"] = mode

                for action_key in action_keys:
                    if dry_run or mode == "TEST":
                        action_result = {"ok": True, "status": "dry_run", "action_key": action_key, "mode": mode}
                    elif mode == "ASK":
                        action_result = _execute_action_key(action_key, requested_mode=mode)
                    else:
                        action_result = _execute_action_key(action_key, requested_mode=mode)
                    result["actions"].append(action_result)

                rule["last_run_at"] = _now()
                rule["last_result"] = result
                rule["updated_at"] = _now()
                result["status"] = "dry_run" if (dry_run or mode == "TEST") else ("executed")

        results.append(result)
        _log({"type": "rule_checked", **result})

    _write_json(RULES_FILE, rules)

    return {
        "ok": True,
        "dry_run": dry_run,
        "checked": len(results),
        "triggered": len([r for r in results if r.get("triggered")]),
        "results": results,
    }


# --- Rules worker ---
import threading

_RULES_WORKER_STARTED = False


def start_rules_worker(interval_sec: int = 30) -> None:
    """
    Background worker for condition rules.
    Проверяет enabled rules и запускает action_key только через execution adapter.
    Cooldown уже учитывается внутри run_due_rules_once().
    """
    global _RULES_WORKER_STARTED

    if _RULES_WORKER_STARTED:
        return

    _RULES_WORKER_STARTED = True

    def _loop() -> None:
        while True:
            try:
                run_due_rules_once(dry_run=False)
            except Exception as exc:
                _log({
                    "type": "rules_worker_error",
                    "error": str(exc),
                })
            time.sleep(interval_sec)

    t = threading.Thread(target=_loop, name="rules_worker", daemon=True)
    t.start()

    _log({
        "type": "rules_worker_started",
        "interval_sec": interval_sec,
    })



def run_single_rule(rule_id: str, dry_run: bool = True) -> Dict[str, Any]:
    rules = list_ai_rules()
    rule = next((r for r in rules if r.get("rule_id") == rule_id), None)

    if not rule:
        return {"ok": False, "error": "rule_not_found", "rule_id": rule_id}

    condition = rule.get("condition") or {}
    entity_id = condition.get("entity_id")
    ha_state = _get_ha_state(entity_id)
    actual = ha_state.get("state")
    triggered = evaluate_condition(actual, condition.get("operator"), condition.get("value"))

    result = {
        "ok": True,
        "rule_id": rule_id,
        "title": rule.get("title"),
        "triggered": triggered,
        "actual": actual,
        "condition": condition,
        "dry_run": dry_run,
        "actions": [],
    }

    if triggered:
        action_keys = rule.get("action_keys") or ([rule.get("action_key")] if rule.get("action_key") else [])

        mode = _current_mode_for_rules()
        result["mode"] = mode

        for action_key in action_keys:
            if dry_run or mode == "TEST":
                action_result = {"ok": True, "status": "dry_run", "action_key": action_key, "mode": mode}
            elif mode == "ASK":
                action_result = _execute_action_key(action_key, requested_mode=mode)
            else:
                action_result = _execute_action_key(action_key, requested_mode=mode)
            result["actions"].append(action_result)

        result["status"] = "dry_run" if (dry_run or mode == "TEST") else ("executed")
    else:
        result["status"] = "not_triggered"

    _log({"type": "single_rule_run", **result})
    return result
