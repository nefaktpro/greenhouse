import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
STATE_FILE = BASE_DIR / "data" / "runtime" / "system_state.json"

DEFAULTS = {
    "MANUAL": {"name": "MANUAL", "execute": True, "log": True, "ask": False, "ai_control": False},
    "TEST": {"name": "TEST", "execute": False, "log": True, "ask": False, "ai_control": False},
    "ASK": {"name": "ASK", "execute": False, "log": True, "ask": True, "ai_control": False},
    "AUTO": {"name": "AUTO", "execute": True, "log": True, "ask": False, "ai_control": False},
    "AUTOPILOT": {"name": "AUTOPILOT", "execute": True, "log": True, "ask": False, "ai_control": True},
}

def _ensure_file():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        STATE_FILE.write_text(json.dumps(DEFAULTS["MANUAL"], ensure_ascii=False, indent=2), encoding="utf-8")

def get_mode():
    _ensure_file()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return str(data.get("name", "MANUAL")).upper()
    except Exception:
        return "MANUAL"

def get_mode_flags():
    _ensure_file()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        name = str(data.get("name", "MANUAL")).upper()
        base = DEFAULTS.get(name, DEFAULTS["MANUAL"]).copy()
        base.update(data)
        base["name"] = name
        return base
    except Exception:
        return DEFAULTS["MANUAL"].copy()

def set_mode(name: str):
    _ensure_file()
    mode_name = str(name).upper()
    data = DEFAULTS.get(mode_name, DEFAULTS["MANUAL"]).copy()
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
