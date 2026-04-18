from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

STATE_PATH = Path("/home/mi/greenhouse_v17/system_state.json")

router = APIRouter(prefix="/api/modes", tags=["modes"])

DEFAULT_STATE = {
    "mode": "MANUAL",
    "execute": False,
    "log": True,
    "ask": False,
    "ai_control": False,
}

MODE_PRESETS = {
    "MANUAL": {"execute": False, "log": True, "ask": False, "ai_control": False},
    "TEST": {"execute": False, "log": True, "ask": False, "ai_control": False},
    "ASK": {"execute": False, "log": True, "ask": True, "ai_control": False},
    "AUTO": {"execute": True, "log": True, "ask": False, "ai_control": False},
    "AUTOPILOT": {"execute": True, "log": True, "ask": False, "ai_control": True},
}


def read_state():
    if not STATE_PATH.exists():
        return DEFAULT_STATE.copy()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {**DEFAULT_STATE, **data}
    except Exception:
        pass
    return DEFAULT_STATE.copy()


def write_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


class ModeIn(BaseModel):
    mode: str


@router.get("/current")
def current_mode():
    state = read_state()
    return {"ok": True, "state": state}


@router.post("/set")
def set_mode(payload: ModeIn):
    mode = payload.mode.strip().upper()
    if mode not in MODE_PRESETS:
        return {"ok": False, "error": "unsupported_mode", "mode": mode}
    state = {"mode": mode, **MODE_PRESETS[mode]}
    write_state(state)
    return {"ok": True, "state": state}
