from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


BASE_DIR = Path(__file__).resolve().parents[2]
CAPABILITIES_PATH = BASE_DIR / "data" / "registry" / "device_capabilities.json"


def load_device_capabilities() -> Dict[str, Any]:
    if not CAPABILITIES_PATH.exists():
        return {}

    with CAPABILITIES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return {}

    return data


def get_capability_for_role(target_role: str) -> Dict[str, Any]:
    data = load_device_capabilities()
    value = data.get(target_role, {})
    return value if isinstance(value, dict) else {}
