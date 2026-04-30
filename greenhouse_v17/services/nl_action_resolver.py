from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
ACTION_MAP_PATH = ROOT / "data" / "registry" / "action_map.json"


def _load_action_map() -> Dict[str, Any]:
    try:
        return json.loads(ACTION_MAP_PATH.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}


def _op_words(op: str) -> list[str]:
    if op == "on":
        return ["on", "turn_on", "вкл", "включ"]
    return ["off", "turn_off", "выкл", "выключ"]


def resolve_action_from_text(text: str, op: str, zone: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Универсальный MVP-resolver:
    текст + операция + зона -> action_key из data/registry/action_map.json.

    Не содержит конкретных entity_id.
    Не ходит в HA.
    Не выполняет действие.
    """
    t = (text or "").lower()
    amap = _load_action_map()
    if not amap:
        return None

    # object class from natural language
    object_type = None
    if any(w in t for w in ["вент", "продув", "циркуляц"]):
        object_type = "fan"
        object_words = ["fan", "air", "circulation", "вент"]
        role_words = ["air_circulation", "circulation"]
        human_object = "вентилятор"
    elif "свет" in t or "ламп" in t:
        object_type = "light"
        object_words = ["light", "lamp", "свет"]
        role_words = ["light", "lighting"]
        human_object = "свет"
    else:
        return None

    # Group command: "оба / все / вентиляторы" -> multiple action_keys via registry.
    wants_group = (
        zone is None
        and any(w in t for w in ["оба", "обе", "все", "всё", "вентиляторы", "венты"])
    )
    if object_type in ("fan", "light") and wants_group:
        op_candidates = _op_words(op)
        group = []
        for key, cfg in amap.items():
            blob = (key + " " + json.dumps(cfg, ensure_ascii=False)).lower()
            if any(w in blob for w in object_words) and any(w in blob for w in role_words) and any(w in blob for w in op_candidates):
                if op == "on" and any(w in key.lower() for w in ["_off", "off"]):
                    continue
                if op == "off" and any(w in key.lower() for w in ["_on", "on"]):
                    continue
                group.append(key)

        # убрать legacy-дубли вроде fan_low_on, если есть canonical fan_bottom_on
        if "fan_bottom_on" in group and "fan_low_on" in group:
            group.remove("fan_low_on")
        if "fan_bottom_off" in group and "fan_low_off" in group:
            group.remove("fan_low_off")

        group = sorted(set(group))
        if group:
            action_ru = "включать" if op == "on" else "выключать"
            return {
                "kind": "resolved_group",
                "action_keys": group,
                "title": f"{action_ru} все {human_object}",
                "source": "registry_action_map",
            }

        return {
            "kind": "clarification",
            "message": f"[LOCAL] Понял группу «{human_object}», но не нашёл actions в registry."
        }

    zone_words = []
    human_zone = ""
    if zone == "top":
        zone_words = ["top", "upper", "верх"]
        human_zone = "верхний "
    elif zone == "bottom":
        zone_words = ["bottom", "low", "lower", "низ"]
        human_zone = "нижний "

    op_candidates = _op_words(op)

    scored = []
    for key, cfg in amap.items():
        blob = (key + " " + json.dumps(cfg, ensure_ascii=False)).lower()

        score = 0

        if any(w in blob for w in object_words):
            score += 3
        if any(w in blob for w in role_words):
            score += 3
        if any(w in blob for w in op_candidates):
            score += 3
        if zone_words and any(w in blob for w in zone_words):
            score += 3

        # penalties
        if zone == "top" and any(w in blob for w in ["bottom", "low", "lower", "низ"]):
            score -= 5
        if zone == "bottom" and any(w in blob for w in ["top", "upper", "верх"]):
            score -= 5
        if op == "on" and any(w in key.lower() for w in ["_off", "off"]):
            score -= 5
        if op == "off" and any(w in key.lower() for w in ["_on", "on"]):
            score -= 5

        if score >= 6:
            scored.append((score, key, cfg))

    if not scored:
        return None

    scored.sort(reverse=True, key=lambda x: x[0])
    best_score = scored[0][0]
    best = [x for x in scored if x[0] == best_score]

    if len(best) > 1:
        return {
            "kind": "clarification",
            "message": "[LOCAL] Нашёл несколько подходящих действий в registry. Уточни зону или устройство."
        }

    action_key = best[0][1]
    action_ru = "включать" if op == "on" else "выключать"

    return {
        "kind": "resolved_action",
        "action_key": action_key,
        "title": f"{action_ru} {human_zone}{human_object}".strip(),
        "source": "registry_action_map",
        "matched_score": best_score,
    }
