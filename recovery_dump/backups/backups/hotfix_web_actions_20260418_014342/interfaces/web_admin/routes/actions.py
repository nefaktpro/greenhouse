from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from greenhouse_v17.services.webadmin_execution_service import execute_action, create_pending_ask

router = APIRouter(prefix="/api/actions", tags=["actions"])


class ExecuteActionIn(BaseModel):
    action_key: str
    ask: bool = False
    title: str | None = None


@router.post("/execute")
def execute_action_route(payload: ExecuteActionIn):
    if payload.ask:
        state = create_pending_ask(action_key=payload.action_key, title=payload.title)
        return {"ok": True, "mode": "ASK", "pending": state}

    result = execute_action(action_key=payload.action_key)
    return {"ok": bool(result.get("ok")), "result": result}
