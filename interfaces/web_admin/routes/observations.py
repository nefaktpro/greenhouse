from fastapi import APIRouter, Query
from greenhouse_v17.services.followup_service import list_observations

router = APIRouter(prefix="/api/observations", tags=["observations"])


@router.get("")
def api_list_observations(limit: int = Query(100, ge=1, le=500)):
    return {
        "ok": True,
        "count": len(list_observations(limit)),
        "items": list_observations(limit),
    }
