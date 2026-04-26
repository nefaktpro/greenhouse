from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/home/mi/greenhouse_v17")


FILE_DESCRIPTIONS = {
    "data/registry/devices.csv": {
        "title": "Устройства",
        "purpose": "Главный список устройств и HA entity_id. Source of truth по физическим объектам.",
        "edit": "careful",
    },
    "data/registry/action_map.json": {
        "title": "Action Map",
        "purpose": "Связь action_key → logical_role / operation. Через это работают Control, ASK и AI.",
        "edit": "safe_json",
    },
    "data/registry/device_capabilities.json": {
        "title": "Capabilities",
        "purpose": "Инженерные ограничения устройств: режимы, safety, задержки, verify.",
        "edit": "safe_json",
    },
    "data/registry/scenarios.json": {
        "title": "Scenarios",
        "purpose": "Сценарии как данные, а не Python-код.",
        "edit": "safe_json",
    },
    "data/registry/registry_manifest.json": {
        "title": "Registry Manifest",
        "purpose": "Карта registry-файлов и их роли.",
        "edit": "safe_json",
    },
    "data/registry/nl_map.json": {
        "title": "NL Map",
        "purpose": "Карта живых фраз → action_key для AI Router.",
        "edit": "safe_json",
    },
    "chat/intent_parser.py": {
        "title": "Intent Parser",
        "purpose": "Python-код разбора человеческого текста. Не редактировать из UI.",
        "edit": "critical",
    },
    "ai/router.py": {
        "title": "AI Router",
        "purpose": "Маршрутизация AI-задач: вопрос, observation, команда, память.",
        "edit": "critical",
    },
    "ai/context_builder.py": {
        "title": "Context Builder",
        "purpose": "Собирает минимальный runtime context для AI.",
        "edit": "critical",
    },
    "ai/context_resolver.py": {
        "title": "Context Resolver",
        "purpose": "Контролируемый каталог контекстов для AI.",
        "edit": "critical",
    },
}

ALLOWED_CONTEXTS = [
    {
        "key": "registry",
        "title": "Registry",
        "description": "Канонические устройства, действия, capabilities и scenarios.",
        "files": [
            "data/registry/devices.csv",
            "data/registry/action_map.json",
            "data/registry/device_capabilities.json",
            "data/registry/scenarios.json",
            "data/registry/registry_manifest.json",
            "data/registry/nl_map.json",
        ],
        "access": "metadata_and_safe_preview",
    },
    {
        "key": "runtime",
        "title": "Runtime",
        "description": "Текущий режим, ASK-state и оперативное состояние системы.",
        "files": [
            "system_state.json",
            "ask_state.json",
        ],
        "access": "safe_runtime",
    },
    {
        "key": "chat",
        "title": "Chat / Intent",
        "description": "Natural language вход, intent parser и AI router.",
        "files": [
            "chat/intent_parser.py",
            "chat/chat_router.py",
            "ai/router.py",
            "ai/context_builder.py",
            "ai/context_resolver.py",
        ],
        "access": "metadata_only",
    },
    {
        "key": "memory",
        "title": "Memory",
        "description": "Будущая активная память, observations, summaries, cleanup.",
        "files": [
            "knowledge.json",
            "chat_history.json",
            "decision_log.json",
            "strawberry_log.json",
            "data/memory/logs/manual_log.json",
            "data/memory/logs/ask_log.json",
            "data/memory/logs/test_log.json",
            "data/memory/logs/auto_log.json",
            "data/memory/logs/autopilot_log.json",
            "data/memory/logs/all_events_log.json",
        ],
        "access": "planned_or_optional",
    },
]


def _safe_path(path: str) -> Path:
    p = (ROOT / path).resolve()
    if not str(p).startswith(str(ROOT.resolve())):
        raise ValueError("path_outside_project")
    return p


