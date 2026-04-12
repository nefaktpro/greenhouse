from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_DIR = PROJECT_ROOT / "data" / "registry"


@dataclass
class RegistrySnapshot:
    devices: list[dict[str, Any]]
    capabilities: dict[str, Any]
    action_map: dict[str, Any]
    zones: dict[str, Any]


class RegistryLoader:
    """
    In-memory registry cache.
    Loads registry files once and reloads only on demand.
    """

    def __init__(self, registry_dir: Path | None = None) -> None:
        self.registry_dir = registry_dir or REGISTRY_DIR
        self._lock = RLock()
        self._snapshot: RegistrySnapshot | None = None

    def load(self, force_reload: bool = False) -> RegistrySnapshot:
        with self._lock:
            if self._snapshot is not None and not force_reload:
                return self._snapshot

            snapshot = RegistrySnapshot(
                devices=self._load_devices(),
                capabilities=self._load_json("device_capabilities.json"),
                action_map=self._load_json("action_map.json"),
                zones=self._load_json("zones.json"),
            )
            self._snapshot = snapshot
            return snapshot

    def reload(self) -> RegistrySnapshot:
        return self.load(force_reload=True)

    def _load_devices(self) -> list[dict[str, Any]]:
        path = self.registry_dir / "devices.csv"
        if not path.exists():
            return []

        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            return [dict(row) for row in reader]

    def _load_json(self, filename: str) -> dict[str, Any]:
        path = self.registry_dir / filename
        if not path.exists():
            return {}

        with path.open("r", encoding="utf-8") as f:
            return json.load(f)


_registry_loader_singleton: RegistryLoader | None = None


def get_registry_loader() -> RegistryLoader:
    global _registry_loader_singleton
    if _registry_loader_singleton is None:
        _registry_loader_singleton = RegistryLoader()
    return _registry_loader_singleton
