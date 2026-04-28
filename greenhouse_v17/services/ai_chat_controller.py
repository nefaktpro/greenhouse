import json
import re
from typing import Any, Dict, Optional

import requests

from greenhouse_v17.services.webadmin_execution_service import (
    create_pending_ask,
    load_ask_state,
    cancel_pending_ask,
)

FAN_ACTIONS = {
    ("top", "on"): "fan_top_on",
    ("top", "off"): "fan_top_off",
    ("bottom", "on"): "fan_bottom_on",
    ("bottom", "off"): "fan_bottom_off",
}

FOLLOWUP_ACTIONS = {
    "fan_top_on": "fan_top_off",
    "fan_bottom_on": "fan_bottom_off",
    "fan_low_on": "fan_low_off",
}


def _parse_duration_seconds(text: str) -> tuple[Optional[int], Optional[str]]:
    """
    Parses ONLY explicit action duration:
    - на 5 секунд
    - на 10 минут
    Does NOT treat "через 10 сек" as duration.
    """
    t = text.lower()

    m = re.search(r"\bна\s+(\d+)\s*(секунд[уы]?|сек|s|минут[уы]?|мин|m|час[аов]?|ч|h)\b", t)
    if not m:
        return None, None

    value = int(m.group(1))
    unit = m.group(2)

    if unit.startswith(("сек", "s")):
        return value, f"{value} сек"
    if unit.startswith(("мин", "m")):
        return value * 60, f"{value} мин"
    if unit.startswith(("час", "ч", "h")):
        return value * 3600, f"{value} ч"

    return None, None


def _parse_delay_seconds(text: str):
    """
    Parses delayed start phrases:
    - через 10 минут
    - через 30 сек
    - через 1 час
    """
    t = text.lower()
    m = re.search(r"(?:через|спустя)\s+(\d+)\s*(секунд|секунды|сек|s|минут|минуты|мин|m|часов|часа|час|ч|h)", t)
    if not m:
        return None, None

    value = int(m.group(1))
    unit = m.group(2)

    if unit.startswith(("сек", "s")):
        return value, f"через {value} сек"
    if unit.startswith(("мин", "m")):
        return value * 60, f"через {value} мин"
    if unit.startswith(("час", "ч", "h")):
        return value * 3600, f"через {value} ч"

    return None, None


def _detect_fan_command(text: str) -> Optional[Dict[str, Any]]:
    t = text.lower().strip()

    if not any(w in t for w in ["вент", "вентил", "fan"]):
        return None

    zone = None
    if any(w in t for w in ["верх", "top", "верхний"]):
        zone = "top"
    elif any(w in t for w in ["низ", "ниж", "bottom", "low"]):
        zone = "bottom"

    op = None
    if any(w in t for w in ["включ", "вкл", "запусти", "on", "вруби"]):
        op = "on"
    elif any(w in t for w in ["выключ", "выкл", "отключ", "off", "останов"]):
        op = "off"

    if not zone or not op:
        return {
            "kind": "need_clarification",
            "message": "Понял, что речь про вентилятор, но не хватает зоны или действия. Например: включи верхний вентилятор на 10 минут.",
        }

    action_key = FAN_ACTIONS.get((zone, op))
    if not action_key:
        return None

    duration_seconds, duration_text = _parse_duration_seconds(text)
    delay_seconds, delay_text = _parse_delay_seconds(text)

    # If phrase is only delayed start ("через 10 сек"), do NOT treat it as duration.
    # Duration should be explicit, usually "на 10 сек".
    if delay_seconds and not re.search(r"\bна\s+\d+", text.lower()):
        duration_seconds = None
        duration_text = None

    followup_action_key = FOLLOWUP_ACTIONS.get(action_key) if duration_seconds and op == "on" else None

    zone_ru = "верх" if zone == "top" else "низ"
    op_ru = "включить" if op == "on" else "выключить"

    lines = [
        "Я понял команду так:",
        "",
        f"• Устройство: вентилятор",
        f"• Зона: {zone_ru}",
        f"• Действие: {op_ru}",
        f"• action_key: {action_key}",
    ]

    if delay_seconds:
        lines.append(f"• Запуск: {delay_text}")

    if duration_seconds:
        lines.append(f"• Таймер: {duration_text}")
        if followup_action_key:
            lines.append(f"• После таймера: {followup_action_key}")
            lines.append("")

    lines.append("")
    lines.append("Создаю ASK на подтверждение.")

    return {
        "kind": "control_candidate",
        "object": "fan",
        "zone": zone,
        "operation": op,
        "action_key": action_key,
        "duration_seconds": duration_seconds,
        "duration_text": duration_text,
        "delay_seconds": delay_seconds,
        "delay_text": delay_text,
        "followup_action_key": followup_action_key,
        "confidence": 0.95,
        "requires_confirmation": True,
        "message": "\n".join(lines),
    }



