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


def init_case_runs_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS case_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                case_id TEXT NOT NULL,
                parent_case_id TEXT,
                trace_id TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                source TEXT,
                mode TEXT,
                created_by TEXT,

                case_status TEXT,
                case_kind TEXT,
                title TEXT,
                summary TEXT,

                linked_test_id TEXT,
                linked_followup_id TEXT,
                linked_error_id TEXT,
                linked_validation_id TEXT,

                action_key TEXT,
                entity_id TEXT,
                target_role TEXT,

                confidence REAL,
                validated INTEGER,
                repeatable INTEGER,
                important INTEGER,

                learning TEXT,
                recommended_action TEXT,
                note TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_case_runs_case_id
            ON case_runs(case_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_case_runs_status
            ON case_runs(case_status, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_case_runs_entity
            ON case_runs(entity_id, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_case_runs_action_key
            ON case_runs(action_key, updated_at DESC)
            """
        )


def _to_int_bool(value: Optional[bool]) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0


def insert_case_run(
    *,
    case_id: str,
    parent_case_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    source: Optional[str] = None,
    mode: Optional[str] = None,
    created_by: Optional[str] = None,
    case_status: Optional[str] = None,
    case_kind: Optional[str] = None,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    linked_test_id: Optional[str] = None,
    linked_followup_id: Optional[str] = None,
    linked_error_id: Optional[str] = None,
    linked_validation_id: Optional[str] = None,
    action_key: Optional[str] = None,
    entity_id: Optional[str] = None,
    target_role: Optional[str] = None,
    confidence: Optional[float] = None,
    validated: Optional[bool] = None,
    repeatable: Optional[bool] = None,
    important: Optional[bool] = None,
    learning: Optional[str] = None,
    recommended_action: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    init_case_runs_db()
    now = utc_now_iso()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO case_runs (
                case_id,
                parent_case_id,
                trace_id,
                created_at,
                updated_at,
                source,
                mode,
                created_by,
                case_status,
                case_kind,
                title,
                summary,
                linked_test_id,
                linked_followup_id,
                linked_error_id,
                linked_validation_id,
                action_key,
                entity_id,
                target_role,
                confidence,
                validated,
                repeatable,
                important,
                learning,
                recommended_action,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                parent_case_id,
                trace_id,
                now,
                now,
                source,
                mode,
                created_by,
                case_status,
                case_kind,
                title,
                summary,
                linked_test_id,
                linked_followup_id,
                linked_error_id,
                linked_validation_id,
                action_key,
                entity_id,
                target_role,
                confidence,
                _to_int_bool(validated),
                _to_int_bool(repeatable),
                _to_int_bool(important),
                learning,
                recommended_action,
                note,
            ),
        )


def read_recent_case_runs(limit: int = 50) -> list[dict]:
    init_case_runs_db()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM case_runs
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
