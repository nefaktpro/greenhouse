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


def init_followup_runs_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS followup_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                followup_id TEXT NOT NULL,
                parent_followup_id TEXT,
                trace_id TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                source TEXT,
                mode TEXT,
                created_by TEXT,

                followup_status TEXT,
                followup_kind TEXT,

                linked_log_type TEXT,
                linked_log_id TEXT,
                linked_action_key TEXT,
                linked_entity_id TEXT,
                linked_target_role TEXT,

                reason TEXT,
                expected_check TEXT,
                actual_result TEXT,
                decision TEXT,

                scheduled_for TEXT,
                started_at TEXT,
                completed_at TEXT,
                canceled_at TEXT,

                execution_ok INTEGER,
                verify_ok INTEGER,
                verify_v2_ok INTEGER,
                verify_v2_status TEXT,

                confidence REAL,
                source_text TEXT,
                note TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_followup_runs_followup_id
            ON followup_runs(followup_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_followup_runs_status
            ON followup_runs(followup_status, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_followup_runs_entity
            ON followup_runs(linked_entity_id, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_followup_runs_action_key
            ON followup_runs(linked_action_key, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_followup_runs_scheduled_for
            ON followup_runs(scheduled_for DESC)
            """
        )


def _to_int_bool(value: Optional[bool]) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0


def insert_followup_run(
    *,
    followup_id: str,
    parent_followup_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    source: Optional[str] = None,
    mode: Optional[str] = None,
    created_by: Optional[str] = None,
    followup_status: Optional[str] = None,
    followup_kind: Optional[str] = None,
    linked_log_type: Optional[str] = None,
    linked_log_id: Optional[str] = None,
    linked_action_key: Optional[str] = None,
    linked_entity_id: Optional[str] = None,
    linked_target_role: Optional[str] = None,
    reason: Optional[str] = None,
    expected_check: Optional[str] = None,
    actual_result: Optional[str] = None,
    decision: Optional[str] = None,
    scheduled_for: Optional[str] = None,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    canceled_at: Optional[str] = None,
    execution_ok: Optional[bool] = None,
    verify_ok: Optional[bool] = None,
    verify_v2_ok: Optional[bool] = None,
    verify_v2_status: Optional[str] = None,
    confidence: Optional[float] = None,
    source_text: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    init_followup_runs_db()
    now = utc_now_iso()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO followup_runs (
                followup_id,
                parent_followup_id,
                trace_id,
                created_at,
                updated_at,
                source,
                mode,
                created_by,
                followup_status,
                followup_kind,
                linked_log_type,
                linked_log_id,
                linked_action_key,
                linked_entity_id,
                linked_target_role,
                reason,
                expected_check,
                actual_result,
                decision,
                scheduled_for,
                started_at,
                completed_at,
                canceled_at,
                execution_ok,
                verify_ok,
                verify_v2_ok,
                verify_v2_status,
                confidence,
                source_text,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                followup_id,
                parent_followup_id,
                trace_id,
                now,
                now,
                source,
                mode,
                created_by,
                followup_status,
                followup_kind,
                linked_log_type,
                linked_log_id,
                linked_action_key,
                linked_entity_id,
                linked_target_role,
                reason,
                expected_check,
                actual_result,
                decision,
                scheduled_for,
                started_at,
                completed_at,
                canceled_at,
                _to_int_bool(execution_ok),
                _to_int_bool(verify_ok),
                _to_int_bool(verify_v2_ok),
                verify_v2_status,
                confidence,
                source_text,
                note,
            ),
        )


def read_recent_followup_runs(limit: int = 50) -> list[dict]:
    init_followup_runs_db()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM followup_runs
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
