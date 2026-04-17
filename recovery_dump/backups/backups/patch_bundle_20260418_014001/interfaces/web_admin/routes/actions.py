from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from greenhouse_v17.services.action_service import execute_action
from interfaces.web_admin.deps import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


class ExecuteActionRequest(BaseModel):
    action_key: str
    force_execute: bool | None = False


@router.post("/execute")
def execute_action_route(payload: ExecuteActionRequest):
    action_key = str(payload.action_key or "").strip()
    if not action_key:
        raise HTTPException(status_code=400, detail="action_key_required")

    try:
        result = execute_action(
            action_key=action_key,
            force_execute=bool(payload.force_execute),
        )
    except TypeError:
        result = execute_action(action_key)

    return {
        "ok": True,
        "action_key": action_key,
        "result": result,
    }
