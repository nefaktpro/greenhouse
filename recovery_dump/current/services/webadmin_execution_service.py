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
    "fan_on": "on",
    "fan_off": "off",
    "light_on": "on",
    "light_off": "off",
    "open": "open",
    "close": "closed",
    "open_cover": "open",
    "close_cover": "closed",
}

SERVICE_BY_OPERATION = {
    "turn_on": ("switch", "turn_on"),
    "turn_off": ("switch", "turn_off"),
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

    def consume_item(item: Any, fallback_key: Optional[str] = None) -> None:
        if not isinstance(item, dict):
            return
        key = (
            item.get("action_key")
            or item.get("key")
            or item.get("name")
            or fallback_key
        )
        if key:
            node = dict(item)
            node["action_key"] = str(key)
            out[str(key)] = node

    if isinstance(raw, list):
        for item in raw:
            consume_item(item)
        return out

    if isinstance(raw, dict):
        if isinstance(raw.get("items"), list):
            for item in raw["items"]:
                consume_item(item)
        if isinstance(raw.get("actions"), list):
            for item in raw["actions"]:
                consume_item(item)

        for k, v in raw.items():
            if isinstance(v, dict):
                consume_item(v, fallback_key=str(k))

    return out


@lru_cache(maxsize=1)
def load_action_map() -> Dict[str, Dict[str, Any]]:
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


def debug_action_map_full(action_key: Optional[str] = None) -> Dict[str, Any]:
    amap = load_action_map()
    payload: Dict[str, Any] = {
        "action_map_path": str(ACTION_MAP_PATH),
        "exists": ACTION_MAP_PATH.exists(),
        "count": len(amap),
        "keys_sample": list(sorted(amap.keys()))[:50],
    }
    if action_key:
        payload["requested_key"] = action_key
        payload["node"] = amap.get(action_key)
        alias = ALIASES.get(action_key)
        if alias:
            payload["alias"] = alias
            payload["alias_node"] = amap.get(alias)
    return payload


def debug_action_map_summary() -> Dict[str, Any]:
    return debug_action_map_full()


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
        return "fan_on" if domain == "fan" else "light_on" if domain == "light" else "turn_on"
    if op in {"off", "disable"}:
        return "fan_off" if domain == "fan" else "light_off" if domain == "light" else "turn_off"
    if op in {"open", "close", "open_cover", "close_cover"}:
        return op

    if domain == "fan":
        return "fan_off" if "off" in op else "fan_on"
    if domain == "light":
        return "light_off" if "off" in op else "light_on"
    if domain == "cover":
        return "close_cover" if "close" in op else "open_cover"
    return "turn_off" if "off" in op else "turn_on"


def _entity_from_device_id(device_id: Any) -> Optional[str]:
    if device_id is None:
        return None
    device = load_devices_index().get(str(device_id))
    if not device:
        return None
    return (
        device.get("Entity_ID")
        or device.get("EntityID")
        or device.get("entity_id")
    )


def _resolve_from_node(node: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
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
        # вариант через device_id
        entity_id = _entity_from_device_id(
            node.get("device_id")
            or node.get("target_device_id")
            or node.get("id")
        )

    if not entity_id:
        # вариант через targets / devices / entities
        targets = node.get("targets") or node.get("devices") or node.get("entities")
        if isinstance(targets, list) and targets:
            first = targets[0]
            if isinstance(first, str) and "." in first:
                entity_id = first
            elif isinstance(first, dict):
                entity_id = (
                    first.get("entity_id")
                    or first.get("target_entity_id")
                    or first.get("ha_entity_id")
                    or _entity_from_device_id(
                        first.get("device_id")
                        or first.get("target_device_id")
                        or first.get("id")
                    )
                )

    if not entity_id:
        # вариант через logical_role / target_role / capability — для тестовых вентиляторов делаем fallback
        logical_role = str(
            node.get("logical_role")
            or node.get("target_role")
            or node.get("capability")
            or node.get("role")
            or ""
        ).strip().lower()

        if logical_role in {"top_air_circulation", "fan_top", "top_fan"}:
            entity_id = "switch.setevoi_filtr_novyi_socket_1"
        elif logical_role in {"bottom_air_circulation", "fan_bottom", "fan_low", "bottom_fan"}:
            entity_id = "switch.setevoi_filtr_novyi_socket_2"

    return entity_id, operation


def _resolve_from_action_map(action_key: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    amap = load_action_map()

    keys = [action_key]
    alias = ALIASES.get(action_key)
    if alias:
        keys.append(alias)

    for key in keys:
        node = amap.get(key)
        if not isinstance(node, dict):
            continue
        entity_id, operation = _resolve_from_node(node)
        if entity_id:
            return entity_id, operation, node

    return None, None, {}


def resolve_action(action_key: str) -> Tuple[str, str, Dict[str, Any]]:
    entity_id, operation, meta = _resolve_from_action_map(action_key)
    if not entity_id:
        dbg = debug_action_map_full(action_key)
        raise ValueError(
            f"Action '{action_key}' not found or entity_id missing in action_map/devices.csv; debug={json.dumps(dbg, ensure_ascii=False)}"
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
