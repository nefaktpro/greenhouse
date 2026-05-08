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


def init_ai_decision_runs_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_decision_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                decision_id TEXT NOT NULL,
                parent_decision_id TEXT,
                trace_id TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                source TEXT,
                mode TEXT,
                created_by TEXT,

                decision_status TEXT,
                decision_kind TEXT,

                provider TEXT,
                model TEXT,

                user_message TEXT,
                normalized_intent TEXT,
                decision_summary TEXT,
                decision_reasoning TEXT,

                proposed_action_key TEXT,
                proposed_target_role TEXT,
                proposed_entity_id TEXT,
                proposed_operation TEXT,
                proposed_expected_state TEXT,

                ask_required INTEGER,
                ask_created INTEGER,
                ask_confirmed INTEGER,
                ask_canceled INTEGER,

                execution_linked INTEGER,
                execution_ok INTEGER,
                verify_ok INTEGER,
                verify_v2_ok INTEGER,
                verify_v2_status TEXT,

                confidence REAL,
                risk_level TEXT,

                context_types TEXT,
                note TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_decision_runs_decision_id
            ON ai_decision_runs(decision_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_decision_runs_status
            ON ai_decision_runs(decision_status, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_decision_runs_action_key
            ON ai_decision_runs(proposed_action_key, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_decision_runs_entity
            ON ai_decision_runs(proposed_entity_id, updated_at DESC)
            """
        )


def _to_int_bool(value: Optional[bool]) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0


def insert_ai_decision_run(
    *,
    decision_id: str,
    parent_decision_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    source: Optional[str] = None,
    mode: Optional[str] = None,
    created_by: Optional[str] = None,
    decision_status: Optional[str] = None,
    decision_kind: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    user_message: Optional[str] = None,
    normalized_intent: Optional[str] = None,
    decision_summary: Optional[str] = None,
    decision_reasoning: Optional[str] = None,
    proposed_action_key: Optional[str] = None,
    proposed_target_role: Optional[str] = None,
    proposed_entity_id: Optional[str] = None,
    proposed_operation: Optional[str] = None,
    proposed_expected_state: Optional[str] = None,
    ask_required: Optional[bool] = None,
    ask_created: Optional[bool] = None,
    ask_confirmed: Optional[bool] = None,
    ask_canceled: Optional[bool] = None,
    execution_linked: Optional[bool] = None,
    execution_ok: Optional[bool] = None,
    verify_ok: Optional[bool] = None,
    verify_v2_ok: Optional[bool] = None,
    verify_v2_status: Optional[str] = None,
    confidence: Optional[float] = None,
    risk_level: Optional[str] = None,
    context_types: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    init_ai_decision_runs_db()
    now = utc_now_iso()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO ai_decision_runs (
                decision_id,
                parent_decision_id,
                trace_id,
                created_at,
                updated_at,
                source,
                mode,
                created_by,
                decision_status,
                decision_kind,
                provider,
                model,
                user_message,
                normalized_intent,
                decision_summary,
                decision_reasoning,
                proposed_action_key,
                proposed_target_role,
                proposed_entity_id,
                proposed_operation,
                proposed_expected_state,
                ask_required,
                ask_created,
                ask_confirmed,
                ask_canceled,
                execution_linked,
                execution_ok,
                verify_ok,
                verify_v2_ok,
                verify_v2_status,
                confidence,
                risk_level,
                context_types,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                parent_decision_id,
                trace_id,
                now,
                now,
                source,
                mode,
                created_by,
                decision_status,
                decision_kind,
                provider,
                model,
                user_message,
                normalized_intent,
                decision_summary,
                decision_reasoning,
                proposed_action_key,
                proposed_target_role,
                proposed_entity_id,
                proposed_operation,
                proposed_expected_state,
                _to_int_bool(ask_required),
                _to_int_bool(ask_created),
                _to_int_bool(ask_confirmed),
                _to_int_bool(ask_canceled),
                _to_int_bool(execution_linked),
                _to_int_bool(execution_ok),
                _to_int_bool(verify_ok),
                _to_int_bool(verify_v2_ok),
                verify_v2_status,
                confidence,
                risk_level,
                context_types,
                note,
            ),
        )


def read_recent_ai_decision_runs(limit: int = 50) -> list[dict]:
    init_ai_decision_runs_db()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM ai_decision_runs
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
