from fastapi import APIRouter, Query
from greenhouse_v17.services.followup_service import list_case_candidates

router = APIRouter(prefix="/api/case-candidates", tags=["case-candidates"])


@router.get("")
def api_list_case_candidates(
    limit: int = Query(100, ge=1, le=500),
    status: str | None = None,
):
    items = list_case_candidates(limit=limit, status=status)
    return {
        "ok": True,
        "count": len(items),
        "items": items,
    }
