#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/mi/greenhouse_v17"
cd "$ROOT"

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/backups/hotfix_web_actions_$TS"
mkdir -p "$BACKUP_DIR"

backup_if_exists() {
  local path="$1"
  if [ -f "$path" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$path")"
    cp "$path" "$BACKUP_DIR/$path"
    echo "[backup] $path"
  fi
}

backup_if_exists "greenhouse_v17/services/webadmin_execution_service.py"
backup_if_exists "interfaces/web_admin/routes/web.py"
backup_if_exists "interfaces/web_admin/routes/actions.py"

python3 - <<'PY'
from pathlib import Path
import re

path = Path("/home/mi/greenhouse_v17/interfaces/web_admin/routes/web.py")
text = path.read_text(encoding="utf-8")

# 1) Чиним TemplateResponse на keyword-аргументы
text = re.sub(
    r'templates\.TemplateResponse\(\s*"([^"]+)"\s*,\s*\{"request":\s*request\}\s*\)',
    r'templates.TemplateResponse(request=request, name="\1", context={"request": request})',
    text,
)

# 2) Если где-то уже есть другие старые вызовы с request-первым аргументом не трогаем
path.write_text(text, encoding="utf-8")
print("[patched] interfaces/web_admin/routes/web.py")
PY

cat > greenhouse_v17/services/webadmin_execution_service.py <<'PY'
from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = Path("/home/mi/greenhouse_v17")
REGISTRY_DIR = ROOT / "data" / "registry"
RUNTIME_DIR = ROOT / "data" / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

ACTION_MAP_PATH = REGISTRY_DIR / "action_map.json"
DEVICES_PATH = REGISTRY_DIR / "devices.csv"
ASK_STATE_PATH = RUNTIME_DIR / "web_ask_state.json"
SYSTEM_STATE_PATH = ROOT / "system_state.json"
EXECUTION_LOG_PATH = RUNTIME_DIR / "execution_log.jsonl"

DEFAULT_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))
VERIFY_SLEEP_SEC = float(os.getenv("GH_VERIFY_SLEEP_SEC", "2.0"))

HA_URL = (
    os.getenv("HOME_ASSISTANT_URL")
    or os.getenv("HA_BASE_URL")
    or os.getenv("HOME_ASSISTANT_BASE_URL")
    or "http://127.0.0.1:8123"
).rstrip("/")

HA_TOKEN = (
    os.getenv("HOME_ASSISTANT_TOKEN")
    or os.getenv("HA_TOKEN")
    or ""
)

HEADERS = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json",
}

EXPECTED_BY_OPERATION = {
    "turn_on": "on",
    "turn_off": "off",
    "open": "open",
    "close": "closed",
    "open_cover": "open",
    "close_cover": "closed",
    "fan_on": "on",
    "fan_off": "off",
    "light_on": "on",
    "light_off": "off",
}

SERVICE_BY_OPERATION = {
    "turn_on": ("switch", "turn_on"),
    "turn_off": ("switch", "turn_off"),
    "toggle": ("switch", "toggle"),
    "fan_on": ("fan", "turn_on"),
    "fan_off": ("fan", "turn_off"),
    "light_on": ("light", "turn_on"),
    "light_off": ("light", "turn_off"),
    "open": ("cover", "open_cover"),
    "close": ("cover", "close_cover"),
    "open_cover": ("cover", "open_cover"),
    "close_cover": ("cover", "close_cover"),
}

ALIASES = {
    "fan_low_on": "fan_bottom_on",
    "fan_low_off": "fan_bottom_off",
    "fan_bottom_on": "fan_low_on",
    "fan_bottom_off": "fan_low_off",
}

@dataclass
class ExecutionResult:
    ok: bool
    action_key: str
    entity_id: Optional[str] = None
    operation: Optional[str] = None
    requested_mode: Optional[str] = None
    dry_run: bool = False
    expected_state: Optional[str] = None
    actual_state: Optional[str] = None
    verified: bool = False
    service_domain: Optional[str] = None
    service_name: Optional[str] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_action_map_payload(raw: Any) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}

    def consume_item(item: Any) -> None:
        if not isinstance(item, dict):
            return
        key = (
            item.get("action_key")
            or item.get("key")
            or item.get("name")
            or item.get("id")
        )
        if key:
            out[str(key)] = item

    if isinstance(raw, list):
        for item in raw:
            consume_item(item)
        return out

    if isinstance(raw, dict):
        # формат {"items":[...]}
        if isinstance(raw.get("items"), list):
            for item in raw["items"]:
                consume_item(item)

        # формат {"actions":[...]}
        if isinstance(raw.get("actions"), list):
            for item in raw["actions"]:
                consume_item(item)

        # формат {"fan_top_on": {...}, ...}
        for k, v in raw.items():
            if isinstance(v, dict):
                if "action_key" not in v:
                    vv = dict(v)
                    vv["action_key"] = k
                    out[str(k)] = vv
                else:
                    out[str(k)] = v

    return out


@lru_cache(maxsize=1)
def load_action_map() -> Dict[str, Any]:
    raw = _json_load(ACTION_MAP_PATH, {})
    return _normalize_action_map_payload(raw)


