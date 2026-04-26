from fastapi import APIRouter
from pydantic import BaseModel

from greenhouse_v17.services.mode_service import get_mode_flags, set_mode as set_mode_service, MODE_PRESETS

router = APIRouter(prefix="/api/modes", tags=["modes"])


class ModeIn(BaseModel):
    mode: str


@router.get("/current")
def current_mode():
    return {"ok": True, "state": get_mode_flags()}


@router.post("/set")
def set_mode(payload: ModeIn):
    mode = payload.mode.strip().upper()
    if mode not in MODE_PRESETS:
        return {"ok": False, "error": "unsupported_mode", "mode": mode}
    state = set_mode_service(mode)
    return {"ok": True, "state": state}
