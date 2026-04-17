from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = BASE_DIR / "data" / "registry" / "scenarios.json"

def load_scenarios() -> Dict[str, Any]:
    if not SCENARIOS_PATH.exists():
        return {"version": 1, "items": []}
    return json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))

def save_scenarios(payload: Dict[str, Any]) -> None:
    SCENARIOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCENARIOS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def list_scenarios() -> List[Dict[str, Any]]:
    data = load_scenarios()
    return data.get("items", [])

def upsert_scenario(item: Dict[str, Any]) -> Dict[str, Any]:
    data = load_scenarios()
    items = data.get("items", [])
    key = item["key"]
    replaced = False
    for i, old in enumerate(items):
        if old.get("key") == key:
            items[i] = item
            replaced = True
            break
    if not replaced:
        items.append(item)
    data["items"] = items
    save_scenarios(data)
    return item
