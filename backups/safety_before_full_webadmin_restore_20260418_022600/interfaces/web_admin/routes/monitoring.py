from __future__ import annotations

from fastapi import APIRouter

from interfaces.web_admin.routes.registry import load_devices

router = APIRouter()


@router.get("/overview")
def monitoring_overview():
    items = load_devices()
    categories = {}
    for item in items:
        t = item.get("type") or "unknown"
        categories[t] = categories.get(t, 0) + 1
    return {
        "ok": True,
        "kind": "overview",
        "count": len(items),
        "categories": categories,
        "items": items[:100],
    }


@router.get("/safety")
def monitoring_safety():
    return {
        "ok": True,
        "kind": "safety",
        "status": "available",
        "summary": "Safety API route is alive",
        "critical_rules": [
            "fire_priority",
            "leak_priority",
            "power_priority",
        ],
    }
