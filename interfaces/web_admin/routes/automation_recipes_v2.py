from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from greenhouse_v17.services.automation_recipe_v2_service import (
    create_recipe_v2,
    delete_recipe_v2,
    list_recipes_v2,
    read_recipes_v2_log,
    run_due_recipes_v2_once,
    set_recipe_v2_enabled,
    start_recipe_v2_worker,
)

router = APIRouter(prefix="/api/automation/recipes-v2", tags=["automation-recipes-v2"])

start_recipe_v2_worker()


class RecipeV2Request(BaseModel):
    title: str
    trigger: Dict[str, Any]
    action_plan: Dict[str, Any]
    conditions: Optional[Dict[str, Any]] = None
    enabled: bool = True
    source_text: str = ""


@router.get("")
def api_list_recipes_v2():
    return {"ok": True, "items": list_recipes_v2()}


@router.post("")
def api_create_recipe_v2(payload: RecipeV2Request):
    return {"ok": True, "item": create_recipe_v2(**payload.model_dump())}


@router.post("/run-due")
def api_run_due_recipes_v2():
    return run_due_recipes_v2_once()


@router.post("/{recipe_id}/enable")
def api_enable_recipe_v2(recipe_id: str):
    item = set_recipe_v2_enabled(recipe_id, True)
    return {"ok": bool(item), "item": item}


@router.post("/{recipe_id}/disable")
def api_disable_recipe_v2(recipe_id: str):
    item = set_recipe_v2_enabled(recipe_id, False)
    return {"ok": bool(item), "item": item}


@router.delete("/{recipe_id}")
def api_delete_recipe_v2(recipe_id: str):
    return {"ok": delete_recipe_v2(recipe_id)}


@router.get("/logs")
def api_recipe_v2_logs(limit: int = 100):
    return {"ok": True, "items": read_recipes_v2_log(limit=limit)}
