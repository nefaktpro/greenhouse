from __future__ import annotations

from execution.engine.execution_engine import execute_action_key


def execute_action(action_key: str):
    """
    Transitional compatibility wrapper.

    Old code can still import execute_action from action_executor.py,
    but the real work is already delegated to the new execution layer.
    """
    return execute_action_key(action_key)
