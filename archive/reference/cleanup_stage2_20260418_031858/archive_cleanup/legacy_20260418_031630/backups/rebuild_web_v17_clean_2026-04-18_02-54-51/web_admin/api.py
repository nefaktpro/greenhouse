from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from interfaces.web_admin.routes.actions import router as actions_router
from interfaces.web_admin.routes.ask import router as ask_router
from interfaces.web_admin.routes.auth import router as auth_router
from interfaces.web_admin.routes.modes import router as modes_router
from interfaces.web_admin.routes.monitoring import router as monitoring_router
from interfaces.web_admin.routes.registry import router as registry_router
from interfaces.web_admin.routes.web import router as web_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Greenhouse v17 Web Admin",
    version="1.0.0",
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "web_admin",
        "project": "greenhouse_v17",
    }

@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": "internal_error",
            "details": str(exc),
        },
    )

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(registry_router, prefix="/api/registry", tags=["registry"])
app.include_router(modes_router, prefix="/api/modes", tags=["modes"])
app.include_router(ask_router, prefix="/api/ask", tags=["ask"])
app.include_router(actions_router, prefix="/api/actions", tags=["actions"])
app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(web_router)
