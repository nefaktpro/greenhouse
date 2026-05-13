from __future__ import annotations

import asyncio
import json
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

AI_LOG = ROOT / "data" / "memory" / "ai_chat_io_log.jsonl"
SUMMARY_ROOT = ROOT / "data" / "memory" / "summaries"
DAILY_DIR = SUMMARY_ROOT / "daily"
WEEKLY_DIR = SUMMARY_ROOT / "weekly"
MONTHLY_DIR = SUMMARY_ROOT / "monthly"
TODAY_DIR = SUMMARY_ROOT / "today"

EVENTS_FILE = ROOT / "data" / "memory" / "events" / "memory_summary_events.jsonl"
STATE_FILE = ROOT / "data" / "runtime" / "memory_summary_worker_state.json"

_worker_started = False


def _now() -> datetime:
    return datetime.now()


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    TODAY_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    _ensure_dirs()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _event(event: str, status: str, details: dict[str, Any]) -> None:
    _ensure_dirs()
    row = {
        "ts": _iso(),
        "layer": "memory_summary",
        "event": event,
        "status": status,
        "details": details,
    }
    with EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _parse_ts(value: Any) -> datetime | None:
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value))
        if isinstance(value, str):
            if value.replace(".", "", 1).isdigit():
                return datetime.fromtimestamp(float(value))
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None
    return None


def _read_jsonl(path: Path, limit: int = 5000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    rows: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"raw": line})
    return rows


def _rows_for_date(target: date) -> list[dict[str, Any]]:
    rows = _read_jsonl(AI_LOG, limit=20000)
    result = []
    for r in rows:
        dt = _parse_ts(r.get("ts") or r.get("time") or r.get("created_at"))
        if dt and dt.date() == target:
            result.append(r)
    return result


def _classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counters = {
        "rows": len(rows),
        "user_messages": 0,
        "ai_answers": 0,
        "local_control": 0,
        "openai": 0,
        "ask": 0,
        "errors": 0,
        "schedules": 0,
        "timers": 0,
        "automation": 0,
        "cleanup": 0,
        "memory": 0,
        "photos": 0,
        "weather": 0,
    }

    important: list[str] = []
    errors: list[str] = []
    next_steps: list[str] = []
    actions: list[str] = []

    for r in rows:
        text = json.dumps(r, ensure_ascii=False)
        low = text.lower()

        if r.get("user_message"):
            counters["user_messages"] += 1
        if r.get("answer"):
            counters["ai_answers"] += 1
        if r.get("provider") == "control" or "[local]" in low:
            counters["local_control"] += 1
        if r.get("provider") == "openai":
            counters["openai"] += 1

        if "ask" in low:
            counters["ask"] += 1
        if "error" in low or "exception" in low or "traceback" in low or '"ok": false' in low:
            counters["errors"] += 1
            errors.append(text[:700])
        if "schedule" in low or "расписан" in low:
            counters["schedules"] += 1
        if "timer" in low or "через " in low or " секунд" in low:
            counters["timers"] += 1
        if "automation" in low or "recipe_v2" in low:
            counters["automation"] += 1
        if "cleanup" in low or "archive" in low or "candidate" in low:
            counters["cleanup"] += 1
        if "memory" in low or "digest" in low or "summary" in low or "конспект" in low:
            counters["memory"] += 1
        if "photo" in low or "camera" in low or "фото" in low:
            counters["photos"] += 1
        if "weather" in low or "погод" in low:
            counters["weather"] += 1

        if any(x in low for x in ["создал", "сделал", "почини", "работает", "поднялась", "готово"]):
            important.append(text[:700])
        if any(x in low for x in ["дальше", "следующий", "todo", "потом", "надо"]):
            next_steps.append(text[:700])
        if any(x in low for x in ["action_key", "ask_created", "recipe_v2_created", "schedule", "timer"]):
            actions.append(text[:700])

    return {
        "counters": counters,
        "important": important[:30],
        "errors": errors[:30],
        "next_steps": next_steps[:30],
        "actions": actions[:30],
    }


