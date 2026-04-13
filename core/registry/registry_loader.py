from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


DEFAULT_REGISTRY_DIR = Path("/home/mi/greenhouse_v2/data/registry")


class RegistryError(Exception):
    """Base error for registry loading and resolution."""


class RegistryFileMissingError(RegistryError):
    """Raised when a required registry file is missing."""


class RoleResolutionError(RegistryError):
    """Raised when a logical role cannot be resolved."""


class ScenarioResolutionError(RegistryError):
    """Raised when a scenario cannot be resolved."""


@dataclass
class RegistryBundle:
    registry_dir: Path
    roles_map: Dict[str, Any]
    scenarios_raw: Dict[str, Any]
    scenarios: Dict[str, Any]
    device_knowledge: Dict[str, Any]


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RegistryFileMissingError(f"Registry file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RegistryError(f"Expected JSON object in {path}, got: {type(data).__name__}")
    return data


def _extract_scenarios_map(scenarios_raw: Dict[str, Any]) -> Dict[str, Any]:
    # Поддерживаем оба формата:
    # 1) {"humidifier_on": {...}}
    # 2) {"meta": {...}, "scenarios": {"humidifier_on": {...}}}
    nested = scenarios_raw.get("scenarios")
    if isinstance(nested, dict):
        return nested
    return scenarios_raw


def load_registry_bundle(registry_dir: Path | str = DEFAULT_REGISTRY_DIR) -> RegistryBundle:
    registry_path = Path(registry_dir)

    roles_map = _load_json(registry_path / "roles_map.json")
    scenarios_raw = _load_json(registry_path / "scenarios.json")
    scenarios = _extract_scenarios_map(scenarios_raw)
    device_knowledge = _load_json(registry_path / "device_knowledge_full.json")

    return RegistryBundle(
        registry_dir=registry_path,
        roles_map=roles_map,
        scenarios_raw=scenarios_raw,
        scenarios=scenarios,
        device_knowledge=device_knowledge,
    )


def get_role_entity(role: str, registry_dir: Path | str = DEFAULT_REGISTRY_DIR) -> Any:
    bundle = load_registry_bundle(registry_dir)
    try:
        entity_value = bundle.roles_map[role]
    except KeyError as exc:
        raise RoleResolutionError(f"Role not found in roles_map.json: {role}") from exc

    return entity_value


def get_scenario(name: str, registry_dir: Path | str = DEFAULT_REGISTRY_DIR) -> Dict[str, Any]:
    bundle = load_registry_bundle(registry_dir)
    try:
        scenario = bundle.scenarios[name]
    except KeyError as exc:
        available = ", ".join(sorted(bundle.scenarios.keys())[:20])
        raise ScenarioResolutionError(
            f"Scenario not found in scenarios.json: {name}. Available examples: {available}"
        ) from exc

    if not isinstance(scenario, dict):
        raise ScenarioResolutionError(f"Scenario '{name}' must be a JSON object")

    return scenario


def get_all_roles(registry_dir: Path | str = DEFAULT_REGISTRY_DIR) -> Dict[str, Any]:
    return load_registry_bundle(registry_dir).roles_map


def get_all_scenarios(registry_dir: Path | str = DEFAULT_REGISTRY_DIR) -> Dict[str, Any]:
    return load_registry_bundle(registry_dir).scenarios
