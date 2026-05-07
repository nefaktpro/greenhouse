from __future__ import annotations

import os
import time
from typing import Optional

import requests

from greenhouse_v17.services.verify_contract import make_verify_result


def run_state_verify_debug(
    *,
    entity_id: str,
    expected_state: Optional[str] = None,
    verify_delay_sec: int = 2,
    timeout_sec: int = 15,
):
    if not entity_id:
        return make_verify_result(
            ok=False,
            status="failed",
            strategy="state",
            entity_id=entity_id,
            expected_state=expected_state,
            actual_state=None,
            reason="missing_entity_id",
        )

    ha_url = (
        os.environ.get("HOME_ASSISTANT_URL")
        or os.environ.get("HA_URL")
        or "http://127.0.0.1:8123"
    ).rstrip("/")

    ha_token = os.environ.get("HOME_ASSISTANT_TOKEN") or os.environ.get("HA_TOKEN")
    if not ha_token:
        return make_verify_result(
            ok=False,
            status="failed",
            strategy="state",
            entity_id=entity_id,
            expected_state=expected_state,
            actual_state=None,
            reason="missing_ha_token",
        )

    if verify_delay_sec > 0:
        time.sleep(verify_delay_sec)

    url = f"{ha_url}/api/states/{entity_id}"

    try:
        session = requests.Session()
        session.trust_env = False
        resp = session.get(
            url,
            headers={
                "Authorization": f"Bearer {ha_token}",
                "Content-Type": "application/json",
            },
            timeout=timeout_sec,
        )

        if resp.status_code == 404:
            return make_verify_result(
                ok=False,
                status="unavailable",
                strategy="state",
                entity_id=entity_id,
                expected_state=expected_state,
                actual_state=None,
                reason="entity_not_found",
                extra={"http_status": resp.status_code},
            )

        resp.raise_for_status()
        payload = resp.json()

    except requests.Timeout:
        return make_verify_result(
            ok=False,
            status="timeout",
            strategy="state",
            entity_id=entity_id,
            expected_state=expected_state,
            actual_state=None,
            reason="state_read_timeout",
        )
    except Exception as e:
        return make_verify_result(
            ok=False,
            status="failed",
            strategy="state",
            entity_id=entity_id,
            expected_state=expected_state,
            actual_state=None,
            reason=f"state_read_error:{type(e).__name__}",
        )

    actual_state = str(payload.get("state"))

    if actual_state in ("unavailable", "unknown", "", "None", "none"):
        return make_verify_result(
            ok=False,
            status="unavailable",
            strategy="state",
            entity_id=entity_id,
            expected_state=expected_state,
            actual_state=actual_state,
            reason=f"bad_state:{actual_state}",
            extra={"last_updated": payload.get("last_updated")},
        )

    if expected_state is None:
        return make_verify_result(
            ok=True,
            status="ok",
            strategy="state",
            entity_id=entity_id,
            expected_state=expected_state,
            actual_state=actual_state,
            reason="state_read_ok",
            extra={"last_updated": payload.get("last_updated")},
        )

    if actual_state == str(expected_state):
        return make_verify_result(
            ok=True,
            status="ok",
            strategy="state",
            entity_id=entity_id,
            expected_state=expected_state,
            actual_state=actual_state,
            reason="expected_state_matched",
            extra={"last_updated": payload.get("last_updated")},
        )

    return make_verify_result(
        ok=False,
        status="failed",
        strategy="state",
        entity_id=entity_id,
        expected_state=expected_state,
        actual_state=actual_state,
        reason="expected_state_mismatch",
        extra={"last_updated": payload.get("last_updated")},
    )
