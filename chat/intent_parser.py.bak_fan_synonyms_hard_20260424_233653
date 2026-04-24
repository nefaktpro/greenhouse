from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParsedIntent:
    raw_text: str
    intent_type: str
    confidence: float
    action: Optional[str] = None
    target: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


STATUS_KEYWORDS = [
    "что с теплицей",
    "что сейчас",
    "статус",
    "как дела",
    "что происходит",
    "сводка",
    "отчет",
    "отчёт",
]

WHY_KEYWORDS = [
    "почему",
    "зачем",
    "из-за чего",
]

MEMORY_SAVE_KEYWORDS = [
    "запомни",
    "сохрани",
]

MEMORY_FORGET_KEYWORDS = [
    "забудь",
    "удали из памяти",
]

OBSERVATION_MARKERS = [
    "пар",
    "дует",
    "сухо",
    "влажно",
    "вял",
    "мокро",
    "пахнет",
    "выглядит",
]

ACTION_ON_KEYWORDS = [
    "включи",
    "вруби",
    "запусти",
]

ACTION_OFF_KEYWORDS = [
    "выключи",
    "отключи",
    "останови",
]

TOP_FAN_MARKERS = [
    "верхний вентилятор",
    "верхний вент",
    "вентилятор верх",
    "верхний",
]

LOW_FAN_MARKERS = [
    "нижний вентилятор",
    "нижний вент",
    "вентилятор низ",
    "нижний",
]

ALL_FAN_MARKERS = [
    "вентиляторы",
    "все вентиляторы",
    "оба вентилятора",
]


def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def contains_any(text: str, variants: List[str]) -> bool:
    return any(variant in text for variant in variants)


def detect_fan_target(text: str) -> Optional[str]:
    if contains_any(text, ALL_FAN_MARKERS):
        return "all_fans"
    if contains_any(text, TOP_FAN_MARKERS):
        return "fan_top"
    if contains_any(text, LOW_FAN_MARKERS):
        return "fan_low"
    return None


def parse_intent(text: str) -> ParsedIntent:
    normalized = normalize_text(text)

    if not normalized:
        return ParsedIntent(
            raw_text=text,
            intent_type="empty",
            confidence=1.0,
            tags=["empty"],
        )

    if contains_any(normalized, MEMORY_SAVE_KEYWORDS):
        memory_text = normalized
        for marker in MEMORY_SAVE_KEYWORDS:
            memory_text = memory_text.replace(marker, "", 1).strip()

        return ParsedIntent(
            raw_text=text,
            intent_type="memory_save",
            confidence=0.95,
            payload={"text": memory_text},
            tags=["memory"],
        )

    if contains_any(normalized, MEMORY_FORGET_KEYWORDS):
        forget_text = normalized
        for marker in MEMORY_FORGET_KEYWORDS:
            forget_text = forget_text.replace(marker, "", 1).strip()

        return ParsedIntent(
            raw_text=text,
            intent_type="memory_forget",
            confidence=0.9,
            payload={"text": forget_text},
            tags=["memory"],
        )

    if contains_any(normalized, WHY_KEYWORDS):
        return ParsedIntent(
            raw_text=text,
            intent_type="why_question",
            confidence=0.9,
            tags=["question", "why"],
        )

    if contains_any(normalized, STATUS_KEYWORDS):
        return ParsedIntent(
            raw_text=text,
            intent_type="status_question",
            confidence=0.95,
            tags=["question", "status"],
        )

    is_turn_on = contains_any(normalized, ACTION_ON_KEYWORDS)
    is_turn_off = contains_any(normalized, ACTION_OFF_KEYWORDS)

    if is_turn_on or is_turn_off:
        fan_target = detect_fan_target(normalized)

        if fan_target:
            return ParsedIntent(
                raw_text=text,
                intent_type="device_action",
                confidence=0.95,
                action="turn_on" if is_turn_on else "turn_off",
                target=fan_target,
                tags=["action", "device", "fan"],
            )

        return ParsedIntent(
            raw_text=text,
            intent_type="device_action",
            confidence=0.6,
            action="turn_on" if is_turn_on else "turn_off",
            target=None,
            tags=["action", "device", "unknown_target"],
        )

    if contains_any(normalized, OBSERVATION_MARKERS):
        return ParsedIntent(
            raw_text=text,
            intent_type="observation",
            confidence=0.75,
            payload={"text": text.strip()},
            tags=["observation"],
        )

    if "?" in text:
        return ParsedIntent(
            raw_text=text,
            intent_type="generic_question",
            confidence=0.6,
            tags=["question", "generic"],
        )

    return ParsedIntent(
        raw_text=text,
        intent_type="generic_message",
        confidence=0.4,
        payload={"text": text.strip()},
        tags=["generic"],
    )
