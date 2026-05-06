from fastapi import APIRouter, Body, Query
from greenhouse_v17.services.registry_db_service import (
    get_device_passport,
    get_registry_device_view,
    list_device_passports,
    registry_stats,
    save_device_passport_from_payload,
    sync_registry_to_db,
)

router = APIRouter(prefix="/api/registry-db", tags=["registry-db"])


@router.get("/stats")
def api_registry_db_stats():
    return registry_stats()


@router.post("/sync")
def api_registry_db_sync():
    return sync_registry_to_db()


@router.get("/devices")
def api_registry_db_devices(
    limit: int = Query(500, ge=1, le=1000),
    q: str | None = None,
    controllable: bool | None = None,
    has_entity: bool | None = None,
    has_passport: bool | None = None,
):
    items = get_registry_device_view(
        limit=limit,
        q=q,
        controllable=controllable,
        has_entity=has_entity,
        has_passport=has_passport,
    )
    return {"ok": True, "count": len(items), "items": items}


@router.get("/passports")
def api_registry_db_passports(limit: int = Query(200, ge=1, le=1000)):
    items = list_device_passports(limit=limit)
    return {"ok": True, "count": len(items), "items": items}


@router.get("/passports/{logical_role}")
def api_registry_db_passport(logical_role: str):
    item = get_device_passport(logical_role)
    if not item:
        return {"ok": False, "error": "passport_not_found", "logical_role": logical_role}
    return {"ok": True, "item": item}


@router.post("/passports")
def api_registry_db_save_passport(payload: dict = Body(...)):
    result = save_device_passport_from_payload(payload)
    return result
