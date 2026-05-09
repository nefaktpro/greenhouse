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


def init_validation_rejection_runs_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS validation_rejection_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                validation_id TEXT NOT NULL,
                parent_validation_id TEXT,
                trace_id TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                source TEXT,
                mode TEXT,
                created_by TEXT,

                layer TEXT,
                candidate_type TEXT,

                action_key TEXT,
                entity_id TEXT,
                target_role TEXT,

                status TEXT,
                rejection_reason TEXT,
                rule_name TEXT,
                safety_blocked INTEGER,

                message TEXT,
                suggested_resolution TEXT,

                confidence REAL,
                note TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_validation_rejection_runs_validation_id
            ON validation_rejection_runs(validation_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_validation_rejection_runs_status
            ON validation_rejection_runs(status, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_validation_rejection_runs_entity
            ON validation_rejection_runs(entity_id, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_validation_rejection_runs_action_key
            ON validation_rejection_runs(action_key, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_validation_rejection_runs_rule_name
            ON validation_rejection_runs(rule_name, updated_at DESC)
            """
        )


def _to_int_bool(value: Optional[bool]) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0


def insert_validation_rejection_run(
    *,
    validation_id: str,
    parent_validation_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    source: Optional[str] = None,
    mode: Optional[str] = None,
    created_by: Optional[str] = None,
    layer: Optional[str] = None,
    candidate_type: Optional[str] = None,
    action_key: Optional[str] = None,
    entity_id: Optional[str] = None,
    target_role: Optional[str] = None,
    status: Optional[str] = None,
    rejection_reason: Optional[str] = None,
    rule_name: Optional[str] = None,
    safety_blocked: Optional[bool] = None,
    message: Optional[str] = None,
    suggested_resolution: Optional[str] = None,
    confidence: Optional[float] = None,
    note: Optional[str] = None,
) -> None:
    init_validation_rejection_runs_db()
    now = utc_now_iso()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO validation_rejection_runs (
                validation_id,
                parent_validation_id,
                trace_id,
                created_at,
                updated_at,
                source,
                mode,
                created_by,
                layer,
                candidate_type,
                action_key,
                entity_id,
                target_role,
                status,
                rejection_reason,
                rule_name,
                safety_blocked,
                message,
                suggested_resolution,
                confidence,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                validation_id,
                parent_validation_id,
                trace_id,
                now,
                now,
                source,
                mode,
                created_by,
                layer,
                candidate_type,
                action_key,
                entity_id,
                target_role,
                status,
                rejection_reason,
                rule_name,
                _to_int_bool(safety_blocked),
                message,
                suggested_resolution,
                confidence,
                note,
            ),
        )


def read_recent_validation_rejection_runs(limit: int = 50) -> list[dict]:
    init_validation_rejection_runs_db()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM validation_rejection_runs
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
