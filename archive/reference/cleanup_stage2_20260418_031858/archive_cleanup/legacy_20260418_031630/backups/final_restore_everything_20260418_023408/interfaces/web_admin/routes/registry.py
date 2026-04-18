from fastapi import APIRouter, Depends
from pathlib import Path
import json

from greenhouse_v17.services.registry_service import list_devices
from greenhouse_v17.services.capability_service import load_capabilities
from greenhouse_v17.services.scenario_service import load_scenarios
from interfaces.web_admin.deps import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])

ROOT = Path(__file__).resolve().parents[3]
ACTION_MAP_PATH = ROOT / "data" / "registry" / "action_map.json"

@router.get("/devices")
def get_devices():
    devices = list_devices()
    return {
        "ok": True,
        "count": len(devices),
        "items": devices,
    }

@router.get("/capabilities")
def get_capabilities():
    capabilities = load_capabilities()
    return {
        "ok": True,
        "count": len(capabilities),
        "items": capabilities,
    }

@router.get("/scenarios")
def get_scenarios():
    scenarios = load_scenarios()
    items = scenarios.get("items", []) if isinstance(scenarios, dict) else []
    return {
        "ok": True,
        "count": len(items),
        "items": items,
        "raw": scenarios,
    }

@router.get("/actions")
def get_actions():
    if not ACTION_MAP_PATH.exists():
        return {
            "ok": False,
            "error": "action_map_not_found",
            "path": str(ACTION_MAP_PATH),
        }

    data = json.loads(ACTION_MAP_PATH.read_text(encoding="utf-8"))
    return {
        "ok": True,
        "count": len(data),
        "items": data,
    }
