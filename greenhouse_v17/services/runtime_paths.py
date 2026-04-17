from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
REGISTRY_DIR = DATA_DIR / "registry"
RUNTIME_DIR = DATA_DIR / "runtime"
LOGS_DIR = DATA_DIR / "logs"
MEMORY_DIR = DATA_DIR / "memory"

ASK_STATE_PATH = RUNTIME_DIR / "ask_state.json"
SYSTEM_STATE_PATH = RUNTIME_DIR / "system_state.json"
DECISION_LOG_PATH = LOGS_DIR / "decision_log.json"
OBSERVATIONS_PATH = MEMORY_DIR / "observations.json"

def ensure_runtime_dirs() -> None:
    for p in [DATA_DIR, REGISTRY_DIR, RUNTIME_DIR, LOGS_DIR, MEMORY_DIR]:
        p.mkdir(parents=True, exist_ok=True)
