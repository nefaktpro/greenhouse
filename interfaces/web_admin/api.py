from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from interfaces.web_admin.routes.actions import router as actions_router
from interfaces.web_admin.routes.ask import router as ask_router
from interfaces.web_admin.routes.auth import router as auth_router
from interfaces.web_admin.routes.modes import router as modes_router
from interfaces.web_admin.routes.registry import router as registry_router
from interfaces.web_admin.routes.web import router as web_router
from interfaces.web_admin.routes.control_debug import router as control_debug_router
from interfaces.web_admin.routes.monitoring import router as router_monitoring
from interfaces.web_admin.routes.live_states import router as live_states_router
from interfaces.web_admin.routes.lab import router as lab_router
from interfaces.web_admin.routes.ai import router as ai_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Greenhouse v17 Web Admin",
    version="0.4.0",
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


app.include_router(ai_router)
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(registry_router, prefix="/api/registry", tags=["registry"])
app.include_router(modes_router, prefix="/api/modes", tags=["modes"])
app.include_router(ask_router, prefix="/api/ask", tags=["ask"])
app.include_router(actions_router, prefix="/api/actions", tags=["actions"])
app.include_router(web_router, prefix="/web", tags=["web"])
app.include_router(router_monitoring)

app.include_router(web_router)
app.include_router(actions_router)
app.include_router(ask_router)
app.include_router(modes_router)
app.include_router(live_states_router)
app.include_router(lab_router)
app.include_router(control_debug_router, tags=["control_debug"])

from interfaces.web_admin.routes import ai_timers
app.include_router(ai_timers.router)
