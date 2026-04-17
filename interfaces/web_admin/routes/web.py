from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "page_title": "Greenhouse v17 — Login",
        },
    )


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "page_title": "Greenhouse v17 — Dashboard",
        },
    )


@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    return templates.TemplateResponse(
        "ask.html",
        {
            "request": request,
            "page_title": "Greenhouse v17 — ASK",
        },
    )


@router.get("/modes", response_class=HTMLResponse)
def modes_page(request: Request):
    return templates.TemplateResponse(
        "modes.html",
        {
            "request": request,
            "page_title": "Greenhouse v17 — Modes",
        },
    )


@router.get("/registry", response_class=HTMLResponse)
def registry_page(request: Request):
    return templates.TemplateResponse(
        "registry.html",
        {
            "request": request,
            "page_title": "Greenhouse v17 — Registry",
        },
    )
