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


def init_error_safety_runs_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS error_safety_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                error_id TEXT NOT NULL,
                parent_error_id TEXT,
                trace_id TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                source TEXT,
                mode TEXT,
                created_by TEXT,

                layer TEXT,
                event_type TEXT,
                severity TEXT,
                status TEXT,

                safety_related INTEGER,
                blocked INTEGER,
                auto_followup_created INTEGER,
                case_candidate_created INTEGER,

                action_key TEXT,
                entity_id TEXT,
                target_role TEXT,

                rule_name TEXT,
                error_code TEXT,
                message TEXT,
                details_text TEXT,

                decision TEXT,
                resolution TEXT,

                confidence REAL,
                note TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_error_safety_runs_error_id
            ON error_safety_runs(error_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_error_safety_runs_status
            ON error_safety_runs(status, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_error_safety_runs_entity
            ON error_safety_runs(entity_id, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_error_safety_runs_action_key
            ON error_safety_runs(action_key, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_error_safety_runs_severity
            ON error_safety_runs(severity, updated_at DESC)
            """
        )


def _to_int_bool(value: Optional[bool]) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0


def insert_error_safety_run(
    *,
    error_id: str,
    parent_error_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    source: Optional[str] = None,
    mode: Optional[str] = None,
    created_by: Optional[str] = None,
    layer: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    safety_related: Optional[bool] = None,
    blocked: Optional[bool] = None,
    auto_followup_created: Optional[bool] = None,
    case_candidate_created: Optional[bool] = None,
    action_key: Optional[str] = None,
    entity_id: Optional[str] = None,
    target_role: Optional[str] = None,
    rule_name: Optional[str] = None,
    error_code: Optional[str] = None,
    message: Optional[str] = None,
    details_text: Optional[str] = None,
    decision: Optional[str] = None,
    resolution: Optional[str] = None,
    confidence: Optional[float] = None,
    note: Optional[str] = None,
) -> None:
    init_error_safety_runs_db()
    now = utc_now_iso()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO error_safety_runs (
                error_id,
                parent_error_id,
                trace_id,
                created_at,
                updated_at,
                source,
                mode,
                created_by,
                layer,
                event_type,
                severity,
                status,
                safety_related,
                blocked,
                auto_followup_created,
                case_candidate_created,
                action_key,
                entity_id,
                target_role,
                rule_name,
                error_code,
                message,
                details_text,
                decision,
                resolution,
                confidence,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            ,
            (
                error_id,
                parent_error_id,
                trace_id,
                now,
                now,
                source,
                mode,
                created_by,
                layer,
                event_type,
                severity,
                status,
                _to_int_bool(safety_related),
                _to_int_bool(blocked),
                _to_int_bool(auto_followup_created),
                _to_int_bool(case_candidate_created),
                action_key,
                entity_id,
                target_role,
                rule_name,
                error_code,
                message,
                details_text,
                decision,
                resolution,
                confidence,
                note,
            ),
        )


def read_recent_error_safety_runs(limit: int = 50) -> list[dict]:
    init_error_safety_runs_db()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM error_safety_runs
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """
            ,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
