from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from interfaces.web_admin.routes.web import render

router = APIRouter()

@router.get("/web/automation", response_class=HTMLResponse)
def web_automation(request: Request):
    return render(request, "web/automation.html", "Greenhouse v17 — Automation")
