from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    success: bool
    action_key: str
    operation: str | None = None
    entity_id: str | None = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
