from __future__ import annotations

from typing import Dict, Any

def get_default_object() -> Dict[str, Any]:
    return {
        "object_id": "greenhouse_main",
        "title": "Main Greenhouse",
        "status": "active",
        "ha_connection": "primary",
        "ui_editable": True
    }
