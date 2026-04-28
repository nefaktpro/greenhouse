from __future__ import annotations

import csv
import os
from collections import OrderedDict
from pathlib import Path

import requests
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
REGISTRY_PATH = Path("/home/mi/greenhouse_v17/data/registry/devices.csv")


def env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def ha_base_url() -> str:
    return env_first("HOME_ASSISTANT_URL", "HA_BASE_URL", default="http://127.0.0.1:8123").rstrip("/")


def ha_token() -> str:
    return env_first("HOME_ASSISTANT_TOKEN", "HA_TOKEN", default="")


def ha_headers() -> dict[str, str]:
    token = ha_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def pick(row: dict, *keys: str) -> str:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for key in keys:
        if key in row and str(row[key]).strip():
            return str(row[key]).strip()
        lk = key.strip().lower()
        if lk in lowered and str(lowered[lk]).strip():
            return str(lowered[lk]).strip()
    return ""


def sort_id(raw: str):
    out = []
    for part in str(raw or "").split("."):
        try:
            out.append((0, int(part)))
        except Exception:
            out.append((1, part))
    return tuple(out)


def load_registry_rows() -> list[dict]:
    rows: list[dict] = []
    if not REGISTRY_PATH.exists():
        return rows

    with REGISTRY_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_id = pick(row, "Entity_ID", "entity_id", "entity", "ha_entity_id")
            if not entity_id:
                continue
            rows.append(
                {
                    "id": pick(row, "ID", "DeviceID", "device_id", "id"),
                    "parent": pick(row, "Parent", "ParentID", "parent", "parent_id"),
                    "name": pick(row, "Name", "name"),
                    "type": pick(row, "Type", "type"),
                    "unit": pick(row, "Unit", "unit"),
                    "location": pick(row, "Location", "location", "zone"),
                    "logical_role": pick(row, "logical_role", "Logical_Role", "role"),
                    "entity_id": entity_id,
                    "description": pick(row, "Description", "description"),
                }
            )

    rows.sort(key=lambda x: (sort_id(x.get("id", "")), x.get("name", "")))
    return rows


def infer_ops(entity_id: str, item_type: str, name: str, logical_role: str) -> list[str]:
    domain = (entity_id.split(".", 1)[0] if "." in entity_id else "").lower()
    hint = " ".join([item_type or "", name or "", logical_role or ""]).lower()

    if domain in {"switch", "light", "fan", "input_boolean", "humidifier"}:
        return ["on", "off", "toggle"]
    if domain == "cover":
        return ["open", "close", "stop"]
    if domain == "climate":
        return ["on", "off"]
    if domain == "lock":
        return ["lock", "unlock"]
    if domain == "valve":
        return ["open", "close"]

    if any(x in hint for x in ["штор", "curtain", "cover"]):
        return ["open", "close", "stop"]
    if any(x in hint for x in ["вент", "fan", "vent"]):
        return ["on", "off", "toggle"]
    if any(x in hint for x in ["свет", "lamp", "light"]):
        return ["on", "off", "toggle"]
    if any(x in hint for x in ["увлаж", "humid"]):
        return ["on", "off", "toggle"]
    if any(x in hint for x in ["полив", "насос", "pump", "клапан", "valve"]):
        return ["on", "off"]
    if any(x in hint for x in ["щит", "реле", "розет", "power", "relay", "switch"]):
        return ["on", "off", "toggle"]

    return []


def group_name(entity_id: str, item_type: str, name: str, logical_role: str) -> str:
    domain = (entity_id.split(".", 1)[0] if "." in entity_id else "").lower()
    hint = " ".join([item_type or "", name or "", logical_role or ""]).lower()

    if domain == "cover" or any(x in hint for x in ["штор", "curtain", "cover"]):
        return "Шторы / Cover"
    if domain == "fan" or any(x in hint for x in ["вент", "fan", "vent"]):
        return "Вентиляция"
    if domain in {"climate", "humidifier"} or any(x in hint for x in ["увлаж", "обогрев", "термостат", "climate"]):
        return "Климат / Увлажнение / Обогрев"
    if domain == "light" or any(x in hint for x in ["свет", "lamp", "light"]):
        return "Свет"
    if domain in {"switch", "input_boolean"} or any(x in hint for x in ["щит", "реле", "розет", "power", "relay", "switch"]):
        return "Питание / Реле / Розетки"
    if domain == "valve" or any(x in hint for x in ["полив", "насос", "pump", "клапан", "valve"]):
        return "Полив / Насосы / Клапаны"
    return "Мониторинг / Без управления"


def get_state(entity_id: str) -> dict:
    token = ha_token()
    if not token:
        return {"entity_id": entity_id, "state": "unknown", "error": "HA token not found"}

    try:
        r = requests.get(f"{ha_base_url()}/api/states/{entity_id}", headers=ha_headers(), timeout=20)
        r.raise_for_status()
        data = r.json()
        return {
            "entity_id": entity_id,
            "state": data.get("state", "unknown"),
            "last_changed": data.get("last_changed", ""),
            "last_updated": data.get("last_updated", ""),
            "attributes": data.get("attributes", {}),
        }
    except Exception as e:
        return {"entity_id": entity_id, "state": "unknown", "error": str(e)}


def load_states() -> dict[str, dict]:
    token = ha_token()
    if not token:
        return {}

    try:
        r = requests.get(f"{ha_base_url()}/api/states", headers=ha_headers(), timeout=20)
        r.raise_for_status()
        result = {}
        for item in r.json():
            eid = item.get("entity_id")
            if eid:
                result[eid] = item
        return result
    except Exception:
        return {}