def _llm_control_candidate(text: str) -> Optional[Dict[str, Any]]:
    """
    LLM fallback: если локальный parser не понял фразу, просим модель вернуть JSON-кандидат.
    ВАЖНО: LLM всё равно НЕ исполняет действие. Только предлагает action_key для ASK.
    """
    try:
        import json
        import re
        from greenhouse_v17.services.ai_client import ask_ai_with_fallback

        allowed = {
            "fan_top_on": {"followup": "fan_top_off", "label": "верхний вентилятор включить"},
            "fan_top_off": {"followup": None, "label": "верхний вентилятор выключить"},
            "fan_bottom_on": {"followup": "fan_bottom_off", "label": "нижний вентилятор включить"},
            "fan_bottom_off": {"followup": None, "label": "нижний вентилятор выключить"},
            "fan_low_on": {"followup": "fan_low_off", "label": "нижний вентилятор включить"},
            "fan_low_off": {"followup": None, "label": "нижний вентилятор выключить"},
        }

        prompt = f"""
Ты AI Router GREENHOUSE v17.

Задача: понять, является ли сообщение пользователя командой управления вентилятором.
AI НЕ выполняет действие. AI только формирует ASK-кандидат.

Разрешённые action_key:
{json.dumps(allowed, ensure_ascii=False, indent=2)}

Верни СТРОГО JSON без markdown.

Формат, если команда понятна:
{{
  "kind": "control_candidate",
  "action_key": "fan_top_on",
  "duration_seconds": 10,
  "duration_text": "10 сек",
  "confidence": 0.0
}}

Если команды нет или неясно:
{{
  "kind": "not_control",
  "reason": "..."
}}

Сообщение пользователя:
{text}
"""
        ai = ask_ai_with_fallback(prompt)
        raw = ai.get("answer") or ""

        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return None

        data = json.loads(m.group(0))
        if data.get("kind") != "control_candidate":
            return None

        action_key = data.get("action_key")
        if action_key not in allowed:
            return None

        duration_seconds = data.get("duration_seconds")
        try:
            duration_seconds = int(duration_seconds) if duration_seconds else None
        except Exception:
            duration_seconds = None

        duration_text = data.get("duration_text")

        delay_seconds = data.get("delay_seconds")
        try:
            delay_seconds = int(delay_seconds) if delay_seconds else None
        except Exception:
            delay_seconds = None

        delay_text = data.get("delay_text") or (f"через {delay_seconds} сек" if delay_seconds else None)
        followup_action_key = allowed[action_key].get("followup") if duration_seconds and action_key.endswith("_on") else None

        zone = "top" if "top" in action_key else "bottom"
        op = "on" if action_key.endswith("_on") else "off"

        zone_ru = "верх" if zone == "top" else "низ"
        op_ru = "включить" if op == "on" else "выключить"

        lines = [
            "AI понял команду так:",
            "",
            f"• Устройство: вентилятор",
            f"• Зона: {zone_ru}",
            f"• Действие: {op_ru}",
            f"• action_key: {action_key}",
        ]

        if delay_seconds:
            lines.append(f"• Запуск: {delay_text}")

        if duration_seconds:
            lines.append(f"• Таймер: {duration_text or str(duration_seconds) + ' сек'}")
            if followup_action_key:
                lines.append(f"• После таймера: {followup_action_key}")

        lines.append("")
        lines.append("Создаю ASK на подтверждение.")

        return {
            "kind": "control_candidate",
            "object": "fan",
            "zone": zone,
            "operation": op,
            "action_key": action_key,
            "duration_seconds": duration_seconds,
            "duration_text": duration_text or (f"{duration_seconds} сек" if duration_seconds else None),
            "delay_seconds": delay_seconds,
            "delay_text": delay_text,
            "followup_action_key": followup_action_key,
            "confidence": data.get("confidence", 0.75),
            "requires_confirmation": True,
            "message": "\n".join(lines),
            "parser": "llm",
        }

    except Exception as e:
        return None


