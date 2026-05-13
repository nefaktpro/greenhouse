from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DIGEST_DIR = ROOT / "data" / "memory" / "chat_digests"
AI_LOG = ROOT / "data" / "memory" / "ai_chat_io_log.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _read_jsonl(path: Path, limit: int = 300) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"raw": line})
    return rows


def get_chat_digest_status() -> dict[str, Any]:
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(DIGEST_DIR.glob("*.md"), reverse=True)
    return {
        "ok": True,
        "digest_dir": str(DIGEST_DIR.relative_to(ROOT)),
        "source_log": str(AI_LOG.relative_to(ROOT)),
        "source_exists": AI_LOG.exists(),
        "digests": [
            {
                "name": f.name,
                "path": str(f.relative_to(ROOT)),
                "size": f.stat().st_size,
                "updated": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }
            for f in files[:30]
        ],
    }


def generate_chat_digest(period: str = "today", limit: int = 300) -> dict[str, Any]:
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)

    rows = _read_jsonl(AI_LOG, limit=limit)

    date_key = _today()
    out = DIGEST_DIR / f"{date_key}_{period}.md"

    # MVP: local structured digest. AI summarizer подключим позже.
    user_msgs = []
    ai_msgs = []
    errors = []
    actions = []

    for r in rows:
        text = json.dumps(r, ensure_ascii=False) if not isinstance(r, dict) else json.dumps(r, ensure_ascii=False)
        low = text.lower()

        if "error" in low or "exception" in low or "traceback" in low:
            errors.append(text[:500])

        if any(x in low for x in ["action_key", "execute", "ask", "schedule", "timer", "cleanup"]):
            actions.append(text[:500])

        if "user" in low or "message" in low:
            user_msgs.append(text[:500])
        else:
            ai_msgs.append(text[:500])

    content = f"""# GREENHOUSE v17 — Chat Digest

Дата генерации: {_now()}
Период: {period}
Источник: `{AI_LOG.relative_to(ROOT)}`
Прочитано строк: {len(rows)}

## 1. Короткий итог

Автоматический foundation-конспект создан локально. AI-summary ещё не подключён.
Raw chat не удалён и не архивирован.

## 2. Потенциальные действия / automation / cleanup

Всего найдено: {len(actions)}

""" + "\n".join(f"- `{x}`" for x in actions[:30]) + f"""

## 3. Ошибки / warnings

Всего найдено: {len(errors)}

""" + "\n".join(f"- `{x}`" for x in errors[:30]) + f"""

## 4. Последние сообщения / события

""" + "\n".join(f"- `{json.dumps(r, ensure_ascii=False)[:700]}`" for r in rows[-50:]) + """

## 5. TODO next

- Подключить AI summarizer.
- Делать daily/weekly digest.
- Помечать raw chat как compressed только после успешного digest.
- Связать с Cleanup Layer.
"""

    out.write_text(content, encoding="utf-8")

    return {
        "ok": True,
        "path": str(out.relative_to(ROOT)),
        "rows": len(rows),
        "actions": len(actions),
        "errors": len(errors),
    }


def read_chat_digest(path: str) -> dict[str, Any]:
    if not path:
        return {"ok": False, "error": "path_required"}

    target = (ROOT / path).resolve()

    try:
        target.relative_to(DIGEST_DIR.resolve())
    except Exception:
        return {"ok": False, "error": "path_not_allowed"}

    if not target.exists() or not target.is_file():
        return {"ok": False, "error": "file_not_found", "path": path}

    return {
        "ok": True,
        "path": str(target.relative_to(ROOT)),
        "name": target.name,
        "size": target.stat().st_size,
        "content": target.read_text(encoding="utf-8", errors="ignore"),
    }