def _json_meta(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {"type": "dict", "size": len(data), "keys": list(data.keys())[:20]}
        if isinstance(data, list):
            return {"type": "list", "size": len(data)}
        return {"type": type(data).__name__}
    except Exception as e:
        return {"type": "json_error", "error": str(e)}


def _file_meta(path_str: str) -> Dict[str, Any]:
    path = _safe_path(path_str)
    desc = FILE_DESCRIPTIONS.get(path_str, {})
    meta = {
        "path": path_str,
        "title": desc.get("title", path_str),
        "purpose": desc.get("purpose", "Описание пока не добавлено."),
        "edit": desc.get("edit", "readonly"),
        "exists": path.exists(),
    }
    if not path.exists():
        return meta

    stat = path.stat()
    meta.update({
        "size_bytes": stat.st_size,
        "suffix": path.suffix,
    })

    if path.suffix == ".json":
        meta["json"] = _json_meta(path)
    elif path.suffix == ".csv":
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            meta["csv"] = {
                "lines": len(lines),
                "header": lines[0] if lines else "",
            }
        except Exception as e:
            meta["csv"] = {"error": str(e)}
    else:
        meta["preview"] = "metadata_only"

    return meta


def get_context_catalog() -> Dict[str, Any]:
    contexts: List[Dict[str, Any]] = []

    for ctx in ALLOWED_CONTEXTS:
        files = [_file_meta(f) for f in ctx["files"]]
        contexts.append({
            **ctx,
            "files": files,
            "files_total": len(files),
            "files_existing": sum(1 for f in files if f.get("exists")),
        })

    return {
        "ok": True,
        "policy": {
            "ai_direct_file_access": False,
            "ai_direct_ha_access": False,
            "ai_direct_execution": False,
            "resolver_required": True,
        },
        "contexts": contexts,
    }



def read_context_file(path_str: str) -> Dict[str, Any]:
    path = _safe_path(path_str)
    meta = _file_meta(path_str)

    if not path.exists():
        return {"ok": False, "error": "file_not_found", "meta": meta}

    # Большой лимит для AI Context UI.
    # Не бесконечный, чтобы случайно не положить браузер огромной историей.
    # Для будущих больших чатов/памяти позже добавим пагинацию/чанки.
    max_chars = 5_000_000

    content = path.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": True,
        "meta": meta,
        "content": content[:max_chars],
        "truncated": len(content) > max_chars,
    }




def save_context_file(path_str: str, content: str) -> Dict[str, Any]:
    from datetime import datetime
    import shutil

    meta = _file_meta(path_str)

    if not meta.get("exists"):
        return {"ok": False, "error": "file_not_found", "meta": meta}

    allowed = {f for ctx in ALLOWED_CONTEXTS for f in ctx["files"]}
    if path_str not in allowed:
        return {"ok": False, "error": "file_not_in_context_catalog", "meta": meta}

    path = _safe_path(path_str)
    edit_mode = meta.get("edit", "critical")

    # JSON валидируем, остальные файлы сохраняем как текст.
    if path.suffix == ".json":
        try:
            parsed = json.loads(content)
        except Exception as e:
            return {"ok": False, "error": "invalid_json", "details": str(e), "meta": meta}
        new_content = json.dumps(parsed, ensure_ascii=False, indent=2) + "\n"
    else:
        new_content = content
        if not new_content.endswith("\n"):
            new_content += "\n"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "backups" / "ui_edits" / ts
    backup_path = backup_dir / path.relative_to(ROOT)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)

    path.write_text(new_content, encoding="utf-8")

    return {
        "ok": True,
        "path": path_str,
        "edit": edit_mode,
        "backup": str(backup_path.relative_to(ROOT)),
        "warning": "edited_from_ai_context_ui",
        "meta": _file_meta(path_str),
    }



def list_backups():
    import os
    base = ROOT / "backups" / "ui_edits"
    items = []

    if not base.exists():
        return {"ok": True, "items": []}

    for root, _, files in os.walk(base):
        for f in files:
            full = Path(root) / f
            rel = full.relative_to(ROOT)

            items.append({
                "path": str(rel),
                "name": f,
                "size": full.stat().st_size
            })

    items.sort(key=lambda x: x["path"], reverse=True)
    return {"ok": True, "items": items}


