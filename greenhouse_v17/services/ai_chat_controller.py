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




def _detect_schedule_command(text: str) -> Optional[Dict[str, Any]]:
    t = (text or "").lower()

    if not any(w in t for w in ["каждый день", "по будням", "по выходным", "ежедневно", "включай", "выключай"]):
        return None

    op = "off" if "выключ" in t else "on"

    zone = None
    if any(w in t for w in ["верх", "верхний", "сверху"]):
        zone = "top"
    elif any(w in t for w in ["низ", "нижний", "снизу"]):
        zone = "bottom"

    from greenhouse_v17.services.nl_action_resolver import resolve_action_from_text

    resolved = resolve_action_from_text(text, op=op, zone=zone)
    if not resolved:
        return None

    if resolved.get("kind") == "clarification":
        return {
            "kind": "schedule_clarification",
            "message": resolved.get("message", "[LOCAL] Нужно уточнить устройство или зону.")
        }

    action_key = resolved.get("action_key")
    action_keys = resolved.get("action_keys") or ([action_key] if action_key else [])
    title = resolved["title"]

    m = re.search(r'(?:в\s*)?(\d{1,2})(?::(\d{2}))?', t)
    if not m:
        return {
            "kind": "schedule_clarification",
            "message": "[LOCAL] Понял, что это расписание, но не понял время. Пример: каждый день в 08:00 включай верхний вент."
        }

    h = int(m.group(1))
    minute = int(m.group(2) or 0)
    if h > 23 or minute > 59:
        return {"kind": "schedule_error", "message": "[LOCAL] Некорректное время расписания."}

    if "будн" in t:
        days = ["mon", "tue", "wed", "thu", "fri"]
        days_text = "по будням"
    elif "выходн" in t:
        days = ["sat", "sun"]
        days_text = "по выходным"
    else:
        days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        days_text = "каждый день"

    time_hhmm = f"{h:02d}:{minute:02d}"
    action_ru = "включать" if op == "on" else "выключать"

    return {
        "kind": "schedule_candidate",
        "source": "local_schedule_parser",
        "action_key": action_key,
        "action_keys": action_keys,
        "title": title,
        "time": time_hhmm,
        "days": days,
        "days_text": days_text,
        "source_text": text,
        "message": f"[LOCAL] Я понял расписание так:\n\n• {action_ru} {title}\n• {days_text}\n• время: {time_hhmm}\n\nСоздаю ASK на подтверждение."
    }

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

    state = load_ask_state()
    candidate = (state or {}).get("meta", {}).get("ai_candidate") or (state or {}).get("ai_candidate")
    if candidate and candidate.get("kind") == "schedule_candidate":
        res = create_ai_schedule(
            action_key=candidate["action_key"],
            time_hhmm=candidate["time"],
            days=candidate["days"],
            source_text=candidate.get("source_text", ""),
            enabled=True,
        )
        cancel_pending_ask()
        if not res.get("ok"):
            return {
                "ok": False,
                "source": "local_schedule_parser",
                "message": f"[LOCAL] Не смог создать расписание: {res}",
                "result": res,
            }
        return {
            "ok": True,
            "source": "local_schedule_parser",
            "message": f"[LOCAL] Расписание создано: {candidate['title']} — {candidate['days_text']} в {candidate['time']}.",
            "result": res,
        }

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






def _get_current_mode_safe() -> str:
    try:
        from greenhouse_v17.services.mode_service import get_mode_flags
        flags = get_mode_flags()
        mode = flags.get("mode") or flags.get("current_mode") or flags.get("name")
        return str(mode or "MANUAL").upper()
    except Exception:
        return "MANUAL"




