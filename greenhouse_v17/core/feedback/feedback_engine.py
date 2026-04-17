from __future__ import annotations

import time
import requests
from typing import Optional, Dict, Any

def _load_ha_config():
    try:
        from greenhouse_v17.config import HOME_ASSISTANT_URL as url
    except Exception:
        try:
            from greenhouse_v17.config import HA_BASE_URL as url
        except Exception:
            from greenhouse_v17.config import HOME_ASSISTANT_BASE_URL as url  # type: ignore
    try:
        from greenhouse_v17.config import HOME_ASSISTANT_TOKEN as token
    except Exception:
        try:
            from greenhouse_v17.config import HA_TOKEN as token
        except Exception:
            from greenhouse_v17.config import HOME_ASSISTANT_ACCESS_TOKEN as token  # type: ignore
    try:
        from greenhouse_v17.config import REQUEST_TIMEOUT as timeout
    except Exception:
        timeout = 10
    return url.rstrip("/"), token, timeout

def get_entity_state(entity_id: str) -> Dict[str, Any]:
    base_url, token, timeout = _load_ha_config()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    r = requests.get(
        f"{base_url}/api/states/{entity_id}",
        headers=headers,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()

def verify_entity_state(
    entity_id: str,
    expected_state: Optional[str],
    retries: int = 4,
    delay_seconds: float = 1.5,
) -> Dict[str, Any]:
    last_payload = None
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            payload = get_entity_state(entity_id)
            last_payload = payload
            actual = str(payload.get("state"))
            ok = expected_state is None or actual == expected_state
            if ok:
                return {
                    "ok": True,
                    "entity_id": entity_id,
                    "expected_state": expected_state,
                    "actual_state": actual,
                    "last_updated": payload.get("last_updated"),
                    "attempt": attempt,
                }
        except Exception as e:
            last_error = str(e)

        if attempt < retries:
            time.sleep(delay_seconds)

    if last_payload is not None:
        return {
            "ok": False,
            "entity_id": entity_id,
            "expected_state": expected_state,
            "actual_state": str(last_payload.get("state")),
            "last_updated": last_payload.get("last_updated"),
            "attempt": retries,
        }

    return {
        "ok": False,
        "entity_id": entity_id,
        "expected_state": expected_state,
        "actual_state": None,
        "error": last_error,
        "attempt": retries,
    }