def restore_backup(backup_path: str):
    src = _safe_path(backup_path)

    if not src.exists():
        return {"ok": False, "error": "backup_not_found"}

    # вытаскиваем оригинальный путь
    parts = src.parts
    try:
        idx = parts.index("ui_edits")
        original = ROOT / Path(*parts[idx+2:])  # пропускаем timestamp
    except:
        return {"ok": False, "error": "invalid_backup_path"}

    original.parent.mkdir(parents=True, exist_ok=True)

    original.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    return {"ok": True, "restored_to": str(original)}

# === Human descriptions for AI Context UI ===
FILE_DESCRIPTIONS.update({
    "system_state.json": {
        "title": "System State",
        "purpose": "Текущий режим системы и флаги поведения. Важно для MANUAL / ASK / TEST / AUTO.",
        "edit": "careful"
    },
    "ask_state.json": {
        "title": "ASK State",
        "purpose": "Текущее pending-действие, ожидающее подтверждения. Обычно меняется системой.",
        "edit": "careful"
    },

    "knowledge.json": {
        "title": "Knowledge",
        "purpose": "База знаний / заметки / правила / факты для будущей памяти AI.",
        "edit": "safe_json"
    },
    "chat_history.json": {
        "title": "Chat History",
        "purpose": "История сообщений чата. В будущем AI сможет запрашивать её срезами.",
        "edit": "careful"
    },
    "decision_log.json": {
        "title": "Old Decision Log",
        "purpose": "Старый общий лог решений. Сейчас основной лог переехал в data/memory/logs/.",
        "edit": "careful"
    },
    "strawberry_log.json": {
        "title": "Strawberry Log",
        "purpose": "Агрономические наблюдения по клубнике: состояние, рост, проблемы, заметки.",
        "edit": "safe_json"
    },

    "data/memory/knowledge.json": {
        "title": "Memory / Knowledge",
        "purpose": "Новая база знаний AI: notes, rules, facts.",
        "edit": "safe_json"
    },
    "data/memory/chat_history.json": {
        "title": "Memory / Chat History",
        "purpose": "Новая история чата для AI-памяти. Длинные истории позже лучше читать чанками.",
        "edit": "careful"
    },
    "data/memory/decision_log.json": {
        "title": "Memory / Decision Log",
        "purpose": "Общий decision log старого формата. Сейчас режимные логи лежат в data/memory/logs/.",
        "edit": "careful"
    },
    "data/memory/strawberry_log.json": {
        "title": "Memory / Strawberry Log",
        "purpose": "Новая агро-память по клубнике: наблюдения, события, выводы.",
        "edit": "safe_json"
    },

    "data/memory/logs/manual_log.json": {
        "title": "Manual Log",
        "purpose": "Лог действий в MANUAL: что пользователь выполнил напрямую.",
        "edit": "careful"
    },
    "data/memory/logs/ask_log.json": {
        "title": "ASK Log",
        "purpose": "Лог ASK: что было создано, подтверждено или отменено через подтверждение.",
        "edit": "careful"
    },
    "data/memory/logs/test_log.json": {
        "title": "TEST Log",
        "purpose": "Лог TEST/dry-run: что система хотела бы сделать, но не исполняла.",
        "edit": "careful"
    },
    "data/memory/logs/auto_log.json": {
        "title": "AUTO Log",
        "purpose": "Лог AUTO-режима: автоматические действия без участия пользователя.",
        "edit": "critical"
    },
    "data/memory/logs/autopilot_log.json": {
        "title": "Autopilot Log",
        "purpose": "Основной лог будущего AI-автопилота. AI должен читать его первым, а остальные логи — по запросу.",
        "edit": "critical"
    },
    "data/memory/logs/all_events_log.json": {
        "title": "All Events Index",
        "purpose": "Короткий общий индекс событий по всем режимам. Нужен для навигации по логам.",
        "edit": "careful"
    },

    "chat/chat_router.py": {
        "title": "Chat Router",
        "purpose": "Главный обработчик чата: текст → intent → режим → ASK или execution.",
        "edit": "critical"
    }
})

