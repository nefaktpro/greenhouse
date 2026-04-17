from fastapi import FastAPI
from fastapi.responses import JSONResponse

from interfaces.web_admin.routes.auth import router as auth_router
from interfaces.web_admin.routes.registry import router as registry_router
from interfaces.web_admin.routes.modes import router as modes_router
from interfaces.web_admin.routes.ask import router as ask_router

app = FastAPI(
    title="Greenhouse v17 Web Admin",
    version="0.2.0",
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
