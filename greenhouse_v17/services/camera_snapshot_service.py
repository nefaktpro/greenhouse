from __future__ import annotations

import json
import os
import sqlite3
import time
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

BASE_DIR = Path("/home/mi/greenhouse_v17")
PHOTO_DIR = BASE_DIR / "data" / "photos"
SETTINGS_PATH = BASE_DIR / "data" / "runtime" / "camera_settings.json"
DB_PATH = BASE_DIR / "data" / "logs" / "unified_logs.db"

CAMERAS = [
    {
        "camera_id": "cam_overview",
        "name": "Камера общий план",
        "entity_id": "camera.smart_camera_2",
        "zone": "overview",
        "position": "общий план",
        "logical_role": "camera_overview",
    },
    {
        "camera_id": "cam_lower_right",
        "name": "Нижний ряд справа",
        "entity_id": "camera.kamera_vertikalnaia_pomidor",
        "zone": "lower_right",
        "position": "нижний ряд справа",
        "logical_role": "camera_lower_right",
    },
    {
        "camera_id": "cam_lower_left",
        "name": "Нижний ярус слева",
        "entity_id": "camera.security_camera_4_2",
        "zone": "lower_left",
        "position": "нижний ярус слева",
        "logical_role": "camera_lower_left",
    },
    {
        "camera_id": "cam_upper_right",
        "name": "Верхний ярус справа",
        "entity_id": "camera.kamera_verkhnii_stellazh_obshchii_plan",
        "zone": "upper_right",
        "position": "верхний ярус справа",
        "logical_role": "camera_upper_right",
    },
    {
        "camera_id": "cam_upper_left",
        "name": "Верхний слева / огурцы",
        "entity_id": "camera.kamera_na_ogurtsy",
        "zone": "upper_left",
        "position": "верхний слева / огурцы",
        "logical_role": "camera_upper_left",
    },
]

