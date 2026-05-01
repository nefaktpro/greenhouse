from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data/memory/memory.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_memory_db() -> Dict[str, Any]:
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS observations (
            observation_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            source TEXT,
            category TEXT,
            action_key TEXT,
            followup_id TEXT,
            importance TEXT,
            quality TEXT,
            valid_for_case INTEGER,
            title TEXT,
            summary TEXT,
            payload_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS case_candidates (
            case_candidate_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            source TEXT,
            status TEXT,
            case_type TEXT,
            action_key TEXT,
            observation_id TEXT,
            followup_id TEXT,
            confidence REAL,
            title TEXT,
            conclusion TEXT,
            payload_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            source TEXT,
            source_candidate_id TEXT,
            case_type TEXT,
            action_key TEXT,
            confidence REAL,
            conclusion TEXT,
            payload_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_observations_created_at ON observations(created_at);
        CREATE INDEX IF NOT EXISTS idx_observations_category ON observations(category);
        CREATE INDEX IF NOT EXISTS idx_case_candidates_status ON case_candidates(status);
        CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at);
        """)
    return {"ok": True, "db_path": str(DB_PATH)}


def upsert_observation(item: Dict[str, Any]) -> Dict[str, Any]:
    init_memory_db()
    observation_id = item.get("observation_id")
    if not observation_id:
        return {"ok": False, "error": "missing_observation_id"}
    with _conn() as con:
        con.execute("""
        INSERT OR REPLACE INTO observations (
            observation_id, created_at, source, category, action_key, followup_id,
            importance, quality, valid_for_case, title, summary, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            observation_id,
            item.get("created_at") or _now_iso(),
            item.get("source"),
            item.get("category"),
            item.get("action_key"),
            item.get("followup_id"),
            item.get("importance"),
            item.get("quality"),
            1 if item.get("valid_for_case") else 0,
            item.get("title"),
            item.get("summary"),
            json.dumps(item, ensure_ascii=False),
        ))
    return {"ok": True, "observation_id": observation_id}


def upsert_case_candidate(item: Dict[str, Any]) -> Dict[str, Any]:
    init_memory_db()
    cid = item.get("case_candidate_id")
    if not cid:
        return {"ok": False, "error": "missing_case_candidate_id"}
    with _conn() as con:
        con.execute("""
        INSERT OR REPLACE INTO case_candidates (
            case_candidate_id, created_at, source, status, case_type, action_key,
            observation_id, followup_id, confidence, title, conclusion, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cid,
            item.get("created_at") or _now_iso(),
            item.get("source"),
            item.get("status"),
            item.get("case_type"),
            item.get("action_key"),
            item.get("observation_id"),
            item.get("followup_id"),
            item.get("confidence"),
            item.get("title"),
            item.get("conclusion"),
            json.dumps(item, ensure_ascii=False),
        ))
    return {"ok": True, "case_candidate_id": cid}


def upsert_case(item: Dict[str, Any]) -> Dict[str, Any]:
    init_memory_db()
    case_id = item.get("case_id")
    if not case_id:
        return {"ok": False, "error": "missing_case_id"}
    with _conn() as con:
        con.execute("""
        INSERT OR REPLACE INTO cases (
            case_id, created_at, source, source_candidate_id, case_type,
            action_key, confidence, conclusion, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case_id,
            item.get("created_at") or _now_iso(),
            item.get("source"),
            item.get("source_candidate_id"),
            item.get("case_type"),
            item.get("action_key"),
            item.get("confidence"),
            item.get("conclusion"),
            json.dumps(item, ensure_ascii=False),
        ))
    return {"ok": True, "case_id": case_id}


def list_rows(table: str, limit: int = 100, status: Optional[str] = None) -> List[Dict[str, Any]]:
    if table not in {"observations", "case_candidates", "cases"}:
        return []
    init_memory_db()
    limit = max(1, min(int(limit), 500))
    with _conn() as con:
        if status and table == "case_candidates":
            rows = con.execute(
                "SELECT payload_json FROM case_candidates WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = con.execute(
                f"SELECT payload_json FROM {table} ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [json.loads(r["payload_json"]) for r in rows]


def stats() -> Dict[str, Any]:
    init_memory_db()
    with _conn() as con:
        return {
            "ok": True,
            "db_path": str(DB_PATH),
            "observations": con.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
            "case_candidates": con.execute("SELECT COUNT(*) FROM case_candidates").fetchone()[0],
            "cases": con.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
        }
