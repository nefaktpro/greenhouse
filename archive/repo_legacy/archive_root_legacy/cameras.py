#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests

CAMERAS = [
    {"id": "camera.smart_camera_2", "name": "🎥 Веранда (общий план)", "device_id": "2.4"},
    {"id": "camera.kamera_verkhnii_stellazh_obshchii_plan", "name": "📸 Верхний правый", "device_id": "27.79"},
    {"id": "camera.kamera_na_ogurtsy", "name": "📸 Верхний левый", "device_id": "28.80"},
    {"id": "camera.security_camera_4_2", "name": "📸 Нижний левый", "device_id": "32.85"},
    {"id": "camera.kamera_vertikalnaia_pomidor", "name": "📸 Нижний правый", "device_id": "33.86"},
]


def _load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
_load_env_file(ENV_PATH)

HA_URL = (os.getenv("HA_BASE_URL") or os.getenv("HA_URL") or "").rstrip("/")
HA_TOKEN = os.getenv("HA_TOKEN", "").strip()

HA_HEADERS = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json",
}


def get_camera(camera_id: str):
    """Получает фото с камеры через HA camera_proxy."""
    if not HA_URL or not HA_TOKEN:
        return None
    try:
        r = requests.get(
            f"{HA_URL}/api/camera_proxy/{camera_id}",
            headers=HA_HEADERS,
            timeout=20,
        )
        if r.status_code == 200:
            return r.content
    except Exception:
        return None
    return None


def get_camera_name(camera_id: str) -> str:
    for cam in CAMERAS:
        if cam["id"] == camera_id:
            return cam["name"]
    return "Камера"


def get_all_cameras():
    return CAMERAS


def get_report_cameras():
    """
    Камеры для утреннего отчёта.
    Проблемную общую камеру пока исключаем.
    """
    skip_ids = {
        "camera.smart_camera_2",  # 🎥 Веранда (общий план) пока не отвечает
    }
    return [cam for cam in CAMERAS if cam["id"] not in skip_ids]
