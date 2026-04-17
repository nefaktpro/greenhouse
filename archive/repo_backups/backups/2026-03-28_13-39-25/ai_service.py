import os
import requests
from dotenv import load_dotenv

from current_snapshot import build_current_snapshot
from ai_engine import analyze_with_ai

load_dotenv("/home/mi/teplica_bot/.env")

HA_BASE_URL = os.getenv("HA_BASE_URL")
HA_TOKEN = os.getenv("HA_TOKEN")

if not HA_BASE_URL:
    raise RuntimeError("HA_BASE_URL не найден в .env")
if not HA_TOKEN:
    raise RuntimeError("HA_TOKEN не найден в .env")


def fetch_ha_states():
    url = f"{HA_BASE_URL.rstrip('/')}/api/states"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Ошибка Home Assistant: {response.status_code} {response.text}")

    return response.json()


def get_ai_analysis() -> str:
    raw_states = fetch_ha_states()
    snapshot = build_current_snapshot(raw_states)
    analysis = analyze_with_ai(snapshot)
    return analysis


def get_ai_analysis_with_snapshot() -> tuple[str, str]:
    raw_states = fetch_ha_states()
    snapshot = build_current_snapshot(raw_states)
    analysis = analyze_with_ai(snapshot)
    return snapshot, analysis