# --- AI Chat prompt as explicit Memory context file ---
# Added by GREENHOUSE v17 AI Chat integration.
try:
    _original_get_context_catalog_for_ai_prompt
except NameError:
    _original_get_context_catalog_for_ai_prompt = get_context_catalog

    def get_context_catalog():
        catalog = _original_get_context_catalog_for_ai_prompt()

        prompt_item = {
            "path": "data/memory/ai_chat_system_prompt.md",
            "title": "AI Chat System Prompt",
            "purpose": "Файл, который всегда добавляется к каждому сообщению в AI Chat: роль ИИ, правила поведения и базовое знание о GREENHOUSE v17.",
            "edit": "careful",
            "exists": True,
        }

        contexts = catalog.get("contexts", []) if isinstance(catalog, dict) else []

        memory_ctx = None
        for ctx in contexts:
            title = str(ctx.get("title", "")).lower()
            key = str(ctx.get("key", "")).lower()
            if "memory" in title or "memory" in key:
                memory_ctx = ctx
                break

        if memory_ctx is None:
            memory_ctx = {
                "key": "memory",
                "title": "Memory",
                "description": "Память AI, знания, история и системные prompt-файлы.",
                "files": [],
            }
            contexts.append(memory_ctx)

        files = memory_ctx.setdefault("files", [])
        if not any(f.get("path") == prompt_item["path"] for f in files):
            files.append(prompt_item)

        if isinstance(catalog, dict):
            catalog["contexts"] = contexts

        return catalog

# --- allow saving AI Chat system prompt ---
try:
    _original_save_context_file_for_ai_prompt
except NameError:
    _original_save_context_file_for_ai_prompt = save_context_file

    def save_context_file(path: str, content: str):
        if path == "data/memory/ai_chat_system_prompt.md":
            from pathlib import Path
            root = Path("/home/mi/greenhouse_v17")
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)

            backup_dir = root / "backups" / "ui_edits"
            backup_dir.mkdir(parents=True, exist_ok=True)

            if target.exists():
                import datetime
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"ai_chat_system_prompt.md.{ts}.bak"
                backup_path.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")

            target.write_text(content, encoding="utf-8")
            return {
                "ok": True,
                "path": path,
                "message": "saved",
                "backup": True,
            }

        return _original_save_context_file_for_ai_prompt(path, content)

# --- AI watch marks for context catalog ---
try:
    _original_get_context_catalog_ai_watch
except NameError:
    _original_get_context_catalog_ai_watch = get_context_catalog

    AI_WATCH_HINTS = {
        "system_state.json": "Режим системы: MANUAL / ASK / TEST и флаги execute/ask/ai_control.",
        "data/runtime/ask_state.json": "Текущий pending ASK: что ждёт подтверждения.",
        "data/registry/devices.csv": "Главный список устройств, entity_id, зоны и роли.",
        "data/registry/action_map.json": "Список action_key, которые можно отправлять в pipeline.",
        "data/registry/device_capabilities.json": "Ограничения, зависимости и разрешённые действия устройств.",
        "data/memory/ai_chat_system_prompt.md": "Главный prompt AI Chat: роль, правила и базовое знание системы.",
        "data/memory/ai_chat_io_log.jsonl": "Что реально уходило в ИИ и что он отвечал.",
        "data/memory/logs/manual_log.json": "История ручных действий.",
        "data/memory/logs/ask_log.json": "История ASK действий.",
    }

    def get_context_catalog():
        catalog = _original_get_context_catalog_ai_watch()
        for ctx in catalog.get("contexts", []):
            for f in ctx.get("files", []):
                p = f.get("path", "")
                for key, hint in AI_WATCH_HINTS.items():
                    if key in p:
                        f["ai_watch"] = True
                        f["ai_watch_hint"] = hint
                        f["purpose"] = hint
                        if f.get("edit") == "readonly" and "ai_chat_system_prompt.md" in p:
                            f["edit"] = "careful"
        return catalog

# --- AI Chat history/log files in catalog ---
try:
    _original_get_context_catalog_chat_history_files
