#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import threading
import logging

from test_mode import run_silent_test_cycle

logger = logging.getLogger(__name__)

_scheduler_started = False


def _safe_int(value, default):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def silent_test_loop():
    interval_min = _safe_int(os.getenv("TEST_CYCLE_MINUTES", "30"), 30)
    enabled = os.getenv("TEST_CYCLE_ENABLED", "1").strip() == "1"

    logger.info("silent_test_loop started: enabled=%s interval=%s min", enabled, interval_min)

    while True:
        try:
            if enabled:
                ok, msg = run_silent_test_cycle()
                logger.info("silent_test_cycle: ok=%s msg=%s", ok, msg)
            else:
                logger.info("silent_test_cycle skipped: disabled")
        except Exception as e:
            logger.exception("silent_test_cycle failed: %s", e)

        time.sleep(max(60, interval_min * 60))


def start_scheduler_jobs():
    global _scheduler_started

    if _scheduler_started:
        logger.info("scheduler already started")
        return

    t = threading.Thread(target=silent_test_loop, daemon=True)
    t.start()

    _scheduler_started = True
    logger.info("scheduler thread started")
