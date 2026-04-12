from __future__ import annotations

from typing import Any


def execute_ha_service(domain: str, service: str, service_data: dict[str, Any]) -> dict[str, Any]:
    """
    Temporary stub.
    Later it will call the real Home Assistant client.
    """
    return {
        "ok": True,
        "domain": domain,
        "service": service,
        "service_data": service_data,
    }
