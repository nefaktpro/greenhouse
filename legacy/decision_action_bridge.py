from typing import Any, Dict, List

DECISION_TO_ACTION_KEY = {
    "fan_top_on": "fan_top_on",
    "fan_top_off": "fan_top_off",
    "fan_low_on": "fan_bottom_on",
    "fan_low_off": "fan_bottom_off",
}

def extract_action_keys_from_decisions(decisions: List[Dict[str, Any]]) -> List[str]:
    result: List[str] = []

    for item in decisions or []:
        if not isinstance(item, dict):
            continue

        candidates = [
            item.get("action_key"),
            item.get("decision"),
            item.get("action"),
            item.get("key"),
            item.get("name"),
        ]

        resolved = None
        for candidate in candidates:
            if isinstance(candidate, str) and candidate in DECISION_TO_ACTION_KEY:
                resolved = DECISION_TO_ACTION_KEY[candidate]
                break

        if resolved:
            result.append(resolved)

    return result
