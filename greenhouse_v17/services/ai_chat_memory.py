import json
import time
from pathlib import Path
from typing import Any, Dict, List

from greenhouse_v17.services.ai_client import ask_ai_with_fallback

PROMPT_PATH = Path("/home/mi/greenhouse_v17/data/memory/ai_chat_system_prompt.md")
HISTORY_PATH = Path("/home/mi/greenhouse_v17/data/runtime/ai_chat_live_history.json")
LOG_PATH = Path("/home/mi/greenhouse_v17/data/memory/ai_chat_io_log.jsonl")


DEFAULT_PROMPT = """Ты AI-чат системы GREENHOUSE v17.

Роль:
- обычный разговорный чат с пользователем
- можешь обсуждать систему, идеи, файлы, архитектуру, состояние и контекст
- НЕ выполняешь действия напрямую
- команды управления устройствами находятся в AI Lab и идут через pipeline
- отвечай по-русски, спокойно, коротко и понятно

В запрос тебе передаются:
- CURRENT_CONTEXT
- RECENT_DIALOG_HISTORY
- USER_MESSAGE
"""


def _ensure():
    PROMPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not PROMPT_PATH.exists():
        PROMPT_PATH.write_text(DEFAULT_PROMPT, encoding="utf-8")
    if not HISTORY_PATH.exists():
        HISTORY_PATH.write_text("[]", encoding="utf-8")
    if not LOG_PATH.exists():
        LOG_PATH.write_text("", encoding="utf-8")


def _safe_catalog_summary() -> Dict[str, Any]:
    try:
        from ai.context_resolver import get_context_catalog
        catalog = get_context_catalog()
        out = []
        for ctx in catalog.get("contexts", []):
            files = []
            for f in ctx.get("files", []):
                files.append({
                    "path": f.get("path"),
                    "title": f.get("title"),
                    "purpose": f.get("purpose"),
                    "edit": f.get("edit"),
                    "ai_watch": f.get("ai_watch", False),
                    "ai_watch_hint": f.get("ai_watch_hint"),
                    "exists": f.get("exists"),
                })
            out.append({
                "key": ctx.get("key"),
                "title": ctx.get("title"),
                "description": ctx.get("description"),
                "files": files,
            })
        return {"contexts": out}
    except Exception as e:
        return {"error": str(e), "contexts": []}


def _safe_context() -> Dict[str, Any]:
    try:
        from greenhouse_v17.services.context.context_service import build_context
        return build_context()
    except Exception as e:
        return {
            "runtime": {"mode": "UNKNOWN"},
            "available_contexts": [],
            "context_error": str(e),
        }


def get_prompt() -> str:
    _ensure()
    return PROMPT_PATH.read_text(encoding="utf-8")


def load_history() -> List[Dict[str, Any]]:
    _ensure()
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(history: List[Dict[str, Any]]) -> None:
    _ensure()
    HISTORY_PATH.write_text(
        json.dumps(history[-60:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_history() -> Dict[str, Any]:
    save_history([])
    return {"ok": True, "history": []}


def append_io_log(entry: Dict[str, Any]) -> None:
    _ensure()
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_io_logs(limit: int = 80) -> List[Dict[str, Any]]:
    _ensure()
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out



def ask_ai_chat_live(message: str) -> Dict[str, Any]:
    _ensure()

    # --- STEP 1: try control layer first ---
    try:
        from greenhouse_v17.services.ai_chat_controller import handle_chat_message
        control = handle_chat_message(message)

        if control:
            return {
                "ok": True,
                "kind": "control",
                "answer": control.get("message"),
                "control": control,
                "history": load_history(),
            }
    except Exception as e:
        print("AI control layer error:", e)

    # --- STEP 2: fallback to LLM ---

def ask_ai_chat_live(message: str) -> Dict[str, Any]:
    _ensure()

    history = load_history()
    context = _safe_context()
    history_sent = history[-12:]
    system_prompt = get_prompt()

    prompt = f"""{system_prompt}

CURRENT_CONTEXT:
{json.dumps(context, ensure_ascii=False, indent=2)}

RECENT_DIALOG_HISTORY:
{json.dumps(history_sent, ensure_ascii=False, indent=2)}

AVAILABLE_CONTEXT_CATALOG:
{json.dumps(_safe_catalog_summary(), ensure_ascii=False, indent=2)}

USER_MESSAGE:
{message}
"""

    started = time.time()

    try:
        ai = ask_ai_with_fallback(prompt)
        answer = ai.get("answer") or "AI не вернул ответ."
        ok = bool(ai.get("ok", True))
        error = ai.get("error")
    except Exception as e:
        ai = {}
        answer = f"Ошибка AI: {e}"
        ok = False
        error = str(e)

    history.append({"role": "user", "content": message, "ts": time.time()})
    history.append({"role": "assistant", "content": answer, "ts": time.time()})
    save_history(history)

    entry = {
        "ts": time.time(),
        "duration_ms": round((time.time() - started) * 1000),
        "user_message": message,
        "system_prompt_path": str(PROMPT_PATH),
        "context_sent": context,
        "history_sent": history_sent,
        "prompt_sent": prompt,
        "answer": answer,
        "provider": ai.get("provider"),
        "model": ai.get("model"),
        "latency_ms": ai.get("latency_ms"),
        "fallback_used": ai.get("fallback_used"),
        "ok": ok,
        "error": error,
        "primary_error": ai.get("primary_error"),
    }
    append_io_log(entry)

    return {
        "ok": ok,
        "kind": "ai_chat_live",
        "answer": answer,
        "provider": ai.get("provider"),
        "latency_ms": ai.get("latency_ms"),
        "context": context,
        "history": load_history(),
        "error": error,
    }


def clear_io_logs() -> Dict[str, Any]:
    _ensure()
    LOG_PATH.write_text("", encoding="utf-8")
    return {"ok": True, "message": "AI IO log cleared"}

# --- REQUEST_CONTEXT protocol v1 ---
def _extract_requested_paths(text: str):
    import re
    paths = []
    for m in re.finditer(r"path:\s*([^\n\r]+)", text or "", re.IGNORECASE):
        p = m.group(1).strip().strip("`'\" ")
        if p and p not in paths:
            paths.append(p)
    return paths[:3]


def _load_requested_context(paths):
    from ai.context_resolver import read_context_file
    out = []
    for path in paths:
        try:
            data = read_context_file(path)
            content = data.get("content")
            if content and len(content) > 12000:
                content = content[:12000] + "\n\n...[TRUNCATED]"
            out.append({
                "path": path,
                "ok": bool(data.get("ok")),
                "content": content,
                "meta": data.get("meta"),
                "error": data.get("error"),
            })
        except Exception as e:
            out.append({"path": path, "ok": False, "error": str(e)})
    return out


_original_ask_ai_chat_live_request_context = ask_ai_chat_live

def ask_ai_chat_live(message: str):
    first = _original_ask_ai_chat_live_request_context(message)
    answer = first.get("answer") or ""
    paths = _extract_requested_paths(answer)

    if not paths:
        return first

    requested = _load_requested_context(paths)

    followup_message = f"""Пользователь спросил:
{message}

Ты запросил дополнительный контекст:
{json.dumps(requested, ensure_ascii=False, indent=2)}

Теперь дай финальный ответ пользователю.
Не повторяй REQUEST_CONTEXT, если данных хватает.
"""

    second = _original_ask_ai_chat_live_request_context(followup_message)
    second["requested_context"] = requested
    second["request_context_used"] = True
    return second
