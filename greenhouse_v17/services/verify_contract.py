from __future__ import annotations

from typing import Any, Dict, Literal, Optional

VerifyStatus = Literal["ok", "failed", "unavailable", "stale", "timeout", "partial"]
VerifyStrategy = Literal["state", "delayed_state", "sensor_effect", "climate_effect"]

def make_verify_result(
    *,
    ok: bool,
    status: VerifyStatus,
    strategy: VerifyStrategy,
    entity_id: Optional[str] = None,
    expected_state: Optional[str] = None,
    actual_state: Optional[str] = None,
    reason: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ok": ok,
        "status": status,
        "strategy": strategy,
        "entity_id": entity_id,
        "expected_state": expected_state,
        "actual_state": actual_state,
        "reason": reason,
    }
    if extra:
        result.update(extra)
    return result
