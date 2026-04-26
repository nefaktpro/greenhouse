import json
from pathlib import Path

STATE_PATH = Path("/home/mi/greenhouse_v17/system_state.json")

MODE_PRESETS = {
    "MANUAL": {"execute": True, "log": True, "ask": False, "ai_control": False},
    "TEST": {"execute": False, "log": True, "ask": False, "ai_control": False},
    "ASK": {"execute": False, "log": True, "ask": True, "ai_control": False},
    "AUTO": {"execute": True, "log": True, "ask": False, "ai_control": False},
    "AUTOPILOT": {"execute": True, "log": True, "ask": False, "ai_control": True},
}

DEFAULT_STATE = {"mode": "MANUAL", **MODE_PRESETS["MANUAL"]}


def _normalize_state(state: dict) -> dict:
    mode = str(state.get("mode", "MANUAL")).upper()
    if mode not in MODE_PRESETS:
        mode = "MANUAL"
    return {"mode": mode, "name": mode, **MODE_PRESETS[mode]}


def get_mode_flags() -> dict:
    if not STATE_PATH.exists():
        set_mode("MANUAL")
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        state = DEFAULT_STATE
    return _normalize_state(state)


def set_mode(mode: str) -> dict:
    mode = str(mode or "MANUAL").upper()
    if mode not in MODE_PRESETS:
        raise ValueError(f"unsupported_mode: {mode}")
    state = {"mode": mode, **MODE_PRESETS[mode]}
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return _normalize_state(state)
