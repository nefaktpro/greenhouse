from __future__ import annotations

import fnmatch
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "data" / "cleanup" / "cleanup_registry.json"
DB_PATH = ROOT / "data" / "cleanup" / "cleanup.db"

BACKUP_MARKERS = (".bak", "_bak", "backup", "before_", "checkpoint_", "patch_", ".tar.gz")
LOG_MARKERS = (".log", ".jsonl")
DB_EXT = (".db", ".sqlite", ".sqlite3")
PHOTO_EXT = (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def human_size(num: int) -> str:
    n = float(num or 0)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{num} B"


def load_cleanup_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"version": "missing", "sources": []}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def init_cleanup_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS cleanup_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                total_sources INTEGER NOT NULL,
                total_files INTEGER NOT NULL,
                total_size INTEGER NOT NULL,
                total_candidates INTEGER NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS cleanup_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER,
                created_at TEXT NOT NULL,
                source_id TEXT,
                group_name TEXT,
                risk TEXT,
                candidate_type TEXT,
                path TEXT,
                size INTEGER,
                reason TEXT,
                ai_allowed INTEGER DEFAULT 0,
                auto_delete_allowed INTEGER DEFAULT 0
            )
            """
        )

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS cleanup_candidate_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                path TEXT NOT NULL,
                source_id TEXT,
                group_name TEXT,
                candidate_type TEXT,
                decision TEXT NOT NULL,
                actor TEXT DEFAULT 'user',
                reason TEXT,
                payload_json TEXT
            )
            """
        )
        con.commit()


@dataclass
class FileStat:
    path: str
    size: int
    mtime: float
    suffix: str


def _iter_source_files(source: dict[str, Any], max_files: int = 20000) -> list[FileStat]:
    kind = source.get("kind", "files")
    base = ROOT / str(source.get("path", "."))
    files: list[FileStat] = []

    if kind == "glob":
        patterns = source.get("patterns") or []
        for pattern in patterns:
            for p in ROOT.glob(pattern):
                if p.is_file():
                    st = p.stat()
                    files.append(FileStat(_rel(p), st.st_size, st.st_mtime, p.suffix.lower()))
                    if len(files) >= max_files:
                        return files
        return files

    if not base.exists():
        return files

    if base.is_file():
        st = base.stat()
        return [FileStat(_rel(base), st.st_size, st.st_mtime, base.suffix.lower())]

    for p in base.rglob("*"):
        if p.is_file():
            st = p.stat()
            files.append(FileStat(_rel(p), st.st_size, st.st_mtime, p.suffix.lower()))
            if len(files) >= max_files:
                break
    return files


def _candidate_for_file(source: dict[str, Any], f: FileStat) -> dict[str, Any] | None:
    path_l = f.path.lower()
    name_l = Path(f.path).name.lower()
    group = source.get("group", "other")
    risk = source.get("risk", "medium")
    ai_allowed = bool(source.get("ai_scan_allowed"))
    auto_delete = bool(source.get("auto_delete_allowed"))

    if source.get("protected"):
        if any(marker in name_l for marker in [".bak", "backup", "copy"]):
            return {
                "candidate_type": "protected_backup_review",
                "reason": "Protected source contains backup/copy file; review only, no auto-delete.",
                "risk": "high",
                "ai_allowed": ai_allowed,
                "auto_delete_allowed": False,
            }
        return None

    if any(marker in name_l for marker in BACKUP_MARKERS):
        return {
            "candidate_type": "backup_archive_candidate",
            "reason": "Looks like patch/backup file. Archive candidate, delete disabled.",
            "risk": risk,
            "ai_allowed": ai_allowed,
            "auto_delete_allowed": auto_delete,
        }

    if f.size > 1024 * 1024 and (path_l.endswith(LOG_MARKERS) or "/logs/" in path_l):
        return {
            "candidate_type": "large_log_candidate",
            "reason": "Large log file. Candidate for compression/archive/AI summary.",
            "risk": "medium",
            "ai_allowed": ai_allowed,
            "auto_delete_allowed": False,
        }

    if f.size > 512 * 1024 and path_l.endswith(DB_EXT):
        return {
            "candidate_type": "sqlite_stats_candidate",
            "reason": "SQLite database should be included in retention/VACUUM/stats policy.",
            "risk": risk,
            "ai_allowed": ai_allowed,
            "auto_delete_allowed": False,
        }

    if group == "photos" and path_l.endswith(PHOTO_EXT):
        return {
            "candidate_type": "photo_retention_candidate",
            "reason": "Photo/media file should follow archive/retention policy.",
            "risk": "medium",
            "ai_allowed": ai_allowed,
            "auto_delete_allowed": False,
        }

    if group == "runtime" and ("completed" in path_l or "old" in path_l or "tmp" in path_l):
        return {
            "candidate_type": "runtime_stale_review",
            "reason": "Runtime file looks completed/old/tmp; review only.",
            "risk": "high",
            "ai_allowed": False,
            "auto_delete_allowed": False,
        }

    return None


