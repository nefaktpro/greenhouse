import json
from datetime import datetime
from typing import Any, Dict, Optional

from greenhouse_v17.services.runtime_paths import ASK_STATE_PATH, ensure_runtime_dirs

def save_ask_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_runtime_dirs()
    data = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        **payload,
    }
    ASK_STATE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data

def load_ask_state() -> Optional[Dict[str, Any]]:
    ensure_runtime_dirs()
    if not ASK_STATE_PATH.exists():
        return None
    try:
        return json.loads(ASK_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None

def clear_ask_state() -> None:
    ensure_runtime_dirs()
    if ASK_STATE_PATH.exists():
        ASK_STATE_PATH.unlink()
