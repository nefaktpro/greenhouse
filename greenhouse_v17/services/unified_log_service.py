from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

DB_PATH = Path("data/logs/unified_logs.db")
JSON_EXPORT_PATH = Path("data/logs/unified_logs_recent.json")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)


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


def init_unified_logs_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,

                source TEXT,
                mode TEXT,

                action_key TEXT,
                entity_id TEXT,
                target_role TEXT,
                operation TEXT,

                service_domain TEXT,
                service_name TEXT,

                ok INTEGER NOT NULL,
                message TEXT,

                expected_state TEXT,
                actual_state TEXT,
                verified INTEGER,
                verify_strategy TEXT,

                verify_v2_ok INTEGER,
                verify_v2_status TEXT,
                verify_v2_reason TEXT,
                verify_v2_strategy TEXT,

                ha_status_code INTEGER,
                duration_ms INTEGER
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_execution_log_ts
            ON execution_log(ts DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_execution_log_entity_id
            ON execution_log(entity_id, ts DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_execution_log_action_key
            ON execution_log(action_key, ts DESC)
            """
        )


def _to_int_bool(value: Optional[bool]) -> Optional[int]:
    if value is None:
        return None
    return 1 if bool(value) else 0


def append_execution_log(
    *,
    source: Optional[str],
    mode: Optional[str],
    action_key: Optional[str],
    entity_id: Optional[str],
    target_role: Optional[str],
    operation: Optional[str],
    service_domain: Optional[str],
    service_name: Optional[str],
    ok: bool,
    message: Optional[str],
    expected_state: Optional[str],
    actual_state: Optional[str],
    verified: Optional[bool],
    verify_strategy: Optional[str],
    verify_v2_ok: Optional[bool],
    verify_v2_status: Optional[str],
    verify_v2_reason: Optional[str],
    verify_v2_strategy: Optional[str],
    ha_status_code: Optional[int],
    duration_ms: Optional[int],
) -> None:
    init_unified_logs_db()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO execution_log (
                ts,
                source,
                mode,
                action_key,
                entity_id,
                target_role,
                operation,
                service_domain,
                service_name,
                ok,
                message,
                expected_state,
                actual_state,
                verified,
                verify_strategy,
                verify_v2_ok,
                verify_v2_status,
                verify_v2_reason,
                verify_v2_strategy,
                ha_status_code,
                duration_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now_iso(),
                source,
                mode,
                action_key,
                entity_id,
                target_role,
                operation,
                service_domain,
                service_name,
                1 if ok else 0,
                message,
                expected_state,
                actual_state,
                _to_int_bool(verified),
                verify_strategy,
                _to_int_bool(verify_v2_ok),
                verify_v2_status,
                verify_v2_reason,
                verify_v2_strategy,
                ha_status_code,
                duration_ms,
            ),
        )

    export_recent_execution_logs_to_json(limit=200)


def read_recent_execution_logs(limit: int = 50) -> list[dict]:
    init_unified_logs_db()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM execution_log
            ORDER BY ts DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def export_recent_execution_logs_to_json(limit: int = 200) -> None:
    ensure_parent_dir()
    items = read_recent_execution_logs(limit=limit)
    payload = {
        "ok": True,
        "source": "sqlite_export",
        "db_path": str(DB_PATH),
        "limit": limit,
        "count": len(items),
        "items": items,
    }
    JSON_EXPORT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_last_log_for_entity(entity_id: str) -> Optional[dict]:
    init_unified_logs_db()

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM execution_log
            WHERE entity_id = ?
            ORDER BY ts DESC, id DESC
            LIMIT 1
            """,
            (entity_id,),
        ).fetchone()

    return dict(row) if row else None
