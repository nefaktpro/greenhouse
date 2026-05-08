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


def init_timer_runs_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS timer_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timer_id TEXT NOT NULL,
                parent_timer_id TEXT,
                trace_id TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                source TEXT,
                mode TEXT,
                created_by TEXT,

                timer_kind TEXT,
                timer_status TEXT,

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

                delay_seconds INTEGER,
                duration_seconds INTEGER,

                requested_at TEXT,
                scheduled_for TEXT,
                fired_at TEXT,
                completed_at TEXT,
                canceled_at TEXT,

                execution_ok INTEGER,
                execution_message TEXT,

                verify_ok INTEGER,
                verify_actual_state TEXT,

                verify_v2_ok INTEGER,
                verify_v2_status TEXT,
                verify_v2_reason TEXT,

                rollback_planned INTEGER,
                rollback_ok INTEGER,
                rollback_message TEXT,

                duration_ms INTEGER,
                latency_ms INTEGER,

                source_text TEXT,
                note TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timer_runs_timer_id
            ON timer_runs(timer_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timer_runs_status
            ON timer_runs(timer_status, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timer_runs_entity
            ON timer_runs(entity_id, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timer_runs_action_key
            ON timer_runs(action_key, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timer_runs_scheduled_for
            ON timer_runs(scheduled_for DESC)
            """
        )


def _to_int_bool(value: Optional[bool]) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0


def insert_timer_run(
    *,
    timer_id: str,
    parent_timer_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    source: Optional[str] = None,
    mode: Optional[str] = None,
    created_by: Optional[str] = None,
    timer_kind: Optional[str] = None,
    timer_status: Optional[str] = None,
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
    delay_seconds: Optional[int] = None,
    duration_seconds: Optional[int] = None,
    requested_at: Optional[str] = None,
    scheduled_for: Optional[str] = None,
    fired_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    canceled_at: Optional[str] = None,
    execution_ok: Optional[bool] = None,
    execution_message: Optional[str] = None,
    verify_ok: Optional[bool] = None,
    verify_actual_state: Optional[str] = None,
    verify_v2_ok: Optional[bool] = None,
    verify_v2_status: Optional[str] = None,
    verify_v2_reason: Optional[str] = None,
    rollback_planned: Optional[bool] = None,
    rollback_ok: Optional[bool] = None,
    rollback_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    latency_ms: Optional[int] = None,
    source_text: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    init_timer_runs_db()
    now = utc_now_iso()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO timer_runs (
                timer_id,
                parent_timer_id,
                trace_id,
                created_at,
                updated_at,
                source,
                mode,
                created_by,
                timer_kind,
                timer_status,
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
                delay_seconds,
                duration_seconds,
                requested_at,
                scheduled_for,
                fired_at,
                completed_at,
                canceled_at,
                execution_ok,
                execution_message,
                verify_ok,
                verify_actual_state,
                verify_v2_ok,
                verify_v2_status,
                verify_v2_reason,
                rollback_planned,
                rollback_ok,
                rollback_message,
                duration_ms,
                latency_ms,
                source_text,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timer_id,
                parent_timer_id,
                trace_id,
                now,
                now,
                source,
                mode,
                created_by,
                timer_kind,
                timer_status,
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
                delay_seconds,
                duration_seconds,
                requested_at,
                scheduled_for,
                fired_at,
                completed_at,
                canceled_at,
                _to_int_bool(execution_ok),
                execution_message,
                _to_int_bool(verify_ok),
                verify_actual_state,
                _to_int_bool(verify_v2_ok),
                verify_v2_status,
                verify_v2_reason,
                _to_int_bool(rollback_planned),
                _to_int_bool(rollback_ok),
                rollback_message,
                duration_ms,
                latency_ms,
                source_text,
                note,
            ),
        )


def read_recent_timer_runs(limit: int = 50) -> list[dict]:
    init_timer_runs_db()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM timer_runs
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