def scan_cleanup_sources(save: bool = True) -> dict[str, Any]:
    init_cleanup_db()
    registry = load_cleanup_registry()
    sources = registry.get("sources") or []

    source_results: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []

    for source in sources:
        files = _iter_source_files(source)
        total_size = sum(f.size for f in files)
        suffix_counts: dict[str, int] = {}
        biggest = sorted(files, key=lambda x: x.size, reverse=True)[:10]

        for f in files:
            key = f.suffix or "[no_ext]"
            suffix_counts[key] = suffix_counts.get(key, 0) + 1

            cand = _candidate_for_file(source, f)
            if cand:
                cand.update(
                    {
                        "source_id": source.get("source_id"),
                        "group": source.get("group"),
                        "path": f.path,
                        "size": f.size,
                        "size_human": human_size(f.size),
                    }
                )
                all_candidates.append(cand)

        source_results.append(
            {
                "source_id": source.get("source_id"),
                "title": source.get("title"),
                "group": source.get("group"),
                "risk": source.get("risk"),
                "protected": bool(source.get("protected")),
                "ai_scan_allowed": bool(source.get("ai_scan_allowed")),
                "local_cleanup_allowed": bool(source.get("local_cleanup_allowed")),
                "auto_delete_allowed": bool(source.get("auto_delete_allowed")),
                "archive_allowed": bool(source.get("archive_allowed")),
                "default_schedule": source.get("default_schedule"),
                "path": source.get("path"),
                "exists": (ROOT / str(source.get("path", "."))).exists() if source.get("kind") != "glob" else True,
                "file_count": len(files),
                "total_size": total_size,
                "total_size_human": human_size(total_size),
                "suffix_counts": dict(sorted(suffix_counts.items())),
                "candidate_count": len([c for c in all_candidates if c.get("source_id") == source.get("source_id")]),
                "biggest_files": [
                    {"path": f.path, "size": f.size, "size_human": human_size(f.size)}
                    for f in biggest
                ],
                "description": source.get("description"),
            }
        )

    groups: dict[str, dict[str, Any]] = {}
    for s in source_results:
        g = s.get("group") or "other"
        groups.setdefault(g, {"group": g, "sources": 0, "files": 0, "size": 0, "candidates": 0})
        groups[g]["sources"] += 1
        groups[g]["files"] += _safe_int(s.get("file_count"))
        groups[g]["size"] += _safe_int(s.get("total_size"))
        groups[g]["candidates"] += _safe_int(s.get("candidate_count"))

    for g in groups.values():
        g["size_human"] = human_size(g["size"])

    decisions = get_candidate_decisions()

    for c in all_candidates:
        d = decisions.get("by_path", {}).get(c.get("path"))
        if d:
            c["decision"] = d.get("decision")
            c["decision_at"] = d.get("created_at")
        else:
            c["decision"] = "new"

    payload = {
        "ok": True,
        "mode": "scan_only",
        "delete_enabled": False,
        "created_at": _now(),
        "registry_path": _rel(REGISTRY_PATH),
        "db_path": _rel(DB_PATH),
        "total_sources": len(source_results),
        "total_files": sum(_safe_int(s.get("file_count")) for s in source_results),
        "total_size": sum(_safe_int(s.get("total_size")) for s in source_results),
        "total_size_human": human_size(sum(_safe_int(s.get("total_size")) for s in source_results)),
        "total_candidates": len(all_candidates),
        "candidate_decisions": decisions.get("by_path", {}),
        "candidate_decision_counts": decisions.get("counts", {}),
        "groups": sorted(groups.values(), key=lambda x: x["group"]),
        "sources": source_results,
        "candidates": all_candidates[:500],
        "candidate_limit_note": "Showing first 500 candidates" if len(all_candidates) > 500 else None,
    }

    if save:
        with sqlite3.connect(DB_PATH) as con:
            cur = con.execute(
                """
                INSERT INTO cleanup_scans
                (created_at, total_sources, total_files, total_size, total_candidates, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["created_at"],
                    payload["total_sources"],
                    payload["total_files"],
                    payload["total_size"],
                    payload["total_candidates"],
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            scan_id = cur.lastrowid
            for c in all_candidates[:5000]:
                con.execute(
                    """
                    INSERT INTO cleanup_candidates
                    (scan_id, created_at, source_id, group_name, risk, candidate_type, path, size, reason, ai_allowed, auto_delete_allowed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scan_id,
                        payload["created_at"],
                        c.get("source_id"),
                        c.get("group"),
                        c.get("risk"),
                        c.get("candidate_type"),
                        c.get("path"),
                        _safe_int(c.get("size")),
                        c.get("reason"),
                        1 if c.get("ai_allowed") else 0,
                        1 if c.get("auto_delete_allowed") else 0,
                    ),
                )
            con.commit()

    return payload


