from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


SCHEMA_VERSION = "device_passport_v1"


BASE_SCHEMA: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,

    "base": {
        "name": "",
        "logical_role": "",
        "entity_id": "",
        "device_type": "",
        "zone": "",
        "description": "",
        "physical_description": "",
        "importance": "normal",
        "tags": [],
    },

    "control": {
        "enabled": False,
        "actions": [],
        "supports_on_off": False,
        "supports_levels": False,
        "supports_position": False,
        "supports_modes": False,
        "default_timeout_sec": 30,
        "cooldown_sec": 10,
    },

    "effect": {
        "enabled": False,
        "affects": [],
    },

    "verification": {
        "strategy": ["state"],
        "related_sensors": [],
        "related_cameras": [],
        "expected_state": "",
        "verify_delay_sec": 5,
        "confidence": "medium",
    },

    "movement": {
        "enabled": False,
        "movement_type": "",
        "supports_position": False,
        "position_sensor": "",
        "travel_time_sec": 0,
        "can_jam": False,
        "weather_sensitive": False,
    },

    "climate": {
        "enabled": False,
        "affects_temperature": False,
        "affects_humidity": False,
        "affects_airflow": False,
        "target_range": {},
        "safe_range": {},
        "thermal_inertia": "medium",
    },

    "power": {
        "depends_on": [],
        "power_source": "",
        "ups_protected": False,
        "critical_power": False,
    },

    "safety": {
        "risk_level": "low",
        "water_risk": False,
        "fire_risk": False,
        "freeze_risk": False,
        "dry_run_risk": False,
        "requires_confirmation": False,
        "blocked_modes": [],
        "emergency_shutdown_conditions": [],
    },

    "dependencies": {
        "requires": [],
        "conflicts_with": [],
        "recommended_with": [],
        "blocks": [],
    },

    "observation": {
        "photo_useful": False,
        "ai_analysis_useful": False,
        "test_relevant": False,
        "seasonal_behavior": False,
    },

    "notes": {
        "operator_notes": "",
        "maintenance_notes": "",
        "known_problems": [],
        "todo": [],
    },
}


PRESETS: Dict[str, Dict[str, Any]] = {
    "fan": {
        "base": {"device_type": "fan", "tags": ["airflow"]},
        "control": {"enabled": True, "actions": ["turn_on", "turn_off"], "supports_on_off": True},
        "effect": {
            "enabled": True,
            "affects": [
                {"parameter": "humidity", "direction": "decrease", "expected_delta": -2, "delay_sec": 60},
                {"parameter": "airflow", "direction": "increase", "expected_delta": None, "delay_sec": 10},
            ],
        },
        "verification": {"strategy": ["state", "sensor", "delayed_check"], "verify_delay_sec": 5},
        "climate": {"enabled": True, "affects_airflow": True, "thermal_inertia": "fast"},
    },

    "humidifier": {
        "base": {"device_type": "humidifier", "tags": ["humidity"]},
        "control": {"enabled": True, "actions": ["turn_on", "turn_off"], "supports_on_off": True},
        "effect": {
            "enabled": True,
            "affects": [
                {"parameter": "humidity", "direction": "increase", "expected_delta": 5, "delay_sec": 900}
            ],
        },
        "verification": {"strategy": ["state", "sensor", "delayed_check"], "verify_delay_sec": 10},
        "climate": {"enabled": True, "affects_humidity": True, "thermal_inertia": "slow"},
        "safety": {"water_risk": True, "risk_level": "medium"},
    },

    "watering": {
        "base": {"device_type": "watering", "tags": ["water", "irrigation"]},
        "control": {"enabled": True, "actions": ["turn_on", "turn_off"], "supports_on_off": True},
        "effect": {
            "enabled": True,
            "affects": [
                {"parameter": "soil_moisture", "direction": "increase", "expected_delta": 5, "delay_sec": 1200}
            ],
        },
        "verification": {"strategy": ["state", "sensor", "delayed_check"], "verify_delay_sec": 5},
        "safety": {"water_risk": True, "dry_run_risk": True, "risk_level": "medium"},
    },

    "light": {
        "base": {"device_type": "light", "tags": ["light"]},
        "control": {"enabled": True, "actions": ["turn_on", "turn_off"], "supports_on_off": True},
        "effect": {
            "enabled": True,
            "affects": [
                {"parameter": "light", "direction": "increase", "expected_delta": None, "delay_sec": 10}
            ],
        },
        "verification": {"strategy": ["state", "photo"], "verify_delay_sec": 5},
        "observation": {"photo_useful": True, "ai_analysis_useful": True},
    },

    "cover": {
        "base": {"device_type": "cover", "tags": ["movement"]},
        "control": {
            "enabled": True,
            "actions": ["open", "close", "stop"],
            "supports_position": True,
        },
        "movement": {
            "enabled": True,
            "movement_type": "cover",
            "supports_position": True,
            "travel_time_sec": 45,
            "can_jam": True,
            "weather_sensitive": True,
        },
        "verification": {"strategy": ["state", "photo", "delayed_check"], "verify_delay_sec": 30},
        "safety": {"risk_level": "medium", "requires_confirmation": False},
        "observation": {"photo_useful": True, "ai_analysis_useful": True},
    },

    "window": {
        "base": {"device_type": "window", "tags": ["movement", "climate"]},
        "control": {
            "enabled": True,
            "actions": ["open", "close", "stop"],
            "supports_position": True,
        },
        "movement": {
            "enabled": True,
            "movement_type": "window",
            "supports_position": True,
            "travel_time_sec": 60,
            "can_jam": True,
            "weather_sensitive": True,
        },
        "climate": {"enabled": True, "affects_temperature": True, "affects_humidity": True, "affects_airflow": True},
        "verification": {"strategy": ["state", "photo", "sensor", "delayed_check"], "verify_delay_sec": 30},
        "safety": {"risk_level": "medium", "freeze_risk": True},
    },

    "heating_mat": {
        "base": {"device_type": "heating_mat", "tags": ["heat", "root_zone"]},
        "control": {"enabled": True, "actions": ["turn_on", "turn_off"], "supports_on_off": True},
        "effect": {
            "enabled": True,
            "affects": [
                {"parameter": "root_temperature", "direction": "increase", "expected_delta": 2, "delay_sec": 1800}
            ],
        },
        "climate": {"enabled": True, "affects_temperature": True, "thermal_inertia": "slow"},
        "verification": {"strategy": ["state", "sensor", "delayed_check"], "verify_delay_sec": 10},
        "safety": {"risk_level": "medium", "fire_risk": True},
    },

    "pump": {
        "base": {"device_type": "pump", "tags": ["water", "pump"]},
        "control": {"enabled": True, "actions": ["turn_on", "turn_off"], "supports_on_off": True},
        "effect": {
            "enabled": True,
            "affects": [
                {"parameter": "water_flow", "direction": "increase", "expected_delta": None, "delay_sec": 10}
            ],
        },
        "verification": {"strategy": ["state", "sensor", "delayed_check"], "verify_delay_sec": 5},
        "safety": {"risk_level": "high", "water_risk": True, "dry_run_risk": True, "requires_confirmation": True},
    },

    "climate_unit": {
        "base": {"device_type": "climate_unit", "tags": ["climate", "temperature"]},
        "control": {"enabled": True, "actions": ["turn_on", "turn_off"], "supports_on_off": True, "supports_modes": True},
        "effect": {
            "enabled": True,
            "affects": [
                {"parameter": "temperature", "direction": "decrease_or_increase", "expected_delta": None, "delay_sec": 900},
                {"parameter": "humidity", "direction": "decrease", "expected_delta": None, "delay_sec": 900},
            ],
        },
        "climate": {
            "enabled": True,
            "affects_temperature": True,
            "affects_humidity": True,
            "affects_airflow": True,
            "thermal_inertia": "slow",
        },
        "verification": {"strategy": ["state", "sensor", "delayed_check"], "verify_delay_sec": 10},
        "safety": {"risk_level": "medium", "blocked_modes": []},
    },

    "sensor": {
        "base": {"device_type": "sensor", "tags": ["sensor"]},
        "control": {"enabled": False},
        "effect": {"enabled": False, "affects": []},
        "verification": {"strategy": ["data_quality"], "verify_delay_sec": 0, "confidence": "medium"},
        "observation": {"test_relevant": True},
    },

    "camera": {
        "base": {"device_type": "camera", "tags": ["camera", "photo"]},
        "control": {"enabled": False},
        "effect": {"enabled": False, "affects": []},
        "verification": {"strategy": ["photo"], "related_cameras": [], "confidence": "medium"},
        "observation": {"photo_useful": True, "ai_analysis_useful": True, "test_relevant": True},
    },

    "power": {
        "base": {"device_type": "power", "tags": ["power", "infrastructure"]},
        "control": {"enabled": True, "actions": ["turn_on", "turn_off"], "supports_on_off": True},
        "effect": {
            "enabled": True,
            "affects": [
                {"parameter": "power_available", "direction": "state_change", "expected_delta": None, "delay_sec": 5}
            ],
        },
        "verification": {"strategy": ["state"], "verify_delay_sec": 5},
        "power": {"critical_power": True},
        "safety": {"risk_level": "high", "requires_confirmation": True},
    },
}


def deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def build_passport_template(
    preset: str = "sensor",
    logical_role: str = "",
    entity_id: str = "",
    name: str = "",
    zone: str = "",
    description: str = "",
) -> Dict[str, Any]:
    item = deepcopy(BASE_SCHEMA)
    item = deep_merge(item, PRESETS.get(preset, {}))

    item["base"]["logical_role"] = logical_role
    item["base"]["entity_id"] = entity_id
    item["base"]["name"] = name or logical_role
    item["base"]["zone"] = zone
    item["base"]["description"] = description

    # Compatibility with current device_passports table/readers
    item["logical_role"] = logical_role
    item["entity_id"] = entity_id
    item["name"] = name or logical_role
    item["zone"] = zone
    item["description"] = description
    item["verify_strategy"] = item["verification"]["strategy"][0] if item["verification"]["strategy"] else "state"
    item["reliability"] = "unknown"
    item["related_sensors"] = item["verification"].get("related_sensors", [])
    item["related_cameras"] = item["verification"].get("related_cameras", [])
    item["dependencies"] = item["dependencies"]
    item["safety"] = item["safety"]

    affects = item["effect"].get("affects") or []
    first_effect = affects[0] if affects else {}
    item["effect_model"] = {
        "type": item["effect"].get("enabled") and "environmental" or "none",
        "target": first_effect.get("parameter", ""),
        "direction": first_effect.get("direction", ""),
        "sensor": "",
        "expected_delta": first_effect.get("expected_delta"),
        "typical_delay_sec": first_effect.get("delay_sec", 0),
    }

    return item


def list_presets() -> List[Dict[str, str]]:
    labels = {
        "fan": "Вентилятор / циркуляция",
        "humidifier": "Увлажнитель",
        "watering": "Полив",
        "light": "Свет",
        "cover": "Штора / заслонка",
        "window": "Окно / форточка",
        "heating_mat": "Коврик подогрева",
        "pump": "Насос",
        "climate_unit": "Кондиционер / климат",
        "sensor": "Датчик",
        "camera": "Камера",
        "power": "Питание / реле / щиток",
    }
    return [{"key": key, "label": labels.get(key, key)} for key in PRESETS.keys()]
