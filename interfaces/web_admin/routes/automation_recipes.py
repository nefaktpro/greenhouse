from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from greenhouse_v17.services.automation_recipe_service import (
    create_delay_duration_recipe,
    create_scheduled_condition_duration_recipe,
    delete_recipe,
    list_recipes,
    read_recipes_log,
    run_due_recipes_once,
    set_recipe_enabled,
    start_recipe_worker,
)

router = APIRouter(prefix="/api/automation/recipes", tags=["automation-recipes"])

start_recipe_worker()


class DelayDurationRequest(BaseModel):
    action_key: str
    delay_sec: int
    duration_sec: int
    title: str = ""
    off_action_key: Optional[str] = None
    enabled: bool = True
    source_text: str = ""


class ScheduledConditionDurationRequest(BaseModel):
    title: str
    days: List[str]
    time: str
    condition: Dict[str, Any]
    action_key: str
    duration_sec: int
    off_action_key: Optional[str] = None
    enabled: bool = True
    source_text: str = ""


@router.get("")
def api_list_recipes():
    return {"ok": True, "items": list_recipes()}


@router.post("/delay-duration")
def api_create_delay_duration(payload: DelayDurationRequest):
    return {"ok": True, "item": create_delay_duration_recipe(**payload.model_dump())}


@router.post("/scheduled-condition-duration")
def api_create_scheduled_condition_duration(payload: ScheduledConditionDurationRequest):
    data = payload.model_dump()
    return {
        "ok": True,
        "item": create_scheduled_condition_duration_recipe(
            title=data["title"],
            days=data["days"],
            time_hhmm=data["time"],
            condition=data["condition"],
            action_key=data["action_key"],
            duration_sec=data["duration_sec"],
            off_action_key=data.get("off_action_key"),
            enabled=data.get("enabled", True),
            source_text=data.get("source_text", ""),
        )
    }


@router.post("/run-due")
def api_run_due_recipes():
    return run_due_recipes_once()


@router.post("/{recipe_id}/enable")
def api_enable_recipe(recipe_id: str):
    item = set_recipe_enabled(recipe_id, True)
    return {"ok": bool(item), "item": item}


@router.post("/{recipe_id}/disable")
def api_disable_recipe(recipe_id: str):
    item = set_recipe_enabled(recipe_id, False)
    return {"ok": bool(item), "item": item}


@router.delete("/{recipe_id}")
def api_delete_recipe(recipe_id: str):
    return {"ok": delete_recipe(recipe_id)}


@router.get("/logs")
def api_recipe_logs(limit: int = 100):
    return {"ok": True, "items": read_recipes_log(limit=limit)}