def build_groups() -> list[dict]:
    rows = load_registry_rows()
    states = load_states()
    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for title in [
        "Питание / Реле / Розетки",
        "Свет",
        "Шторы / Cover",
        "Вентиляция",
        "Климат / Увлажнение / Обогрев",
        "Полив / Насосы / Клапаны",
        "Мониторинг / Без управления",
    ]:
        groups[title] = []

    for item in rows:
        ops = infer_ops(item["entity_id"], item["type"], item["name"], item["logical_role"])
        title = group_name(item["entity_id"], item["type"], item["name"], item["logical_role"])
        state_obj = states.get(item["entity_id"], {})
        groups[title].append(
            {
                **item,
                "ops": ops,
                "state": state_obj.get("state", "unknown"),
            }
        )

    return [{"title": k, "rows": v} for k, v in groups.items() if v]


def call_ha(entity_id: str, operation: str) -> dict:
    if not ha_token():
        return {"ok": False, "error": "HA token not found in environment"}

    domain = entity_id.split(".", 1)[0].lower()
    op = operation.lower().strip()

    if domain in {"sensor", "binary_sensor", "camera", "number", "select"}:
        return {"ok": False, "error": f"{domain} is read-only"}

    if op == "on":
        service = "turn_on"
    elif op == "off":
        service = "turn_off"
    elif op == "toggle":
        service = "toggle"
    elif op == "open":
        service = "open_cover" if domain == "cover" else "open_valve"
    elif op == "close":
        service = "close_cover" if domain == "cover" else "close_valve"
    elif op == "stop":
        service = "stop_cover"
    elif op in {"lock", "unlock"}:
        service = op
    else:
        return {"ok": False, "error": f"unsupported operation: {operation}"}

    try:
        r = requests.post(
            f"{ha_base_url()}/api/services/{domain}/{service}",
            headers=ha_headers(),
            json={"entity_id": entity_id},
            timeout=20,
        )
        r.raise_for_status()
        return {"ok": True, "service": f"{domain}.{service}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/web/control-debug", response_class=HTMLResponse)
def control_debug_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="control_debug.html",
        context={
            "request": request,
            "groups": build_groups(),
        },
    )


@router.post("/web/control-debug/execute")
def control_debug_execute(payload: dict):
    entity_id = str(payload.get("entity_id", "")).strip()
    operation = str(payload.get("operation", "")).strip()

    if not entity_id or not operation:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "entity_id and operation are required"},
        )

    result = call_ha(entity_id, operation)
    state = get_state(entity_id)

    if result.get("ok"):
        return {
            "ok": True,
            "message": f"OK: {entity_id} -> {operation}",
            "entity_id": entity_id,
            "operation": operation,
            "state": state.get("state", "unknown"),
            "state_payload": state,
        }

    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "message": f"ERROR: {entity_id} -> {operation}",
            "error": result.get("error", "unknown"),
            "entity_id": entity_id,
            "operation": operation,
            "state": state.get("state", "unknown"),
            "state_payload": state,
        },
    )


@router.post("/web/control-debug/refresh-tuya-ha")
def refresh_tuya_ha_debug():
    """
    Safe HA/Tuya refresh:
    - checks HA availability
    - counts unavailable Tuya/LocalTuya entities
    - tries to reload Tuya/LocalTuya config entries through HA
    - does NOT switch any devices on/off
    """
    before_states = load_states()
    before_unavailable = [
        eid for eid, st in before_states.items()
        if ("tuya" in eid.lower() or "humidifier" in eid.lower() or "uvlaz" in eid.lower() or "uviazh" in eid.lower())
        and st.get("state") in {"unavailable", "unknown"}
    ]

    reload_results = []
    try:
        entries_resp = requests.get(
            f"{ha_base_url()}/api/config/config_entries/entry",
            headers=ha_headers(),
            timeout=20,
        )
        entries_resp.raise_for_status()
        entries = entries_resp.json()

        for e in entries:
            domain = str(e.get("domain", "")).lower()
            title = str(e.get("title", ""))
            entry_id = e.get("entry_id")

            if domain in {"tuya", "localtuya"} and entry_id:
                try:
                    rr = requests.post(
                        f"{ha_base_url()}/api/config/config_entries/entry/{entry_id}/reload",
                        headers=ha_headers(),
                        timeout=30,
                    )
                    reload_results.append({
                        "domain": domain,
                        "title": title,
                        "entry_id": entry_id,
                        "ok": rr.status_code in (200, 204),
                        "status_code": rr.status_code,
                        "text": rr.text[:300],
                    })
                except Exception as ex:
                    reload_results.append({
                        "domain": domain,
                        "title": title,
                        "entry_id": entry_id,
                        "ok": False,
                        "error": str(ex),
                    })

    except Exception as e:
        return {
            "ok": False,
            "message": "HA доступен не полностью или config_entries API недоступен",
            "error": str(e),
            "before_unavailable_count": len(before_unavailable),
            "before_unavailable_sample": before_unavailable[:30],
        }

    import time
    time.sleep(8)

    after_states = load_states()
    after_unavailable = [
        eid for eid, st in after_states.items()
        if ("tuya" in eid.lower() or "humidifier" in eid.lower() or "uvlaz" in eid.lower() or "uviazh" in eid.lower())
        and st.get("state") in {"unavailable", "unknown"}
    ]

    return {
        "ok": True,
        "message": "Reload Tuya/LocalTuya выполнен. Устройства не включались и не выключались.",
        "before_unavailable_count": len(before_unavailable),
        "after_unavailable_count": len(after_unavailable),
        "before_unavailable_sample": before_unavailable[:30],
        "after_unavailable_sample": after_unavailable[:30],
        "reload_results": reload_results,
    }
