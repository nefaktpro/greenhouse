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
    t = text.lower()

    # "на 10 минут", "10 мин", "на 30 секунд", "1 час"
    m = re.search(r"(?:на\s+)?(\d+)\s*(секунд[уы]?|сек|s|минут[уы]?|мин|m|час[аов]?|ч|h)\b", t)
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

    if duration_seconds:
        lines.append(f"• Таймер: {duration_text}")
        if followup_action_key:
            lines.append(f"• После таймера: {followup_action_key}")
            lines.append("")
            lines.append("Важно: сейчас таймер сохраняется в ASK, авто-выключение отдельным scheduler ещё не включено.")

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
        "followup_action_key": candidate.get("followup_action_key"),
        "requires_timer": bool(candidate.get("duration_seconds") and candidate.get("followup_action_key")),
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


def handle_chat_message(text: str) -> Dict[str, Any]:
    t = text.strip().lower()

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

        prompt = f"""
{system_prompt}

CURRENT_CONTEXT:
{{}}

AVAILABLE_CONTEXT_CATALOG:
{json.dumps(catalog, ensure_ascii=False, indent=2)[:12000]}

USER_MESSAGE:
{text}
"""

        ai = ask_ai_with_fallback(prompt)
        return {
            "ok": True,
            "kind": "ai_answer",
            "message": ai.get("answer") or "AI не вернул ответ.",
            "ai": ai,
        }
    except Exception as e:
        return {"ok": False, "kind": "error", "error": str(e)}
