from __future__ import annotations

from fastapi import APIRouter

from greenhouse_v17.services.automation_service import automation_summary, run_due_all

router = APIRouter(prefix="/api/automation", tags=["automation"])


@router.get("")
def api_automation_summary():
    return automation_summary()


@router.post("/run-due-all")
def api_run_due_all(dry_run_rules: bool = False):
    return run_due_all(dry_run_rules=dry_run_rules)
