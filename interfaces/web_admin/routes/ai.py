from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from greenhouse_v17.services.ai_chat_controller import handle_chat_message
from greenhouse_v17.services.ai_client import get_ai_connection_status, get_deepseek_connection_status, ask_ai_smoke_test
import os
import time

from ai.router import route_ai_message
from ai.context_resolver import get_context_catalog, read_context_file, save_context_file, list_backups, restore_backup
from chat.chat_router import handle_chat_message

router = APIRouter(tags=["ai-lab"])
templates = Jinja2Templates(directory="interfaces/web_admin/templates")


class AIMessageIn(BaseModel):
    text: str


class ContextFileSaveIn(BaseModel):
    path: str
    content: str


@router.get("/web/ai", response_class=HTMLResponse)
def ai_lab_page(request: Request):
    return templates.TemplateResponse(request, "ai_lab.html", {})


@router.post("/api/ai/message")
def ai_message(payload: AIMessageIn):
    # AI Lab preview only.
    # Важно: здесь НЕ вызываем handle_chat_message(),
    # потому что chat_router теперь может создавать ASK / выполнять action.
    ai_result = route_ai_message(payload.text)

    return {
        "ok": True,
        "input": payload.text,
        "ai_router": ai_result,
        "chat_response": {
            "preview_only": True,
            "note": "AI Lab does not create ASK until /api/ai/create-ask is called."
        },
    }


from greenhouse_v17.services.webadmin_execution_service import create_pending_ask, load_ask_state

@router.post("/api/ai/create-ask")
def create_ask_via_actions(payload: AIMessageIn):
    ai_result = route_ai_message(payload.text)
    proposed = ai_result.get("proposed_action")

    if not proposed:
        return {"ok": False, "error": "no_proposed_action"}

    action_key = proposed.get("action_key")
    if not action_key:
        return {"ok": False, "error": "no_action_key"}

    current = load_ask_state()
    if current.get("has_pending"):
        return {
            "ok": False,
            "error": "pending_ask_exists",
            "message": "Сначала подтвердите или отмените текущее ASK-действие.",
            "pending": current,
        }

    state = create_pending_ask(
        action_key=action_key,
        title=f"AI: {payload.text}",
        source="web_admin",
    )

    return {"ok": True, "pending": state}




@router.get("/web/ai/memory", response_class=HTMLResponse)
def ai_memory_page(request: Request):
    return templates.TemplateResponse(request, "ai_memory.html", {})

@router.get("/web/ai/chat", response_class=HTMLResponse)
def ai_chat_page(request: Request):
    return templates.TemplateResponse(request, "ai_chat.html", {})
@router.get("/web/ai/status", response_class=HTMLResponse)
def ai_status_page(request: Request):
    return templates.TemplateResponse(request, "ai_status.html", {})


@router.get("/web/ai/context", response_class=HTMLResponse)
def ai_context_page(request: Request):
    return templates.TemplateResponse(request, "ai_context.html", {})


@router.get("/api/ai/context/catalog")
def ai_context_catalog():
    return get_context_catalog()


@router.get("/api/ai/context/file")
def ai_context_file(path: str):
    return read_context_file(path)


@router.post("/api/ai/context/file/save")
def ai_context_file_save(payload: ContextFileSaveIn):
    return save_context_file(payload.path, payload.content)


@router.get("/api/ai/context/backups")
def ai_context_backups():
    return list_backups()


from pydantic import BaseModel
from greenhouse_v17.services.ai_chat_controller import handle_chat_message
from greenhouse_v17.services.ai_client import get_ai_connection_status, get_deepseek_connection_status, ask_ai_smoke_test
import os
import time

class RestoreIn(BaseModel):
    path: str


@router.post("/api/ai/context/restore")
def ai_context_restore(payload: RestoreIn):
    return restore_backup(payload.path)