def _create_logical_schedule_management_ask(candidate: Dict[str, Any], text: str) -> Dict[str, Any]:
    """
    Logical ASK: not an execution action.
    Used for schedule enable/disable/delete.
    Must be handled by confirm before execute_action().
    """
    import json
    import time
    from pathlib import Path

    op = candidate.get("op")
    idx = candidate.get("index")

    if op == "delete":
        title = f"Удалить расписание {idx}?"
    elif op == "disable":
        title = f"Выключить расписание {idx}?"
    elif op == "enable":
        title = f"Включить расписание {idx}?"
    else:
        title = f"Изменить расписание {idx}?"

    state = {
        "has_pending": True,
        "kind": "schedule_management_candidate",
        "title": title,
        "source": "local_schedule_parser",
        "created_at": time.time(),
        "source_text": text,
        "ai_candidate": candidate,
        "ask_meta": {
            "logical_type": "schedule_management",
            "ai_candidate": candidate,
        },
        # action_key intentionally absent from logical ASK
    }

    from greenhouse_v17.services.webadmin_execution_service import save_ask_state
    save_ask_state(state)

    return {
        "ok": True,
        "source": "local_schedule_parser",
        "kind": "ask_created",
        "message": f"[LOCAL] {title}\\n\\nСоздаю ASK на подтверждение.",
        "ask": state,
    }


def _apply_schedule_management_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    from greenhouse_v17.services.ai_schedule_service import (
        delete_ai_schedule,
        set_ai_schedule_enabled,
    )

    op = candidate.get("op")
    schedule_id = candidate.get("schedule_id")
    idx = candidate.get("index")

    if op == "delete":
        res = delete_ai_schedule(schedule_id)
        return {"ok": True, "source": "local_schedule_parser", "message": f"[LOCAL] Удалил расписание {idx}.", "result": res}

    if op == "disable":
        res = set_ai_schedule_enabled(schedule_id, False)
        return {"ok": True, "source": "local_schedule_parser", "message": f"[LOCAL] Сделал расписание {idx} неактивным.", "result": res}

    if op == "enable":
        res = set_ai_schedule_enabled(schedule_id, True)
        return {"ok": True, "source": "local_schedule_parser", "message": f"[LOCAL] Сделал расписание {idx} активным.", "result": res}

    return {"ok": False, "source": "local_schedule_parser", "message": "[LOCAL] Не понял операцию с расписанием."}


def _handle_schedule_management_command(text: str) -> Optional[Dict[str, Any]]:
    t = (text or "").lower().strip()

    from greenhouse_v17.services.ai_schedule_service import (
        list_ai_schedules,
        delete_ai_schedule,
        set_ai_schedule_enabled,
    )

    if "расписан" in t and any(w in t for w in ["покажи", "список", "какие", "что есть"]):
        items = list_ai_schedules()
        if not items:
            return {"ok": True, "source": "local_schedule_parser", "message": "[LOCAL] Расписаний пока нет."}

        lines = ["[LOCAL] Расписания:"]
        for i, item in enumerate(items, 1):
            status = "активно" if item.get("enabled", True) else "неактивно"
            actions = item.get("action_keys") or [item.get("action_key")]
            lines.append(
                f"{i}. {status} — {', '.join([a for a in actions if a])} — {item.get('time')} — {', '.join(item.get('days', []))}"
            )
        return {"ok": True, "source": "local_schedule_parser", "message": "\n".join(lines), "items": items}

    if "расписан" not in t:
        return None

    import re
    m = re.search(r'(\d+)', t)
    if not m:
        return {"ok": True, "source": "local_schedule_parser", "message": "[LOCAL] Укажи номер расписания. Например: удали расписание 2."}

    idx = int(m.group(1)) - 1
    items = list_ai_schedules()
    if idx < 0 or idx >= len(items):
        return {"ok": False, "source": "local_schedule_parser", "message": "[LOCAL] Не нашёл расписание с таким номером."}

    schedule_id = items[idx].get("schedule_id")

    op = None
    if any(w in t for w in ["удали", "удалить", "сотри"]):
        op = "delete"
    elif any(w in t for w in ["выключи", "отключи", "пауза", "неактив"]):
        op = "disable"
    elif any(w in t for w in ["включи", "актив"]):
        op = "enable"

    if op:
        candidate = {
            "kind": "schedule_management_candidate",
            "op": op,
            "schedule_id": schedule_id,
            "index": idx + 1,
            "source_text": text,
        }

        mode = _get_current_mode_safe()

        if mode == "ASK":
            return _create_logical_schedule_management_ask(candidate, text)

        if mode == "TEST":
            return {
                "ok": True,
                "source": "local_schedule_parser",
                "message": f"[LOCAL][TEST] Было бы выполнено: {op} расписание {idx+1}.",
                "candidate": candidate,
            }

        return _apply_schedule_management_candidate(candidate)

    return None


