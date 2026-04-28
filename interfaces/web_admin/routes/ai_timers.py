from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from greenhouse_v17.services.webadmin_execution_service import list_ai_timers, cancel_ai_timer

router = APIRouter()
templates = Jinja2Templates(directory="interfaces/web_admin/templates")


@router.get("/api/ai/timers")
def api_ai_timers():
    return {"ok": True, "items": list_ai_timers()}


@router.get("/web/ai/timers", response_class=HTMLResponse)
def web_ai_timers(request: Request):
    # Важно: новый Starlette/FastAPI безопаснее вызывать с request первым
    return templates.TemplateResponse(
        request,
        "ai_timers.html",
        {"page_title": "AI Timers"}
    )


@router.post("/api/ai/timers/cancel/{timer_id}")
def api_ai_timer_cancel(timer_id: str):
    return cancel_ai_timer(timer_id)
