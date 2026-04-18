from __future__ import annotations

from typing import Dict, Any
from greenhouse_v17.services.registry_service import load_capabilities, save_capabilities

def get_capability(logical_role: str) -> Dict[str, Any]:
    return load_capabilities().get(logical_role, {})

def upsert_capability(logical_role: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = load_capabilities()
    data[logical_role] = payload
    save_capabilities(data)
    return payload
