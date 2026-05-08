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


def init_test_runs_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                test_id TEXT NOT NULL,
                parent_test_id TEXT,
                trace_id TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                source TEXT,
                mode TEXT,
                created_by TEXT,

                test_status TEXT,
                test_kind TEXT,
                title TEXT,
                hypothesis TEXT,
                goal TEXT,

                target_role TEXT,
                zone TEXT,
                entity_id TEXT,
                action_key TEXT,

                started_at TEXT,
                ended_at TEXT,

                execution_ok INTEGER,
                verify_ok INTEGER,
                verify_v2_ok INTEGER,
                verify_v2_status TEXT,

                confidence REAL,
                result_summary TEXT,
                learning TEXT,

                source_text TEXT,
                note TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_test_runs_test_id
            ON test_runs(test_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_test_runs_status
            ON test_runs(test_status, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_test_runs_entity
            ON test_runs(entity_id, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_test_runs_action_key
            ON test_runs(action_key, updated_at DESC)
            """
        )


def _to_int_bool(value: Optional[bool]) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0


def insert_test_run(
    *,
    test_id: str,
    parent_test_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    source: Optional[str] = None,
    mode: Optional[str] = None,
    created_by: Optional[str] = None,
    test_status: Optional[str] = None,
    test_kind: Optional[str] = None,
    title: Optional[str] = None,
    hypothesis: Optional[str] = None,
    goal: Optional[str] = None,
    target_role: Optional[str] = None,
    zone: Optional[str] = None,
    entity_id: Optional[str] = None,
    action_key: Optional[str] = None,
    started_at: Optional[str] = None,
    ended_at: Optional[str] = None,
    execution_ok: Optional[bool] = None,
    verify_ok: Optional[bool] = None,
    verify_v2_ok: Optional[bool] = None,
    verify_v2_status: Optional[str] = None,
    confidence: Optional[float] = None,
    result_summary: Optional[str] = None,
    learning: Optional[str] = None,
    source_text: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    init_test_runs_db()
    now = utc_now_iso()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO test_runs (
                test_id,
                parent_test_id,
                trace_id,
                created_at,
                updated_at,
                source,
                mode,
                created_by,
                test_status,
                test_kind,
                title,
                hypothesis,
                goal,
                target_role,
                zone,
                entity_id,
                action_key,
                started_at,
                ended_at,
                execution_ok,
                verify_ok,
                verify_v2_ok,
                verify_v2_status,
                confidence,
                result_summary,
                learning,
                source_text,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                test_id,
                parent_test_id,
                trace_id,
                now,
                now,
                source,
                mode,
                created_by,
                test_status,
                test_kind,
                title,
                hypothesis,
                goal,
                target_role,
                zone,
                entity_id,
                action_key,
                started_at,
                ended_at,
                _to_int_bool(execution_ok),
                _to_int_bool(verify_ok),
                _to_int_bool(verify_v2_ok),
                verify_v2_status,
                confidence,
                result_summary,
                learning,
                source_text,
                note,
            ),
        )


def read_recent_test_runs(limit: int = 50) -> list[dict]:
    init_test_runs_db()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM test_runs
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
