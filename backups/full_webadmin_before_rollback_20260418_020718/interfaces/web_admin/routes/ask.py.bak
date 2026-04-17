from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from greenhouse_v17.services.ask_service import load_ask_state, clear_ask_state
from greenhouse_v17.services.action_service import execute_action

router = APIRouter()


class ConfirmAskRequest(BaseModel):
    execute: bool | None = True


@router.get("/current")
def get_current_ask_route():
    state = load_ask_state()
    return {
        "ok": True,
        "has_pending": bool(state),
        "item": state,
    }


@router.post("/cancel")
def cancel_ask_route():
    state = load_ask_state()
    if not state:
        return {
            "ok": True,
            "cancelled": False,
            "reason": "no_pending_ask",
        }

    clear_ask_state()
    return {
        "ok": True,
        "cancelled": True,
        "item": state,
    }


@router.post("/confirm")
def confirm_ask_route(payload: ConfirmAskRequest):
    state = load_ask_state()
    if not state:
        return {
            "ok": False,
            "confirmed": False,
            "reason": "no_pending_ask",
        }

    action_key = state.get("action_key")
    if not action_key:
        raise HTTPException(status_code=400, detail="pending_ask_missing_action_key")

    if payload.execute is False:
        clear_ask_state()
        return {
            "ok": True,
            "confirmed": True,
            "executed": False,
            "item": state,
            "note": "ASK state confirmed and cleared without execution",
        }

    try:
        # force_execute=True нужен, чтобы web-confirm реально исполнял ASK action,
        # а не создавал новый ASK pending повторно.
        result = execute_action(action_key, force_execute=True)
    except TypeError:
        # если в текущей версии execute_action не принимает force_execute
        result = execute_action(action_key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ask_confirm_execution_failed: {exc}")

    clear_ask_state()

    return {
        "ok": True,
        "confirmed": True,
        "executed": True,
        "item": state,
        "result": result,
    }
