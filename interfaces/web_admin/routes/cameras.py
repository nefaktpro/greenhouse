from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from greenhouse_v17.services.camera_snapshot_service import (
    get_camera_states,
    get_settings,
    list_cameras,
    recent_logs,
    recent_photos,
    read_live_image,
    run_daily_snapshot_if_due,
    create_photo_observation,
    recent_observations,
    save_settings,
    take_all_snapshots,
    take_snapshot,
)

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()



class CameraSettingsIn(BaseModel):
    daily_enabled: bool = True
    daily_time: str = "10:00"


class SnapshotIn(BaseModel):
    camera_id: str
    source: str = "manual"


class ObservationIn(BaseModel):
    photo_log_id: str | None = None
    id: str | None = None
    camera_id: str | None = None
    camera_name: str | None = None
    entity_id: str | None = None
    zone: str | None = None
    file_path: str | None = None
    category: str = "other"
    importance: str = "medium"
    text: str = ""
    source: str = "user"


@router.get("/web/cameras")
def cameras_page(request: Request):
    return templates.TemplateResponse(
        request,
        "cameras.html",
        {
            "request": request,
            "cameras": list_cameras(),
            "settings": get_settings(),
        },
    )


@router.get("/api/cameras/status")
def api_cameras_status():
    return get_camera_states()


@router.get("/api/cameras/settings")
def api_cameras_settings():
    return {"ok": True, "settings": get_settings()}


@router.post("/api/cameras/settings")
def api_cameras_save_settings(payload: CameraSettingsIn):
    return {"ok": True, "settings": save_settings(payload.model_dump())}


@router.post("/api/cameras/snapshot")
def api_camera_snapshot(payload: SnapshotIn):
    return take_snapshot(payload.camera_id, source=payload.source or "manual")


@router.post("/api/cameras/snapshot-all")
def api_camera_snapshot_all():
    return take_all_snapshots(source="manual_all")


@router.get("/api/cameras/logs")
def api_camera_logs(limit: int = 50):
    return recent_logs(limit=limit)



@router.get("/api/cameras/live-image")
def api_camera_live_image(camera_id: str):
    ok, content, content_type = read_live_image(camera_id)
    if not ok:
        return {"ok": False, "error": content_type}
    return Response(content=content, media_type=content_type)


@router.get("/api/cameras/file")
def api_camera_file(path: str):
    p = Path(path)
    base = Path("/home/mi/greenhouse_v17/data/photos").resolve()
    resolved = p.resolve()
    if not str(resolved).startswith(str(base)):
        return {"ok": False, "error": "path_not_allowed"}
    if not resolved.exists():
        return {"ok": False, "error": "file_not_found"}
    return FileResponse(str(resolved))


@router.get("/api/sql-logs/cameras/recent")
def api_sql_logs_cameras_recent(limit: int = 100):
    return recent_logs(limit=limit)


@router.post("/api/cameras/daily/run-if-due")
def api_camera_daily_run_if_due():
    return run_daily_snapshot_if_due()


@router.get("/api/cameras/photos")
def api_camera_recent_photos(limit: int = 100, camera_id: str | None = None, source: str | None = None):
    return recent_photos(limit=limit, camera_id=camera_id, source=source)


@router.post("/api/cameras/observations")
def api_camera_create_observation(payload: ObservationIn):
    return create_photo_observation(payload.model_dump())


@router.get("/api/cameras/observations")
def api_camera_observations(limit: int = 50, camera_id: str | None = None):
    return recent_observations(limit=limit, camera_id=camera_id)
