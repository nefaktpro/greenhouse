from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/web", tags=["web"])


def render(request: Request, name: str, **extra):
    ctx = {"request": request, **extra}
    return templates.TemplateResponse(request=request, name=name, context=ctx)


@router.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    # Временный безопасный root: ведём на уже существующий control
    return render(request, "control.html")


@router.get("/control", response_class=HTMLResponse)
def control_page(request: Request):
    # Новый control — как ДОП. экран, а не замена сайта
    return render(request, "control.html")


@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    return render(request, "ask.html")


@router.get("/modes", response_class=HTMLResponse)
def modes_page(request: Request):
    return render(request, "modes.html")


@router.get("/registry", response_class=HTMLResponse)
def registry_page(request: Request):
    return render(request, "registry.html")


@router.get("/monitoring", response_class=HTMLResponse)
def monitoring_page(request: Request):
    return render(request, "monitoring.html")


@router.get("/safety", response_class=HTMLResponse)
def safety_page(request: Request):
    return render(request, "safety.html")
