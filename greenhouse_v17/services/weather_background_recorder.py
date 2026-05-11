from __future__ import annotations
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from greenhouse_v17.services.weather_history_service import (
    record_weather_snapshot,
    record_forecast,
    record_comparison,
)
OUTSIDE_TEMP = "sensor.vlazhnost_nizhnii_gorshok_belyi_temperature"
OUTSIDE_HUM = "sensor.vlazhnost_nizhnii_gorshok_belyi_humidity"
FORECAST_ENTITY = "weather.home_assistant"
LAST_RUNTIME = "/home/mi/greenhouse_v17/data/weather/weather_runtime.json"
SETTINGS_FILE = "/home/mi/greenhouse_v17/data/weather/weather_recorder_settings.json"
FACT_INTERVAL_SEC = 3600
FORECAST_INTERVAL_SEC = 3600
def _settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"enabled": True, "fact_interval_sec": FACT_INTERVAL_SEC, "forecast_interval_sec": FORECAST_INTERVAL_SEC}

def _ha():
    return (
        os.getenv("HA_URL") or os.getenv("HA_BASE_URL") or "http://127.0.0.1:8123",
        os.getenv("HA_TOKEN"),
    )
def _get_state(entity_id: str):
    ha_url, token = _ha()
    req = urllib.request.Request(
        ha_url.rstrip() + "/api/states/" + entity_id,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
def _get_forecast():
    ha_url, token = _ha()
    payload = json.dumps({
        "entity_id": FORECAST_ENTITY,
        "type": "hourly"
    }).encode()
    req = urllib.request.Request(
        ha_url.rstrip() + "/api/services/weather/get_forecasts?return_response",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    data = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
    return data.get("service_response", {}).get(FORECAST_ENTITY, {}).get("forecast", [])
def run_once(write_forecast=False):
    temp = _get_state(OUTSIDE_TEMP)
    hum = _get_state(OUTSIDE_HUM)
    weather = _get_state(FORECAST_ENTITY)
    temp_val = float(temp.get("state"))
    hum_val = float(hum.get("state"))
    record_weather_snapshot(
        temp_val,
        hum_val,
        OUTSIDE_TEMP,
        OUTSIDE_HUM,
    )
    forecast = []
    forecast_now_temp = None
    if write_forecast:
        forecast = _get_forecast()
        record_forecast(FORECAST_ENTITY, forecast)
        if forecast:
            forecast_now_temp = forecast[0].get("temperature")
    comparison = record_comparison(
        temp_val,
        hum_val,
        forecast_now_temp,
        weather.get("state"),
    )
    runtime = {
        "status": "live",
        "last_write": datetime.now(timezone.utc).isoformat(),
        "fact_interval_sec": FACT_INTERVAL_SEC,
        "forecast_interval_sec": FORECAST_INTERVAL_SEC,
        "outside_temperature": temp_val,
        "outside_humidity": hum_val,
        "forecast_entity": FORECAST_ENTITY,
        "comparison": comparison,
    }
    os.makedirs(os.path.dirname(LAST_RUNTIME), exist_ok=True)
    with open(LAST_RUNTIME, "w", encoding="utf-8") as f:
        json.dump(runtime, f, ensure_ascii=False, indent=2)
    return runtime
def loop_forever():
    last_forecast = 0
    while True:
        now = time.time()
        try:
            write_forecast = (now - last_forecast) >= FORECAST_INTERVAL_SEC
            runtime = run_once(write_forecast=write_forecast)
            if write_forecast:
                last_forecast = now
            print("[weather-recorder]", runtime["last_write"])
        except Exception as e:
            print("[weather-recorder][ERROR]", repr(e))
        time.sleep(FACT_INTERVAL_SEC)
if __name__ == "__main__":
    loop_forever()
