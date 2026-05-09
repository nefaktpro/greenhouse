from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from greenhouse_v17.services.mode_service import get_mode_flags
from greenhouse_v17.services.decision_logger import log_decision

from greenhouse_v17.services.webadmin_execution_service import execute_action, create_pending_ask, debug_action_map_full, load_action_map, resolve_action, _read_state_value, load_ask_state
from greenhouse_v17.services.unified_log_service import read_last_log_for_entity
from greenhouse_v17.services.validation_rejection_log_service import insert_validation_rejection_run

router = APIRouter(prefix="/api/actions", tags=["actions"])


def _log_validation_rejection(
    *,
    mode_name: str,
    action_key: str,
    payload_dict: dict,
) -> None:
    try:
        insert_validation_rejection_run(
            validation_id=f"validation_{action_key}_{mode_name}",
            source="web_admin",
            mode=mode_name,
            created_by="system",
            layer="validation",
            candidate_type="action_execution",
            action_key=action_key,
            entity_id=str(payload_dict.get("entity_id") or ""),
            target_role=str(payload_dict.get("target_role") or ""),
            status="rejected",
            rejection_reason=str(payload_dict.get("error") or payload_dict.get("message") or "validation_reject"),
            rule_name=str(payload_dict.get("details") or ""),
            safety_blocked=("safety" in str(payload_dict).lower() or "blocked" in str(payload_dict).lower()),
            message=str(payload_dict.get("message") or payload_dict.get("details") or ""),
            suggested_resolution="Проверить mode / ask / safety / capability и повторить через допустимый маршрут.",
            confidence=0.95,
            note="auto from actions route",
        )
    except Exception:
        pass




class ExecuteActionIn(BaseModel):
    action_key: str
    ask: bool = False
    title: str | None = None


@router.post("/execute")
def execute_action_route(payload: ExecuteActionIn):
    mode = get_mode_flags()
    mode_name = mode.get("name", "UNKNOWN")

    # В ASK режиме любое действие сначала уходит в pending ASK.
    # Прямое исполнение из Control/Web запрещено.
    if payload.ask or mode.get("ask"):
        current = load_ask_state()
        if current.get("has_pending"):
            reject_payload = {
                "ok": False,
                "mode": mode_name,
                "routed_to": "ASK",
                "error": "pending_ask_exists",
                "message": "Сначала подтвердите или отмените текущее ASK-действие.",
                "pending": current,
            }
            _log_validation_rejection(
                mode_name=mode_name,
                action_key=payload.action_key,
                payload_dict=reject_payload,
            )
            return reject_payload

        state = create_pending_ask(
            action_key=payload.action_key,
            title=payload.title or payload.action_key,
            source="web_admin"
        )
        log_decision(
            mode=mode_name,
            source="control",
            event="ask_created",
            action_key=payload.action_key,
            ok=True,
            result="pending",
            details={"pending": state},
        )
        return {
            "ok": True,
            "mode": mode_name,
            "routed_to": "ASK",
            "pending": state
        }

    result = execute_action(action_key=payload.action_key)
    log_decision(
        mode=mode_name,
        source="control",
        event="action_executed",
        action_key=payload.action_key,
        ok=bool(result.get("ok")),
        result=result.get("status") or result.get("message"),
        details={"execution_result": result},
    )
    response_payload = {
        "ok": bool(result.get("ok")),
        "mode": mode_name,
        "routed_to": "EXECUTION",
        "result": result
    }

    if not bool(result.get("ok")):
        _log_validation_rejection(
            mode_name=mode_name,
            action_key=payload.action_key,
            payload_dict={
                "error": result.get("error"),
                "message": result.get("message"),
                "details": result.get("details"),
                "entity_id": result.get("entity_id"),
                "target_role": result.get("target_role"),
            },
        )

    return response_payload


@router.get("/debug/action-map")
def debug_action_map():
    return {"ok": True, "debug": debug_action_map_full()}


@router.get("/catalog")
def actions_catalog():
    items = []
    amap = load_action_map()

    for action_key, node in sorted(amap.items()):
        if not isinstance(node, dict):
            continue
        try:
            entity_id, operation, meta = resolve_action(action_key)
            state = _read_state_value(entity_id) if entity_id else None
        except Exception as e:
            entity_id, operation, state = None, node.get("operation"), None
            meta = {"error": str(e), **node}

        items.append({
            "action_key": action_key,
            "title": node.get("title"),
            "target_role": node.get("target_role") or node.get("logical_role") or node.get("role"),
            "operation": operation,
            "entity_id": entity_id,
            "state": state,
            "meta": meta,
        })

    return {"ok": True, "count": len(items), "items": items}

@router.get("/logs/execution/last")
def api_last_execution_log(entity_id: str):
    item = read_last_log_for_entity(entity_id)
    return {"ok": True, "item": item}