def _create_web_ask(candidate: Dict[str, Any], source_text: str) -> Dict[str, Any]:
    current = load_ask_state()
    if current.get("has_pending"):
        return {
            "ok": False,
            "kind": "pending_ask_exists",
            "message": "Сначала подтвердите или отмените текущее ASK-действие.",
            "pending": current,
        }

    action_key = candidate["action_key"]
    meta = {
        "source_text": source_text,
        "ai_candidate": candidate,
        "duration_seconds": candidate.get("duration_seconds"),
        "duration_text": candidate.get("duration_text"),
        "delay_seconds": candidate.get("delay_seconds"),
        "delay_text": candidate.get("delay_text"),
        "followup_action_key": candidate.get("followup_action_key"),
        "requires_timer": bool(
            candidate.get("delay_seconds")
            or (candidate.get("duration_seconds") and candidate.get("followup_action_key"))
        ),
    }

    state = create_pending_ask(
        action_key=action_key,
        title=f"AI ASK: {source_text}",
        source="ai_chat",
        meta=meta,
    )

    return {
            "ok": True,
            "kind": "ask_created",
            "source": "local_parser",
        "action_key": action_key,
        "pending": state,
        "message": candidate["message"],
    }


def confirm_pending() -> Dict[str, Any]:
    current = load_ask_state()
    if not current.get("has_pending"):
        return {"ok": False, "kind": "no_pending", "message": "Нет pending ASK для подтверждения."}

    try:
        r = requests.post("http://127.0.0.1:8081/api/ask/confirm", timeout=45)
        try:
            result = r.json()
        except Exception:
            result = {"status_code": r.status_code, "text": r.text}

        return {
            "ok": r.ok,
            "kind": "confirmed",
            "result": result,
            "message": "ASK подтверждён через общий Web/Admin ASK pipeline.",
        }
    except Exception as e:
        return {"ok": False, "kind": "ask_confirm_error", "error": str(e)}



def _load_ai_chat_history_tail(limit: int = 12) -> list[dict]:
    try:
        from pathlib import Path
        import json
        hp = Path("data/runtime/ai_chat_live_history.json")
        if not hp.exists():
            return []
        data = json.loads(hp.read_text(encoding="utf-8") or "[]")
        if isinstance(data, list):
            return data[-limit:]
    except Exception:
        pass
    return []


def _parse_request_context(text: str) -> list[dict]:
    """
    Парсит REQUEST_CONTEXT из ответа AI.
    Поддерживает формат:
    REQUEST_CONTEXT:
    - path: data/registry/devices.csv
    - reason: ...
    """
    import re

    if not text or "REQUEST_CONTEXT" not in text:
        return []

    items = []
    current = {}

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        m_path = re.match(r"^-?\s*path\s*:\s*(.+?)\s*$", line, re.I)
        if m_path:
            if current.get("path"):
                items.append(current)
                current = {}
            current["path"] = m_path.group(1).strip().strip("`'\"")
            continue

        m_reason = re.match(r"^-?\s*reason\s*:\s*(.+?)\s*$", line, re.I)
        if m_reason:
            current["reason"] = m_reason.group(1).strip()
            continue

    if current.get("path"):
        items.append(current)

    return items


def _allowed_context_paths() -> set[str]:
    try:
        from ai.context_resolver import get_context_catalog
        catalog = get_context_catalog()
        paths = set()
        for ctx in catalog.get("contexts", []):
            for f in ctx.get("files", []):
                path = f.get("path")
                if path and f.get("ai_requestable"):
                    paths.add(path)
        return paths
    except Exception:
        return set()


def _read_requested_contexts(requests: list[dict]) -> list[dict]:
    from ai.context_resolver import read_context_file

    allowed = _allowed_context_paths()
    results = []

    for req in requests[:5]:
        path = (req.get("path") or "").strip()
        if not path:
            continue

        if allowed and path not in allowed:
            results.append({
                "path": path,
                "ok": False,
                "error": "file_not_allowed_by_context_catalog",
                "reason": req.get("reason"),
            })
            continue

        data = read_context_file(path)

        # ограничиваем кусок, чтобы не разнести prompt огромным файлом
        if data.get("ok") and isinstance(data.get("content"), str):
            content = data["content"]
            data["content"] = content[:60000]
            data["truncated_for_ai"] = len(content) > 60000

        data["reason"] = req.get("reason")
        results.append(data)

    return results