def generate_daily_summary(target_date: str | None = None, force: bool = False) -> dict[str, Any]:
    _ensure_dirs()

    d = date.fromisoformat(target_date) if target_date else (_now().date() - timedelta(days=1))
    rows = _rows_for_date(d)

    out = DAILY_DIR / f"{d.isoformat()}.md"
    meta = DAILY_DIR / f"{d.isoformat()}.json"

    if out.exists() and not force:
        return {"ok": True, "skipped": True, "reason": "already_exists", "path": str(out.relative_to(ROOT))}

    if not rows:
        _event("daily_summary_skipped", "skipped", {"date": d.isoformat(), "reason": "no_activity"})
        return {"ok": True, "skipped": True, "reason": "no_activity", "date": d.isoformat()}

    data = _classify(rows)
    c = data["counters"]

    content = f"""# GREENHOUSE v17 — Daily Summary

Дата: {d.isoformat()}
Создано: {_iso()}
Источник: `{AI_LOG.relative_to(ROOT)}`
Режим: production daily memory summary

## 1. Коротко

За день обнаружена активность в AI/chat log.

- строк/events: {c['rows']}
- user messages: {c['user_messages']}
- AI/control answers: {c['ai_answers']}
- local/control: {c['local_control']}
- OpenAI: {c['openai']}
- ASK mentions: {c['ask']}
- schedules: {c['schedules']}
- timers: {c['timers']}
- automations: {c['automation']}
- cleanup/memory: {c['cleanup']}/{c['memory']}
- errors/warnings: {c['errors']}

## 2. Важные события

""" + "\n".join(f"- `{x}`" for x in data["important"]) + """

## 3. Действия / ASK / automation

""" + "\n".join(f"- `{x}`" for x in data["actions"]) + """

## 4. Ошибки / warnings

""" + "\n".join(f"- `{x}`" for x in data["errors"]) + """

## 5. Возможные next steps

""" + "\n".join(f"- `{x}`" for x in data["next_steps"]) + """

## 6. Memory status

Raw chat не удалён.
Этот summary является compressed memory layer.
Следующий этап: weekly/monthly compression + cleanup candidates.
"""

    out.write_text(content, encoding="utf-8")
    meta.write_text(json.dumps({
        "type": "daily_summary",
        "date": d.isoformat(),
        "created_at": _iso(),
        "activity_detected": True,
        "source": str(AI_LOG.relative_to(ROOT)),
        "path": str(out.relative_to(ROOT)),
        "counters": c,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    _event("daily_summary_created", "ok", {"date": d.isoformat(), "path": str(out.relative_to(ROOT)), "counters": c})

    return {"ok": True, "path": str(out.relative_to(ROOT)), "meta": str(meta.relative_to(ROOT)), "counters": c}


def _daily_files() -> list[Path]:
    return sorted(DAILY_DIR.glob("*.md"))


def _weekly_files() -> list[Path]:
    return sorted(WEEKLY_DIR.glob("*.md"))


def generate_weekly_if_ready(force: bool = False) -> dict[str, Any]:
    _ensure_dirs()
    files = _daily_files()
    if len(files) < 7:
        return {"ok": True, "skipped": True, "reason": "not_enough_daily", "daily_count": len(files)}

    selected = files[-7:]
    week_key = selected[-1].stem + "_week"
    out = WEEKLY_DIR / f"{week_key}.md"

    if out.exists() and not force:
        return {"ok": True, "skipped": True, "reason": "weekly_exists", "path": str(out.relative_to(ROOT))}

    body = "\n\n---\n\n".join(f"# SOURCE {f.name}\n\n{f.read_text(encoding='utf-8', errors='ignore')}" for f in selected)
    out.write_text(f"""# GREENHOUSE v17 — Weekly Summary

Создано: {_iso()}
Собрано daily summaries: {len(selected)}

{body}
""", encoding="utf-8")

    _event("weekly_summary_created", "ok", {"path": str(out.relative_to(ROOT)), "sources": [f.name for f in selected]})
    return {"ok": True, "path": str(out.relative_to(ROOT)), "sources": [f.name for f in selected]}


def generate_monthly_if_ready(force: bool = False) -> dict[str, Any]:
    _ensure_dirs()
    files = _weekly_files()
    if len(files) < 4:
        return {"ok": True, "skipped": True, "reason": "not_enough_weekly", "weekly_count": len(files)}

    selected = files[-4:]
    month_key = selected[-1].stem + "_month"
    out = MONTHLY_DIR / f"{month_key}.md"

    if out.exists() and not force:
        return {"ok": True, "skipped": True, "reason": "monthly_exists", "path": str(out.relative_to(ROOT))}

    body = "\n\n---\n\n".join(f"# SOURCE {f.name}\n\n{f.read_text(encoding='utf-8', errors='ignore')}" for f in selected)
    out.write_text(f"""# GREENHOUSE v17 — Monthly Summary

Создано: {_iso()}
Собрано weekly summaries: {len(selected)}

{body}
""", encoding="utf-8")

    _event("monthly_summary_created", "ok", {"path": str(out.relative_to(ROOT)), "sources": [f.name for f in selected]})
    return {"ok": True, "path": str(out.relative_to(ROOT)), "sources": [f.name for f in selected]}


def run_summary_cycle(target_date: str | None = None, force: bool = False) -> dict[str, Any]:
    daily = generate_daily_summary(target_date=target_date, force=force)

    ai_daily = {"ok": True, "skipped": True, "reason": "daily_not_created"}
    if daily.get("ok") and not daily.get("skipped"):
        ai_daily = generate_ai_summary_for_latest_daily()

    weekly = generate_rolling_week_ai(force=True)
    monthly = generate_rolling_month_ai(force=True)

    state = _load_state()
    state["last_cycle_at"] = _iso()
    state["last_cycle_result"] = {
        "daily": daily,
        "ai_daily": ai_daily,
        "weekly": weekly,
        "monthly": monthly,
    }
    _save_state(state)

    return {"ok": True, "daily": daily, "ai_daily": ai_daily, "weekly": weekly, "monthly": monthly}


def get_summary_status() -> dict[str, Any]:
    _ensure_dirs()
    state = _load_state()
    daily = sorted(DAILY_DIR.glob("*.md"), reverse=True)
    weekly = sorted(WEEKLY_DIR.glob("*.md"), reverse=True)
    monthly = sorted(MONTHLY_DIR.glob("*.md"), reverse=True)
    rolling_week = [f for f in weekly if f.name == "rolling_week_ai.md"]
    ai_weekly = [f for f in weekly if f.stem.endswith("_week_ai") and f.name != "rolling_week_ai.md"]
    technical_weekly = [f for f in weekly if not f.stem.endswith("_week_ai") and f.name != "rolling_week_ai.md"]
    rolling_month = [f for f in monthly if f.name == "rolling_month_ai.md"]
    ai_monthly = [f for f in monthly if f.stem.endswith("_month_ai") and f.name != "rolling_month_ai.md"]
    technical_monthly = [f for f in monthly if not f.stem.endswith("_month_ai") and f.name != "rolling_month_ai.md"]

    latest_event = None
    if EVENTS_FILE.exists():
        lines = EVENTS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
        if lines:
            try:
                latest_event = json.loads(lines[-1])
            except Exception:
                latest_event = {"raw": lines[-1]}

    local_daily = [f for f in daily if not f.stem.endswith("_ai") and "_ai_" not in f.stem]
    ai_daily = [f for f in daily if f.stem.endswith("_ai")]

    return {
        "ok": True,
        "mode": "production_ai_memory",
        "provider_priority": "DeepSeek → OpenAI",
        "schedule": "daily at 07:00 for yesterday: local source → AI summary",
        "state": state,
        "latest_event": latest_event,
        "counts": {
            "local_daily": len(local_daily),
            "ai_daily": len(ai_daily),
            "rolling_week": len(rolling_week),
            "rolling_month": len(rolling_month),
            "ai_weekly": len(ai_weekly),
            "ai_monthly": len(ai_monthly),
            "technical_weekly": len(technical_weekly),
            "technical_monthly": len(technical_monthly),
        },
        "latest": {
            "local_daily": [{"name": f.name, "path": str(f.relative_to(ROOT)), "size": f.stat().st_size} for f in local_daily[:10]],
            "ai_daily": [{"name": f.name, "path": str(f.relative_to(ROOT)), "size": f.stat().st_size} for f in ai_daily[:10]],
            "rolling_week": [{"name": f.name, "path": str(f.relative_to(ROOT)), "size": f.stat().st_size} for f in rolling_week[:10]],
            "rolling_month": [{"name": f.name, "path": str(f.relative_to(ROOT)), "size": f.stat().st_size} for f in rolling_month[:10]],
            "ai_weekly": [{"name": f.name, "path": str(f.relative_to(ROOT)), "size": f.stat().st_size} for f in ai_weekly[:10]],
            "ai_monthly": [{"name": f.name, "path": str(f.relative_to(ROOT)), "size": f.stat().st_size} for f in ai_monthly[:10]],
            "technical_weekly": [{"name": f.name, "path": str(f.relative_to(ROOT)), "size": f.stat().st_size} for f in technical_weekly[:10]],
            "technical_monthly": [{"name": f.name, "path": str(f.relative_to(ROOT)), "size": f.stat().st_size} for f in technical_monthly[:10]],
        },
    }


async def _summary_worker_loop() -> None:
    _ensure_dirs()
    while True:
        try:
            now = _now()
            state = _load_state()
            today_key = now.date().isoformat()
            if now.time() >= time(7, 0) and state.get("last_daily_worker_date") != today_key:
                result = run_summary_cycle(target_date=(now.date() - timedelta(days=1)).isoformat(), force=False)
                state = _load_state()
                state["last_daily_worker_date"] = today_key
                state["last_daily_worker_at"] = _iso(now)
                state["last_daily_worker_result"] = result
                _save_state(state)
        except Exception as e:
            _event("summary_worker_error", "error", {"error": str(e)})
        await asyncio.sleep(60)


def start_memory_summary_worker() -> dict[str, Any]:
    global _worker_started
    if _worker_started:
        return {"ok": True, "already_started": True}
    _worker_started = True
    asyncio.create_task(_summary_worker_loop())
    _event("summary_worker_started", "ok", {"schedule": "07:00"})
    return {"ok": True, "started": True}


def latest_activity_date() -> str | None:
    rows = _read_jsonl(AI_LOG, limit=50000)
    latest = None
    for r in rows:
        dt = _parse_ts(r.get("ts") or r.get("time") or r.get("created_at"))
        if dt and (latest is None or dt > latest):
            latest = dt
    return latest.date().isoformat() if latest else None


def run_summary_for_latest_activity(force: bool = True) -> dict[str, Any]:
    d = latest_activity_date()
    if not d:
        return {"ok": False, "error": "no_activity_found"}
    return run_summary_cycle(target_date=d, force=force)


def read_summary_file(path: str) -> dict[str, Any]:
    if not path:
        return {"ok": False, "error": "path_required"}

    target = (ROOT / path).resolve()
    allowed = [DAILY_DIR.resolve(), WEEKLY_DIR.resolve(), MONTHLY_DIR.resolve()]

    try:
        if not any(str(target).startswith(str(a)) for a in allowed):
            return {"ok": False, "error": "path_not_allowed"}
    except Exception:
        return {"ok": False, "error": "path_not_allowed"}

    if not target.exists() or not target.is_file():
        return {"ok": False, "error": "file_not_found", "path": path}

    return {
        "ok": True,
        "name": target.name,
        "path": str(target.relative_to(ROOT)),
        "size": target.stat().st_size,
        "content": target.read_text(encoding="utf-8", errors="ignore"),
    }


def _latest_daily_file() -> Path | None:
    files = [
        f for f in sorted(DAILY_DIR.glob("*.md"), reverse=True)
        if not f.stem.endswith("_ai") and "_ai_" not in f.stem
    ]
    return files[0] if files else None


def generate_ai_summary_for_latest_daily() -> dict[str, Any]:
    """
    AI layer over daily summary.
    Production-safe:
    - raw chat не удаляет
    - daily md остаётся source
    - если AI provider недоступен, пишет local fallback
    """
    _ensure_dirs()

    src = _latest_daily_file()
    if not src:
        return {"ok": False, "error": "no_daily_summary"}

    text = src.read_text(encoding="utf-8", errors="ignore")
    out = src.with_name(src.stem + "_ai.md")

    prompt = f"""Ты AI-редактор памяти GREENHOUSE v17.

Сделай короткий полезный конспект для будущего AI-контекста.
Не придумывай факты. Используй только данные ниже.

Формат:
# AI Summary
## Главное
## Что сделали
## Ошибки / проблемы
## Решения / изменения архитектуры
## Что дальше
## Риски / что не забыть

SOURCE:
{text[:45000]}
"""

    ai_text = None
    provider = "local_fallback"

    # Existing GREENHOUSE AI client. Summary priority: DeepSeek -> OpenAI.
    try:
        from greenhouse_v17.services.ai_client import ask_ai_summary
        res = ask_ai_summary(prompt)
        if isinstance(res, dict) and res.get("ok"):
            ai_text = res.get("answer")
            provider = res.get("provider") or "ai_summary"
        else:
            ai_text = None
    except Exception:
        ai_text = None

    if not ai_text:
        _event("ai_daily_summary_skipped", "skipped", {
            "source": str(src.relative_to(ROOT)),
            "reason": "ai_provider_not_connected",
        })
        return {
            "ok": False,
            "error": "ai_provider_not_connected",
            "source": str(src.relative_to(ROOT)),
            "message": "AI provider не подключился. Fake/fallback AI summary больше не создаётся.",
        }

    out.write_text(ai_text, encoding="utf-8")

    _event("ai_daily_summary_created", "ok", {
        "source": str(src.relative_to(ROOT)),
        "path": str(out.relative_to(ROOT)),
        "provider": provider,
    })

    return {
        "ok": True,
        "source": str(src.relative_to(ROOT)),
        "path": str(out.relative_to(ROOT)),
        "provider": provider,
    }


def _ai_compress_summary(source_text: str, title: str, source_label: str) -> dict[str, Any]:
    prompt = f"""Ты AI-редактор памяти GREENHOUSE v17.

Сожми материал в точный структурированный конспект для долгосрочной памяти системы.
Не придумывай факты. Используй только данные ниже.
Пиши на русском, кратко, но с сохранением важных решений, ошибок и next steps.

Формат:
# {title}

## Главное
## Что сделали
## Ошибки / проблемы
## Архитектурные изменения
## Что дальше
## Риски / что не забыть

SOURCE: {source_label}

DATA:
{source_text[:50000]}
"""

    try:
        from greenhouse_v17.services.ai_client import ask_ai_summary
        res = ask_ai_summary(prompt)
        if isinstance(res, dict) and res.get("ok") and res.get("answer"):
            return {
                "ok": True,
                "provider": res.get("provider"),
                "model": res.get("model"),
                "answer": res.get("answer"),
                "fallback_used": res.get("fallback_used"),
            }
        return {
            "ok": False,
            "error": "ai_summary_failed",
            "details": res,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": "ai_summary_exception",
            "details": str(e),
        }


def generate_ai_weekly_if_ready(force: bool = False) -> dict[str, Any]:
    _ensure_dirs()

    ai_daily = sorted([
        f for f in DAILY_DIR.glob("*_ai.md")
        if not f.stem.endswith("_ai_ai")
    ])

    if len(ai_daily) < 7 and not force:
        return {"ok": True, "skipped": True, "reason": "not_enough_ai_daily", "ai_daily_count": len(ai_daily)}

    if not ai_daily:
        return {"ok": True, "skipped": True, "reason": "no_ai_daily"}

    selected = ai_daily[-7:]
    out = WEEKLY_DIR / f"{selected[-1].stem.replace('_ai','')}_week_ai.md"

    source_text = "\n\n---\n\n".join(
        f"# SOURCE {f.name}\n\n{f.read_text(encoding='utf-8', errors='ignore')}"
        for f in selected
    )

    ai = _ai_compress_summary(
        source_text=source_text,
        title="GREENHOUSE v17 — AI Weekly Summary",
        source_label=", ".join(f.name for f in selected),
    )

    if not ai.get("ok"):
        _event("ai_weekly_summary_skipped", "skipped", ai)
        return ai

    out.write_text(ai["answer"], encoding="utf-8")

    _event("ai_weekly_summary_created", "ok", {
        "path": str(out.relative_to(ROOT)),
        "sources": [f.name for f in selected],
        "provider": ai.get("provider"),
        "model": ai.get("model"),
    })

    return {
        "ok": True,
        "path": str(out.relative_to(ROOT)),
        "sources": [f.name for f in selected],
        "provider": ai.get("provider"),
        "model": ai.get("model"),
    }


def generate_ai_monthly_if_ready(force: bool = False) -> dict[str, Any]:
    _ensure_dirs()

    ai_weekly = sorted(WEEKLY_DIR.glob("*_week_ai.md"))

    if len(ai_weekly) < 4 and not force:
        return {"ok": True, "skipped": True, "reason": "not_enough_ai_weekly", "ai_weekly_count": len(ai_weekly)}

    if not ai_weekly:
        return {"ok": True, "skipped": True, "reason": "no_ai_weekly"}

    selected = ai_weekly[-4:]
    out = MONTHLY_DIR / f"{selected[-1].stem.replace('_week_ai','')}_month_ai.md"

    source_text = "\n\n---\n\n".join(
        f"# SOURCE {f.name}\n\n{f.read_text(encoding='utf-8', errors='ignore')}"
        for f in selected
    )

    ai = _ai_compress_summary(
        source_text=source_text,
        title="GREENHOUSE v17 — AI Monthly Summary",
        source_label=", ".join(f.name for f in selected),
    )

    if not ai.get("ok"):
        _event("ai_monthly_summary_skipped", "skipped", ai)
        return ai

    out.write_text(ai["answer"], encoding="utf-8")

    _event("ai_monthly_summary_created", "ok", {
        "path": str(out.relative_to(ROOT)),
        "sources": [f.name for f in selected],
        "provider": ai.get("provider"),
        "model": ai.get("model"),
    })

    return {
        "ok": True,
        "path": str(out.relative_to(ROOT)),
        "sources": [f.name for f in selected],
        "provider": ai.get("provider"),
        "model": ai.get("model"),
    }


def _ai_daily_files() -> list[Path]:
    return sorted([
        f for f in DAILY_DIR.glob("*_ai.md")
        if not f.stem.endswith("_ai_ai")
    ])


def generate_rolling_week_ai(force: bool = True) -> dict[str, Any]:
    _ensure_dirs()

    files = _ai_daily_files()
    if not files:
        return {"ok": True, "skipped": True, "reason": "no_ai_daily"}

    selected = files[-7:]
    out = WEEKLY_DIR / "rolling_week_ai.md"

    source_text = "\n\n---\n\n".join(
        f"# SOURCE {f.name}\n\n{f.read_text(encoding='utf-8', errors='ignore')}"
        for f in selected
    )

    ai = _ai_compress_summary(
        source_text=source_text,
        title="GREENHOUSE v17 — Rolling Week AI Memory",
        source_label=", ".join(f.name for f in selected),
    )

    if not ai.get("ok"):
        _event("rolling_week_ai_skipped", "skipped", ai)
        return ai

    out.write_text(ai["answer"], encoding="utf-8")

    _event("rolling_week_ai_created", "ok", {
        "path": str(out.relative_to(ROOT)),
        "sources": [f.name for f in selected],
        "provider": ai.get("provider"),
        "model": ai.get("model"),
    })

    return {
        "ok": True,
        "path": str(out.relative_to(ROOT)),
        "sources": [f.name for f in selected],
        "provider": ai.get("provider"),
        "model": ai.get("model"),
    }


def generate_rolling_month_ai(force: bool = True) -> dict[str, Any]:
    _ensure_dirs()

    files = _ai_daily_files()
    if not files:
        return {"ok": True, "skipped": True, "reason": "no_ai_daily"}

    selected = files[-28:]
    out = MONTHLY_DIR / "rolling_month_ai.md"

    source_text = "\n\n---\n\n".join(
        f"# SOURCE {f.name}\n\n{f.read_text(encoding='utf-8', errors='ignore')}"
        for f in selected
    )

    ai = _ai_compress_summary(
        source_text=source_text,
        title="GREENHOUSE v17 — Rolling Month AI Memory",
        source_label=", ".join(f.name for f in selected),
    )

    if not ai.get("ok"):
        _event("rolling_month_ai_skipped", "skipped", ai)
        return ai

    out.write_text(ai["answer"], encoding="utf-8")

    _event("rolling_month_ai_created", "ok", {
        "path": str(out.relative_to(ROOT)),
        "sources": [f.name for f in selected],
        "provider": ai.get("provider"),
        "model": ai.get("model"),
    })

    return {
        "ok": True,
        "path": str(out.relative_to(ROOT)),
        "sources": [f.name for f in selected],
        "provider": ai.get("provider"),
        "model": ai.get("model"),
    }


def _read_text_limited(path: Path, limit: int) -> str:
    if not path.exists() or not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text) > limit:
        return text[:limit] + "\n\n[TRUNCATED_FOR_AI_CONTEXT]"
    return text


def _latest_file(pattern_dir: Path, pattern: str) -> Path | None:
    files = sorted(pattern_dir.glob(pattern), reverse=True)
    return files[0] if files else None


def _compact_ai_chat_row(r: dict[str, Any]) -> dict[str, Any]:
    """
    Compact row for current-day context.
    Do NOT include prompt_sent/history_sent/control_result full dumps.
    """
    out = {
        "ts": r.get("ts") or r.get("time") or r.get("created_at"),
        "kind": r.get("kind"),
        "provider": r.get("provider"),
        "model": r.get("model"),
        "user_message": r.get("user_message"),
        "answer": r.get("answer"),
    }

    control = r.get("control_result")
    if isinstance(control, dict):
        out["control_kind"] = control.get("kind")
        out["control_source"] = control.get("source")
        out["action_key"] = control.get("action_key")
        out["control_message"] = control.get("message")

    # trim long fields
    for k in list(out.keys()):
        if isinstance(out[k], str) and len(out[k]) > 1200:
            out[k] = out[k][:1200] + "…"

    return {k: v for k, v in out.items() if v not in [None, "", [], {}]}


def _today_compact_rows(limit: int = 500) -> list[dict[str, Any]]:
    today = _now().date()
    rows = _read_jsonl(AI_LOG, limit=20000)
    out = []

    for r in rows:
        dt = _parse_ts(r.get("ts") or r.get("time") or r.get("created_at"))
        if dt and dt.date() == today:
            out.append(_compact_ai_chat_row(r))

    return out[-limit:]


def generate_today_delta_ai(force: bool = False) -> dict[str, Any]:
    """
    Intermediate AI summary for current day.
    This prevents losing the middle of today between latest daily and recent tail.
    """
    _ensure_dirs()

    rows = _today_compact_rows(limit=500)
    if not rows:
        return {"ok": True, "skipped": True, "reason": "no_today_activity"}

    raw = json.dumps(rows, ensure_ascii=False, indent=2)
    out = TODAY_DIR / "today_delta_ai.md"

    if out.exists() and not force:
        # simple freshness guard: reuse for ~10 minutes
        age = _now().timestamp() - out.stat().st_mtime
        if age < 600:
            return {
                "ok": True,
                "skipped": True,
                "reason": "fresh_existing_today_delta",
                "path": str(out.relative_to(ROOT)),
                "age_seconds": int(age),
            }

    ai = _ai_compress_summary(
        source_text=raw,
        title="GREENHOUSE v17 — Today Delta AI Memory",
        source_label="current day compact ai_chat_io_log rows",
    )

    if not ai.get("ok"):
        _event("today_delta_ai_skipped", "skipped", ai)
        return ai

    out.write_text(ai["answer"], encoding="utf-8")

    _event("today_delta_ai_created", "ok", {
        "path": str(out.relative_to(ROOT)),
        "rows": len(rows),
        "provider": ai.get("provider"),
        "model": ai.get("model"),
    })

    return {
        "ok": True,
        "path": str(out.relative_to(ROOT)),
        "rows": len(rows),
        "provider": ai.get("provider"),
        "model": ai.get("model"),
    }


def build_ai_memory_context(
    *,
    recent_tail_count: int = 20,
    today_raw_char_limit: int = 12000,
    today_row_limit: int = 80,
) -> dict[str, Any]:
    """
    Context bridge for AI chat.

    Returns compact memory blocks:
    - latest daily AI summary
    - rolling week AI summary
    - rolling month AI summary
    - today delta: raw compact rows OR today_delta_ai.md when too large
    """
    _ensure_dirs()

    latest_daily = _latest_daily_file()
    # _latest_daily_file intentionally returns local daily; for AI context need latest *_ai.md
    ai_daily_files = _ai_daily_files()
    latest_ai_daily = ai_daily_files[-1] if ai_daily_files else None

    rolling_week = WEEKLY_DIR / "rolling_week_ai.md"
    rolling_month = MONTHLY_DIR / "rolling_month_ai.md"
    today_delta_file = TODAY_DIR / "today_delta_ai.md"

    today_rows = _today_compact_rows(limit=500)
    today_raw_rows = today_rows[-today_row_limit:]
    today_raw = json.dumps(today_raw_rows, ensure_ascii=False, indent=2)

    today_mode = "raw"
    today_content = today_raw
    today_meta: dict[str, Any] = {
        "mode": "raw",
        "rows_total_today": len(today_rows),
        "rows_sent": len(today_raw_rows),
    }

    if len(today_raw) > today_raw_char_limit or len(today_rows) > today_row_limit:
        gen = generate_today_delta_ai(force=True)
        if gen.get("ok") and today_delta_file.exists():
            today_mode = "ai_summary"
            today_content = _read_text_limited(today_delta_file, 14000)
            today_meta = {
                "mode": "ai_summary",
                "path": str(today_delta_file.relative_to(ROOT)),
                "rows_total_today": len(today_rows),
                "generator": gen,
            }
        else:
            today_content = today_raw[:today_raw_char_limit] + "\n\n[TRUNCATED_TODAY_DELTA_RAW]"
            today_meta = {
                "mode": "raw_truncated",
                "rows_total_today": len(today_rows),
                "rows_sent": len(today_raw_rows),
                "generator_error": gen,
            }

    blocks = {
        "latest_daily_ai": {
            "path": str(latest_ai_daily.relative_to(ROOT)) if latest_ai_daily else None,
            "content": _read_text_limited(latest_ai_daily, 9000) if latest_ai_daily else "",
        },
        "rolling_week_ai": {
            "path": str(rolling_week.relative_to(ROOT)) if rolling_week.exists() else None,
            "content": _read_text_limited(rolling_week, 12000) if rolling_week.exists() else "",
        },
        "rolling_month_ai": {
            "path": str(rolling_month.relative_to(ROOT)) if rolling_month.exists() else None,
            "content": _read_text_limited(rolling_month, 12000) if rolling_month.exists() else "",
        },
        "today_delta": {
            "meta": today_meta,
            "content": today_content,
        },
    }

    meta = {
        "latest_daily_ai": blocks["latest_daily_ai"]["path"],
        "rolling_week_ai": blocks["rolling_week_ai"]["path"],
        "rolling_month_ai": blocks["rolling_month_ai"]["path"],
        "today_delta_mode": today_mode,
        "today_rows_total": len(today_rows),
        "recent_tail_count": recent_tail_count,
    }

    text = f"""
MEMORY_SUMMARY_CONTEXT

[Последний ежедневный ИИ-конспект]
path: {blocks['latest_daily_ai']['path']}
{blocks['latest_daily_ai']['content']}

[Память последних до 7 дней]
path: {blocks['rolling_week_ai']['path']}
{blocks['rolling_week_ai']['content']}

[Память последних до 28 дней]
path: {blocks['rolling_month_ai']['path']}
{blocks['rolling_month_ai']['content']}

TODAY_DELTA_CONTEXT
mode: {today_mode}
meta: {json.dumps(today_meta, ensure_ascii=False)}
{today_content}
"""

    return {
        "ok": True,
        "text": text[:42000],
        "meta": meta,
        "blocks": blocks,
    }
