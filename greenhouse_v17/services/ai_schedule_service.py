from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from greenhouse_v17.services.webadmin_execution_service import execute_action


ROOT = Path(__file__).resolve().parents[2]
SCHEDULES_PATH = ROOT / "data" / "runtime" / "ai_schedules.json"
SCHEDULE_LOG_PATH = ROOT / "data" / "memory" / "logs" / "schedule_log.json"

DAYS_MAP = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun",
}

RU_DAYS = {
    "mon": "Пн",
    "tue": "Вт",
    "wed": "Ср",
    "thu": "Чт",
    "fri": "Пт",
    "sat": "Сб",
    "sun": "Вс",
}


def _ensure_files() -> None:
    SCHEDULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SCHEDULES_PATH.exists():
        SCHEDULES_PATH.write_text("[]", encoding="utf-8")
    if not SCHEDULE_LOG_PATH.exists():
        SCHEDULE_LOG_PATH.write_text("[]", encoding="utf-8")


def _read_json(path: Path) -> Any:
    _ensure_files()
    try:
        return json.loads(path.read_text(encoding="utf-8") or "[]")
    except Exception:
        return []


def _write_json(path: Path, data: Any) -> None:
    _ensure_files()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_schedule_log(event: str, item: Dict[str, Any] | None = None, extra: Dict[str, Any] | None = None) -> None:
    try:
        rows = _read_json(SCHEDULE_LOG_PATH)
        rows.append({
            "time": time.time(),
            "event": event,
            "schedule": item or {},
            "extra": extra or {},
        })
        rows = rows[-500:]
        _write_json(SCHEDULE_LOG_PATH, rows)
    except Exception as e:
        print("[SCHEDULE LOG ERROR]", e)


def list_ai_schedules() -> List[Dict[str, Any]]:
    items = _read_json(SCHEDULES_PATH)
    return sorted(items, key=lambda x: (not x.get("enabled", True), x.get("time", ""), x.get("created_at", 0)))


def create_ai_schedule(
    action_key: str | None,
    time_hhmm: str,
    days: List[str],
    source_text: str | None = None,
    enabled: bool = True,
    action_keys: List[str] | None = None,
) -> Dict[str, Any]:
    action_key = (action_key or "").strip() if action_key else ""
    action_keys = [x.strip() for x in (action_keys or []) if x and x.strip()]
    time_hhmm = (time_hhmm or "").strip()

    if not action_key and not action_keys:
        return {"ok": False, "error": "action_key_required"}
    if action_keys and not action_key:
        action_key = action_keys[0]
    if not time_hhmm or ":" not in time_hhmm:
        return {"ok": False, "error": "time_hhmm_required"}

    days = [d for d in days if d in RU_DAYS]
    if not days:
        days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    items = _read_json(SCHEDULES_PATH)
    item = {
        "schedule_id": "sch_" + uuid.uuid4().hex[:12],
        "enabled": bool(enabled),
        "action_key": action_key,
        "action_keys": action_keys or [action_key],
        "time": time_hhmm,
        "days": days,
        "source_text": source_text or "",
        "created_at": time.time(),
        "updated_at": time.time(),
        "last_run_key": None,
        "last_run_at": None,
        "last_result": None,
    }
    items.append(item)
    _write_json(SCHEDULES_PATH, items)
    append_schedule_log("schedule_created", item)
    return {"ok": True, "item": item}


def set_ai_schedule_enabled(schedule_id: str, enabled: bool) -> Dict[str, Any]:
    items = _read_json(SCHEDULES_PATH)
    found = None
    for item in items:
        if item.get("schedule_id") == schedule_id:
            item["enabled"] = bool(enabled)
            item["updated_at"] = time.time()
            found = item
            break
    if not found:
        return {"ok": False, "error": "not_found"}
    _write_json(SCHEDULES_PATH, items)
    append_schedule_log("schedule_enabled_changed", found, {"enabled": enabled})
    return {"ok": True, "item": found}


def run_due_schedules_once() -> Dict[str, Any]:
    now = datetime.now()
    day = DAYS_MAP[now.weekday()]
    hhmm = now.strftime("%H:%M")
    run_key = now.strftime("%Y-%m-%d_%H:%M")

    items = _read_json(SCHEDULES_PATH)
    executed = []

    for item in items:
        if not item.get("enabled", True):
            continue
        if day not in item.get("days", []):
            continue
        if item.get("time") != hhmm:
            continue
        if item.get("last_run_key") == run_key:
            continue

        action_keys = item.get("action_keys") or [item.get("action_key")]
        try:
            append_schedule_log("schedule_due", item, {"run_key": run_key})
            results = []
            for action_key in action_keys:
                if not action_key:
                    continue
                results.append({
                    "action_key": action_key,
                    "result": execute_action(action_key=action_key, source="ai_schedule")
                })

            result = {
                "ok": all((r.get("result") or {}).get("ok", True) for r in results),
                "results": results,
            }
            item["last_run_key"] = run_key
            item["last_run_at"] = time.time()
            item["last_result"] = result
            item["updated_at"] = time.time()
            append_schedule_log("schedule_executed", item, {"result": result})
            executed.append({"schedule_id": item.get("schedule_id"), "action_keys": action_keys, "result": result})
        except Exception as e:
            item["last_run_key"] = run_key
            item["last_run_at"] = time.time()
            item["last_result"] = {"ok": False, "error": str(e)}
            item["updated_at"] = time.time()
            append_schedule_log("schedule_error", item, {"error": str(e)})
            executed.append({"schedule_id": item.get("schedule_id"), "action_key": action_key, "error": str(e)})

    _write_json(SCHEDULES_PATH, items)
    return {"ok": True, "executed": executed}


_worker_started = False


def start_schedule_worker() -> None:
    global _worker_started
    if _worker_started:
        return
    _worker_started = True

    def loop():
        print("[SCHEDULE] worker started")
        while True:
            try:
                run_due_schedules_once()
            except Exception as e:
                print("[SCHEDULE WORKER ERROR]", e)
            time.sleep(30)

    t = threading.Thread(target=loop, daemon=True)
    t.start()


def read_schedule_log(limit: int = 80) -> List[Dict[str, Any]]:
    rows = _read_json(SCHEDULE_LOG_PATH)
    return rows[-limit:]


def delete_ai_schedule(schedule_id: str) -> Dict[str, Any]:
    items = _read_json(SCHEDULES_PATH)
    kept = []
    deleted = None
    for item in items:
        if item.get("schedule_id") == schedule_id:
            deleted = item
        else:
            kept.append(item)

    if not deleted:
        return {"ok": False, "error": "not_found"}

    _write_json(SCHEDULES_PATH, kept)
    append_schedule_log("schedule_deleted", deleted)
    return {"ok": True, "item": deleted}
