from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    return templates.TemplateResponse("control.html", {"request": request})


@router.get("/control", response_class=HTMLResponse)
def control_page(request: Request):
    return templates.TemplateResponse("control.html", {"request": request})


@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    return templates.TemplateResponse("ask.html", {"request": request})


@router.get("/modes", response_class=HTMLResponse)
def modes_page(request: Request):
    return templates.TemplateResponse("modes.html", {"request": request})
