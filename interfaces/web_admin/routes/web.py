from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/web", tags=["web"])

def render(request: Request, template_name: str, page_title: str):
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={"request": request, "page_title": page_title},
    )

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html", "Greenhouse v17 — Login")

@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return render(request, "dashboard.html", "Greenhouse v17 — Dashboard")

@router.get("/control", response_class=HTMLResponse)
def control_page(request: Request):
    return render(request, "control.html", "Greenhouse v17 — Control")

@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    return render(request, "ask.html", "Greenhouse v17 — ASK")

@router.get("/modes", response_class=HTMLResponse)
def modes_page(request: Request):
    return render(request, "modes.html", "Greenhouse v17 — Modes")

@router.get("/registry", response_class=HTMLResponse)
def registry_page(request: Request):
    return render(request, "registry.html", "Greenhouse v17 — Registry")

@router.get("/monitoring", response_class=HTMLResponse)
def monitoring_page(request: Request):
    return render(request, "monitoring.html", "Greenhouse v17 — Monitoring")

@router.get("/safety", response_class=HTMLResponse)
def safety_page(request: Request):
    return render(request, "safety.html", "Greenhouse v17 — Safety")



# Legacy TEST URLs -> LAB URLs, чтобы старые ссылки не ломались
@router.get("/test/devices")
def legacy_test_devices():
    return RedirectResponse(url="/web/lab/devices", status_code=307)

@router.get("/test/thermostat")
def legacy_test_thermostat():
    return RedirectResponse(url="/web/lab/thermostat", status_code=307)

@router.get("/test/humidifier")
def legacy_test_humidifier():
    return RedirectResponse(url="/web/lab/humidifier", status_code=307)

@router.get("/test/sensor24")
def legacy_test_sensor24():
    return RedirectResponse(url="/web/lab/sensor24", status_code=307)

@router.get("/lab/devices", response_class=HTMLResponse)
def test_devices_page(request: Request):
    return render(request, "lab_devices.html", "Greenhouse v17 — Lab Devices")


@router.get("/lab/thermostat", response_class=HTMLResponse)
def test_thermostat_page(request: Request):
    return render(request, "lab_thermostat.html", "Greenhouse v17 — Lab Thermostat")


@router.get("/lab/humidifier", response_class=HTMLResponse)
def test_humidifier_page(request: Request):
    return render(request, "lab_humidifier.html", "Greenhouse v17 — Lab Humidifier")


@router.get("/lab/sensor24", response_class=HTMLResponse)
def test_sensor24_page(request: Request):
    return render(request, "lab_sensor24.html", "Greenhouse v17 — Lab Sensor24")


@router.get("/rules", response_class=HTMLResponse)
def web_rules(request: Request):
    return render(request, "rules.html", "Greenhouse v17 — Rules")


@router.get("/web/observations")
def observations_page(request: Request):
    return templates.TemplateResponse("observations.html", {"request": request})


@router.get("/observations", response_class=HTMLResponse)
def observations_page(request: Request):
    return render(request, "observations.html", "Greenhouse v17 — Observations")



@router.get("/cases", response_class=HTMLResponse)
def cases_page(request: Request):
    return render(request, "cases.html", "Greenhouse v17 — Cases")


@router.get("/devices", response_class=HTMLResponse)
def devices_page(request: Request):
    return render(request, "devices.html", "Greenhouse v17 — Devices")


@router.get("/passports", response_class=HTMLResponse)
def passports_page(request: Request):
    return render(request, "passports.html", "Greenhouse v17 — Device Passports")


@router.get("/device/{logical_role}", response_class=HTMLResponse)
def device_center_page(request: Request, logical_role: str):
    return render(request, "device_center.html", "Greenhouse v17 — Device Center")