def get_cleanup_status() -> dict[str, Any]:
    init_cleanup_db()
    registry = load_cleanup_registry()
    latest = None
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute(
            "SELECT id, created_at, total_sources, total_files, total_size, total_candidates FROM cleanup_scans ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            latest = {
                "scan_id": row[0],
                "created_at": row[1],
                "total_sources": row[2],
                "total_files": row[3],
                "total_size": row[4],
                "total_size_human": human_size(row[4]),
                "total_candidates": row[5],
            }
    return {
        "ok": True,
        "mode": "scan_only",
        "delete_enabled": False,
        "ai_auto_delete_enabled": False,
        "registry_path": _rel(REGISTRY_PATH),
        "db_path": _rel(DB_PATH),
        "source_count": len(registry.get("sources") or []),
        "latest_scan": latest,
    }


def get_cleanup_sources() -> dict[str, Any]:
    registry = load_cleanup_registry()
    return {"ok": True, "sources": registry.get("sources") or []}


def update_cleanup_policy(
    source_id: str,
    *,
    ai_scan_allowed=None,
    local_cleanup_allowed=None,
    auto_delete_allowed=None,
    archive_allowed=None,
    protected=None,
    default_schedule=None,
    retention_days=None,
):
    registry = load_cleanup_registry()
    sources = registry.get("sources") or []

    updated = False

    for src in sources:
        if src.get("source_id") != source_id:
            continue

        if ai_scan_allowed is not None:
            src["ai_scan_allowed"] = bool(ai_scan_allowed)

        if local_cleanup_allowed is not None:
            src["local_cleanup_allowed"] = bool(local_cleanup_allowed)

        if auto_delete_allowed is not None:
            src["auto_delete_allowed"] = bool(auto_delete_allowed)

        if archive_allowed is not None:
            src["archive_allowed"] = bool(archive_allowed)

        if protected is not None:
            src["protected"] = bool(protected)

        if default_schedule is not None:
            src["default_schedule"] = default_schedule

        if retention_days is not None:
            src["retention_days"] = retention_days

        updated = True
        break

    if not updated:
        return {
            "ok": False,
            "error": "source_not_found",
            "source_id": source_id,
        }

    REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return {
        "ok": True,
        "source_id": source_id,
    }


ALLOWED_CANDIDATE_DECISIONS = {
    "keep",
    "archive_later",
    "ai_review",
    "protect",
    "ignore",
    "reset",
}


