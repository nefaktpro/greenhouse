from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


LOG_DIR = Path("data/memory/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

MODE_FILES = {
    "MANUAL": "manual_log.json",
    "ASK": "ask_log.json",
    "TEST": "test_log.json",
    "AUTO": "auto_log.json",
    "AUTOPILOT": "autopilot_log.json",
}

INDEX_FILE = LOG_DIR / "all_events_log.json"
MAX_PER_FILE = 2000
MAX_INDEX = 3000


def _read_list(path: Path) -> list:
    if not path.exists():
        path.write_text("[]", encoding="utf-8")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_list(path: Path, data: list, limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data[-limit:], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def log_decision(
    *,
    mode: str,
    source: str,
    event: str,
    action_key: str | None = None,
    ok: bool | None = None,
    result: str | None = None,
    details: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    mode_name = (mode or "UNKNOWN").upper()
    filename = MODE_FILES.get(mode_name, f"{mode_name.lower()}_log.json")
    path = LOG_DIR / filename

    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "mode": mode_name,
        "source": source,
        "event": event,
        "action_key": action_key,
        "ok": ok,
        "result": result,
        "details": details or {},
    }

    mode_log = _read_list(path)
    mode_log.append(entry)
    _write_list(path, mode_log, MAX_PER_FILE)

    index = _read_list(INDEX_FILE)
    index.append({
        "time": entry["time"],
        "mode": mode_name,
        "source": source,
        "event": event,
        "action_key": action_key,
        "ok": ok,
        "result": result,
        "log_file": str(path),
    })
    _write_list(INDEX_FILE, index, MAX_INDEX)

    return entry