def _answer_with_requested_context(user_text: str, first_answer: str, requests: list[dict]) -> dict:
    import json
    from pathlib import Path
    from greenhouse_v17.services.ai_client import ask_ai_with_fallback
    from ai.context_resolver import get_context_catalog

    prompt_path = Path("data/memory/ai_chat_system_prompt.md")
    system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    history_tail = _load_ai_chat_history_tail()
    catalog = get_context_catalog()
    context_results = _read_requested_contexts(requests)

    prompt = f"""
{system_prompt}

Ты уже запросил дополнительный контекст через REQUEST_CONTEXT.
Backend прочитал разрешённые файлы через Context Resolver.

ВАЖНО:
- Если данных хватает — дай финальный ответ пользователю.
- НЕ повторяй REQUEST_CONTEXT.
- Не говори, что не можешь читать файлы, если content ниже есть.
- Если файл большой — используй первые строки/структуру и честно скажи, если данных мало.

RECENT_DIALOG_HISTORY:
{json.dumps(history_tail, ensure_ascii=False, indent=2)}

USER_MESSAGE:
{user_text}

FIRST_AI_ANSWER:
{first_answer}

RESOLVED_CONTEXT:
{json.dumps(context_results, ensure_ascii=False, indent=2)}

AVAILABLE_CONTEXT_CATALOG:
{json.dumps(catalog, ensure_ascii=False, indent=2)[:12000]}
"""

    ai = ask_ai_with_fallback(prompt)
    return {
        "ok": True,
        "kind": "ai_answer_with_context",
            "source": "llm+context",
        "message": ai.get("answer") or "AI не вернул ответ после получения контекста.",
        "ai": ai,
        "requested_context": requests,
        "resolved_context_meta": [
            {
                "path": x.get("meta", {}).get("path") or x.get("path"),
                "ok": x.get("ok"),
                "error": x.get("error"),
                "truncated": x.get("truncated") or x.get("truncated_for_ai"),
                "size_bytes": x.get("meta", {}).get("size_bytes"),
            }
            for x in context_results
        ],
    }


def _find_last_request_context_from_history() -> tuple[str, list[dict]]:
    history = _load_ai_chat_history_tail(20)
    for item in reversed(history):
        if item.get("role") == "assistant":
            content = item.get("content") or ""
            reqs = _parse_request_context(content)
            if reqs:
                return content, reqs
    return "", []



def handle_chat_message(text: str) -> Dict[str, Any]:
    t = text.strip().lower()

    # Подтверждение последнего REQUEST_CONTEXT: "давай", "покажи", "запроси"
    # Не трогаем "ок/да", потому что они используются для ASK confirm.
    if t in ["давай", "покажи", "запроси", "можно", "получай", "загрузи"]:
        prev_answer, reqs = _find_last_request_context_from_history()
        if reqs:
            return _answer_with_requested_context(text, prev_answer, reqs)

    if t in ["ок", "ok", "да", "yes", "подтверждаю"]:
        return confirm_pending()

    if t in ["нет", "no", "отмена", "cancel"]:
        result = cancel_pending_ask()
        return {"ok": True, "kind": "cancelled", "message": "Ок, отменил pending ASK.", "result": result}

    candidate = _detect_fan_command(text)
    if candidate:
        if candidate["kind"] == "control_candidate":
            return _create_web_ask(candidate, text)
        return {"ok": True, **candidate}

    llm_candidate = _llm_control_candidate(text)
    if llm_candidate:
        return _create_web_ask(llm_candidate, text)

    # AI chat без управления: обычный разговор, но с system prompt + catalog
    try:
        import json
        from pathlib import Path
        from greenhouse_v17.services.ai_client import ask_ai_with_fallback
        from ai.context_resolver import get_context_catalog

        prompt_path = Path("data/memory/ai_chat_system_prompt.md")
        system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

        catalog = get_context_catalog()

        history_tail = _load_ai_chat_history_tail()

        prompt = f"""
{system_prompt}

CURRENT_CONTEXT:
{{}}

RECENT_DIALOG_HISTORY:
{json.dumps(history_tail, ensure_ascii=False, indent=2)}

AVAILABLE_CONTEXT_CATALOG:
{json.dumps(catalog, ensure_ascii=False, indent=2)[:30000]}

USER_MESSAGE:
{text}
"""

        ai = ask_ai_with_fallback(prompt)
        first_answer = ai.get("answer") or "AI не вернул ответ."

        reqs = _parse_request_context(first_answer)
        if reqs:
            return _answer_with_requested_context(text, first_answer, reqs)

        return {
            "ok": True,
            "kind": "ai_answer",
            "source": "llm",
            "message": first_answer,
            "ai": ai,
        }
    except Exception as e:
        return {"ok": False, "kind": "error", "error": str(e)}