except NameError:
    _original_get_context_catalog_chat_history_files = get_context_catalog

    def get_context_catalog():
        catalog = _original_get_context_catalog_chat_history_files()
        contexts = catalog.get("contexts", []) if isinstance(catalog, dict) else []

        def find_or_create(key, title, description):
            for ctx in contexts:
                if str(ctx.get("key", "")).lower() == key or str(ctx.get("title", "")).lower() == title.lower():
                    return ctx
            ctx = {"key": key, "title": title, "description": description, "files": []}
            contexts.append(ctx)
            return ctx

        memory = find_or_create("memory", "Memory", "Память AI, история чата, знания и системные prompt-файлы.")
        logs = find_or_create("logs", "Logs", "Логи действий, запросов к AI и системных событий.")

        items = [
            (memory, {
                "path": "data/runtime/ai_chat_live_history.json",
                "title": "AI Chat Live History",
                "purpose": "Полная сохранённая история нового AI Chat: user/assistant сообщения.",
                "edit": "careful",
                "exists": True,
                "ai_watch": True,
                "ai_watch_hint": "Здесь смотреть всю историю разговорного AI-чата.",
            }),
            (logs, {
                "path": "data/memory/ai_chat_io_log.jsonl",
                "title": "AI Chat IO Log",
                "purpose": "Подробный лог: что ушло в ИИ, какой контекст был приложен и что ИИ ответил.",
                "edit": "careful",
                "exists": True,
                "ai_watch": True,
                "ai_watch_hint": "Главный debug-лог AI Chat.",
            }),
        ]

        for ctx, item in items:
            files = ctx.setdefault("files", [])
            if not any(f.get("path") == item["path"] for f in files):
                files.append(item)

        if isinstance(catalog, dict):
            catalog["contexts"] = contexts
        return catalog

# --- AI requestability marks for context catalog ---
try:
    _original_get_context_catalog_requestable_marks
except NameError:
    _original_get_context_catalog_requestable_marks = get_context_catalog

    AI_FILE_HINTS = {
        "data/runtime/ask_state.json": "Текущий pending ASK: что ожидает подтверждения прямо сейчас.",
        "data/registry/scenarios.json": "Сценарии как данные: будущие правила и цепочки действий.",
        "data/registry/registry_manifest.json": "Карта registry-файлов и их роли.",
        "data/registry/nl_map.json": "Живые фразы пользователя → action_key для AI Router.",
        "data/registry/devices.csv": "Главный список устройств, entity_id, зоны и роли.",
        "data/registry/action_map.json": "Доступные action_key и связь с execution pipeline.",
        "data/registry/device_capabilities.json": "Возможности, ограничения и safety-условия устройств.",
        "knowledge.json": "База знаний / заметки / правила / факты для AI-памяти.",
        "chat_history.json": "Старая/общая история сообщений чата.",
        "data/runtime/ai_chat_live_history.json": "Новая сохранённая история AI Chat.",
        "decision_log.json": "Старый общий лог решений; нужен только как reference.",
        "strawberry_log.json": "Агрономические наблюдения по клубнике.",
        "data/memory/logs/test_log.json": "TEST/dry-run лог: что система хотела бы сделать без исполнения.",
        "data/memory/logs/auto_log.json": "AUTO-лог: автоматические действия.",
        "data/memory/logs/autopilot_log.json": "Будущий основной лог AI-автопилота.",
        "data/memory/logs/all_events_log.json": "Индекс событий по всем режимам.",
        "data/memory/logs/ask_log.json": "ASK-лог: создано / подтверждено / отменено.",
        "data/memory/logs/manual_log.json": "MANUAL-лог: ручные действия.",
        "data/memory/ai_chat_io_log.jsonl": "AI debug: что уходило в ИИ и что он отвечал.",
        "data/memory/ai_chat_system_prompt.md": "Главный system prompt AI Chat.",
        "chat/intent_parser.py": "Код разбора естественного языка. Смотреть для отладки intent.",
        "chat/chat_router.py": "Обработчик чата: intent → mode → ASK/execution.",
        "ai/router.py": "Маршрутизация AI-задач.",
        "ai/context_builder.py": "Сбор минимального runtime context.",
        "ai/context_resolver.py": "Каталог и безопасная выдача контекстов.",
    }

    def get_context_catalog():
        catalog = _original_get_context_catalog_requestable_marks()
        for ctx in catalog.get("contexts", []):
            for f in ctx.get("files", []):
                p = str(f.get("path", ""))

                # Всё, что есть в каталоге, ИИ может запросить через REQUEST_CONTEXT.
                f["ai_requestable"] = bool(f.get("exists", True))
                f["ai_request_rule"] = "ИИ может запросить этот файл только через REQUEST_CONTEXT. Содержимое не отправляется автоматически."

                for key, hint in AI_FILE_HINTS.items():
                    if key in p or p.endswith(key):
                        f["ai_watch"] = True
                        f["ai_watch_hint"] = hint
                        if not f.get("purpose") or f.get("purpose") == "Описание пока не добавлено.":
                            f["purpose"] = hint
                        break

        return catalog

