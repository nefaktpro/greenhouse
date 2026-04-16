from __future__ import annotations

from typing import Any, Dict, Iterable, Set


def validate_safety(
    *,
    safety_context: Dict[str, Any],
    safety_flags: Iterable[str] | None,
) -> Dict[str, Any]:
    """
    safety_context пример:
    {
        "fire_active": False,
        "leak_active": False,
        "power_unknown": False,
        "critical_sensor_missing": False,
    }
    """
    flags: Set[str] = set(safety_flags or [])

    fire_active = bool(safety_context.get("fire_active", False))
    leak_active = bool(safety_context.get("leak_active", False))
    power_unknown = bool(safety_context.get("power_unknown", False))
    critical_sensor_missing = bool(safety_context.get("critical_sensor_missing", False))

    if fire_active and "disable_on_fire" in flags:
        return {
            "ok": False,
            "reason": "blocked by active fire emergency",
            "code": "FIRE_BLOCK",
        }

    if leak_active and "disable_on_leak" in flags:
        return {
            "ok": False,
            "reason": "blocked by active leak emergency",
            "code": "LEAK_BLOCK",
        }

    if power_unknown and "disable_on_power_unknown" in flags:
        return {
            "ok": False,
            "reason": "blocked because power state is unknown",
            "code": "POWER_UNKNOWN_BLOCK",
        }

    if critical_sensor_missing and "requires_fresh_sensor_data" in flags:
        return {
            "ok": False,
            "reason": "blocked because critical sensor data is missing/stale",
            "code": "STALE_OR_MISSING_SENSOR_DATA",
        }

    return {
        "ok": True,
        "reason": "safety validation passed",
        "code": "SAFETY_OK",
    }
