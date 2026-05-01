from __future__ import annotations

import json
import os
import time
import uuid
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
FOLLOWUPS_PATH = ROOT / "data/runtime/followups.json"
FOLLOWUP_LOG_PATH = ROOT / "data/memory/logs/followup_log.json"
OBSERVATIONS_PATH = ROOT / "data/runtime/observations.json"
CASE_CANDIDATES_PATH = ROOT / "data/runtime/case_candidates.json"
CASES_PATH = ROOT / "data/runtime/cases.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_load(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _json_dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _append_log(event: Dict[str, Any]) -> None:
    logs = _json_load(FOLLOWUP_LOG_PATH, [])
    if not isinstance(logs, list):
        logs = []
    event.setdefault("time", _now_iso())
    logs.append(event)
    _json_dump(FOLLOWUP_LOG_PATH, logs[-1000:])


def _append_observation(item: Dict[str, Any]) -> Dict[str, Any]:
    observations = _json_load(OBSERVATIONS_PATH, [])
    if not isinstance(observations, list):
        observations = []

    item.setdefault("observation_id", f"obs_{uuid.uuid4().hex[:10]}")
    item.setdefault("created_at", _now_iso())
    item.setdefault("source", "followup")
    item.setdefault("status", "active")

    observations.append(item)
    _json_dump(OBSERVATIONS_PATH, observations[-2000:])

    try:
        from greenhouse_v17.services.memory_db_service import upsert_observation
        upsert_observation(item)
    except Exception as exc:
        _append_log({
            "type": "memory_db_write_failed",
            "target": "observation",
            "error": str(exc),
        })

    _append_log({
        "type": "observation_created",
        "observation_id": item.get("observation_id"),
        "source": item.get("source"),
        "category": item.get("category"),
        "action_key": item.get("action_key"),
    })
    return item


def list_observations(limit: int = 100) -> List[Dict[str, Any]]:
    observations = _json_load(OBSERVATIONS_PATH, [])
    if not isinstance(observations, list):
        return []
    return observations[-int(limit):]


def _append_case_candidate(item: Dict[str, Any]) -> Dict[str, Any]:
    candidates = _json_load(CASE_CANDIDATES_PATH, [])
    if not isinstance(candidates, list):
        candidates = []

    item.setdefault("case_candidate_id", f"cc_{uuid.uuid4().hex[:10]}")
    item.setdefault("created_at", _now_iso())
    item.setdefault("source", "observation")
    item.setdefault("status", "draft")

    candidates.append(item)
    _json_dump(CASE_CANDIDATES_PATH, candidates[-2000:])

    try:
        from greenhouse_v17.services.memory_db_service import upsert_case_candidate
        upsert_case_candidate(item)
    except Exception as exc:
        _append_log({
            "type": "memory_db_write_failed",
            "target": "case_candidate",
            "error": str(exc),
        })

    _append_log({
        "type": "case_candidate_created",
        "case_candidate_id": item.get("case_candidate_id"),
        "observation_id": item.get("observation_id"),
        "action_key": item.get("action_key"),
        "category": item.get("category"),
    })
    return item


def list_case_candidates(limit: int = 100, status: Optional[str] = None) -> List[Dict[str, Any]]:
    candidates = _json_load(CASE_CANDIDATES_PATH, [])
    if not isinstance(candidates, list):
        return []
    if status:
        candidates = [x for x in candidates if x.get("status") == status]
    return candidates[-int(limit):]