# --- stronger context descriptions for AI catalog ---
try:
    _original_get_context_catalog_better_hints
except NameError:
    _original_get_context_catalog_better_hints = get_context_catalog

    BETTER_CONTEXT_HINTS = {
        "system_state.json": {
            "purpose": "Текущий режим системы и режимные флаги: MANUAL / ASK / TEST, execute, ask, ai_control.",
            "watch": "Смотреть, когда нужно понять текущий режим и можно ли выполнять действия."
        },
        "ask_state.json": {
            "purpose": "Текущее pending ASK-действие: есть ли действие, которое ждёт подтверждения.",
            "watch": "Смотреть, когда пользователь спрашивает что сейчас ждёт подтверждения или почему действие не выполнилось."
        },
        "data/registry/devices.csv": {
            "purpose": "Главный список устройств: device_id, entity_id, зона, location, logical_role, enabled/criticality.",
            "watch": "Смотреть, когда нужно понять какие устройства есть и к каким HA entity они привязаны."
        },
        "data/registry/action_map.json": {
            "purpose": "Карта action_key → target_role + operation. Через неё команды попадают в execution pipeline.",
            "watch": "Смотреть, когда нужно понять какие действия доступны или какой action_key нужен."
        },
        "data/registry/device_capabilities.json": {
            "purpose": "Возможности и ограничения logical_role: что можно делать, safety, зависимости, cooldown, verify.",
            "watch": "Смотреть перед рекомендациями действий и при вопросах о безопасности."
        },
        "data/registry/scenarios.json": {
            "purpose": "Сценарии как данные: наборы действий/логика сценариев без Python-кода.",
            "watch": "Смотреть, когда вопрос про сценарии, автоматизацию или наборы действий."
        },
        "data/registry/registry_manifest.json": {
            "purpose": "Карта registry-файлов: какие registry-файлы существуют и какую роль выполняют.",
            "watch": "Смотреть, когда нужно разобраться в структуре registry."
        },
        "data/registry/nl_map.json": {
            "purpose": "Карта естественных фраз пользователя → action_key для natural language управления.",
            "watch": "Смотреть, когда чат не понимает команду или нужно добавить новую фразу."
        },
        "knowledge.json": {
            "purpose": "База знаний: факты, правила, заметки и устойчивые знания для будущей AI-памяти.",
            "watch": "Смотреть, когда пользователь спрашивает что система уже знает."
        },
        "chat_history.json": {
            "purpose": "Старая/общая история чата. Сейчас основной новый AI Chat хранится отдельно.",
            "watch": "Смотреть только если нужен старый контекст."
        },
        "data/runtime/ai_chat_live_history.json": {
            "purpose": "Новая история AI Chat: пары сообщений user/assistant.",
            "watch": "Смотреть, когда нужна вся история текущего AI-чата."
        },
        "data/memory/ai_chat_io_log.jsonl": {
            "purpose": "AI IO log: полный debug того, что было отправлено в ИИ, какие файлы подложены и что ИИ ответил.",
            "watch": "Смотреть для отладки AI-ответов и REQUEST_CONTEXT."
        },
        "data/memory/logs/ask_log.json": {
            "purpose": "ASK log: события ask_created / ask_confirmed / ask_cancelled и результаты verify.",
            "watch": "Смотреть, когда вопрос про историю ASK действий."
        },
        "data/memory/logs/manual_log.json": {
            "purpose": "MANUAL log: история действий, выполненных в ручном режиме.",
            "watch": "Смотреть, когда вопрос про ручные действия."
        },
        "data/memory/logs/all_events_log.json": {
            "purpose": "Общий индекс событий по всем режимам: навигация по логам.",
            "watch": "Смотреть первым, если непонятно в каком логе искать событие."
        },
        "data/memory/ai_chat_system_prompt.md": {
            "purpose": "System prompt AI Chat: роль ИИ, правила поведения, REQUEST_CONTEXT protocol.",
            "watch": "Смотреть, когда ИИ неправильно себя ведёт или не знает правила."
        },
        "chat/intent_parser.py": {
            "purpose": "Код распознавания intent из естественного языка.",
            "watch": "Смотреть при проблемах распознавания команд."
        },
        "chat/chat_router.py": {
            "purpose": "Код маршрутизации чата: intent → режим → ASK/execution.",
            "watch": "Смотреть при проблемах Chat → action pipeline."
        },
        "ai/router.py": {
            "purpose": "AI Router: классификация AI-задач и маршрутизация reasoning.",
            "watch": "Смотреть при развитии AI-задач."
        },
        "ai/context_builder.py": {
            "purpose": "Context Builder: сбор минимального runtime context для AI.",
            "watch": "Смотреть, если AI не видит нужный runtime context."
        },
        "ai/context_resolver.py": {
            "purpose": "Context Resolver: каталог файлов и безопасная выдача содержимого по REQUEST_CONTEXT.",
            "watch": "Смотреть, если файл не выдаётся или не отображается в AI Context."
        },
    }

    def get_context_catalog():
        catalog = _original_get_context_catalog_better_hints()
        for ctx in catalog.get("contexts", []):
            for f in ctx.get("files", []):
                p = str(f.get("path", ""))
                matched = None
                for key, val in BETTER_CONTEXT_HINTS.items():
                    if p == key or p.endswith(key) or key in p:
                        matched = val
                        break

                f["ai_requestable"] = bool(f.get("exists", True))
                f["ai_request_rule"] = "ИИ может запросить этот файл через REQUEST_CONTEXT; содержимое не отправляется автоматически."

                if matched:
                    f["purpose"] = matched["purpose"]
                    f["ai_watch"] = True
                    f["ai_watch_hint"] = matched["watch"]

        return catalog

