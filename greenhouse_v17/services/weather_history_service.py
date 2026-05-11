from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

DB_PATH = Path("/home/mi/greenhouse_v17/data/weather/weather_history.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    con.execute("""
    CREATE TABLE IF NOT EXISTS weather_readings (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT NOT NULL,
      source TEXT NOT NULL,
      metric TEXT NOT NULL,
      value REAL,
      unit TEXT,
      entity_id TEXT,
      raw TEXT
    )
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS weather_forecasts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      recorded_at TEXT NOT NULL,
      forecast_time TEXT NOT NULL,
      entity_id TEXT NOT NULL,
      condition TEXT,
      temperature REAL,
      precipitation REAL,
      wind_speed REAL,
      raw TEXT
    )
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS weather_comparison (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT NOT NULL,
      real_temperature REAL,
      forecast_temperature REAL,
      delta_temperature REAL,
      real_humidity REAL,
      forecast_condition TEXT,
      trust_score REAL,
      raw TEXT
    )
    """)

    con.execute("CREATE INDEX IF NOT EXISTS idx_weather_ts ON weather_readings(ts)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_weather_metric ON weather_readings(metric)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_forecast_time ON weather_forecasts(forecast_time)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_comparison_ts ON weather_comparison(ts)")
    return con

def record_weather_snapshot(temp, hum, temp_entity, hum_entity):
    ts = datetime.now(timezone.utc).isoformat()
    with _conn() as con:
        con.execute(
            "INSERT INTO weather_readings(ts,source,metric,value,unit,entity_id,raw) VALUES(?,?,?,?,?,?,?)",
            (ts, "ha_outside_sensor", "outside_temperature", float(temp), "°C", temp_entity, None),
        )
        con.execute(
            "INSERT INTO weather_readings(ts,source,metric,value,unit,entity_id,raw) VALUES(?,?,?,?,?,?,?)",
            (ts, "ha_outside_sensor", "outside_humidity", float(hum), "%", hum_entity, None),
        )
    return {"ok": True, "ts": ts}

def record_forecast(entity_id: str, forecast: list[dict]):
    recorded_at = datetime.now(timezone.utc).isoformat()
    if not forecast:
        return {"ok": True, "count": 0}

    with _conn() as con:
        for item in forecast[:48]:
            con.execute(
                """
                INSERT INTO weather_forecasts(
                  recorded_at, forecast_time, entity_id, condition, temperature,
                  precipitation, wind_speed, raw
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    recorded_at,
                    item.get("datetime") or "",
                    entity_id,
                    item.get("condition"),
                    _float_or_none(item.get("temperature")),
                    _float_or_none(item.get("precipitation")),
                    _float_or_none(item.get("wind_speed")),
                    json.dumps(item, ensure_ascii=False),
                ),
            )
    return {"ok": True, "count": min(len(forecast), 48), "recorded_at": recorded_at}

def record_comparison(real_temp, real_hum, forecast_now_temp, forecast_condition):
    ts = datetime.now(timezone.utc).isoformat()

    real_temp_f = _float_or_none(real_temp)
    forecast_temp_f = _float_or_none(forecast_now_temp)
    delta = None
    trust = None

    if real_temp_f is not None and forecast_temp_f is not None:
        delta = round(real_temp_f - forecast_temp_f, 2)
        trust = max(0.0, min(1.0, round(1.0 - abs(delta) / 10.0, 2)))

    raw = {
        "real_temperature": real_temp_f,
        "forecast_temperature": forecast_temp_f,
        "delta_temperature": delta,
        "real_humidity": _float_or_none(real_hum),
        "forecast_condition": forecast_condition,
        "trust_score": trust,
    }

    with _conn() as con:
        con.execute(
            """
            INSERT INTO weather_comparison(
              ts, real_temperature, forecast_temperature, delta_temperature,
              real_humidity, forecast_condition, trust_score, raw
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                ts,
                raw["real_temperature"],
                raw["forecast_temperature"],
                raw["delta_temperature"],
                raw["real_humidity"],
                raw["forecast_condition"],
                raw["trust_score"],
                json.dumps(raw, ensure_ascii=False),
            ),
        )

    return raw

def recent_weather_history(hours=24):
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _conn() as con:
        rows = con.execute(
            "SELECT ts,metric,value,unit,entity_id FROM weather_readings WHERE ts >= ? ORDER BY ts ASC",
            (since,),
        ).fetchall()

        cmp_rows = con.execute(
            "SELECT ts,real_temperature,forecast_temperature,delta_temperature,real_humidity,forecast_condition,trust_score FROM weather_comparison WHERE ts >= ? ORDER BY ts ASC",
            (since,),
        ).fetchall()

    out = {
        "outside_temperature": [],
        "outside_humidity": [],
        "comparison": [],
    }

    for r in rows:
        if r["metric"] in out:
            out[r["metric"]].append(dict(r))

    out["comparison"] = [dict(r) for r in cmp_rows]
    return out

def db_summary():
    with _conn() as con:
        tables = {}
        for table in ["weather_readings", "weather_forecasts", "weather_comparison"]:
            row = con.execute(f"SELECT COUNT(*) AS c, MIN(rowid) AS min_id, MAX(rowid) AS max_id FROM {table}").fetchone()
            tables[table] = dict(row)
    return {"db_path": str(DB_PATH), "tables": tables}

def _float_or_none(x):
    try:
        if x in (None, "", "unknown", "unavailable"):
            return None
        return float(x)
    except Exception:
        return None
