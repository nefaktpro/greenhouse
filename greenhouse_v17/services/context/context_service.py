import json
from pathlib import Path
from typing import Dict, Any

STATE_PATH = Path("/home/mi/greenhouse_v17/system_state.json")

def get_runtime_context() -> Dict[str, Any]:
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        state = {"mode": "UNKNOWN"}

    return {
        "mode": state.get("mode"),
        "flags": {
            "execute": state.get("execute"),
            "ask": state.get("ask"),
            "ai_control": state.get("ai_control"),
        }
    }

def get_available_contexts():
    return [
        "runtime_state",
        "recent_chat",
        "recent_actions",
        "ask_state",
        "registry_summary"
    ]

def build_context():
    return {
        "runtime": get_runtime_context(),
        "available_contexts": get_available_contexts()
    }