# --- editable AI Context descriptions from JSON ---
try:
    _original_get_context_catalog_external_overrides
except NameError:
    _original_get_context_catalog_external_overrides = get_context_catalog

    def _load_ai_context_overrides():
        import json
        from pathlib import Path
        p = Path("/home/mi/greenhouse_v17/data/memory/ai_context_catalog_overrides.json")
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def get_context_catalog():
        catalog = _original_get_context_catalog_external_overrides()
        overrides = _load_ai_context_overrides()

        # ensure overrides file itself is visible/editable
        contexts = catalog.get("contexts", [])
        memory = None
        for ctx in contexts:
            if str(ctx.get("key", "")).lower() == "memory" or str(ctx.get("title", "")).lower() == "memory":
                memory = ctx
                break
        if memory is None:
            memory = {"key": "memory", "title": "Memory", "description": "Память и AI-настройки.", "files": []}
            contexts.append(memory)

        files = memory.setdefault("files", [])
        if not any(f.get("path") == "data/memory/ai_context_catalog_overrides.json" for f in files):
            files.append({
                "path": "data/memory/ai_context_catalog_overrides.json",
                "title": "AI Context Catalog Overrides",
                "purpose": "Редактируемые описания файлов AI Context.",
                "edit": "safe_json",
                "exists": True
            })

        for ctx in catalog.get("contexts", []):
            for f in ctx.get("files", []):
                path = str(f.get("path", ""))
                f["ai_requestable"] = bool(f.get("exists", True))
                f["ai_request_rule"] = "ИИ может запросить этот файл через REQUEST_CONTEXT; содержимое не отправляется автоматически."

                match = None
                for key, val in overrides.items():
                    if path == key or path.endswith(key) or key in path:
                        match = val
                        break

                if match:
                    f["purpose"] = match.get("purpose", f.get("purpose"))
                    f["ai_watch"] = True
                    f["ai_watch_hint"] = match.get("ai_watch_hint", f.get("ai_watch_hint"))

        catalog["contexts"] = contexts
        return catalog

