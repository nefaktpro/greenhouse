from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def validate_cooldown(
    *,
    last_executed_at: Optional[str],
    constraints: Optional[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    constraints = constraints or {}
    cooldown_minutes = constraints.get("cooldown_minutes")

    if not cooldown_minutes:
        return {
            "ok": True,
            "reason": "no cooldown configured",
            "code": "NO_COOLDOWN",
        }

    last_dt = _parse_ts(last_executed_at)
    if last_dt is None:
        return {
            "ok": True,
            "reason": "no previous execution timestamp",
            "code": "NO_LAST_EXECUTION",
        }

    now = now or datetime.now(timezone.utc)
    elapsed_minutes = (now - last_dt).total_seconds() / 60.0

    if elapsed_minutes < float(cooldown_minutes):
        remaining = round(float(cooldown_minutes) - elapsed_minutes, 1)
        return {
            "ok": False,
            "reason": f"cooldown active, {remaining} min remaining",
            "code": "COOLDOWN_ACTIVE",
        }

    return {
        "ok": True,
        "reason": "cooldown passed",
        "code": "COOLDOWN_OK",
    }
