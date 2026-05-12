from __future__ import annotations

import logging

from greenhouse_v17.services.camera_snapshot_service import start_camera_daily_worker

log = logging.getLogger(__name__)

_STARTED = False


def start_background_workers() -> None:
    """
    Central startup bootstrap for background workers.

    Rules:
    - UI/routes do not start workers.
    - api.py only calls this bootstrap on application startup.
    - Each worker must be idempotent and safe for repeated startup calls.
    """
    global _STARTED
    if _STARTED:
        return

    _STARTED = True

    try:
        start_camera_daily_worker()
        log.info("camera_daily_worker started")
    except Exception:
        log.exception("failed to start camera_daily_worker")