# --- AI Core section shown in AI Context UI ---
try:
    _original_get_context_catalog_ai_core_section
except NameError:
    _original_get_context_catalog_ai_core_section = get_context_catalog

    def get_context_catalog():
        catalog = _original_get_context_catalog_ai_core_section()
        contexts = catalog.get("contexts", [])

        core_key = "ai_core"
        core_files = [
            {
                "path": "data/memory/ai_chat_system_prompt.md",
                "title": "System Prompt",
                "purpose": "Постоянные правила поведения AI Chat: роль ИИ, ограничения и REQUEST_CONTEXT protocol.",
                "edit": "careful",
                "exists": True,
                "ai_requestable": True,
                "ai_watch": True,
                "ai_watch_hint": "Добавляется к каждому сообщению в AI Chat."
            },
            {
                "path": "CURRENT_CONTEXT / build_context()",
                "title": "Current Context",
                "purpose": "Текущий runtime context: режим, флаги и оперативное состояние. Отправляется в ИИ с каждым сообщением.",
                "edit": "readonly",
                "exists": True,
                "ai_requestable": False,
                "ai_watch": True,
                "ai_watch_hint": "Не отдельный файл; собирается автоматически."
            },
            {
                "path": "data/runtime/ai_chat_live_history.json",
                "title": "Recent Dialog History",
                "purpose": "История AI Chat. В ИИ уходит короткий хвост последних сообщений, полный файл можно запросить отдельно.",
                "edit": "careful",
                "exists": True,
                "ai_requestable": True,
                "ai_watch": True,
                "ai_watch_hint": "Нужен для памяти текущего разговора."
            },
            {
                "path": "AVAILABLE_CONTEXT_CATALOG",
                "title": "Available Context Catalog",
                "purpose": "Каталог разрешённых источников: section, path, title, purpose, ai_requestable, ai_watch_hint.",
                "edit": "readonly",
                "exists": True,
                "ai_requestable": False,
                "ai_watch": True,
                "ai_watch_hint": "Отправляется в ИИ с каждым сообщением как карта того, что можно запросить."
            },
            {
                "path": "data/memory/ai_context_catalog_overrides.json",
                "title": "Catalog Descriptions",
                "purpose": "Редактируемые описания файлов AI Context: что внутри и когда ИИ должен их запрашивать.",
                "edit": "safe_json",
                "exists": True,
                "ai_requestable": True,
                "ai_watch": True,
                "ai_watch_hint": "Главное место для редактирования описаний файлов."
            },
            {
                "path": "data/memory/ai_chat_io_log.jsonl",
                "title": "AI IO Log",
                "purpose": "Длинный debug-лог: что ушло в ИИ, какой context/history/catalog был приложен и что ИИ ответил.",
                "edit": "careful",
                "exists": True,
                "ai_requestable": True,
                "ai_watch": True,
                "ai_watch_hint": "Нужен для проверки, что реально отправлялось в модель."
            },
        ]

        # удалить старый ai_core, если есть
        contexts = [c for c in contexts if str(c.get("key")) != core_key]

        contexts.insert(0, {
            "key": core_key,
            "title": "Основное для ИИ",
            "description": "Что постоянно уходит в AI Chat и чем он пользуется для запросов.",
            "files": core_files,
            "access": "ai_runtime_map",
            "files_total": len(core_files),
            "files_existing": len(core_files),
        })

        catalog["contexts"] = contexts
        return catalog
