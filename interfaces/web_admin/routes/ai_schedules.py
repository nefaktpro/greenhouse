from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from greenhouse_v17.services.ai_schedule_service import (
    create_ai_schedule,
    list_ai_schedules,
    read_schedule_log,
    run_due_schedules_once,
    set_ai_schedule_enabled,
    delete_ai_schedule,
    start_schedule_worker,
)

router = APIRouter()
templates = Jinja2Templates(directory="interfaces/web_admin/templates")

start_schedule_worker()


class ScheduleCreatePayload(BaseModel):
    action_key: str
    time: str
    days: list[str] = []
    source_text: str | None = None
    enabled: bool = True


class ScheduleTogglePayload(BaseModel):
    enabled: bool


@router.get("/web/ai/schedules", response_class=HTMLResponse)
def web_ai_schedules(request: Request):
    return templates.TemplateResponse(
        request,
        "ai_schedules.html",
        {"page_title": "AI Schedules"}
    )


@router.get("/api/ai/schedules")
def api_ai_schedules():
    return {"ok": True, "items": list_ai_schedules()}


@router.post("/api/ai/schedules/create")
def api_ai_schedules_create(payload: ScheduleCreatePayload):
    return create_ai_schedule(
        action_key=payload.action_key,
        time_hhmm=payload.time,
        days=payload.days,
        source_text=payload.source_text,
        enabled=payload.enabled,
    )


@router.post("/api/ai/schedules/{schedule_id}/enabled")
def api_ai_schedules_enabled(schedule_id: str, payload: ScheduleTogglePayload):
    return set_ai_schedule_enabled(schedule_id, payload.enabled)


@router.post("/api/ai/schedules/run-due")
def api_ai_schedules_run_due():
    return run_due_schedules_once()


@router.get("/api/ai/schedules/log")
def api_ai_schedules_log():
    return {"ok": True, "items": read_schedule_log()}



@router.post("/api/ai/schedules/{schedule_id}/delete")
def api_ai_schedules_delete(schedule_id: str):
    return delete_ai_schedule(schedule_id)
