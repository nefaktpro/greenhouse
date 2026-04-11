from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent.parent
OBSERVATIONS_FILE = BASE_DIR / "observations.json"
MAX_OBSERVATIONS = 500


@dataclass
class ObservationRecord:
    timestamp: str
    source: str
    text: str
    category: str = "general"
    zone: Optional[str] = None
    related_devices: Optional[List[str]] = None
    meta: Optional[Dict[str, Any]] = None


def ensure_store_exists() -> None:
    if not OBSERVATIONS_FILE.exists():
        OBSERVATIONS_FILE.write_text("[]", encoding="utf-8")


def load_observations() -> List[Dict[str, Any]]:
    ensure_store_exists()
    try:
        data = json.loads(OBSERVATIONS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


def save_observations(items: List[Dict[str, Any]]) -> None:
    OBSERVATIONS_FILE.write_text(
        json.dumps(items[-MAX_OBSERVATIONS:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_observation(
    text: str,
    source: str = "user",
    category: str = "general",
    zone: Optional[str] = None,
    related_devices: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    items = load_observations()

    record = ObservationRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        source=source,
        text=text.strip(),
        category=category,
        zone=zone,
        related_devices=related_devices or [],
        meta=meta or {},
    )

    record_dict = asdict(record)
    items.append(record_dict)
    save_observations(items)
    return record_dict


def get_recent_observations(limit: int = 10) -> List[Dict[str, Any]]:
    items = load_observations()
    return items[-limit:]
