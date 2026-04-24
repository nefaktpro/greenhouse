from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/test", tags=["test-lab"])

ENV_PATH = "/home/mi/greenhouse_v17/.env"

THERMOSTAT_MAIN = "climate.termostat_veranda"
THERMOSTAT_CHILD_LOCK = "switch.termostat_veranda_child_lock"
THERMOSTAT_FROST = "switch.termostat_veranda_frost_protection"
THERMOSTAT_CORRECTION = "number.termostat_veranda_temperature_correction"

HUMIDIFIER_POWER = "switch.3_uvlazhnitel"
HUMIDIFIER_SOCKET = "switch.smart_power_strip_eu_2_socket_3"
HUMIDIFIER_AUTO = "switch.humidifier_auto"
HUMIDIFIER_SLEEP = "switch.humidifier_sleep"
HUMIDIFIER_TEMP = "sensor.humidifier_temperature"
HUMIDIFIER_HUM = "sensor.humidifier_humidity"
HUMIDIFIER_TIMER = "sensor.humidifier_timer"
HUMIDIFIER_WATER = "binary_sensor.humidifier_water_low"

SENSOR24_TEMP = "sensor.datchik_temeratury_i_vlazhnosti_temperature"
SENSOR24_HUM = "sensor.datchik_temeratury_i_vlazhnosti_humidity"


class BoolBody(BaseModel):
    enabled: bool


class NumberBody(BaseModel):
    value: float


def _load_env() -> None:
    load_dotenv(ENV_PATH)


def _ha_base_url() -> str:
    _load_env()
    return os.getenv("HOME_ASSISTANT_URL") or os.getenv("HA_URL") or "http://127.0.0.1:8123"


def _ha_token() -> str:
    _load_env()
    token = os.getenv("HOME_ASSISTANT_TOKEN") or os.getenv("HA_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="HA token not configured")
    return token


def _ha_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_ha_token()}",
        "Content-Type": "application/json",
    }


def _ha_get(path: str) -> Any:
    r = requests.get(f"{_ha_base_url()}{path}", headers=_ha_headers(), timeout=20)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"HA GET failed: {path} -> {r.status_code}")
    return r.json()


def _ha_post(path: str, payload: Dict[str, Any]) -> Any:
    r = requests.post(f"{_ha_base_url()}{path}", headers=_ha_headers(), json=payload, timeout=20)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"HA POST failed: {path} -> {r.status_code}")
    if not r.text.strip():
        return {"ok": True}
    return r.json()


def _get_state(entity_id: str) -> Dict[str, Any] | None:
    try:
        return _ha_get(f"/api/states/{entity_id}")
    except HTTPException:
        return None


def _switch_set(entity_id: str, enabled: bool) -> Dict[str, Any]:
    service = "turn_on" if enabled else "turn_off"
    domain = entity_id.split(".", 1)[0]
    result = _ha_post(f"/api/services/{domain}/{service}", {"entity_id": entity_id})
    return {
        "ok": True,
        "entity_id": entity_id,
        "enabled": enabled,
        "service_result": result,
        "state": _get_state(entity_id),
    }


def _number_set(entity_id: str, value: float) -> Dict[str, Any]:
    result = _ha_post("/api/services/number/set_value", {"entity_id": entity_id, "value": value})
    return {
        "ok": True,
        "entity_id": entity_id,
        "value": value,
        "service_result": result,
        "state": _get_state(entity_id),
    }


@router.get("/thermostat/state")
def thermostat_state() -> Dict[str, Any]:
    return {
        "ok": True,
        "main": _get_state(THERMOSTAT_MAIN),
        "child_lock": _get_state(THERMOSTAT_CHILD_LOCK),
        "frost_protection": _get_state(THERMOSTAT_FROST),
        "temperature_correction": _get_state(THERMOSTAT_CORRECTION),
    }


@router.post("/thermostat/set_temperature")
def thermostat_set_temperature(body: NumberBody) -> Dict[str, Any]:
    result = _ha_post(
        "/api/services/climate/set_temperature",
        {"entity_id": THERMOSTAT_MAIN, "temperature": body.value},
    )
    return {
        "ok": True,
        "temperature": body.value,
        "service_result": result,
        "state": _get_state(THERMOSTAT_MAIN),
    }


@router.post("/thermostat/set_child_lock")
def thermostat_set_child_lock(body: BoolBody) -> Dict[str, Any]:
    return _switch_set(THERMOSTAT_CHILD_LOCK, body.enabled)


@router.post("/thermostat/set_frost")
def thermostat_set_frost(body: BoolBody) -> Dict[str, Any]:
    return _switch_set(THERMOSTAT_FROST, body.enabled)


@router.post("/thermostat/set_correction")
def thermostat_set_correction(body: NumberBody) -> Dict[str, Any]:
    return _number_set(THERMOSTAT_CORRECTION, body.value)


@router.get("/humidifier/state")
def humidifier_state() -> Dict[str, Any]:
    return {
        "ok": True,
        "power": _get_state(HUMIDIFIER_POWER),
        "socket": _get_state(HUMIDIFIER_SOCKET),
        "auto": _get_state(HUMIDIFIER_AUTO),
        "sleep": _get_state(HUMIDIFIER_SLEEP),
        "temperature": _get_state(HUMIDIFIER_TEMP),
        "humidity": _get_state(HUMIDIFIER_HUM),
        "timer": _get_state(HUMIDIFIER_TIMER),
        "water_low": _get_state(HUMIDIFIER_WATER),
    }


@router.post("/humidifier/set_power")
def humidifier_set_power(body: BoolBody) -> Dict[str, Any]:
    return _switch_set(HUMIDIFIER_POWER, body.enabled)


@router.post("/humidifier/set_socket")
def humidifier_set_socket(body: BoolBody) -> Dict[str, Any]:
    return _switch_set(HUMIDIFIER_SOCKET, body.enabled)


@router.post("/humidifier/set_auto")
def humidifier_set_auto(body: BoolBody) -> Dict[str, Any]:
    return _switch_set(HUMIDIFIER_AUTO, body.enabled)


@router.post("/humidifier/set_sleep")
def humidifier_set_sleep(body: BoolBody) -> Dict[str, Any]:
    return _switch_set(HUMIDIFIER_SLEEP, body.enabled)


def _history_points(entity_id: str, hours: int) -> List[Dict[str, Any]]:
    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    start_s = start.isoformat()
    path = f"/api/history/period/{start_s}?filter_entity_id={entity_id}&minimal_response"
    data = _ha_get(path)

    if not isinstance(data, list) or not data:
        return []

    series = data[0] if isinstance(data[0], list) else data
    points: List[Dict[str, Any]] = []

    for row in series:
        if not isinstance(row, dict):
            continue
        st = row.get("state")
        ts = row.get("last_changed") or row.get("last_updated")
        try:
            value = float(st)
        except Exception:
            continue
        if not ts:
            continue
        points.append({"ts": ts, "value": value})

    return points


@router.get("/sensor24/state")
def sensor24_state() -> Dict[str, Any]:
    return {
        "ok": True,
        "temperature": _get_state(SENSOR24_TEMP),
        "humidity": _get_state(SENSOR24_HUM),
    }


@router.get("/sensor24/history")
def sensor24_history(hours: int = 24) -> Dict[str, Any]:
    hours = max(1, min(hours, 24 * 14))
    return {
        "ok": True,
        "hours": hours,
        "temperature": _history_points(SENSOR24_TEMP, hours),
        "humidity": _history_points(SENSOR24_HUM, hours),
    }
