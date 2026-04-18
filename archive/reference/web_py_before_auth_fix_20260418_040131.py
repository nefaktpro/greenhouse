from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from interfaces.web_admin.security import get_current_user_from_request

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/web", tags=["web"])

def render(request: Request, template_name: str, page_title: str):
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={"request": request, "page_title": page_title},
    )

def is_auth(request: Request) -> bool:
    return bool(get_current_user_from_request(request))

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_auth(request):
        return RedirectResponse(url="/web/", status_code=302)
    return render(request, "login.html", "Greenhouse v17 — Login")

@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "dashboard.html", "Greenhouse v17 — Dashboard")

@router.get("/control", response_class=HTMLResponse)
def control_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "control.html", "Greenhouse v17 — Control")

@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "ask.html", "Greenhouse v17 — ASK")

@router.get("/modes", response_class=HTMLResponse)
def modes_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "modes.html", "Greenhouse v17 — Modes")

@router.get("/registry", response_class=HTMLResponse)
def registry_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "registry.html", "Greenhouse v17 — Registry")

@router.get("/monitoring", response_class=HTMLResponse)
def monitoring_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "monitoring.html", "Greenhouse v17 — Monitoring")

@router.get("/safety", response_class=HTMLResponse)
def safety_page(request: Request):
    if not is_auth(request):
        return RedirectResponse(url="/web/login", status_code=302)
    return render(request, "safety.html", "Greenhouse v17 — Safety")
