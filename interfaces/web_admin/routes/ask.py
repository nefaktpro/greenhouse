from __future__ import annotations

from fastapi import APIRouter

from greenhouse_v17.services.webadmin_execution_service import (
    load_ask_state,
    confirm_pending_ask,
    cancel_pending_ask,
)

router = APIRouter(prefix="/api/ask", tags=["ask"])


@router.get("/current")
def ask_current():
    state = load_ask_state()
    if not state or not state.get("has_pending"):
        return {"ok": True, "has_pending": False, "item": None}
    return {"ok": True, "has_pending": True, "item": state}


@router.post("/confirm")
def ask_confirm():
    return confirm_pending_ask()


@router.post("/cancel")
def ask_cancel():
    return cancel_pending_ask()
