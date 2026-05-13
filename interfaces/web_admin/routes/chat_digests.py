from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

from greenhouse_v17.services.chat_digest_service import (
    get_chat_digest_status,
    generate_chat_digest,
    read_chat_digest,
)

router = APIRouter()
templates = Jinja2Templates(directory="interfaces/web_admin/templates")


@router.get("/web/ai/digests", response_class=HTMLResponse)
def chat_digests_page(request: Request):
    return templates.TemplateResponse(request, "chat_digests.html", {})


@router.get("/api/ai/digests/status")
def chat_digest_status():
    return JSONResponse(get_chat_digest_status())


@router.post("/api/ai/digests/generate")
def chat_digest_generate(period: str = "today", limit: int = 300):
    return JSONResponse(generate_chat_digest(period=period, limit=limit))


@router.post("/api/ai/digests/read")
async def chat_digest_read(request: Request):
    payload = await request.json()
    return JSONResponse(read_chat_digest(payload.get("path")))
