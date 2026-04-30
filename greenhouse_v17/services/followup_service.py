from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


FOLLOWUPS_FILE = Path("data/runtime/followups.json")
FOLLOWUP_LOG_FILE = Path("data/memory/logs/followup_log.json")


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _ts() -> float:
    return time.time()


def _ensure_files() -> None:
    FOLLOWUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    FOLLOWUP_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not FOLLOWUPS_FILE.exists():
        FOLLOWUPS_FILE.write_text("[]", encoding="utf-8")
    if not FOLLOWUP_LOG_FILE.exists():
        FOLLOWUP_LOG_FILE.write_text("[]", encoding="utf-8")


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
    logs = _read_json(FOLLOWUP_LOG_FILE, [])
    if not isinstance(logs, list):
        logs = []
    logs.append({"time": _now(), **event})
    _write_json(FOLLOWUP_LOG_FILE, logs[-500:])


def list_followups(status: Optional[str] = None) -> List[Dict[str, Any]]:
    items = _read_json(FOLLOWUPS_FILE, [])
    if not isinstance(items, list):
        return []
    if status:
        return [x for x in items if x.get("status") == status]
    return items


def read_followup_log(limit: int = 100) -> List[Dict[str, Any]]:
    logs = _read_json(FOLLOWUP_LOG_FILE, [])
    if not isinstance(logs, list):
        return []
    return logs[-limit:]


def create_followup(
    action_key: str,
    entity_id: str,
    expected_state: Optional[str],
    check_after_sec: int = 30,
    source: str = "execution_verify_failed",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    items = list_followups()

    # anti-duplicate: не плодим одинаковые pending follow-up
    for item in items:
        if (
            item.get("status") == "pending"
            and item.get("action_key") == action_key
            and item.get("entity_id") == entity_id
            and item.get("expected_state") == expected_state
        ):
            return {"ok": True, "status": "duplicate_skipped", "item": item}

    due_ts = _ts() + int(check_after_sec or 30)
    item = {
        "followup_id": "fu_" + uuid.uuid4().hex[:10],
        "status": "pending",
        "created_at": _now(),
        "due_at_ts": due_ts,
        "due_after_sec": int(check_after_sec or 30),
        "source": source,
        "type": "state_verify_late",
        "action_key": action_key,
        "entity_id": entity_id,
        "expected_state": expected_state,
        "attempts": [],
        "last_result": None,
        "meta": meta or {},
    }

    items.append(item)
    _write_json(FOLLOWUPS_FILE, items)
    _log({"type": "followup_created", "followup_id": item["followup_id"], "action_key": action_key})
    return {"ok": True, "status": "created", "item": item}


def complete_followup(followup_id: str, status: str = "completed") -> bool:
    items = list_followups()
    changed = False
    for item in items:
        if item.get("followup_id") == followup_id:
            item["status"] = status
            item["completed_at"] = _now()
            changed = True
            break
    if changed:
        _write_json(FOLLOWUPS_FILE, items)
        _log({"type": "followup_marked", "followup_id": followup_id, "status": status})
    return changed


def _read_state(entity_id: str) -> Any:
    from greenhouse_v17.services.webadmin_execution_service import _read_state_value
    return _read_state_value(entity_id)


def run_due_followups_once() -> Dict[str, Any]:
    items = list_followups()
    now_ts = _ts()
    checked = []

    for item in items:
        if item.get("status") != "pending":
            continue
        if float(item.get("due_at_ts") or 0) > now_ts:
            continue

        actual = _read_state(item.get("entity_id"))
        expected = item.get("expected_state")
        ok = expected is None or actual == expected

        attempt = {
            "time": _now(),
            "expected": expected,
            "actual": actual,
            "ok": ok,
        }

        item.setdefault("attempts", []).append(attempt)
        item["last_result"] = attempt
        item["status"] = "completed" if ok else "failed"
        item["completed_at"] = _now()

        checked.append({
            "followup_id": item.get("followup_id"),
            "ok": ok,
            "expected": expected,
            "actual": actual,
            "status": item["status"],
        })

        _log({
            "type": "followup_checked",
            "followup_id": item.get("followup_id"),
            "ok": ok,
            "expected": expected,
            "actual": actual,
            "status": item["status"],
        })

    _write_json(FOLLOWUPS_FILE, items)

    return {
        "ok": True,
        "checked": len(checked),
        "items": checked,
    }
