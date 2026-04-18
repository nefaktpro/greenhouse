from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


def render(request: Request, template_name: str, page_title: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "request": request,
            "page_title": page_title,
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html", "Greenhouse v17 — Login")


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return render(request, "dashboard.html", "Greenhouse v17 — Dashboard")


@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    return render(request, "ask.html", "Greenhouse v17 — ASK")


@router.get("/modes", response_class=HTMLResponse)
def modes_page(request: Request):
    return render(request, "modes.html", "Greenhouse v17 — Modes")


@router.get("/registry", response_class=HTMLResponse)
def registry_page(request: Request):
    return render(request, "registry.html", "Greenhouse v17 — Registry")


@router.get("/control", response_class=HTMLResponse)
def control_page(request: Request):
    return render(request, "control.html", "Greenhouse v17 — Control")

@web_router.get("/monitoring", response_class=HTMLResponse)
def monitoring_page(request: Request):
    return templates.TemplateResponse("monitoring.html", {"request": request})

@web_router.get("/safety", response_class=HTMLResponse)
def safety_page(request: Request):
    return templates.TemplateResponse("safety.html", {"request": request})