def handle_chat_message(text: str) -> Dict[str, Any]:
    schedule_manage = _handle_schedule_management_command(text)
    if schedule_manage:
        return schedule_manage


    # === RECIPE V2 FLOW (before schedule parser) ===
    recipe_v2_candidate = _detect_recipe_v2(text)
    if recipe_v2_candidate:
        mode = _get_current_mode_safe()

        if mode == "ASK":
            return _create_web_ask(recipe_v2_candidate, text)

        if mode == "TEST":
            return {
                "ok": True,
                "source": "local_recipe_v2_parser",
                "kind": "recipe_v2_dry_run",
                "message": f"[LOCAL][TEST] Было бы создано automation:\n• {recipe_v2_candidate['title']}",
                "candidate": recipe_v2_candidate,
            }

        from greenhouse_v17.services.automation_recipe_v2_service import create_recipe_v2
        res = create_recipe_v2(**recipe_v2_candidate["payload"])

        return {
            "ok": True,
            "source": "local_recipe_v2_parser",
            "kind": "recipe_v2_created",
            "message": f"[LOCAL] Создал automation:\n• {recipe_v2_candidate['title']}",
            "result": res,
        }

    schedule_candidate = _detect_schedule_command(text)

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



    # === SCHEDULE MODE-AWARE FLOW ===
    if schedule_candidate:
        mode = _get_current_mode_safe()

        if mode == "ASK":
            return _create_web_ask(schedule_candidate, text)

        if mode == "MANUAL":
            from greenhouse_v17.services.ai_schedule_service import create_ai_schedule

            res = create_ai_schedule(
                action_key=schedule_candidate.get("action_key"),
                action_keys=schedule_candidate.get("action_keys"),
                time_hhmm=schedule_candidate["time"],
                days=schedule_candidate["days"],
                source_text=schedule_candidate.get("source_text", ""),
                enabled=True,
            )

            return {
                "ok": True,
                "source": "local_schedule_parser",
                "kind": "schedule_created",
                "message": f"[LOCAL] Создал расписание:\n• {schedule_candidate['title']} — {schedule_candidate['days_text']} в {schedule_candidate['time']}.",
                "result": res,
            }

        if mode == "TEST":
            return {
                "ok": True,
                "source": "local_schedule_parser",
                "kind": "schedule_dry_run",
                "message": f"[LOCAL][TEST] Было бы создано расписание:\n• {schedule_candidate['title']} — {schedule_candidate['days_text']} в {schedule_candidate['time']}.",
            }

        # AUTO / AUTOPILOT пока безопасно ведём через ASK
        return _create_web_ask(schedule_candidate, text)

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


def _detect_recipe_v2(text: str):
    import re

    t = text.lower()

    if "каждый час" in t and "вент" in t:
        duration_sec = 10
        m = re.search(r"на\s+(\d+)\s*(сек|секунд|секунды|s)", t)
        if m:
            duration_sec = int(m.group(1))

        conditions = None
        if "влаж" in t and ("ниже" in t or "меньше" in t or "<" in t):
            value = "55"
            m2 = re.search(r"(?:ниже|меньше|<)\s*(\d+)", t)
            if m2:
                value = m2.group(1)

            conditions = {
                "entity_id": "sensor.nobito_humidity",
                "operator": "<",
                "value": value,
            }

        title = "Каждый час: вент"
        if conditions:
            title += f" если влажность < {conditions['value']}"
        title += f" на {duration_sec} сек"

        return {
            "kind": "recipe_v2_candidate",
            "title": title,
            "payload": {
                "title": title,
                "trigger": {
                    "type": "interval",
                    "every_sec": 3600
                },
                "conditions": conditions,
                "action_plan": {
                    "type": "duration",
                    "action_key": "fan_top_on",
                    "off_action_key": "fan_top_off",
                    "duration_sec": duration_sec
                },
                "source_text": text
            }
        }

    return None