@lru_cache(maxsize=1)
def load_devices_index() -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    if not DEVICES_PATH.exists():
        return out

    with DEVICES_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            normalized = {str(k).strip(): str(v).strip() for k, v in row.items() if k is not None}
            device_id = (
                normalized.get("ID")
                or normalized.get("DeviceID")
                or normalized.get("device_id")
                or normalized.get("id")
            )
            if device_id:
                out[str(device_id)] = normalized
    return out


def debug_action_map_summary() -> Dict[str, Any]:
    amap = load_action_map()
    return {
        "action_map_path": str(ACTION_MAP_PATH),
        "exists": ACTION_MAP_PATH.exists(),
        "count": len(amap),
        "keys_sample": list(sorted(amap.keys()))[:50],
    }


def _read_current_mode() -> str:
    state = _json_load(SYSTEM_STATE_PATH, {})
    if isinstance(state, dict):
        mode = state.get("mode") or state.get("current_mode") or state.get("name")
        if isinstance(mode, str) and mode.strip():
            return mode.strip().upper()
    return "MANUAL"


def _guess_domain_from_entity(entity_id: str) -> str:
    if "." in entity_id:
        return entity_id.split(".", 1)[0]
    return "switch"


def _normalize_operation(raw: Optional[str], entity_id: Optional[str]) -> str:
    op = (raw or "").strip().lower()
    domain = _guess_domain_from_entity(entity_id or "")

    if op in SERVICE_BY_OPERATION:
        return op

    if op in {"on", "enable"}:
        if domain == "fan":
            return "fan_on"
        if domain == "light":
            return "light_on"
        return "turn_on"

    if op in {"off", "disable"}:
        if domain == "fan":
            return "fan_off"
        if domain == "light":
            return "light_off"
        return "turn_off"

    if op in {"open_cover", "close_cover", "open", "close"}:
        return op

    if domain == "fan":
        return "fan_off" if "off" in op else "fan_on"
    if domain == "light":
        return "light_off" if "off" in op else "light_on"
    if domain == "cover":
        return "close_cover" if "close" in op else "open_cover"

    return "turn_off" if "off" in op else "turn_on"


