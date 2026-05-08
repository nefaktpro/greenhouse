from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

DB_PATH = Path("data/logs/unified_logs.db")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    ensure_parent_dir()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schedule_runs_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id TEXT NOT NULL,
                parent_schedule_id TEXT,
                trace_id TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                source TEXT,
                mode TEXT,
                created_by TEXT,

                schedule_kind TEXT,
                schedule_status TEXT,

                enabled INTEGER,
                ask_required INTEGER,
                ask_created INTEGER,
                ask_confirmed INTEGER,
                ask_canceled INTEGER,

                target_role TEXT,
                zone TEXT,
                entity_id TEXT,

                action_key TEXT,
                off_action_key TEXT,
                operation TEXT,
                expected_state TEXT,

                cron_expr TEXT,
                timezone TEXT,

                requested_at TEXT,
                next_run_at TEXT,
                last_run_at TEXT,
                completed_at TEXT,
                canceled_at TEXT,

                execution_ok INTEGER,
                execution_message TEXT,

                verify_ok INTEGER,
                verify_actual_state TEXT,

                verify_v2_ok INTEGER,
                verify_v2_status TEXT,
                verify_v2_reason TEXT,

                duration_ms INTEGER,
                latency_ms INTEGER,

                source_text TEXT,
                note TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schedule_runs_schedule_id
            ON schedule_runs(schedule_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schedule_runs_status
            ON schedule_runs(schedule_status, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schedule_runs_entity
            ON schedule_runs(entity_id, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schedule_runs_action_key
            ON schedule_runs(action_key, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schedule_runs_next_run_at
            ON schedule_runs(next_run_at DESC)
            """
        )


def _to_int_bool(value: Optional[bool]) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0


def insert_schedule_run(
    *,
    schedule_id: str,
    parent_schedule_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    source: Optional[str] = None,
    mode: Optional[str] = None,
    created_by: Optional[str] = None,
    schedule_kind: Optional[str] = None,
    schedule_status: Optional[str] = None,
    enabled: Optional[bool] = None,
    ask_required: Optional[bool] = None,
    ask_created: Optional[bool] = None,
    ask_confirmed: Optional[bool] = None,
    ask_canceled: Optional[bool] = None,
    target_role: Optional[str] = None,
    zone: Optional[str] = None,
    entity_id: Optional[str] = None,
    action_key: Optional[str] = None,
    off_action_key: Optional[str] = None,
    operation: Optional[str] = None,
    expected_state: Optional[str] = None,
    cron_expr: Optional[str] = None,
    timezone: Optional[str] = None,
    requested_at: Optional[str] = None,
    next_run_at: Optional[str] = None,
    last_run_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    canceled_at: Optional[str] = None,
    execution_ok: Optional[bool] = None,
    execution_message: Optional[str] = None,
    verify_ok: Optional[bool] = None,
    verify_actual_state: Optional[str] = None,
    verify_v2_ok: Optional[bool] = None,
    verify_v2_status: Optional[str] = None,
    verify_v2_reason: Optional[str] = None,
    duration_ms: Optional[int] = None,
    latency_ms: Optional[int] = None,
    source_text: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    init_schedule_runs_db()
    now = utc_now_iso()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO schedule_runs (
                schedule_id,
                parent_schedule_id,
                trace_id,
                created_at,
                updated_at,
                source,
                mode,
                created_by,
                schedule_kind,
                schedule_status,
                enabled,
                ask_required,
                ask_created,
                ask_confirmed,
                ask_canceled,
                target_role,
                zone,
                entity_id,
                action_key,
                off_action_key,
                operation,
                expected_state,
                cron_expr,
                timezone,
                requested_at,
                next_run_at,
                last_run_at,
                completed_at,
                canceled_at,
                execution_ok,
                execution_message,
                verify_ok,
                verify_actual_state,
                verify_v2_ok,
                verify_v2_status,
                verify_v2_reason,
                duration_ms,
                latency_ms,
                source_text,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule_id,
                parent_schedule_id,
                trace_id,
                now,
                now,
                source,
                mode,
                created_by,
                schedule_kind,
                schedule_status,
                _to_int_bool(enabled),
                _to_int_bool(ask_required),
                _to_int_bool(ask_created),
                _to_int_bool(ask_confirmed),
                _to_int_bool(ask_canceled),
                target_role,
                zone,
                entity_id,
                action_key,
                off_action_key,
                operation,
                expected_state,
                cron_expr,
                timezone,
                requested_at,
                next_run_at,
                last_run_at,
                completed_at,
                canceled_at,
                _to_int_bool(execution_ok),
                execution_message,
                _to_int_bool(verify_ok),
                verify_actual_state,
                _to_int_bool(verify_v2_ok),
                verify_v2_status,
                verify_v2_reason,
                duration_ms,
                latency_ms,
                source_text,
                note,
            ),
        )


def read_recent_schedule_runs(limit: int = 50) -> list[dict]:
    init_schedule_runs_db()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM schedule_runs
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
