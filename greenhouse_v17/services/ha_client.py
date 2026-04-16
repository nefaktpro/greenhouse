import requests
from greenhouse_v17.config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN, REQUEST_TIMEOUT

def _headers():
    return {
        "Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
        "Content-Type": "application/json",
    }

def call_switch(entity_id: str, turn_on: bool):
    service = "turn_on" if turn_on else "turn_off"
    r = requests.post(
        f"{HOME_ASSISTANT_URL}/api/services/switch/{service}",
        headers=_headers(),
        json={"entity_id": entity_id},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    return {
        "ok": True,
        "service": service,
        "entity_id": entity_id,
        "response_text": r.text,
    }

def get_state(entity_id: str):
    r = requests.get(
        f"{HOME_ASSISTANT_URL}/api/states/{entity_id}",
        headers=_headers(),
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    return {
        "state": data.get("state"),
        "last_updated": data.get("last_updated"),
        "friendly_name": data.get("attributes", {}).get("friendly_name"),
    }
