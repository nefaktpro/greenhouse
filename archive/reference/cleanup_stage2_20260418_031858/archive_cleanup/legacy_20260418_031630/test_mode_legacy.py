#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from reports import get_ha
from mode_manager import get_mode, get_mode_config
from decision_logger import log_decisions
from action_executor import execute_decisions

RULES_PATH = "/home/mi/greenhouse_v2/automation_rules.json"

LOW_WATER_ENTITY = "sensor.klubnika_poliv_niz_seryi_humidity"          # 11
TOP_WATER_ENTITY = "sensor.datchik_vlazhnosti_spotifilum_humidity"     # 16
LOW_LEAF_ENTITY = "sensor.temperature_and_humidity_sensor_humidity"    # 21 humidity
TOP_LEAF_ENTITY = "sensor.temperature_and_humidity_sensor_2_humidity"  # 22 humidity

LOW_LEAF_TEMP_ENTITY = "sensor.temperature_and_humidity_sensor_temperature"      # 21 temp
TOP_LEAF_TEMP_ENTITY = "sensor.temperature_and_humidity_sensor_2_temperature"    # 22 temp


def load_rules():
    try:
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _to_float(value):
    try:
        return float(str(value).replace("%", "").replace(",", ".").strip())
    except Exception:
        return None


def _state_float(ha, entity_id):
    try:
        data = ha.get_state(entity_id)
        if not data:
            return None
        return _to_float(data.get("state"))
    except Exception:
        return None


def collect_test_decisions():
    rules = load_rules()
    mode = get_mode()
    mode_config = get_mode_config()
    ha = get_ha()

    if ha is None:
        return {
            "mode": mode,
            "mode_config": mode_config,
            "ha_ok": False,
            "info": [],
            "decisions": [],
        }

    low_thr = rules.get("watering", {}).get("low_threshold", 40)
    top_thr = rules.get("watering", {}).get("top_threshold", 33)
    leaf_thr = rules.get("humidity", {}).get("leaf_min", 50)

    fans = rules.get("fans", {})
    low_temp_on_above = fans.get("low_temp_on_above", 26)
    low_temp_off_below = fans.get("low_temp_off_below", 25)
    top_temp_on_above = fans.get("top_temp_on_above", 26)
    top_temp_off_below = fans.get("top_temp_off_below", 25)

    low_water = _state_float(ha, LOW_WATER_ENTITY)
    top_water = _state_float(ha, TOP_WATER_ENTITY)
    low_leaf = _state_float(ha, LOW_LEAF_ENTITY)
    top_leaf = _state_float(ha, TOP_LEAF_ENTITY)
    low_temp = _state_float(ha, LOW_LEAF_TEMP_ENTITY)
    top_temp = _state_float(ha, TOP_LEAF_TEMP_ENTITY)

    info = []
    decisions = []

    if low_water is not None:
        info.append(f"• Низ (11): {low_water:.0f}%")
        if low_water < low_thr:
            decisions.append({
                "type": "watering_low",
                "sensor": "11",
                "entity_id": LOW_WATER_ENTITY,
                "value": low_water,
                "threshold": low_thr,
                "action": "water_low",
                "reason": f"Низ {low_water:.0f}% < {low_thr}%",
                "executed": False
            })
    else:
        info.append("• Низ (11): нет данных")

    if top_water is not None:
        info.append(f"• Верх (16): {top_water:.0f}%")
        if top_water < top_thr:
            decisions.append({
                "type": "watering_top",
                "sensor": "16",
                "entity_id": TOP_WATER_ENTITY,
                "value": top_water,
                "threshold": top_thr,
                "action": "water_top",
                "reason": f"Верх {top_water:.0f}% < {top_thr}%",
                "executed": False
            })
    else:
        info.append("• Верх (16): нет данных")

    if low_leaf is not None:
        info.append(f"• Листья низ (21): {low_leaf:.0f}%")
        if low_leaf < leaf_thr:
            decisions.append({
                "type": "humidity_low",
                "sensor": "21",
                "entity_id": LOW_LEAF_ENTITY,
                "value": low_leaf,
                "threshold": leaf_thr,
                "action": "humidify",
                "reason": f"Листья низ {low_leaf:.0f}% < {leaf_thr}%",
                "executed": False
            })
    else:
        info.append("• Листья низ (21): нет данных")

    if top_leaf is not None:
        info.append(f"• Листья верх (22): {top_leaf:.0f}%")
        if top_leaf < leaf_thr:
            decisions.append({
                "type": "humidity_top",
                "sensor": "22",
                "entity_id": TOP_LEAF_ENTITY,
                "value": top_leaf,
                "threshold": leaf_thr,
                "action": "humidify",
                "reason": f"Листья верх {top_leaf:.0f}% < {leaf_thr}%",
                "executed": False
            })
    else:
        info.append("• Листья верх (22): нет данных")

    if low_temp is not None:
        info.append(f"• Темп. низ (21): {low_temp:.1f}°C")
        if low_temp > low_temp_on_above:
            decisions.append({
                "type": "fan_low_on",
                "sensor": "21",
                "entity_id": LOW_LEAF_TEMP_ENTITY,
                "value": low_temp,
                "threshold": low_temp_on_above,
                "action": "fan_low_on",
                "reason": f"Температура низа {low_temp:.1f}°C > {low_temp_on_above}°C",
                "executed": False
            })
        elif low_temp < low_temp_off_below:
            decisions.append({
                "type": "fan_low_off",
                "sensor": "21",
                "entity_id": LOW_LEAF_TEMP_ENTITY,
                "value": low_temp,
                "threshold": low_temp_off_below,
                "action": "fan_low_off",
                "reason": f"Температура низа {low_temp:.1f}°C < {low_temp_off_below}°C",
                "executed": False
            })
    else:
        info.append("• Темп. низ (21): нет данных")

    if top_temp is not None:
        info.append(f"• Темп. верх (22): {top_temp:.1f}°C")
        if top_temp > top_temp_on_above:
            decisions.append({
                "type": "fan_top_on",
                "sensor": "22",
                "entity_id": TOP_LEAF_TEMP_ENTITY,
                "value": top_temp,
                "threshold": top_temp_on_above,
                "action": "fan_top_on",
                "reason": f"Температура верха {top_temp:.1f}°C > {top_temp_on_above}°C",
                "executed": False
            })
        elif top_temp < top_temp_off_below:
            decisions.append({
                "type": "fan_top_off",
                "sensor": "22",
                "entity_id": TOP_LEAF_TEMP_ENTITY,
                "value": top_temp,
                "threshold": top_temp_off_below,
                "action": "fan_top_off",
                "reason": f"Температура верха {top_temp:.1f}°C < {top_temp_off_below}°C",
                "executed": False
            })
    else:
        info.append("• Темп. верх (22): нет данных")

    if mode == "AUTO":
        allowed_auto_actions = {
            "fan_low_on",
            "fan_low_off",
            "fan_top_on",
            "fan_top_off",
        }
        decisions = [d for d in decisions if d.get("action") in allowed_auto_actions]

    return {
        "mode": mode,
        "mode_config": mode_config,
        "ha_ok": True,
        "info": info,
        "decisions": decisions,
    }


