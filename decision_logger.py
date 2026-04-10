import json
import os
from datetime import datetime

LOG_FILE = "/home/mi/greenhouse_v2/decision_log.json"


def log_decisions(mode, decisions, source="unknown"):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "source": source,
        "decisions": decisions
    }

    data = []

    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []

    data.append(entry)
    data = data[-200:]

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_recent_logs(limit=10):
    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    return data[-limit:]
