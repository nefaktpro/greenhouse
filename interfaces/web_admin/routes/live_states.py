from __future__ import annotations

import os
from typing import Any, Dict, List

import requests
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/live", tags=["live"])


def _ha_url() -> str:
    for key in ("HOME_ASSISTANT_URL", "HA_BASE_URL", "HA_URL"):
        value = os.getenv(key, "").strip()
        if value:
            return value.rstrip("/")
    raise RuntimeError("HA base url is not configured")


def _ha_token() -> str:
    for key in ("HOME_ASSISTANT_TOKEN", "HA_TOKEN"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    raise RuntimeError("HA token is not configured")


@router.get("/states")
def get_live_states() -> Dict[str, Any]:
    try:
        base_url = _ha_url()
        token = _ha_token()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    url = f"{base_url}/api/states"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=25)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"HA request failed: {e}")

    try:
        raw = resp.json()
    except Exception:
        raw = []

    if not resp.ok:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "home_assistant_states_failed",
                "status_code": resp.status_code,
                "raw": raw,
            },
        )

    items: List[Dict[str, Any]] = []
    for item in raw:
        attrs = item.get("attributes") or {}
        items.append(
            {
                "entity_id": item.get("entity_id"),
                "state": item.get("state"),
                "friendly_name": attrs.get("friendly_name"),
                "unit_of_measurement": attrs.get("unit_of_measurement"),
                "device_class": attrs.get("device_class"),
                "last_changed": item.get("last_changed"),
                "last_updated": item.get("last_updated"),
            }
        )

    return {"ok": True, "count": len(items), "items": items}