def build_test_report() -> str:
    data = collect_test_decisions()
    mode = data["mode"]
    mode_config = data["mode_config"]

    if not data["ha_ok"]:
        return "🧪 TEST/AUTO\n\nHA недоступен."

    lines = ["🧪 TEST/AUTO", "", f"Режим: {mode}", ""]

    actions = []
    for d in data["decisions"]:
        if d["action"] == "water_low":
            actions.append(f"💧 Низ {d['value']:.0f}% < {d['threshold']}% → полив низа")
        elif d["action"] == "water_top":
            actions.append(f"💧 Верх {d['value']:.0f}% < {d['threshold']}% → полив верха")
        elif d["action"] == "humidify" and d["sensor"] == "21":
            actions.append(f"🌫 Низ {d['value']:.0f}% < {d['threshold']}% → увлажнение")
        elif d["action"] == "humidify" and d["sensor"] == "22":
            actions.append(f"🌫 Верх {d['value']:.0f}% < {d['threshold']}% → увлажнение")
        elif d["action"] == "fan_low_on":
            actions.append(f"🌬 Темп. низ {d['value']:.1f}°C > {d['threshold']}°C → включить вентиляторы низа")
        elif d["action"] == "fan_low_off":
            actions.append(f"🛑 Темп. низ {d['value']:.1f}°C < {d['threshold']}°C → выключить вентиляторы низа")
        elif d["action"] == "fan_top_on":
            actions.append(f"🌬 Темп. верх {d['value']:.1f}°C > {d['threshold']}°C → включить вентиляторы верха")
        elif d["action"] == "fan_top_off":
            actions.append(f"🛑 Темп. верх {d['value']:.1f}°C < {d['threshold']}°C → выключить вентиляторы верха")

    if mode == "ASK":
        title = "Что система предлагает:"
    else:
        title = "Что система сделала бы:"

    if actions:
        lines.append(title)
        lines.extend(actions)
    else:
        lines.append("✅ Всё в норме, действий не требуется")

    if mode == "ASK" and actions:
        lines.append("")
        lines.append("🟡 Ожидает подтверждение OK")

    lines.append("")
    lines.append("Контроль:")
    lines.extend(data["info"])

    if mode_config.get("log"):
        if mode == "ASK":
            source = "ask_proposal"
            to_log = data["decisions"]
        elif mode == "AUTO":
            source = "auto_cycle"
            to_log = execute_decisions(data["decisions"], dry_run=False)
        elif mode == "AUTOPILOT":
            source = "autopilot_ai"
            to_log = execute_decisions(data["decisions"], dry_run=False)
        else:
            source = "manual_test"
            to_log = data["decisions"]

        log_decisions(mode, to_log, source=source)
        lines.append("")
        lines.append("💾 Сохранено в журнал решений")

    return "\n".join(lines)


def get_ask_payload():
    data = collect_test_decisions()

    if not data["ha_ok"]:
        return {
            "ok": False,
            "message": "HA unavailable",
            "mode": data["mode"],
            "decisions": [],
            "info": [],
        }

    return {
        "ok": True,
        "mode": data["mode"],
        "decisions": data["decisions"],
        "info": data["info"],
    }


def run_silent_test_cycle():
    data = collect_test_decisions()

    if not data["ha_ok"]:
        return False, "HA unavailable"

    if not data["mode_config"].get("log"):
        return True, f"mode={data['mode']} logging_disabled"

    mode = data["mode"]
    decisions = data["decisions"]

    if mode == "AUTO":
        executed = execute_decisions(decisions, dry_run=False)
        log_decisions(mode, executed, source="auto_cycle")
        return True, f"mode={mode} executed={len(executed)}"

    if mode == "AUTOPILOT":
        executed = execute_decisions(decisions, dry_run=False)
        log_decisions(mode, executed, source="autopilot_ai")
        return True, f"mode={mode} executed={len(executed)}"

    if mode == "ASK":
        log_decisions(mode, decisions, source="ask_proposal")
        return True, f"mode={mode} proposals={len(decisions)}"

    log_decisions(mode, decisions, source="scheduler_test")
    return True, f"mode={mode} decisions={len(decisions)}"
