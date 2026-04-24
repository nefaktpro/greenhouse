from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class AIContext:
    created_at: str
    mode: Dict[str, Any]
    runtime: Dict[str, Any] = field(default_factory=dict)
    safety: Dict[str, Any] = field(default_factory=dict)
    registry: Dict[str, Any] = field(default_factory=dict)
    memory: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_minimal_context() -> Dict[str, Any]:
    """
    Минимальный context builder для AI.
    Важно: не даёт AI прямой доступ к файлам, HA или execution.
    """
    try:
        from greenhouse_v17.services.mode_service import get_mode_flags
        mode = get_mode_flags()
    except Exception as e:
        mode = {"error": str(e), "title": "UNKNOWN"}

    ctx = AIContext(
        created_at=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        runtime={
            "source": "minimal_context_builder",
            "execution_access": False,
            "ha_access": False,
        },
        safety={
            "ai_direct_execution_allowed": False,
            "requires_core_validation": True,
        },
        registry={
            "available": [
                "devices",
                "actions",
                "capabilities",
                "scenarios",
            ],
            "access_mode": "metadata_only",
        },
        memory={
            "active_memory_enabled": False,
            "cleanup_enabled": False,
            "observations_enabled": True,
        },
        notes=[
            "AI Router v1: analysis/intent only",
            "No direct execution",
            "No direct HA access",
        ],
    )
    return ctx.to_dict()
