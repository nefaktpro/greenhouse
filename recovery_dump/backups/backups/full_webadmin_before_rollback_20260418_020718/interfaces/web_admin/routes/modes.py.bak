from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from greenhouse_v17.services.mode_service import get_mode, set_mode, DEFAULTS

router = APIRouter()


class SetModeRequest(BaseModel):
    mode: str


@router.get("/current")
def get_current_mode_route():
    mode = str(get_mode()).upper()
    flags = DEFAULTS.get(mode, DEFAULTS["MANUAL"]).copy()
    return {
        "ok": True,
        "mode": mode,
        "flags": flags,
    }


@router.post("/set")
def set_current_mode_route(payload: SetModeRequest):
    requested = str(payload.mode or "").strip().upper()

    if requested not in DEFAULTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported mode: {requested}",
        )

    set_mode(requested)

    mode = str(get_mode()).upper()
    flags = DEFAULTS.get(mode, DEFAULTS["MANUAL"]).copy()
    return {
        "ok": True,
        "mode": mode,
        "flags": flags,
    }