def _check_ai_provider():
    provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
    primary_model = os.getenv("AI_PRIMARY_MODEL") or os.getenv("OPENAI_MODEL") or "not_configured"

    api_key = None
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
    elif provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
    else:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        return {
            "ok": False,
            "configured": False,
            "error": "no_api_key",
            "latency_ms": None,
            "models_count": None,
        }

    try:
        start = time.time()

        # OpenAI SDK v1 compatible ping. Для DeepSeek тоже может работать,
        # если переменные и base_url будут подключены позже.
        from openai import OpenAI

        if provider == "deepseek":
            client = OpenAI(
                api_key=api_key,
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
        else:
            client = OpenAI(api_key=api_key)

        models = client.models.list()
        latency = round((time.time() - start) * 1000)

        return {
            "ok": True,
            "configured": True,
            "error": None,
            "latency_ms": latency,
            "models_count": len(getattr(models, "data", []) or []),
        }
    except Exception as e:
        return {
            "ok": False,
            "configured": True,
            "error": str(e),
            "latency_ms": None,
            "models_count": None,
        }


@router.get("/api/ai/status")
def ai_status():
    provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
    return {
        "ok": True,
        "provider": provider,
        "primary_model": os.getenv("AI_PRIMARY_MODEL") or os.getenv("OPENAI_MODEL") or "not_configured",
        "backup_model": os.getenv("AI_BACKUP_MODEL") or os.getenv("DEEPSEEK_MODEL") or "deepseek_planned",
        "fallback_model": os.getenv("AI_FALLBACK_MODEL") or "local_planned",
        "vision_model": os.getenv("AI_VISION_MODEL") or os.getenv("OPENAI_VISION_MODEL") or "openai_vision_planned",
        "models": {
            "reasoning_primary": {
                "provider": os.getenv("AI_PROVIDER", "openai"),
                "model": os.getenv("AI_PRIMARY_MODEL") or os.getenv("OPENAI_MODEL") or "not_configured",
                "api_key_present": bool(os.getenv("OPENAI_API_KEY") or os.getenv("AI_API_KEY")),
            },
            "reasoning_backup": {
                "provider": "deepseek",
                "model": os.getenv("DEEPSEEK_MODEL") or "deepseek-v4-pro",
                "api_key_present": bool(os.getenv("DEEPSEEK_API_KEY")),
            },
            "vision_primary": {
                "provider": "openai",
                "model": os.getenv("AI_VISION_MODEL") or os.getenv("OPENAI_VISION_MODEL") or "gpt-4o",
                "api_key_present": bool(os.getenv("OPENAI_API_KEY")),
                "purpose": "camera/photo/plant visual analysis",
            },
            "local_fallback": {
                "provider": "local",
                "model": os.getenv("LOCAL_AI_MODEL") or "planned",
                "api_key_present": False,
                "purpose": "offline fallback, not implemented yet",
            },
        },
        "health": get_ai_connection_status(),
        "deepseek_health": get_deepseek_connection_status(),
        "capabilities": {
            "can_analyze_context": True,
            "uses_context_resolver": True,
            "can_generate_ask": True,
            "can_read_memory_via_core": True,
            "can_explain_decisions": True,

            "can_execute_directly": False,
            "can_access_ha_directly": False,
            "can_access_files_directly": False,
            "can_bypass_validation": False,
        },
        "policy": {
            "ai_direct_execution": False,
            "ai_direct_ha_access": False,
            "ai_direct_file_access": False,
            "resolver_required": True,
        },
        "status_note": "AI status page is wired. Real reasoning call is next step.",
    }


@router.get("/api/ai/health/full")
def ai_health_full():
    return get_ai_connection_status()


@router.post("/api/ai/smoke-test")
def ai_smoke_test():
    return ask_ai_smoke_test()


class AIChatRequest(BaseModel):
    message: str


@router.post("/api/ai/chat")
def ai_chat(req: AIChatRequest):
    return handle_chat_message(req.message)


from greenhouse_v17.services.context.context_service import build_context
from greenhouse_v17.services.ai_client import ask_ai_with_fallback

class AIChatV2Request(BaseModel):
    message: str


@router.post("/api/ai/chat2")
def ai_chat_v2(req: AIChatV2Request):
    return ask_ai_chat2(req.message)


class AIChatPromptSaveIn(BaseModel):
    text: str

@router.get("/api/ai/chat2/history")
def ai_chat2_history():
    return {"ok": True, "history": load_ai_chat2_history()}


@router.post("/api/ai/chat2/clear")
def ai_chat2_clear():
    return clear_ai_chat2_history()


@router.get("/api/ai/chat2/prompt")
def ai_chat2_prompt_get():
    return {"ok": True, "text": get_ai_chat_prompt()}


@router.post("/api/ai/chat2/prompt")
def ai_chat2_prompt_save(payload: AIChatPromptSaveIn):
    return save_ai_chat_prompt(payload.text)


from greenhouse_v17.services.ai_chat_memory import (
    ask_ai_chat_live,
    load_history as load_ai_chat_live_history,
    clear_history as clear_ai_chat_live_history,
    load_io_logs as load_ai_chat_io_logs,
    clear_io_logs as clear_ai_chat_io_logs,
)

class AIChatLiveRequest(BaseModel):
    message: str


@router.post("/api/ai/chat-live")
def ai_chat_live(payload: AIChatLiveRequest):
    return ask_ai_chat_live(payload.message)


@router.get("/api/ai/chat-live/history")
def ai_chat_live_history():
    return {"ok": True, "history": load_ai_chat_live_history()}


@router.post("/api/ai/chat-live/clear")
def ai_chat_live_clear():
    return clear_ai_chat_live_history()


@router.get("/api/ai/chat-live/logs")
def ai_chat_live_logs(limit: int = 80):
    return {"ok": True, "items": load_ai_chat_io_logs(limit)}


@router.post("/api/ai/chat-live/logs/clear")
def ai_chat_live_logs_clear():
    return clear_ai_chat_io_logs()
