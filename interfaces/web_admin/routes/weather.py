from __future__ import annotations

import json
import os
import urllib.request
import pathlib
from datetime import datetime, timezone
from fastapi import APIRouter
from greenhouse_v17.services.weather_history_service import record_weather_snapshot, record_forecast, record_comparison, recent_weather_history, db_summary

router = APIRouter(prefix="/api/weather", tags=["weather"])

OUTSIDE_TEMP = "sensor.vlazhnost_nizhnii_gorshok_belyi_temperature"
OUTSIDE_HUM = "sensor.vlazhnost_nizhnii_gorshok_belyi_humidity"
FORECAST_ENTITY = "weather.home_assistant"
RUNTIME_FILE = pathlib.Path("/home/mi/greenhouse_v17/data/weather/weather_runtime.json")
RECORDER_SETTINGS_FILE = pathlib.Path("/home/mi/greenhouse_v17/data/weather/weather_recorder_settings.json")

def _ha():
    return os.getenv("HA_URL") or os.getenv("HA_BASE_URL") or "http://127.0.0.1:8123", os.getenv("HA_TOKEN")

def _get_state(entity_id: str):
    ha_url, token = _ha()
    req = urllib.request.Request(
        ha_url.rstrip() + "/api/states/" + entity_id,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=8).read().decode())

def _get_forecast():
    ha_url, token = _ha()
    payload = json.dumps({"entity_id": FORECAST_ENTITY, "type": "hourly"}).encode()
    req = urllib.request.Request(
        ha_url.rstrip() + "/api/services/weather/get_forecasts?return_response",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    data = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
    return data.get("service_response", {}).get(FORECAST_ENTITY, {}).get("forecast", [])

@router.get("/overview")
def weather_overview():
    try:
        temp = _get_state(OUTSIDE_TEMP)
        hum = _get_state(OUTSIDE_HUM)
        weather = _get_state(FORECAST_ENTITY)
        forecast = _get_forecast()

        temp_val = float(temp.get("state"))
        hum_val = float(hum.get("state"))

        try:
            record_weather_snapshot(temp_val, hum_val, OUTSIDE_TEMP, OUTSIDE_HUM)
        except Exception:
            pass

        next_6h = forecast[:6]
        next_24h = forecast[:24]

        try:
            record_forecast(FORECAST_ENTITY, forecast)
        except Exception:
            pass

        forecast_now_temp = None
        forecast_condition = weather.get("state")
        if forecast:
            forecast_now_temp = forecast[0].get("temperature")
            forecast_condition = forecast[0].get("condition") or forecast_condition

        delta_temp = None
        trust_score = None
        if forecast_now_temp is not None:
            delta_temp = round(temp_val - float(forecast_now_temp), 2)
            trust_score = max(0.0, min(1.0, round(1.0 - abs(delta_temp) / 10.0, 2)))

        try:
            record_comparison(temp_val, hum_val, forecast_now_temp, forecast_condition)
        except Exception:
            pass

        return {
            "ok": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "device_id": "200",
            "logical_role": "environment_outside",
            "fact": {
                "temperature": temp_val,
                "humidity": hum_val,
                "temperature_entity": OUTSIDE_TEMP,
                "humidity_entity": OUTSIDE_HUM,
            },
            "forecast": {
                "entity_id": FORECAST_ENTITY,
                "state": weather.get("state"),
                "attributes": weather.get("attributes", {}),
                "hourly": forecast,
                "next_6h": next_6h,
                "next_24h": next_24h,
            },
            "light": {
                "lux_1": None,
                "lux_2": None,
                "status": "planned"
            },
            "comparison": {
                "forecast_now_temp": forecast_now_temp,
                "delta_temp": delta_temp,
                "trust_score": trust_score
            },
            "greenhouse_impact": {
                "status": "planned_ai_analysis",
                "notes": [
                    "real outside sensors are primary fact",
                    "HA weather forecast is secondary future expectation",
                    "lux sensors planned"
                ]
            },
            "history": recent_weather_history(24),
            "runtime": json.loads(RUNTIME_FILE.read_text(encoding="utf-8")) if RUNTIME_FILE.exists() else {
                "status": "starting"
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/db-summary")
def weather_db_summary():
    return {"ok": True, **db_summary()}


@router.get("/recorder-settings")
def weather_recorder_settings():
    if RECORDER_SETTINGS_FILE.exists():
        return {"ok": True, **json.loads(RECORDER_SETTINGS_FILE.read_text(encoding="utf-8"))}
    return {"ok": True, "enabled": True, "fact_interval_sec": 3600, "forecast_interval_sec": 3600}

@router.post("/recorder-toggle")
def weather_recorder_toggle():
    current = {"enabled": True, "fact_interval_sec": 3600, "forecast_interval_sec": 3600}
    if RECORDER_SETTINGS_FILE.exists():
        current.update(json.loads(RECORDER_SETTINGS_FILE.read_text(encoding="utf-8")))

    current["enabled"] = not bool(current.get("enabled", True))

    RECORDER_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RECORDER_SETTINGS_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")

    # Immediate UI feedback. Background recorder will pick settings on next loop.
    runtime = {}
    if RUNTIME_FILE.exists():
        try:
            runtime = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
        except Exception:
            runtime = {}

    runtime["status"] = "live" if current["enabled"] else "paused"
    runtime["recorder_enabled"] = current["enabled"]
    runtime["fact_interval_sec"] = current.get("fact_interval_sec", 3600)
    runtime["forecast_interval_sec"] = current.get("forecast_interval_sec", 3600)
    RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_FILE.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": True, **current, "runtime": runtime}



@router.get("/db-preview")
def weather_db_preview(table: str = "weather_readings", limit: int = 20):
    import sqlite3
    from greenhouse_v17.services.weather_history_service import DB_PATH

    allowed = {
        "weather_readings": ["ts", "source", "metric", "value", "unit", "entity_id"],
        "weather_forecasts": ["recorded_at", "forecast_time", "entity_id", "condition", "temperature", "precipitation", "wind_speed"],
        "weather_comparison": ["ts", "real_temperature", "forecast_temperature", "delta_temperature", "real_humidity", "forecast_condition", "trust_score"],
    }

    if table not in allowed:
        return {"ok": False, "error": "table_not_allowed", "allowed": list(allowed)}

    limit = max(1, min(int(limit), 200))
    cols = allowed[table]
    col_sql = ", ".join(cols)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        f"SELECT {col_sql} FROM {table} ORDER BY rowid DESC LIMIT ?",
        (limit,),
    ).fetchall()
    con.close()

    return {
        "ok": True,
        "table": table,
        "columns": cols,
        "rows": [dict(r) for r in rows],
    }