def save_candidate_decision(
    *,
    path: str,
    source_id: str | None = None,
    group_name: str | None = None,
    candidate_type: str | None = None,
    decision: str,
    actor: str = "user",
    reason: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_cleanup_db()

    if not path:
        return {"ok": False, "error": "path_required"}

    if decision not in ALLOWED_CANDIDATE_DECISIONS:
        return {
            "ok": False,
            "error": "invalid_decision",
            "allowed": sorted(ALLOWED_CANDIDATE_DECISIONS),
        }

    # reset = удалить пользовательское решение по этому path
    with sqlite3.connect(DB_PATH) as con:
        if decision == "reset":
            con.execute(
                "DELETE FROM cleanup_candidate_decisions WHERE path = ?",
                (path,),
            )
            con.commit()
            return {"ok": True, "path": path, "decision": "reset"}

        con.execute(
            """
            INSERT INTO cleanup_candidate_decisions
            (created_at, path, source_id, group_name, candidate_type, decision, actor, reason, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                path,
                source_id,
                group_name,
                candidate_type,
                decision,
                actor,
                reason,
                json.dumps(payload or {}, ensure_ascii=False),
            ),
        )
        con.commit()

    return {"ok": True, "path": path, "decision": decision}


def get_candidate_decisions() -> dict[str, Any]:
    init_cleanup_db()
    latest_by_path: dict[str, dict[str, Any]] = {}

    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            """
            SELECT created_at, path, source_id, group_name, candidate_type, decision, actor, reason
            FROM cleanup_candidate_decisions
            ORDER BY id ASC
            """
        ).fetchall()

    for row in rows:
        latest_by_path[row[1]] = {
            "created_at": row[0],
            "path": row[1],
            "source_id": row[2],
            "group": row[3],
            "candidate_type": row[4],
            "decision": row[5],
            "actor": row[6],
            "reason": row[7],
        }

    counts: dict[str, int] = {}
    for d in latest_by_path.values():
        key = d.get("decision") or "unknown"
        counts[key] = counts.get(key, 0) + 1

    return {
        "ok": True,
        "count": len(latest_by_path),
        "counts": counts,
        "decisions": list(latest_by_path.values()),
        "by_path": latest_by_path,
    }


def preview_cleanup_file(path: str, max_bytes: int = 24000) -> dict[str, Any]:
    if not path:
        return {"ok": False, "error": "path_required"}

    target = (ROOT / path).resolve()

    try:
        target.relative_to(ROOT)
    except Exception:
        return {"ok": False, "error": "path_outside_project"}

    if not target.exists() or not target.is_file():
        return {"ok": False, "error": "file_not_found", "path": path}

    suffix = target.suffix.lower()
    size = target.stat().st_size

    if suffix in DB_EXT:
        try:
            with sqlite3.connect(target) as con:
                rows = con.execute(
                    "SELECT name, type FROM sqlite_master WHERE type IN ('table','index','view') ORDER BY type, name"
                ).fetchall()

                tables = []
                for name, typ in rows:
                    if typ == "table":
                        try:
                            cnt = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                        except Exception:
                            cnt = None
                        tables.append({"name": name, "type": typ, "rows": cnt})
                    else:
                        tables.append({"name": name, "type": typ, "rows": None})

            return {
                "ok": True,
                "kind": "sqlite",
                "path": path,
                "size": size,
                "size_human": human_size(size),
                "tables": tables,
            }
        except Exception as e:
            return {"ok": False, "error": "sqlite_preview_failed", "details": str(e), "path": path}

    image_ext = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    if suffix in image_ext and (path.startswith("data/photos/") or path.startswith("data/camera/")):
        return {
            "ok": True,
            "kind": "image",
            "path": path,
            "size": size,
            "size_human": human_size(size),
            "view_url": "/api/cleanup/file/view?path=" + quote(path),
        }

    binary_ext = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".tar", ".gz", ".zip", ".pdf", ".pyc"}
    if suffix in binary_ext or path.endswith(".tar.gz"):
        return {
            "ok": True,
            "kind": "binary",
            "path": path,
            "size": size,
            "size_human": human_size(size),
            "message": "Бинарный файл: безопасный текстовый предпросмотр не применяется.",
        }

    try:
        raw = target.read_bytes()[:max_bytes]
        text = raw.decode("utf-8", errors="replace")
        truncated = size > max_bytes

        return {
            "ok": True,
            "kind": "text",
            "path": path,
            "size": size,
            "size_human": human_size(size),
            "truncated": truncated,
            "max_bytes": max_bytes,
            "content": text,
        }
    except Exception as e:
        return {"ok": False, "error": "preview_failed", "details": str(e), "path": path}


def save_candidate_decisions_batch(
    items: list[dict[str, Any]],
    decision: str,
    actor: str = "user",
    reason: str | None = None,
) -> dict[str, Any]:
    if decision not in ALLOWED_CANDIDATE_DECISIONS:
        return {
            "ok": False,
            "error": "invalid_decision",
            "allowed": sorted(ALLOWED_CANDIDATE_DECISIONS),
        }

    if not isinstance(items, list):
        return {"ok": False, "error": "items_must_be_list"}

    saved = 0
    errors = []

    for item in items[:5000]:
        res = save_candidate_decision(
            path=item.get("path"),
            source_id=item.get("source_id"),
            group_name=item.get("group"),
            candidate_type=item.get("candidate_type"),
            decision=decision,
            actor=actor,
            reason=reason or "batch_review_from_cleanup_ui",
            payload=item,
        )
        if res.get("ok"):
            saved += 1
        else:
            errors.append(res)

    return {
        "ok": True,
        "decision": decision,
        "saved": saved,
        "errors": errors[:20],
        "error_count": len(errors),
    }
