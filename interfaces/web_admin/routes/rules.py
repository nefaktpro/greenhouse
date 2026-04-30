from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from greenhouse_v17.services.ai_rules_service import (
    create_ai_rule,
    delete_ai_rule,
    list_ai_rules,
    read_rules_log,
    run_due_rules_once,
    set_ai_rule_enabled,
    test_rule,
    start_rules_worker,
    run_single_rule,
)

router = APIRouter(prefix="/api/rules", tags=["rules"])

start_rules_worker()


class RuleCreateRequest(BaseModel):
    title: str
    entity_id: str
    operator: str
    value: Any
    action_key: Optional[str] = None
    action_keys: Optional[List[str]] = None
    enabled: bool = True
    cooldown_sec: int = 1800
    source_text: str = ""


@router.get("")
def api_list_rules():
    return {"ok": True, "items": list_ai_rules()}


@router.post("")
def api_create_rule(payload: RuleCreateRequest):
    data = payload.model_dump()
    return {"ok": True, "item": create_ai_rule(**data)}


@router.post("/{rule_id}/enable")
def api_enable_rule(rule_id: str):
    item = set_ai_rule_enabled(rule_id, True)
    return {"ok": bool(item), "item": item}


@router.post("/{rule_id}/disable")
def api_disable_rule(rule_id: str):
    item = set_ai_rule_enabled(rule_id, False)
    return {"ok": bool(item), "item": item}


@router.delete("/{rule_id}")
def api_delete_rule(rule_id: str):
    return {"ok": delete_ai_rule(rule_id)}


@router.post("/{rule_id}/test")
def api_test_rule(rule_id: str):
    return test_rule(rule_id)


@router.post("/run-once")
def api_run_rules_once(dry_run: bool = True):
    return run_due_rules_once(dry_run=dry_run)


@router.get("/logs")
def api_rules_logs(limit: int = 100):
    return {"ok": True, "items": read_rules_log(limit=limit)}


@router.post("/{rule_id}/run")
def api_run_single_rule(rule_id: str, dry_run: bool = True):
    return run_single_rule(rule_id, dry_run=dry_run)
