from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_DIR = ROOT / "data/registry"
DB_PATH = REGISTRY_DIR / "registry.db"

DEVICES_CSV = REGISTRY_DIR / "devices.csv"
ACTION_MAP_JSON = REGISTRY_DIR / "action_map.json"
CAPABILITIES_JSON = REGISTRY_DIR / "device_capabilities.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def init_registry_db() -> Dict[str, Any]:
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            parent_id TEXT,
            name TEXT,
            type TEXT,
            entity_id TEXT,
            unit TEXT,
            zone TEXT,
            location TEXT,
            logical_role TEXT,
            enabled INTEGER,
            controllable INTEGER,
            criticality TEXT,
            source TEXT,
            description TEXT,
            is_parent INTEGER,
            payload_json TEXT NOT NULL,
            synced_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS actions (
            action_key TEXT PRIMARY KEY,
            logical_role TEXT,
            target_role TEXT,
            entity_id TEXT,
            service TEXT,
            expected_state TEXT,
            verify_delay_sec INTEGER,
            payload_json TEXT NOT NULL,
            synced_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS capabilities (
            logical_role TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            synced_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS device_passports (
            logical_role TEXT PRIMARY KEY,
            device_id TEXT,
            entity_id TEXT,
            reliability TEXT DEFAULT 'unknown',
            verify_strategy TEXT DEFAULT 'state',
            effect_model_json TEXT,
            related_sensors_json TEXT,
            related_cameras_json TEXT,
            safety_json TEXT,
            payload_json TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_devices_entity_id ON devices(entity_id);
        CREATE INDEX IF NOT EXISTS idx_devices_logical_role ON devices(logical_role);
        CREATE INDEX IF NOT EXISTS idx_devices_zone ON devices(zone);
        CREATE INDEX IF NOT EXISTS idx_actions_entity_id ON actions(entity_id);
        CREATE INDEX IF NOT EXISTS idx_actions_role ON actions(logical_role);
        """)
    return {"ok": True, "db_path": str(DB_PATH)}


def _read_devices_csv() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not DEVICES_CSV.exists():
        return rows

    with DEVICES_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _extract_action_fields(action_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    target_role = (
        payload.get("target_role")
        or payload.get("logical_role")
        or payload.get("role")
        or payload.get("capability")
    )
    entity_id = payload.get("entity_id") or payload.get("entity")
    service = payload.get("service") or payload.get("service_call")
    expected_state = payload.get("expected_state")

    verify_delay = (
        payload.get("verify_delay_sec")
        or payload.get("expected_delay_sec")
        or payload.get("delay_sec")
    )
    try:
        verify_delay = int(verify_delay) if verify_delay is not None else None
    except Exception:
        verify_delay = None

    return {
        "action_key": action_key,
        "logical_role": target_role,
        "target_role": target_role,
        "entity_id": entity_id,
        "service": service,
        "expected_state": expected_state,
        "verify_delay_sec": verify_delay,
    }


def sync_registry_to_db() -> Dict[str, Any]:
    init_registry_db()
    synced_at = _now_iso()

    devices = _read_devices_csv()
    actions = _load_json(ACTION_MAP_JSON, {})
    capabilities = _load_json(CAPABILITIES_JSON, {})

    if not isinstance(actions, dict):
        actions = {}
    if not isinstance(capabilities, dict):
        capabilities = {}

    with _conn() as con:
        con.execute("DELETE FROM devices")
        con.execute("DELETE FROM actions")
        con.execute("DELETE FROM capabilities")

        for r in devices:
            device_id = str(r.get("id") or r.get("ID") or r.get("device_id") or "").strip()
            parent_id = str(r.get("parent_id") or r.get("Parent") or r.get("parent") or "").strip()
            name = r.get("name") or r.get("Name") or ""
            typ = r.get("type") or r.get("Type") or ""
            entity_id = r.get("entity_id") or r.get("Entity_ID") or r.get("entity") or ""
            unit = r.get("unit") or r.get("Unit") or ""
            zone = r.get("zone") or r.get("Location") or r.get("location") or ""
            location = r.get("location") or r.get("Location") or ""
            logical_role = r.get("logical_role") or r.get("role") or r.get("Role") or ""
            enabled_raw = str(r.get("enabled") or r.get("active") or "true").lower()
            controllable_raw = str(r.get("controllable") or "false").lower()
            criticality = r.get("criticality") or r.get("risk") or ""
            source = r.get("source") or ""
            description = r.get("description") or r.get("Description") or ""
            is_parent = 1 if typ == "device" or not entity_id else 0

            if not device_id:
                continue

            con.execute("""
            INSERT OR REPLACE INTO devices (
                id, parent_id, name, type, entity_id, unit, zone, location,
                logical_role, enabled, controllable, criticality, source,
                description, is_parent, payload_json, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                device_id, parent_id, name, typ, entity_id, unit, zone, location,
                logical_role,
                1 if enabled_raw in ("1", "true", "yes", "да") else 0,
                1 if controllable_raw in ("1", "true", "yes", "да") else 0,
                criticality, source, description, is_parent,
                json.dumps(r, ensure_ascii=False), synced_at
            ))

        for action_key, payload in actions.items():
            if not isinstance(payload, dict):
                payload = {"value": payload}
            f = _extract_action_fields(action_key, payload)
            con.execute("""
            INSERT OR REPLACE INTO actions (
                action_key, logical_role, target_role, entity_id, service,
                expected_state, verify_delay_sec, payload_json, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action_key,
                f["logical_role"],
                f["target_role"],
                f["entity_id"],
                f["service"],
                f["expected_state"],
                f["verify_delay_sec"],
                json.dumps(payload, ensure_ascii=False),
                synced_at,
            ))

        for logical_role, payload in capabilities.items():
            con.execute("""
            INSERT OR REPLACE INTO capabilities (
                logical_role, payload_json, synced_at
            ) VALUES (?, ?, ?)
            """, (
                logical_role,
                json.dumps(payload, ensure_ascii=False),
                synced_at,
            ))

    return {
        "ok": True,
        "db_path": str(DB_PATH),
        "devices": len(devices),
        "actions": len(actions),
        "capabilities": len(capabilities),
        "synced_at": synced_at,
    }


def registry_stats() -> Dict[str, Any]:
    init_registry_db()
    with _conn() as con:
        return {
            "ok": True,
            "db_path": str(DB_PATH),
            "devices": con.execute("SELECT COUNT(*) FROM devices").fetchone()[0],
            "entities": con.execute("SELECT COUNT(*) FROM devices WHERE entity_id IS NOT NULL AND entity_id != ''").fetchone()[0],
            "parent_devices": con.execute("SELECT COUNT(*) FROM devices WHERE is_parent = 1").fetchone()[0],
            "actions": con.execute("SELECT COUNT(*) FROM actions").fetchone()[0],
            "capabilities": con.execute("SELECT COUNT(*) FROM capabilities").fetchone()[0],
            "passports": con.execute("SELECT COUNT(*) FROM device_passports").fetchone()[0],
        }


def list_devices(limit: int = 100, controllable: Optional[bool] = None) -> List[Dict[str, Any]]:
    init_registry_db()
    limit = max(1, min(int(limit), 1000))
    with _conn() as con:
        if controllable is None:
            rows = con.execute(
                "SELECT * FROM devices ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM devices WHERE controllable = ? ORDER BY id LIMIT ?",
                (1 if controllable else 0, limit),
            ).fetchall()
    return [dict(r) for r in rows]


def list_actions(limit: int = 200) -> List[Dict[str, Any]]:
    init_registry_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM actions ORDER BY action_key LIMIT ?",
            (max(1, min(int(limit), 1000)),),
        ).fetchall()
    return [dict(r) for r in rows]


def find_device_by_role(logical_role: str) -> Optional[Dict[str, Any]]:
    init_registry_db()
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM devices WHERE logical_role = ? LIMIT 1",
            (logical_role,),
        ).fetchone()
    return dict(row) if row else None


def upsert_device_passport(item: Dict[str, Any]) -> Dict[str, Any]:
    init_registry_db()
    logical_role = item.get("logical_role")
    if not logical_role:
        return {"ok": False, "error": "missing_logical_role"}

    with _conn() as con:
        con.execute("""
        INSERT OR REPLACE INTO device_passports (
            logical_role, device_id, entity_id, reliability,
            verify_strategy, effect_model_json,
            related_sensors_json, related_cameras_json,
            safety_json, payload_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            logical_role,
            item.get("device_id"),
            item.get("entity_id"),
            item.get("reliability") or "unknown",
            item.get("verify_strategy") or "state",
            json.dumps(item.get("effect_model"), ensure_ascii=False),
            json.dumps(item.get("related_sensors"), ensure_ascii=False),
            json.dumps(item.get("related_cameras"), ensure_ascii=False),
            json.dumps(item.get("safety"), ensure_ascii=False),
            json.dumps(item, ensure_ascii=False),
            _now_iso()
        ))

    return {"ok": True, "logical_role": logical_role}


def get_device_passport(logical_role: str) -> Optional[Dict[str, Any]]:
    init_registry_db()
    with _conn() as con:
        row = con.execute(
            "SELECT payload_json FROM device_passports WHERE logical_role = ?",
            (logical_role,),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["payload_json"])