DEFAULT_SETTINGS = {
    "daily_enabled": True,
    "daily_time": "10:00",
    "photo_dir": str(PHOTO_DIR),
    "last_daily_run_date": None,
    "last_daily_run_at": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ha_cfg() -> tuple[str, str]:
    url = (
        os.environ.get("HA_URL")
        or os.environ.get("HOME_ASSISTANT_URL")
        or "http://127.0.0.1:8123"
    ).rstrip("/")
    token = (
        os.environ.get("HA_TOKEN")
        or os.environ.get("HOME_ASSISTANT_TOKEN")
        or os.environ.get("SUPERVISOR_TOKEN")
        or ""
    )
    return url, token


def _headers() -> Dict[str, str]:
    _, token = _ha_cfg()
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def init_camera_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS camera_photo_log (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                camera_id TEXT NOT NULL,
                camera_name TEXT,
                entity_id TEXT NOT NULL,
                zone TEXT,
                source TEXT NOT NULL,
                event TEXT NOT NULL,
                status TEXT NOT NULL,
                file_path TEXT,
                file_size INTEGER,
                duration_ms INTEGER,
                error TEXT,
                meta_json TEXT
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_camera_photo_log_ts ON camera_photo_log(ts)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_camera_photo_log_camera ON camera_photo_log(camera_id)")
        for col, typ in [
            ("observation_category", "TEXT"),
            ("observation_importance", "TEXT"),
            ("observation_text", "TEXT"),
            ("observation_status", "TEXT"),
            ("observation_at", "TEXT")
        ]:
            try:
                con.execute(f"ALTER TABLE camera_photo_log ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS camera_observations (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                photo_log_id TEXT,
                camera_id TEXT,
                camera_name TEXT,
                entity_id TEXT,
                zone TEXT,
                file_path TEXT,
                category TEXT,
                importance TEXT,
                text TEXT,
                source TEXT,
                status TEXT,
                meta_json TEXT
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_camera_observations_ts ON camera_observations(ts)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_camera_observations_camera ON camera_observations(camera_id)")
        con.commit()


def _log(row: Dict[str, Any]) -> None:
    init_camera_db()
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            INSERT OR REPLACE INTO camera_photo_log
            (id, ts, camera_id, camera_name, entity_id, zone, source, event, status,
             file_path, file_size, duration_ms, error, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("id") or f"phlog_{uuid.uuid4().hex[:12]}",
                row.get("ts") or _now_iso(),
                row.get("camera_id"),
                row.get("camera_name") or row.get("name"),
                row.get("entity_id"),
                row.get("zone"),
                row.get("source", "unknown"),
                row.get("event", "snapshot"),
                row.get("status", "unknown"),
                row.get("file_path"),
                row.get("file_size"),
                row.get("duration_ms"),
                row.get("error"),
                json.dumps(row.get("meta", {}), ensure_ascii=False),
            ),
        )
        con.commit()


def get_settings() -> Dict[str, Any]:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    save_settings(DEFAULT_SETTINGS)
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    data = {**DEFAULT_SETTINGS, **settings}
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def list_cameras() -> List[Dict[str, Any]]:
    return [dict(c) for c in CAMERAS]


def _find_camera(camera_id: str) -> Optional[Dict[str, Any]]:
    for cam in CAMERAS:
        if cam["camera_id"] == camera_id or cam["entity_id"] == camera_id:
            return dict(cam)
    return None


def get_camera_states() -> Dict[str, Any]:
    url, _ = _ha_cfg()
    items = []
    for cam in CAMERAS:
        state = "unknown"
        attrs: Dict[str, Any] = {}
        ok = False
        error = None
        try:
            r = requests.get(
                f"{url}/api/states/{cam['entity_id']}",
                headers=_headers(),
                timeout=6,
            )
            if r.status_code == 200:
                payload = r.json()
                state = payload.get("state", "unknown")
                attrs = payload.get("attributes", {}) or {}
                ok = state not in ("unavailable", "unknown")
            else:
                error = f"ha_http_{r.status_code}"
        except Exception as exc:
            error = str(exc)

        items.append(
            {
                **cam,
                "state": state,
                "ok": ok,
                "error": error,
                "entity_picture": attrs.get("entity_picture"),
                "friendly_name": attrs.get("friendly_name"),
            }
        )
    return {"ok": True, "items": items, "settings": get_settings()}


def _snapshot_path(cam: Dict[str, Any], source: str) -> Path:
    now = datetime.now()
    folder = PHOTO_DIR / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
    folder.mkdir(parents=True, exist_ok=True)
    safe = cam["camera_id"].replace("/", "_")
    return folder / f"{now.strftime('%H%M%S')}_{safe}_{source}.jpg"


def _camera_proxy_url(cam: Dict[str, Any]) -> Optional[str]:
    url, _ = _ha_cfg()
    try:
        r = requests.get(
            f"{url}/api/states/{cam['entity_id']}",
            headers=_headers(),
            timeout=6,
        )
        if r.status_code != 200:
            return None
        attrs = (r.json().get("attributes") or {})
        ep = attrs.get("entity_picture")
        if not ep:
            return None
        if ep.startswith("http"):
            return ep
        return f"{url}{ep}"
    except Exception:
        return None


def read_live_image(camera_id: str) -> tuple[bool, bytes, str]:
    cam = _find_camera(camera_id)
    if not cam:
        return False, b"", "camera_not_found"
    proxy = _camera_proxy_url(cam)
    if not proxy:
        return False, b"", "entity_picture_not_found"

    last_error = "unknown"
    for attempt in range(1, 4):
        try:
            r = requests.get(proxy, headers=_headers(), timeout=15)
            if r.status_code == 200 and r.content:
                return True, r.content, "image/jpeg"
            last_error = f"ha_proxy_http_{r.status_code}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.7 * attempt)

    return False, b"", last_error


def take_snapshot(camera_id: str, source: str = "manual") -> Dict[str, Any]:
    cam = _find_camera(camera_id)
    if not cam:
        return {"ok": False, "error": "camera_not_found", "camera_id": camera_id}

    path = _snapshot_path(cam, source)
    started = time.time()
    log_id = f"phlog_{uuid.uuid4().hex[:12]}"

    ok, content, err = read_live_image(cam["camera_id"])
    duration_ms = int((time.time() - started) * 1000)

    if not ok:
        _log({
            **cam,
            "id": log_id,
            "source": source,
            "event": "photo_failed",
            "status": "failed",
            "duration_ms": duration_ms,
            "error": err,
        })
        return {"ok": False, "error": err, **cam}

    try:
        path.write_bytes(content)
        size = path.stat().st_size if path.exists() else 0
        status = "ok" if size > 0 else "failed"
        error = None if size > 0 else "empty_file"

        _log({
            **cam,
            "id": log_id,
            "source": source,
            "event": "photo_taken" if status == "ok" else "photo_failed",
            "status": status,
            "file_path": str(path) if status == "ok" else None,
            "file_size": size,
            "duration_ms": duration_ms,
            "error": error,
        })

        return {
            "ok": status == "ok",
            "status": status,
            "error": error,
            "file_path": str(path) if status == "ok" else None,
            "file_size": size,
            "duration_ms": duration_ms,
            **cam,
        }
    except Exception as exc:
        _log({
            **cam,
            "id": log_id,
            "source": source,
            "event": "photo_failed",
            "status": "failed",
            "duration_ms": duration_ms,
            "error": str(exc),
        })
        return {"ok": False, "error": str(exc), **cam}


def should_run_daily_snapshot(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    settings = get_settings()
    if not settings.get("daily_enabled", True):
        return False

    daily_time = str(settings.get("daily_time") or "10:00")
    today = now.strftime("%Y-%m-%d")

    if settings.get("last_daily_run_date") == today:
        return False

    try:
        hh, mm = [int(x) for x in daily_time.split(":")[:2]]
    except Exception:
        hh, mm = 10, 0

    return now.hour > hh or (now.hour == hh and now.minute >= mm)


def run_daily_snapshot_if_due() -> Dict[str, Any]:
    now = datetime.now()
    if not should_run_daily_snapshot(now):
        return {"ok": True, "ran": False, "reason": "not_due", "settings": get_settings()}

    result = take_all_snapshots(source="daily_snapshot")
    settings = get_settings()
    settings["last_daily_run_date"] = now.strftime("%Y-%m-%d")
    settings["last_daily_run_at"] = now.isoformat()
    save_settings(settings)

    return {"ok": result.get("ok", False), "ran": True, "result": result, "settings": settings}


def recent_photos(limit: int = 100, camera_id: Optional[str] = None, source: Optional[str] = None) -> Dict[str, Any]:
    init_camera_db()
    where = ["status = 'ok'", "file_path IS NOT NULL"]
    args: list[Any] = []
    if camera_id:
        where.append("camera_id = ?")
        args.append(camera_id)
    if source:
        where.append("source = ?")
        args.append(source)

    sql = f"""
        SELECT * FROM camera_photo_log
        WHERE {' AND '.join(where)}
        ORDER BY ts DESC
        LIMIT ?
    """
    args.append(int(limit))

    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, args).fetchall()

    return {"ok": True, "items": [dict(r) for r in rows]}


def take_all_snapshots(source: str = "manual_all") -> Dict[str, Any]:
    results = [take_snapshot(cam["camera_id"], source=source) for cam in CAMERAS]
    return {
        "ok": all(r.get("ok") for r in results),
        "results": results,
    }


def recent_logs(limit: int = 50) -> Dict[str, Any]:
    init_camera_db()
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT * FROM camera_photo_log
            ORDER BY ts DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return {"ok": True, "items": [dict(r) for r in rows]}


def create_photo_observation(payload: Dict[str, Any]) -> Dict[str, Any]:
    init_camera_db()
    photo_id = payload.get("photo_log_id") or payload.get("id")
    if not photo_id:
        return {"ok": False, "error": "photo_log_id_required"}

    obs_at = _now_iso()
    category = payload.get("category") or "other"
    importance = payload.get("importance") or "medium"
    text = payload.get("text") or ""

    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        con.execute(
            """
            UPDATE camera_photo_log
            SET observation_category = ?,
                observation_importance = ?,
                observation_text = ?,
                observation_status = 'active',
                observation_at = ?
            WHERE id = ?
            """,
            (category, importance, text, obs_at, photo_id),
        )
        con.commit()
        row = con.execute("SELECT * FROM camera_photo_log WHERE id = ?", (photo_id,)).fetchone()

    if not row:
        return {"ok": False, "error": "photo_not_found", "photo_log_id": photo_id}

    return {"ok": True, "observation": dict(row)}


def recent_observations(limit: int = 50, camera_id: Optional[str] = None) -> Dict[str, Any]:
    init_camera_db()

    where = ["(observation_status = 'active' OR observation_text IS NOT NULL)"]
    args: list[Any] = []

    if camera_id:
        where.append("camera_id = ?")
        args.append(camera_id)

    sql = f"""
        SELECT *
        FROM camera_photo_log
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(observation_at, ts) DESC
        LIMIT ?
    """
    args.append(int(limit))

    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, args).fetchall()

    return {"ok": True, "items": [dict(r) for r in rows]}


_CAMERA_DAILY_WORKER_STARTED = False


def start_camera_daily_worker(interval_sec: int = 60) -> None:
    """
    Background worker for daily camera snapshots.
    Uses camera_settings.json:
    - daily_enabled
    - daily_time
    - last_daily_run_date
    """
    global _CAMERA_DAILY_WORKER_STARTED
    if _CAMERA_DAILY_WORKER_STARTED:
        return

    _CAMERA_DAILY_WORKER_STARTED = True

    def _loop() -> None:
        while True:
            try:
                run_daily_snapshot_if_due()
            except Exception as exc:
                try:
                    _log({
                        "camera_id": "camera_daily_worker",
                        "camera_name": "Camera Daily Worker",
                        "entity_id": "system.camera_daily_worker",
                        "zone": "system",
                        "source": "camera_daily_worker",
                        "event": "daily_worker_error",
                        "status": "failed",
                        "error": str(exc),
                    })
                except Exception:
                    pass
            time.sleep(max(30, int(interval_sec)))

    threading.Thread(
        target=_loop,
        name="camera_daily_worker",
        daemon=True,
    ).start()