def create_case_candidate_from_observation(obs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    category = obs.get("category")
    action_key = obs.get("action_key")

    if obs.get("valid_for_case") is False:
        _append_log({
            "type": "case_candidate_skipped",
            "reason": "low_quality_observation",
            "observation_id": obs.get("observation_id"),
            "quality_reasons": obs.get("quality_reasons"),
            "action_key": action_key,
        })
        return None

    if category not in ("effect_failure", "effect_success", "verify_failure"):
        return None

    if category == "effect_failure":
        title = f"Кейс-кандидат: действие {action_key} не дало ожидаемый эффект"
        case_type = "failed_case"
        conclusion = obs.get("summary") or "Ожидаемый эффект не достигнут."
        recommendation = "review_or_repeat_test"
        confidence = 0.45
    elif category == "effect_success":
        title = f"Кейс-кандидат: действие {action_key} дало ожидаемый эффект"
        case_type = "successful_case"
        conclusion = obs.get("summary") or "Ожидаемый эффект достигнут."
        recommendation = "save_if_repeated"
        confidence = 0.55
    else:
        title = f"Кейс-кандидат: verify failed для {action_key}"
        case_type = "device_issue_case"
        conclusion = obs.get("summary") or "Verify не подтвердил состояние устройства."
        recommendation = "check_device_reliability"
        confidence = 0.50

    return _append_case_candidate({
        "type": "case_candidate",
        "case_type": case_type,
        "title": title,
        "problem": obs.get("reason") or category,
        "action_key": action_key,
        "context": {
            "target_entity": obs.get("target_entity"),
            "entity_id": obs.get("entity_id"),
            "baseline_value": obs.get("baseline_value"),
            "actual_value": obs.get("actual_value"),
            "delta": obs.get("delta"),
        },
        "result": {
            "category": category,
            "summary": obs.get("summary"),
            "raw_result": obs.get("raw_result"),
        },
        "conclusion": conclusion,
        "confidence": confidence,
        "recommendation": recommendation,
        "observation_id": obs.get("observation_id"),
        "followup_id": obs.get("followup_id"),
        "links": [x for x in [obs.get("observation_id"), obs.get("followup_id")] if x],
        "tags": ["followup", category],
    })


def _observation_from_followup(fu: Dict[str, Any], result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fu_type = fu.get("type")
    action_key = fu.get("action_key")

    if fu_type == "effect_check":
        ok = bool(result.get("ok"))
        delta = result.get("delta")
        reason = result.get("reason") or result.get("error")

        if ok:
            category = "effect_success"
            title = f"Follow-up: эффект действия {action_key} достигнут"
            summary = f"Эффект достигнут: delta={delta}"
            importance = "low"
        else:
            category = "effect_failure"
            title = f"Follow-up: действие {action_key} не дало ожидаемый эффект"
            summary = f"Ожидаемый эффект не достигнут: reason={reason}, delta={delta}"
            importance = "medium"

        quality_info = _effect_result_quality(result)

        return {
            "type": "observation",
            "category": category,
            "title": title,
            "summary": summary,
            "importance": importance if quality_info.get("valid_for_case") else "low",
            "quality": quality_info.get("quality"),
            "valid_for_case": quality_info.get("valid_for_case"),
            "quality_reasons": quality_info.get("quality_reasons"),
            "action_key": action_key,
            "followup_id": fu.get("followup_id"),
            "target_entity": fu.get("target_entity"),
            "baseline_value": result.get("baseline_value"),
            "actual_value": result.get("actual_value"),
            "delta": delta,
            "reason": reason,
            "raw_result": result,
            "links": [fu.get("followup_id")] if fu.get("followup_id") else [],
        }

    if fu_type in ("state_verify_late", "state_verify"):
        ok = bool(result.get("ok"))
        if ok:
            return None

        return {
            "type": "observation",
            "category": "verify_failure",
            "title": f"Follow-up: verify не подтвердил действие {action_key}",
            "summary": f"Ожидали state={result.get('expected')}, получили state={result.get('actual')}",
            "importance": "medium",
            "action_key": action_key,
            "followup_id": fu.get("followup_id"),
            "entity_id": fu.get("entity_id"),
            "expected": result.get("expected"),
            "actual": result.get("actual"),
            "reason": result.get("error") or "state_mismatch",
            "raw_result": result,
            "links": [fu.get("followup_id")] if fu.get("followup_id") else [],
        }

    return None


def _as_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "unknown", "unavailable"):
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def _effect_result_quality(result: Dict[str, Any]) -> Dict[str, Any]:
    baseline = result.get("baseline_value")
    actual = result.get("actual_value")
    error = result.get("error")
    expected_min = result.get("expected_delta_min")
    expected_max = result.get("expected_delta_max")

    reasons = []

    if error:
        reasons.append("ha_or_sensor_error")
    if baseline is None or actual is None:
        reasons.append("missing_numeric_values")
    if baseline == 0 and actual == 0:
        reasons.append("zero_baseline_and_actual")
    if expected_min is not None and float(expected_min) >= 999999:
        reasons.append("impossible_test_threshold")
    if expected_max is not None and float(expected_max) >= 999999:
        reasons.append("impossible_test_threshold")

    ok = len(reasons) == 0
    return {
        "quality": "normal" if ok else "low",
        "valid_for_case": ok,
        "quality_reasons": reasons,
    }


def _get_ha_state(entity_id: str) -> Dict[str, Any]:
    """
    Flexible HA state reader:
    1) tries project HA clients if they exist
    2) falls back to HA_URL + HA_TOKEN / HOME_ASSISTANT_TOKEN
    """
    candidates = [
        ("greenhouse_v17.services.ha_client", "get_state"),
        ("greenhouse_v17.services.ha_service", "get_state"),
        ("greenhouse_v17.services.home_assistant_service", "get_state"),
        ("services.ha_client", "get_state"),
    ]
    for module_name, func_name in candidates:
        try:
            mod = __import__(module_name, fromlist=[func_name])
            fn = getattr(mod, func_name)
            data = fn(entity_id)
            if isinstance(data, dict):
                return data
            return {"entity_id": entity_id, "state": data}
        except Exception:
            pass

    url = (
        os.environ.get("HA_URL")
        or os.environ.get("HOME_ASSISTANT_URL")
        or os.environ.get("HASS_URL")
        or "http://127.0.0.1:8123"
    ).rstrip("/")
    token = (
        os.environ.get("HA_TOKEN")
        or os.environ.get("HOME_ASSISTANT_TOKEN")
        or os.environ.get("HASS_TOKEN")
    )
    if not token:
        return {"entity_id": entity_id, "state": None, "error": "ha_token_missing"}

    req = urllib.request.Request(
        f"{url}/api/states/{entity_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"entity_id": entity_id, "state": None, "error": str(exc)}


def list_followups(include_done: bool = True, status: str | None = None) -> List[Dict[str, Any]]:
    data = _json_load(FOLLOWUPS_PATH, [])
    if not isinstance(data, list):
        return []
    if status:
        return [x for x in data if x.get("status") == status]
    if include_done:
        return data
    return [x for x in data if x.get("status") in ("pending", "in_progress")]


def save_followups(items: List[Dict[str, Any]]) -> None:
    _json_dump(FOLLOWUPS_PATH, items)


def create_followup(
    action_key: str,
    entity_id: Optional[str] = None,
    expected_state: Optional[str] = None,
    check_after_sec: int = 30,
    source: str = "manual",
    meta: Optional[Dict[str, Any]] = None,
    type: str = "state_verify_late",
    target_entity: Optional[str] = None,
    expected_delta_min: Optional[float] = None,
    expected_delta_max: Optional[float] = None,
    baseline_value: Optional[float] = None,
    direction: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Backward-compatible follow-up creator.

    Existing use:
      create_followup(action_key, entity_id, expected_state, ...)

    New effect check:
      create_followup(
        action_key="humidifier_on",
        type="effect_check",
        target_entity="sensor.xxx_humidity",
        expected_delta_min=5,
        expected_delta_max=15,
        check_after_sec=900
      )
    """
    meta = meta or {}
    fu_id = f"fu_{uuid.uuid4().hex[:10]}"

    if type == "effect_check" and baseline_value is None and target_entity:
        state_data = _get_ha_state(target_entity)
        baseline_value = _as_float(state_data.get("state"))
        meta.setdefault("baseline_raw_state", state_data.get("state"))
        if state_data.get("error"):
            meta.setdefault("baseline_error", state_data.get("error"))

    item: Dict[str, Any] = {
        "followup_id": fu_id,
        "status": "pending",
        "created_at": _now_iso(),
        "due_at_ts": time.time() + max(0, int(check_after_sec)),
        "due_after_sec": int(check_after_sec),
        "source": source,
        "type": type,
        "action_key": action_key,
        "entity_id": entity_id,
        "expected_state": expected_state,
        "attempts": [],
        "last_result": None,
        "meta": meta,
    }

    if type == "effect_check":
        item.update({
            "target_entity": target_entity,
            "baseline_value": baseline_value,
            "expected_delta_min": expected_delta_min,
            "expected_delta_max": expected_delta_max,
            "direction": direction,
        })

    items = list_followups(include_done=True)
    items.append(item)
    save_followups(items)

    _append_log({
        "type": "followup_created",
        "followup_id": fu_id,
        "action_key": action_key,
        "followup_type": type,
        "target_entity": target_entity,
    })
    return item


def _check_state_verify(fu: Dict[str, Any]) -> Dict[str, Any]:
    entity_id = fu.get("entity_id")
    expected = fu.get("expected_state")
    if not entity_id:
        return {"ok": False, "error": "missing_entity_id"}

    state_data = _get_ha_state(entity_id)
    actual = state_data.get("state")
    ok = expected is None or str(actual) == str(expected)

    return {
        "time": _now_iso(),
        "expected": expected,
        "actual": actual,
        "ok": bool(ok),
        "error": state_data.get("error"),
    }


def _check_effect(fu: Dict[str, Any]) -> Dict[str, Any]:
    target = fu.get("target_entity")
    if not target:
        return {"time": _now_iso(), "ok": False, "error": "missing_target_entity"}

    state_data = _get_ha_state(target)
    actual_value = _as_float(state_data.get("state"))
    baseline = _as_float(fu.get("baseline_value"))

    if baseline is None:
        return {
            "time": _now_iso(),
            "ok": False,
            "error": "missing_baseline_value",
            "actual_raw": state_data.get("state"),
        }

    if actual_value is None:
        return {
            "time": _now_iso(),
            "ok": False,
            "error": state_data.get("error") or "actual_value_not_numeric",
            "actual_raw": state_data.get("state"),
            "baseline_value": baseline,
        }

    delta = actual_value - baseline
    min_delta = fu.get("expected_delta_min")
    max_delta = fu.get("expected_delta_max")
    direction = fu.get("direction")

    ok = True
    reason = "effect_ok"

    if min_delta is not None and delta < float(min_delta):
        ok = False
        reason = "below_expected_delta"
    if max_delta is not None and delta > float(max_delta):
        ok = False
        reason = "above_expected_delta"
    if direction == "increase" and delta <= 0:
        ok = False
        reason = "not_increased"
    if direction == "decrease" and delta >= 0:
        ok = False
        reason = "not_decreased"

    return {
        "time": _now_iso(),
        "ok": bool(ok),
        "reason": reason,
        "target_entity": target,
        "baseline_value": baseline,
        "actual_value": actual_value,
        "delta": delta,
        "expected_delta_min": min_delta,
        "expected_delta_max": max_delta,
        "direction": direction,
        "error": state_data.get("error"),
    }


def run_due_followups_once() -> Dict[str, Any]:
    items = list_followups(include_done=True)
    now = time.time()
    checked: List[Dict[str, Any]] = []
    changed = False

    for fu in items:
        if fu.get("status") not in ("pending", "in_progress"):
            continue
        if float(fu.get("due_at_ts") or 0) > now:
            continue

        fu["status"] = "in_progress"

        if fu.get("type") == "effect_check":
            result = _check_effect(fu)
        else:
            result = _check_state_verify(fu)

        fu.setdefault("attempts", []).append(result)
        fu["last_result"] = result
        fu["completed_at"] = _now_iso()
        fu["status"] = "completed" if result.get("ok") else "failed"

        checked.append({
            "followup_id": fu.get("followup_id"),
            "type": fu.get("type"),
            "status": fu.get("status"),
            "result": result,
        })

        _append_log({
            "type": "followup_checked",
            "followup_id": fu.get("followup_id"),
            "followup_type": fu.get("type"),
            "ok": result.get("ok"),
            "status": fu.get("status"),
            "result": result,
        })

        observation = _observation_from_followup(fu, result)
        if observation:
            created_obs = _append_observation(observation)
            fu.setdefault("observations", []).append(created_obs.get("observation_id"))

            case_candidate = create_case_candidate_from_observation(created_obs)
            if case_candidate:
                fu.setdefault("case_candidates", []).append(case_candidate.get("case_candidate_id"))

        changed = True

    if changed:
        save_followups(items)

    return {
        "ok": True,
        "checked": len(checked),
        "items": checked,
        "pending": len([x for x in items if x.get("status") in ("pending", "in_progress")]),
    }


def create_effect_followup(
    action_key: str,
    target_entity: str,
    expected_delta_min: Optional[float] = None,
    expected_delta_max: Optional[float] = None,
    check_after_sec: int = 900,
    source: str = "manual_effect_followup",
    meta: Optional[Dict[str, Any]] = None,
    direction: Optional[str] = None,
) -> Dict[str, Any]:
    return create_followup(
        action_key=action_key,
        type="effect_check",
        target_entity=target_entity,
        expected_delta_min=expected_delta_min,
        expected_delta_max=expected_delta_max,
        check_after_sec=check_after_sec,
        source=source,
        meta=meta or {},
        direction=direction,
    )


def complete_followup(followup_id: str, result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    items = list_followups(include_done=True)
    for fu in items:
        if fu.get("followup_id") == followup_id or fu.get("id") == followup_id:
            fu["status"] = "completed"
            fu["completed_at"] = _now_iso()
            if result is not None:
                fu["last_result"] = result
                fu.setdefault("attempts", []).append(result)
            save_followups(items)
            _append_log({
                "type": "followup_completed_manual",
                "followup_id": followup_id,
                "result": result,
            })
            return {"ok": True, "followup": fu}
    return {"ok": False, "error": "followup_not_found", "followup_id": followup_id}


def cancel_followup(followup_id: str, reason: str = "manual_cancel") -> Dict[str, Any]:
    items = list_followups(include_done=True)
    for fu in items:
        if fu.get("followup_id") == followup_id or fu.get("id") == followup_id:
            fu["status"] = "cancelled"
            fu["cancelled_at"] = _now_iso()
            fu["cancel_reason"] = reason
            save_followups(items)
            _append_log({
                "type": "followup_cancelled",
                "followup_id": followup_id,
                "reason": reason,
            })
            return {"ok": True, "followup": fu}
    return {"ok": False, "error": "followup_not_found", "followup_id": followup_id}



# Backward-compatible API for interfaces/web_admin/routes/followups.py
def read_followup_log(limit: int = 100) -> List[Dict[str, Any]]:
    logs = _json_load(FOLLOWUP_LOG_PATH, [])
    if not isinstance(logs, list):
        return []
    return logs[-int(limit):]


# Override previous complete_followup with old route-compatible signature
def complete_followup(
    followup_id: str,
    status: str = "completed",
    result: Optional[Dict[str, Any]] = None,
) -> bool:
    items = list_followups(include_done=True)
    for fu in items:
        if fu.get("followup_id") == followup_id or fu.get("id") == followup_id:
            fu["status"] = status
            fu["completed_at"] = _now_iso()
            if result is not None:
                fu["last_result"] = result
                fu.setdefault("attempts", []).append(result)
            save_followups(items)
            _append_log({
                "type": "followup_status_changed",
                "followup_id": followup_id,
                "status": status,
                "result": result,
            })
            return True
    return False



def _append_case(item: Dict[str, Any]) -> Dict[str, Any]:
    cases = _json_load(CASES_PATH, [])
    if not isinstance(cases, list):
        cases = []

    item.setdefault("case_id", f"case_{uuid.uuid4().hex[:10]}")
    item.setdefault("created_at", _now_iso())

    cases.append(item)
    _json_dump(CASES_PATH, cases[-2000:])

    try:
        from greenhouse_v17.services.memory_db_service import upsert_case
        upsert_case(item)
    except Exception as exc:
        _append_log({
            "type": "memory_db_write_failed",
            "target": "case",
            "error": str(exc),
        })

    _append_log({
        "type": "case_created",
        "case_id": item.get("case_id"),
        "source_candidate": item.get("source_candidate_id"),
    })

    return item


def approve_case_candidate(candidate_id: str, mode: str = "MANUAL") -> Dict[str, Any]:
    candidates = list_case_candidates(limit=1000)

    for c in candidates:
        if c.get("case_candidate_id") == candidate_id:

            if mode == "ASK":
                return {
                    "ok": True,
                    "mode": "ASK",
                    "ask_required": True,
                    "message": "Требуется подтверждение"
                }

            case = _append_case({
                "type": "case",
                "source": "manual_approval",
                "source_candidate_id": candidate_id,
                "action_key": c.get("action_key"),
                "case_type": c.get("case_type"),
                "context": c.get("context"),
                "result": c.get("result"),
                "conclusion": c.get("conclusion"),
                "confidence": min((c.get("confidence") or 0.5) + 0.2, 0.95),
                "tags": c.get("tags"),
            })

            c["status"] = "approved"

            items = _json_load(CASE_CANDIDATES_PATH, [])
            for x in items:
                if x.get("case_candidate_id") == candidate_id:
                    x["status"] = "approved"
            _json_dump(CASE_CANDIDATES_PATH, items)

            return {
                "ok": True,
                "mode": mode,
                "case": case
            }

    return {"ok": False, "error": "candidate_not_found"}


def reject_case_candidate(candidate_id: str) -> Dict[str, Any]:
    items = _json_load(CASE_CANDIDATES_PATH, [])
    found = False

    for x in items:
        if x.get("case_candidate_id") == candidate_id:
            x["status"] = "rejected"
            found = True

    _json_dump(CASE_CANDIDATES_PATH, items)

    return {"ok": found}



