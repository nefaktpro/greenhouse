from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/device-control", tags=["device-control"])


class DeviceCommandIn(BaseModel):
    entity_id: str
    device_type: str
    operation: str
    title: Optional[str] = None


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


def _service_for(device_type: str, operation: str) -> tuple[str, str, Dict[str, Any]]:
    t = (device_type or "").strip().lower()
    op = (operation or "").strip().lower()

    if t in {"switch", "light", "fan"}:
        if op not in {"on", "off"}:
            raise ValueError(f"unsupported operation '{op}' for type '{t}'")
        return t, f"turn_{op}", {}

    if t == "cover":
        mapping = {
            "open": "open_cover",
            "close": "close_cover",
            "stop": "stop_cover",
        }
        if op not in mapping:
            raise ValueError(f"unsupported operation '{op}' for type '{t}'")
        return "cover", mapping[op], {}

    if t == "climate":
        if op == "on":
            return "climate", "turn_on", {}
        if op == "off":
            return "climate", "turn_off", {}
        raise ValueError(f"unsupported operation '{op}' for type '{t}'")

    raise ValueError(f"unsupported controllable type '{t}'")


@router.post("/command")
def device_command(payload: DeviceCommandIn):
    try:
        domain, service, extra = _service_for(payload.device_type, payload.operation)
        base_url = _ha_url()
        token = _ha_token()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    url = f"{base_url}/api/services/{domain}/{service}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body: Dict[str, Any] = {"entity_id": payload.entity_id}
    body.update(extra)

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=20)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"HA request failed: {e}")

    try:
        raw = resp.json()
    except Exception:
        raw = {"text": resp.text}

    if not resp.ok:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "home_assistant_service_call_failed",
                "status_code": resp.status_code,
                "raw": raw,
            },
        )

    return {
        "ok": True,
        "entity_id": payload.entity_id,
        "device_type": payload.device_type,
        "operation": payload.operation,
        "title": payload.title,
        "ha_domain": domain,
        "ha_service": service,
        "raw": raw,
    }