def _resolve_from_action_map(action_key: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    amap = load_action_map()

    candidate_keys = [action_key]
    alias = ALIASES.get(action_key)
    if alias:
        candidate_keys.append(alias)

    for key in candidate_keys:
        node = amap.get(key)
        if not isinstance(node, dict):
            continue

        entity_id = (
            node.get("entity_id")
            or node.get("target_entity_id")
            or node.get("ha_entity_id")
            or node.get("entity")
        )

        operation = (
            node.get("operation")
            or node.get("service")
            or node.get("command")
            or node.get("action")
        )

        if not entity_id:
            device_id = (
                node.get("device_id")
                or node.get("target_device_id")
                or node.get("id")
            )
            if device_id:
                device = load_devices_index().get(str(device_id))
                if device:
                    entity_id = (
                        device.get("Entity_ID")
                        or device.get("EntityID")
                        or device.get("entity_id")
                    )

        if entity_id:
            return entity_id, operation, node

    return None, None, {}


def resolve_action(action_key: str) -> Tuple[str, str, Dict[str, Any]]:
    entity_id, operation, meta = _resolve_from_action_map(action_key)

    if not entity_id:
        dbg = debug_action_map_summary()
        raise ValueError(
            f"Action '{action_key}' not found or entity_id missing in action_map/devices.csv; "
            f"action_map_count={dbg['count']}; keys_sample={dbg['keys_sample'][:10]}"
        )

    operation = _normalize_operation(operation, entity_id)
    return entity_id, operation, meta


def _ha_get_state(entity_id: str) -> Optional[Dict[str, Any]]:
    url = f"{HA_URL}/api/states/{entity_id}"
    r = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    payload = r.json()
    return payload if isinstance(payload, dict) else None


def _read_state_value(entity_id: str) -> Optional[str]:
    payload = _ha_get_state(entity_id)
    if not payload:
        return None
    state = payload.get("state")
    return None if state is None else str(state)


def _service_for(entity_id: str, operation: str) -> Tuple[str, str]:
    if operation in SERVICE_BY_OPERATION:
        return SERVICE_BY_OPERATION[operation]
    domain = _guess_domain_from_entity(entity_id)
    if domain == "fan":
        return ("fan", "turn_on")
    if domain == "light":
        return ("light", "turn_on")
    if domain == "cover":
        return ("cover", "open_cover")
    return ("switch", "turn_on")


def _expected_state_for(operation: str) -> Optional[str]:
    return EXPECTED_BY_OPERATION.get(operation)


def _append_log(record: Dict[str, Any]) -> None:
    EXECUTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXECUTION_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def execute_action(
    action_key: str,
    dry_run: bool = False,
    requested_mode: Optional[str] = None,
    source: str = "web_admin",
) -> Dict[str, Any]:
    requested_mode = (requested_mode or _read_current_mode()).upper()

    entity_id, operation, meta = resolve_action(action_key)
    expected_state = _expected_state_for(operation)
    service_domain, service_name = _service_for(entity_id, operation)

    if requested_mode == "TEST":
        result = ExecutionResult(
            ok=True,
            action_key=action_key,
            entity_id=entity_id,
            operation=operation,
            requested_mode=requested_mode,
            dry_run=True,
            expected_state=expected_state,
            actual_state=None,
            verified=False,
            service_domain=service_domain,
            service_name=service_name,
            message="TEST mode: dry-run only",
            details={"source": source, "meta": meta},
        )
        _append_log(result.to_dict())
        return result.to_dict()

    if dry_run:
        result = ExecutionResult(
            ok=True,
            action_key=action_key,
            entity_id=entity_id,
            operation=operation,
            requested_mode=requested_mode,
            dry_run=True,
            expected_state=expected_state,
            actual_state=None,
            verified=False,
            service_domain=service_domain,
            service_name=service_name,
            message="Dry-run only",
            details={"source": source, "meta": meta},
        )
        _append_log(result.to_dict())
        return result.to_dict()

    url = f"{HA_URL}/api/services/{service_domain}/{service_name}"
    payload = {"entity_id": entity_id}
    call_started = time.time()
    r = requests.post(url, headers=HEADERS, json=payload, timeout=DEFAULT_TIMEOUT)
    raw_status = r.status_code
    try:
        raw_json = r.json()
    except Exception:
        raw_json = {"text": r.text[:1000]}

    r.raise_for_status()

    time.sleep(VERIFY_SLEEP_SEC)
    actual_state = _read_state_value(entity_id)
    verified = expected_state is not None and actual_state == expected_state

    result = ExecutionResult(
        ok=verified if expected_state is not None else True,
        action_key=action_key,
        entity_id=entity_id,
        operation=operation,
        requested_mode=requested_mode,
        dry_run=False,
        expected_state=expected_state,
        actual_state=actual_state,
        verified=verified,
        service_domain=service_domain,
        service_name=service_name,
        message="Executed and verified" if verified else "Executed but verification mismatch",
        details={
            "source": source,
            "meta": meta,
            "ha_status_code": raw_status,
            "ha_response": raw_json,
            "duration_ms": int((time.time() - call_started) * 1000),
        },
    )
    _append_log(result.to_dict())
    return result.to_dict()


def load_ask_state() -> Dict[str, Any]:
    data = _json_load(ASK_STATE_PATH, {})
    return data if isinstance(data, dict) else {}


def save_ask_state(payload: Dict[str, Any]) -> None:
    _json_dump(ASK_STATE_PATH, payload)


def clear_ask_state() -> None:
    if ASK_STATE_PATH.exists():
        ASK_STATE_PATH.unlink()


def create_pending_ask(action_key: str, title: Optional[str] = None, source: str = "web_admin") -> Dict[str, Any]:
    entity_id, operation, meta = resolve_action(action_key)
    payload = {
        "has_pending": True,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": "single_action",
        "action_key": action_key,
        "title": title or meta.get("title") or action_key,
        "entity_id": entity_id,
        "operation": operation,
        "source": source,
    }
    save_ask_state(payload)
    return payload


def confirm_pending_ask() -> Dict[str, Any]:
    state = load_ask_state()
    if not state or not state.get("has_pending"):
        return {"ok": False, "error": "no_pending_ask"}

    action_key = state.get("action_key")
    if not action_key:
        return {"ok": False, "error": "invalid_ask_state"}

    result = execute_action(action_key=action_key, dry_run=False, source="web_admin_ask_confirm")
    clear_ask_state()
    return {"ok": True, "result": result}


def cancel_pending_ask() -> Dict[str, Any]:
    state = load_ask_state()
    clear_ask_state()
    return {"ok": True, "had_pending": bool(state.get("has_pending")) if isinstance(state, dict) else False}


def read_tail_execution_log(limit: int = 30) -> List[Dict[str, Any]]:
    if not EXECUTION_LOG_PATH.exists():
        return []
    lines = EXECUTION_LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
    out: List[Dict[str, Any]] = []
    for line in lines:
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                out.append(item)
        except Exception:
            continue
    return out
PY

python3 - <<'PY'
from pathlib import Path

path = Path("/home/mi/greenhouse_v17/interfaces/web_admin/routes/actions.py")
text = path.read_text(encoding="utf-8")

if "debug_action_map_summary" not in text:
    text = text.replace(
        "from greenhouse_v17.services.webadmin_execution_service import execute_action, create_pending_ask",
        "from greenhouse_v17.services.webadmin_execution_service import execute_action, create_pending_ask, debug_action_map_summary",
    )

if "@router.get(\"/debug/action-map\")" not in text:
    text += """

@router.get("/debug/action-map")
def debug_action_map():
    return {"ok": True, "debug": debug_action_map_summary()}
"""
path.write_text(text, encoding="utf-8")
print("[patched] interfaces/web_admin/routes/actions.py")
PY

echo
echo "=== HOTFIX APPLIED ==="
echo "Backups: $BACKUP_DIR"
