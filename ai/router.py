from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

from ai.context_builder import build_minimal_context

def resolve_action_key(action: str, target: str):
    if not action or not target:
        return None

    mapping = {
        ("turn_on", "fan_top"): "fan_top_on",
        ("turn_off", "fan_top"): "fan_top_off",
    }

    return mapping.get((action, target))

from chat.intent_parser import ParsedIntent, parse_intent


@dataclass
class AIRouterResult:
    ok: bool
    task_type: str
    parsed_intent: Dict[str, Any]
    context: Dict[str, Any]
    response_text: str
    proposed_action: Optional[Dict[str, Any]] = None
    meta: Dict[str, Any] = field(default_factory=dict)


def route_ai_message(text: str) -> Dict[str, Any]:
    """
    AI Router v1.
    Пока НЕ вызывает модель и НЕ исполняет действия.
    Только классифицирует запрос и собирает минимальный контекст.
    """
    parsed: ParsedIntent = parse_intent(text)
    context = build_minimal_context()

    if parsed.intent_type == "device_action":
        response = (
            "AI Router распознал команду управления, "
            "но выполнение напрямую запрещено. "
            "Дальше это должно идти через Core → Validation → Execution."
        )
        action_key = resolve_action_key(parsed.action, parsed.target)

        proposed_action = {
            "intent_type": parsed.intent_type,
            "action": parsed.action,
            "target": parsed.target,
            "requires_validation": True,
            "direct_execution": False,
            "action_key": action_key,
        }
        task_type = "natural_language_control"

    elif parsed.intent_type == "observation":
        response = "AI Router распознал наблюдение. Его можно передать в observation/memory слой."
        proposed_action = None
        task_type = "observation_interpretation"

    elif parsed.intent_type in ("status_question", "why_question", "generic_question"):
        response = "AI Router распознал вопрос. Нужен status/explain/context analysis сценарий."
        proposed_action = None
        task_type = "question_answering"

    elif parsed.intent_type in ("memory_save", "memory_forget"):
        response = "AI Router распознал запрос к памяти. Нужен Memory API, без прямой записи AI в файлы."
        proposed_action = None
        task_type = "memory_request"

    else:
        response = "AI Router получил сообщение, но пока не выбрал специальный сценарий."
        proposed_action = None
        task_type = "general_message"

    return AIRouterResult(
        ok=True,
        task_type=task_type,
        parsed_intent=asdict(parsed),
        context=context,
        response_text=response,
        proposed_action=proposed_action,
        meta={
            "ai_model_called": False,
            "execution_called": False,
            "ha_called": False,
        },
    ).__dict__
