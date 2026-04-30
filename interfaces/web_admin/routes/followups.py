from __future__ import annotations

from fastapi import APIRouter

from greenhouse_v17.services.followup_service import (
    complete_followup,
    list_followups,
    read_followup_log,
    run_due_followups_once,
)

router = APIRouter(prefix="/api/followups", tags=["followups"])


@router.get("")
def api_list_followups(status: str | None = None):
    return {"ok": True, "items": list_followups(status=status)}


@router.post("/run-due")
def api_run_due_followups():
    return run_due_followups_once()


@router.post("/{followup_id}/complete")
def api_complete_followup(followup_id: str):
    return {"ok": complete_followup(followup_id, status="completed")}


@router.post("/{followup_id}/skip")
def api_skip_followup(followup_id: str):
    return {"ok": complete_followup(followup_id, status="skipped")}


@router.get("/logs")
def api_followup_logs(limit: int = 100):
    return {"ok": True, "items": read_followup_log(limit=limit)}
